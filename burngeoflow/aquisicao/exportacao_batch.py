"""Execução GEE em lote via assets temporários, com retomada de tarefas.

A tarefa batch materializa a expressão P1/P2 antes de computeFeatures.
Assim cada página é lida de um asset, não recalcula o grafo acumulativo.
Nenhuma tarefa é declarada bem-sucedida antes de COMPLETED.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from time import monotonic, sleep
from typing import Any, Callable
from uuid import uuid4


class ErroLote(RuntimeError):
    """Falha da infraestrutura de exportação em lote."""


def salvar_estado(path: Path, estado: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporario = path.with_suffix(path.suffix + ".tmp")
    temporario.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporario, path)


def asset_id(projeto: str, incendio: int, ano: int, sessao: str, nome: str,
             tentativa: int = 0) -> str:
    """Destino isolado e criado EXCLUSIVAMENTE pelo BurnGeoFlow."""
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", projeto):
        raise ErroLote("ID de projeto Google Cloud inválido para exportação em lote.")
    if nome not in ("p1", "p2") or not re.fullmatch(r"[a-f0-9]{12}", sessao):
        raise ErroLote("Nome de tarefa ou sessão GEE inválido.")
    if not 0 <= tentativa <= 1:
        raise ErroLote("Número de tentativas batch excedido (máximo 1 retry).")
    sufixo = f"_r{tentativa:02d}" if tentativa else ""
    return f"projects/{projeto}/assets/bgf_{incendio}_{ano}_{sessao}_{nome}{sufixo}"


def _status_remoto(ee: Any, task_id: str) -> dict:
    resultados = ee.data.getTaskStatus(task_id)
    if not isinstance(resultados, list) or not resultados or not isinstance(resultados[0], dict):
        raise ErroLote(f"Earth Engine não retornou status da tarefa {task_id}.")
    return resultados[0]


def iniciar_ou_retomar(
    ee: Any, nome: str, expressao: Any, *, estado: dict, caminho: Path,
    projeto: str, incendio: int, ano: int,
    informar: Callable[[str], None],
) -> dict:
    tarefas = estado["tarefas"]
    tentativa = 0
    historico = []
    if nome in tarefas:
        registro = tarefas[nome]
        tentativa = int(registro.get("tentativa", 0))
        esperado = asset_id(
            projeto, incendio, ano, estado["sessao"], nome.lower(), tentativa
        )
        if registro.get("asset") != esperado:
            raise ErroLote("Checkpoint de tarefa GEE contém asset inconsistente.")
        if not registro.get("task_id"):
            raise ErroLote(
                "Checkpoint indica criação interrompida, sem ID de tarefa. "
                "Verifique tarefas/ativos no Earth Engine antes de reiniciar."
            )
        resposta = _status_remoto(ee, registro["task_id"])
        situacao = resposta.get("state", "UNKNOWN")
        if situacao in ("FAILED", "CANCELLED"):
            if tentativa >= 1:
                raise ErroLote(
                    f"{nome} já falhou em duas tentativas batch. "
                    "Revise o log da tarefa e o checkpoint; não haverá "
                    "reenvio automático ilimitado."
                )
            historico = list(registro.get("historico_tentativas", []))
            historico.append({
                "task_id": registro["task_id"],
                "asset": registro["asset"],
                "estado": situacao,
                "erro": resposta.get("error_message", ""),
            })
            tentativa += 1
            informar(
                f"[GEE/batch] {nome}: tarefa anterior {situacao}; "
                "criando uma única nova tentativa, sem reprocessar outros produtos."
            )
        else:
            if situacao == "COMPLETED":
                registro["estado"] = "COMPLETED"
                salvar_estado(caminho, estado)
            elif situacao not in ("READY", "RUNNING", "SUBMITTED", "CANCEL_REQUESTED"):
                raise ErroLote(
                    f"Estado remoto inesperado da tarefa {registro['task_id']}: "
                    f"{situacao}"
                )
            informar(f"[GEE/batch] Retomando {nome}: tarefa {registro['task_id']}")
            return registro

    destino = asset_id(
        projeto, incendio, ano, estado["sessao"], nome.lower(), tentativa
    )
    # Se a execução for interrompida durante o start(), não criar outra
    # tarefa automaticamente para evitar duplicação silenciosa.
    tarefas[nome] = {
        "asset": destino, "task_id": None, "estado": "criando",
        "tentativa": tentativa, "historico_tentativas": historico,
    }
    salvar_estado(caminho, estado)
    try:
        task = ee.batch.Export.table.toAsset(
            collection=expressao,
            description=f"BurnGeoFlow_{incendio}_{ano}_{nome}",
            assetId=destino,
        )
        task.start()
        if not task.id:
            raise ErroLote(f"Tarefa de exportação {nome} não retornou identificador.")
    except Exception as exc:
        raise ErroLote(
            f"Não foi possível iniciar exportação batch de {nome} para {destino}. "
            "Confira permissão de escrita no projeto e a guia Tasks do Earth Engine. "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    tarefas[nome]["task_id"] = str(task.id)
    tarefas[nome]["estado"] = "SUBMITTED"
    salvar_estado(caminho, estado)
    informar(f"[GEE/batch] {nome} enviado: tarefa {task.id}, asset {destino}")
    return tarefas[nome]


def aguardar(
    ee: Any, nome: str, registro: dict, *,
    informar: Callable[[str], None],
    intervalo_s: float = 25,
    espera_max_s: float = 7200,
    dormir: Callable[[float], None] = sleep,
    relogio: Callable[[], float] = monotonic,
) -> None:
    """Consulta task status, sem presumir progresso percentual."""
    if intervalo_s <= 0 or espera_max_s <= 0:
        raise ValueError("Intervalos de espera devem ser positivos.")
    inicio = relogio()
    anterior = None
    while True:
        try:
            resposta = _status_remoto(ee, registro["task_id"])
        except Exception as exc:
            raise ErroLote(
                f"Falha consultando tarefa batch {nome} "
                f"({registro['task_id']}). A tarefa poderá ser retomada. "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        status = resposta.get("state", "UNKNOWN")
        if status != anterior:
            informar(f"[GEE/batch] {nome}: estado remoto {status}")
            anterior = status
        if status == "COMPLETED":
            registro["estado"] = status
            return
        if status in ("FAILED", "CANCELLED", "CANCEL_REQUESTED"):
            raise ErroLote(
                f"Exportação batch {nome} {status}: {resposta.get('error_message', '')}. "
                f"Tarefa: {registro['task_id']}"
            )
        if status not in ("READY", "RUNNING", "SUBMITTED"):
            raise ErroLote(
                f"Status inesperado da tarefa {registro['task_id']}: {status}"
            )
        decorrido = relogio() - inicio
        if decorrido >= espera_max_s:
            raise ErroLote(
                f"Tarefa {registro['task_id']} ainda está {status} após "
                "a janela local de acompanhamento. O processamento continua "
                "no Earth Engine; execute novamente para retomar a tarefa."
            )
        informar(f"[GEE/batch] {nome}: aguardando servidor "
                f"({int(decorrido)} s decorridos, sem estimativa).")
        dormir(min(intervalo_s, max(0, espera_max_s - decorrido)))


def materializar(
    ee: Any, produtos: dict[str, Any], *, projeto: str, incendio: int,
    ano: int, assinatura: str, pasta: Path,
    informar: Callable[[str], None] = print,
    intervalo_s: float = 25, espera_max_s: float = 7200,
) -> tuple[dict[str, str], Path]:
    """Materializa produtos em assets batch e permite retomada por checkpoint.

    Retorna IDs dos assets. Eles só devem ser apagados DEPOIS da validação
    e gravação local dos dois GeoJSONs.
    """
    if set(produtos) != {"P1", "P2"}:
        raise ErroLote("É necessário fornecer exatamente P1 e P2.")
    if not assinatura:
        raise ErroLote("A assinatura de aquisição é obrigatória.")
    path = pasta / f"estado_batch_{incendio}.json"
    if path.is_file():
        estado = json.loads(path.read_text(encoding="utf-8"))
        if estado.get("assinatura") != assinatura:
            if not estado.get("finalizado"):
                raise ErroLote(
                    f"Há um lote anterior incompatível em {path}. "
                    "Não serão reaproveitadas tarefas de outros parâmetros."
                )
            estado = {}
    else:
        estado = {}
    if not estado or estado.get("finalizado"):
        estado = {
            "assinatura": assinatura,
            "sessao": uuid4().hex[:12],
            "iniciado_utc": datetime.now(timezone.utc).isoformat(),
            "finalizado": False,
            "tarefas": {},
        }
        salvar_estado(path, estado)
    assets: dict[str, str] = {}
    for nome in ("P1", "P2"):
        registro = iniciar_ou_retomar(
            ee, nome, produtos[nome], estado=estado, caminho=path,
            projeto=projeto, incendio=incendio, ano=ano, informar=informar,
        )
        if registro.get("estado") != "COMPLETED":
            aguardar(
                ee, nome, registro, informar=informar,
                intervalo_s=intervalo_s, espera_max_s=espera_max_s,
            )
            salvar_estado(path, estado)
        assets[nome] = registro["asset"]
    return assets, path


def limpar_apos_validacao(
    ee: Any, assets: dict[str, str], path: Path,
    informar: Callable[[str], None] = print,
) -> None:
    """Apaga apenas assets identificados no checkpoint desta aquisição."""
    estado = json.loads(path.read_text(encoding="utf-8"))
    previstos = {nome: r["asset"] for nome, r in estado["tarefas"].items()}
    if previstos != assets or set(previstos) != {"P1", "P2"}:
        raise ErroLote("Não é seguro limpar: assets não correspondem ao checkpoint.")
    estado["finalizado"] = True
    estado["validado_localmente_utc"] = datetime.now(timezone.utc).isoformat()
    salvar_estado(path, estado)
    for nome, destino in assets.items():
        registro = estado["tarefas"][nome]
        if registro.get("asset_removido"):
            continue
        try:
            ee.data.deleteAsset(destino)
            registro["asset_removido"] = True
            salvar_estado(path, estado)
            informar(f"[GEE/batch] {nome}: asset temporário removido.")
        except Exception as exc:
            informar(
                f"[GEE/batch] Aviso: limpeza de {nome} pendente ({destino}): "
                f"{type(exc).__name__}: {exc}. Produto local permanece válido."
            )
