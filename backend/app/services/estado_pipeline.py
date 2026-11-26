"""Estado auditável do pipeline, derivado SOMENTE dos arquivos existentes.

Não acessa o GEE, não reprocessa dados, não confunde 'arquivo existe'
com 'resultado científico válido na metodologia atual'.
"""
from __future__ import annotations

import json
from pathlib import Path
from stat import S_ISREG

from executar_pipeline import definir_etapas, assinatura_codigo, digest
from burngeoflow.processamento.metodologia_v2 import VERSAO


def _ler_json(path: Path) -> tuple[dict, str | None]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("objeto JSON esperado")
        return obj, None
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def _arquivo(path: Path) -> dict:
    try:
        info = path.stat()
    except OSError:
        info = None
    tamanho = info.st_size if info is not None and S_ISREG(info.st_mode) else None
    return {
        "existe": tamanho is not None,
        "bytes": tamanho,
        "estado": "ausente" if tamanho is None else "disponivel" if tamanho else "vazio",
    }


def _hash_confere(path: Path, esperado: object) -> bool:
    try:
        return digest(path) == esperado
    except OSError:
        # Um produto pode desaparecer entre o stat e a abertura para leitura.
        return False


def _sha256_valido(valor: object) -> bool:
    return (isinstance(valor, str) and len(valor) == 64
            and all(c in "0123456789abcdef" for c in valor))


def inspecionar_pipeline(id_incendio: int, base: Path) -> dict:
    """Inspeciona estágios sem abrir/carregar as geometrias GeoJSON."""
    if not isinstance(id_incendio, int) or id_incendio <= 0:
        raise ValueError("ID de incêndio inválido.")
    raiz = Path(base) / str(id_incendio)
    dados = raiz/"dados"/f"estudo_caso_{id_incendio}"
    originais = [
        dados/f"P1_componentes_{id_incendio}.geojson",
        dados/f"P2_regiao_movel_{id_incendio}.geojson",
    ]
    brutos = [
        dados/"brutos_gee"/f"P1_componentes_{id_incendio}.geojson",
        dados/"brutos_gee"/f"P2_regiao_movel_{id_incendio}.geojson",
    ]
    fontes = {
        "bruto_gee_p1": _arquivo(brutos[0]),
        "bruto_gee_p2": _arquivo(brutos[1]),
        "p1_local": _arquivo(originais[0]),
        "p2_local": _arquivo(originais[1]),
    }
    local_ok = all(f["estado"] == "disponivel" for f in
                   (fontes["p1_local"], fontes["p2_local"]))

    manifestov2 = dados/"derivados_v2"/VERSAO/"manifesto_metodologia.json"
    manifesto_v2, erro_v2 = _ler_json(manifestov2)
    v2_base = manifestov2.parent
    arqs_v2 = [
        v2_base/f"P1_componentes_{id_incendio}.geojson",
        v2_base/f"P2_regiao_movel_{id_incendio}.geojson",
    ]
    diagnostico, _ = _ler_json(v2_base/"diagnostico_bloqueio.json")
    progresso_v2, erro_progresso = _ler_json(
        v2_base/"estado_preprocessamento.json"
    )
    metadados_v2 = {
        "versao": VERSAO,
        "estado": "pendente",
        "primeira_data_p2": manifesto_v2.get("primeira_data_p2"),
        "datas_p1": manifesto_v2.get("datas_p1"),
        "datas_p2": manifesto_v2.get("datas_p2"),
        "arquivos": {"p1":_arquivo(arqs_v2[0]), "p2":_arquivo(arqs_v2[1])},
        "erro": erro_v2 or erro_progresso,
        "progresso": progresso_v2,
    }
    if progresso_v2.get("estado") == "executando":
        # Sem heartbeat de processo: o arquivo pode representar uma
        # execução ativa OU interrompida. Não inventar que segue rodando.
        metadados_v2["estado"] = "execucao_nao_finalizada"
    elif progresso_v2.get("estado") == "bloqueado_topologia":
        metadados_v2["estado"] = "bloqueado_topologia"
        metadados_v2["erro"] = progresso_v2.get("erro")
    elif erro_v2 or erro_progresso:
        metadados_v2["estado"] = "erro_manifesto"
    elif manifesto_v2:
        if manifesto_v2.get("metodologia") != VERSAO:
            metadados_v2["estado"] = "versao_incompativel"
        elif not all(f["estado"] == "disponivel"
                     for f in metadados_v2["arquivos"].values()):
            metadados_v2["estado"] = "artefato_perdido"
        elif not fontes["p1_local"]["existe"]:
            metadados_v2["estado"] = "origem_ausente"
        else:
            chaves = ("sha256_p1_origem", "codigo_sha256", "sha256_p1_v2", "sha256_p2_v2")
            codigo = (Path(__file__).resolve().parents[3] /
                      "burngeoflow" / "processamento" / "metodologia_v2.py")
            if not all(_sha256_valido(manifesto_v2.get(chave)) for chave in chaves):
                metadados_v2["estado"] = "proveniencia_incompleta"
            elif not _hash_confere(originais[0], manifesto_v2["sha256_p1_origem"]):
                metadados_v2["estado"] = "origem_alterada"
            elif not _hash_confere(codigo, manifesto_v2["codigo_sha256"]):
                metadados_v2["estado"] = "codigo_v2_alterado"
            elif any(not _hash_confere(path, manifesto_v2[chave])
                     for chave, path in zip(chaves[2:], arqs_v2)):
                metadados_v2["estado"] = "artefato_modificado"
            else:
                metadados_v2["estado"] = "preprocessado_nao_integrado"
    elif diagnostico:
        metadados_v2["estado"] = "bloqueado_topologia"
        metadados_v2["erro"] = diagnostico.get("erro")

    manifesto, erro_manifesto = _ler_json(raiz/"execucao.json")
    hashes = manifesto.get("entradas_sha256") or {}
    if not isinstance(hashes, dict):
        hashes = {}
        erro_manifesto = "entradas_sha256 não é um objeto"
    etapas_historicas = manifesto.get("etapas") or {}
    if not isinstance(etapas_historicas, dict):
        etapas_historicas = {}
        erro_manifesto = "etapas não é um objeto"
    entrada_confere = local_ok and bool(hashes)
    if entrada_confere:
        entrada_confere = all(
            _hash_confere(path, hashes.get(chave))
            for chave, path in zip(("p1","p2"), originais)
        )

    etapas = []
    cadeia_ok = True
    for etapa in definir_etapas(id_incendio,raiz,*originais):
        entrada = etapas_historicas.get(etapa.nome, {})
        if not isinstance(entrada, dict):
            entrada = {}
        original = entrada.get("status")
        faltam = [str(p.relative_to(raiz)) for p in etapa.artefatos
                  if _arquivo(p)["estado"] != "disponivel"]
        assinatura_anterior = entrada.get("codigo_sha256")
        codigo_compativel = (assinatura_anterior is not None
                             and assinatura_anterior == assinatura_codigo(etapa.nome))
        if original == "falha":
            estado = "erro"
        elif original == "concluido" and faltam:
            estado = "artefato_perdido"
        elif original == "concluido" and (not entrada_confere or not codigo_compativel):
            estado = "desatualizado"
        elif original == "concluido" and not cadeia_ok:
            estado = "dependencia_desatualizada"
        elif original == "concluido":
            estado = "concluido_legado"
        elif faltam:
            estado = "pendente"
        else:
            # Há artefatos soltos, mas não há comprovação por manifesto.
            estado = "sem_proveniencia"
        cadeia_ok = cadeia_ok and estado == "concluido_legado"
        etapas.append({
            "nome": etapa.nome, "estado": estado,
            "status_manifesto": original,
            "artefatos_ausentes": faltam,
            "assinatura_confere": codigo_compativel,
            "mensagem": (
                "Arquivos existentes são do pipeline anterior e NÃO "
                "comprovam conformidade com D-001/D-002."
                if estado == "concluido_legado" else
                "Última execução falhou; consulte o log da etapa."
                if estado == "erro" else
                "Arquivo esperado ausente ou vazio."
                if estado == "artefato_perdido" else
                "Reprocessamento necessário; não reutilizar este resultado "
                "como válido na metodologia nova."
            ),
        })

    alertas = []
    if local_ok and not (raiz/"execucao.json").is_file():
        alertas.append(
            "P1/P2 presentes, mas execucao.json não foi encontrado. "
            "Produtos derivados não possuem comprovação de proveniência."
        )
    if not local_ok:
        alertas.append("P1/P2 locais incompletos: verificar insumos antes do processamento.")
    if erro_manifesto:
        alertas.append("Manifesto de execução inválido: "+erro_manifesto)
    if local_ok and metadados_v2["estado"] == "pendente":
        alertas.append("Metodologia D-001/D-002 ainda não preparada neste ID.")
    if metadados_v2["estado"] in {
        "bloqueado_topologia","erro_manifesto","artefato_perdido",
        "origem_ausente","origem_alterada","versao_incompativel",
        "codigo_v2_alterado","proveniencia_incompleta","artefato_modificado",
        "execucao_nao_finalizada",
    }:
        alertas.append("Pré-processamento v2 comprometido: "+metadados_v2["estado"])
    if metadados_v2["estado"] == "preprocessado_nao_integrado":
        alertas.append(
            "P1/P2 v2 foram construídos, mas as etapas dependentes ainda "
            "precisam ser adaptadas e validadas antes de uso científico."
        )
    if any(e["estado"] in {"erro","artefato_perdido","desatualizado",
                          "dependencia_desatualizada"} for e in etapas):
        alertas.append("Há etapas antigas com erro, arquivo perdido ou proveniência inválida.")

    return {
        "id_incendio":id_incendio,
        "metodologia_alvo":VERSAO,
        "metodologia_pipeline_atual":"legado_progressivo_nao_conforme",
        "pronto_para_reprocessamento_integral_v2":False,
        "dados":fontes,
        "preprocessamento_v2":metadados_v2,
        "manifesto_existe":(raiz/"execucao.json").is_file(),
        "entradas_compativeis_manifesto_legado":entrada_confere,
        "etapas":etapas,
        "alertas":alertas,
        "nota":"Inspeção somente leitura: não valida dados fisicamente nem chama GEE.",
    }
