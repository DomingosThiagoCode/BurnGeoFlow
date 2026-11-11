"""Aquisição automática de áreas queimadas acumuladas pelo Earth Engine.

Replica as seções 5-12 do script GEE do projeto CDG_incendio:
- união acumulada dos perímetros diários;
- P1: todos os componentes da geometria acumulada;
- P2: maior componente inicial, seguido pelo maior overlap com o anterior;
  distância ao anterior somente quando não existe overlap.

A aquisição usa ee.data.computeFeatures com paginação. Não exige Drive.
A rotina só substitui P1/P2 depois de validar ambos os GeoJSONs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from burngeoflow.config import ConfiguracaoGEE, carregar_configuracao_gee
from burngeoflow.validacao.produtos import verificar

ASSET = "JRC/GWIS/GlobFire/v2/DailyPerimeters"
ANO_MINIMO, ANO_MAXIMO = 2001, 2020
ERRO_GEOMETRICO_M = 100


class ErroAquisicao(RuntimeError):
    """Erro operacional de aquisição, distinto das falhas científicas."""


def inicializar(config: ConfiguracaoGEE, *, solicitar_login: bool = False) -> Any:
    """Inicializa o GEE sem versionar tokens e sem login interativo implícito."""
    try:
        import ee
    except ImportError as exc:
        raise ErroAquisicao(
            "Pacote Earth Engine ausente. Instale requirements-gee.txt."
        ) from exc
    try:
        if solicitar_login:
            ee.Authenticate()
        ee.Initialize(project=config.projeto)
    except Exception as exc:
        raise ErroAquisicao(
            "Falha na autenticação GEE. Confira EE_PROJECT_ID, habilite o Earth "
            "Engine no Google Cloud e execute 'earthengine authenticate'. "
            f"Detalhe técnico: {type(exc).__name__}: {exc}"
        ) from exc
    return ee


def selecionar_evento(ee: Any, id_incendio: int, ano: int) -> Any:
    """Cria expressão diferida; não faz chamada à rede."""
    if id_incendio <= 0:
        raise ErroAquisicao("O ID do incêndio precisa ser positivo.")
    if ano < ANO_MINIMO or ano > ANO_MAXIMO:
        raise ErroAquisicao(
            f"GlobFire v2 DailyPerimeters cobre {ANO_MINIMO}-{ANO_MAXIMO}."
        )
    return ee.FeatureCollection(f"{ASSET}/{ano}").filter(
        ee.Filter.eq("Id", id_incendio)
    )


def consultar_evento(ee: Any, id_incendio: int, ano: int) -> tuple[Any, int]:
    colecao = selecionar_evento(ee, id_incendio, ano)
    try:
        registros = int(colecao.size().getInfo())
    except Exception as exc:
        raise ErroAquisicao(
            f"Erro ao consultar {ASSET}/{ano}: {type(exc).__name__}: {exc}"
        ) from exc
    if registros == 0:
        raise ErroAquisicao(f"ID {id_incendio} não encontrado no ano {ano}.")
    return colecao, registros


def localizar_evento(
    ee: Any, id_incendio: int, ano: int | None,
    informar: Callable[[str], None] = print,
) -> tuple[Any, int, int]:
    """Procura ano, quando omitido. O catálogo está separado em 20 coleções."""
    if ano is not None:
        evento, registros = consultar_evento(ee, id_incendio, ano)
        return evento, ano, registros
    if id_incendio <= 0:
        raise ErroAquisicao("O ID do incêndio precisa ser positivo.")
    for candidato in range(ANO_MAXIMO, ANO_MINIMO - 1, -1):
        informar(f"[GEE] Consultando ano {candidato}")
        colecao = selecionar_evento(ee, id_incendio, candidato)
        try:
            qtd = int(colecao.size().getInfo())
        except Exception as exc:
            raise ErroAquisicao(
                f"Falha consultando {candidato}: {type(exc).__name__}: {exc}. "
                "Informe --ano para restringir a pesquisa."
            ) from exc
        if qtd:
            return colecao, candidato, qtd
    raise ErroAquisicao(
        f"ID {id_incendio} não encontrado nas coleções de {ANO_MINIMO}-{ANO_MAXIMO}."
    )


def construir_produtos(
    ee: Any, evento: Any, id_incendio: int, ano: int,
    *, erro_m: int = ERRO_GEOMETRICO_M,
) -> tuple[Any, Any, int]:
    """Traduz a lógica de P1/P2 do JavaScript GEE para API Python."""
    if erro_m <= 0:
        raise ErroAquisicao("erro_m deve ser positivo.")
    datas = ee.List(evento.aggregate_array("IDate")).distinct().sort()
    try:
        qtd_datas = int(datas.size().getInfo())
    except Exception as exc:
        raise ErroAquisicao(f"Falha lendo datas IDate: {exc}") from exc
    if qtd_datas < 1:
        raise ErroAquisicao("Evento sem datas IDate válidas.")

    def geometria_diaria(data: Any) -> Any:
        return evento.filter(
            ee.Filter.eq("IDate", ee.Number(data))
        ).geometry().dissolve(erro_m)

    def componentes(geometria: Any, data: Any) -> Any:
        data = ee.Number(data)
        partes = ee.Geometry(geometria).geometries()

        def componente(g: Any) -> Any:
            geom = ee.Geometry(g)
            return ee.Feature(geom, {
                "id_incendio": id_incendio,
                "ano_dataset": ano,
                "data_millis": data,
                "data": ee.Date(data).format("YYYY-MM-dd"),
                "area_km2": geom.area(erro_m).divide(1e6),
            })

        ordenados = ee.FeatureCollection(partes.map(componente)).sort(
            "area_km2", False
        )
        quantidade = ordenados.size()
        lista = ordenados.toList(quantidade)

        def ranquear(i: Any) -> Any:
            indice = ee.Number(i)
            return ee.Feature(lista.get(indice)).set({
                "rank": indice.add(1),
                "eh_maior": indice.eq(0),
            })

        ranqueados = ee.FeatureCollection(
            ee.List.sequence(0, quantidade.subtract(1)).map(ranquear)
        )
        total = ee.Number(ranqueados.aggregate_sum("area_km2"))

        def metadados(f: Any) -> Any:
            feicao = ee.Feature(f)
            area = ee.Number(feicao.get("area_km2"))
            return feicao.set({
                "numero_componentes": quantidade,
                "area_total_km2": total,
                "proporcao_area_pct": area.divide(total).multiply(100),
            })

        return ranqueados.map(metadados)

    primeira = ee.Number(datas.get(0))
    acumulado_inicial = geometria_diaria(primeira)
    p1_inicial = componentes(acumulado_inicial, primeira)
    rm_base = ee.Feature(p1_inicial.filter(ee.Filter.eq("rank", 1)).first())
    area_inicial = ee.Number(rm_base.get("area_km2"))
    total_inicial = ee.Number(rm_base.get("area_total_km2"))
    n_inicial = ee.Number(rm_base.get("numero_componentes"))
    rm_inicial = rm_base.set({
        "ordem_temporal": 1, "rank_global": 1,
        "metodo_continuidade": "inicial_maior_area",
        "overlap_prev_km2": 0, "overlap_prev_pct": 0,
        "overlap_candidato_pct": 0, "distancia_prev_m": 0,
        "delta_area_km2": 0, "delta_area_pct": 0,
        "delta_area_total_km2": 0, "delta_num_componentes": 0,
        "rm_eh_maior": True,
        "proporcao_rm_pct": area_inicial.divide(total_inicial).multiply(100),
    })
    estado_inicial = ee.Dictionary({
        "geom_acumulada": acumulado_inicial,
        "geom_rm_anterior": rm_inicial.geometry(),
        "area_rm_anterior": area_inicial,
        "area_total_anterior": total_inicial,
        "numero_componentes_anterior": n_inicial,
        "lista_rm": ee.List([rm_inicial]),
        "lista_componentes": p1_inicial.toList(p1_inicial.size()),
    })

    def transicao(data: Any, estado_bruto: Any) -> Any:
        estado = ee.Dictionary(estado_bruto)
        data = ee.Number(data)
        geom_anterior = ee.Geometry(estado.get("geom_acumulada"))
        rm_anterior = ee.Geometry(estado.get("geom_rm_anterior"))
        area_rm_anterior = ee.Number(estado.get("area_rm_anterior"))
        total_anterior = ee.Number(estado.get("area_total_anterior"))
        n_anterior = ee.Number(estado.get("numero_componentes_anterior"))
        geometria_atual = geom_anterior.union(geometria_diaria(data), erro_m)
        atuais = componentes(geometria_atual, data)
        n = atuais.size()
        total = ee.Number(atuais.aggregate_sum("area_km2"))

        def comparar(f: Any) -> Any:
            feicao = ee.Feature(f)
            area_intersecao = feicao.geometry().intersection(
                rm_anterior, erro_m
            ).area(erro_m).divide(1e6)
            area_candidato = ee.Number(feicao.get("area_km2"))
            pct_anterior = ee.Number(ee.Algorithms.If(
                area_rm_anterior.gt(0),
                area_intersecao.divide(area_rm_anterior).multiply(100), 0
            ))
            pct_candidato = ee.Number(ee.Algorithms.If(
                area_candidato.gt(0),
                area_intersecao.divide(area_candidato).multiply(100), 0
            ))
            return feicao.set({
                "overlap_prev_km2": area_intersecao,
                "overlap_prev_pct": pct_anterior,
                "overlap_candidato_pct": pct_candidato,
                "distancia_prev_m": feicao.geometry().distance(
                    rm_anterior, erro_m
                ),
            })

        candidatos = atuais.map(comparar)
        maior_overlap = ee.Number(candidatos.aggregate_max("overlap_prev_km2"))
        escolhido = ee.Feature(ee.Algorithms.If(
            maior_overlap.gt(0),
            candidatos.sort("overlap_prev_km2", False).first(),
            candidatos.sort("distancia_prev_m", True).first(),
        ))
        metodo = ee.String(ee.Algorithms.If(
            maior_overlap.gt(0), "sobreposicao", "distancia_fallback"
        ))
        area_atual = ee.Number(escolhido.get("area_km2"))
        rank_atual = ee.Number(escolhido.get("rank"))
        delta = area_atual.subtract(area_rm_anterior)
        delta_pct = ee.Number(ee.Algorithms.If(
            area_rm_anterior.gt(0),
            delta.divide(area_rm_anterior).multiply(100), 0
        ))
        rm_atual = escolhido.set({
            "ordem_temporal": ee.Number(datas.indexOf(data)).add(1),
            "rank_global": rank_atual,
            "metodo_continuidade": metodo,
            "delta_area_km2": delta, "delta_area_pct": delta_pct,
            "delta_area_total_km2": total.subtract(total_anterior),
            "delta_num_componentes": ee.Number(n).subtract(n_anterior),
            "rm_eh_maior": rank_atual.eq(1),
            "proporcao_rm_pct": area_atual.divide(total).multiply(100),
        })
        return ee.Dictionary({
            "geom_acumulada": geometria_atual,
            "geom_rm_anterior": rm_atual.geometry(),
            "area_rm_anterior": area_atual,
            "area_total_anterior": total,
            "numero_componentes_anterior": n,
            "lista_rm": ee.List(estado.get("lista_rm")).add(rm_atual),
            "lista_componentes": ee.List(estado.get("lista_componentes")).cat(
                atuais.toList(atuais.size())
            ),
        })

    estado_final = ee.Dictionary(
        datas.slice(1).iterate(transicao, estado_inicial)
    )
    p1 = ee.FeatureCollection(
        ee.List(estado_final.get("lista_componentes"))
    ).sort("data_millis")
    p2 = ee.FeatureCollection(
        ee.List(estado_final.get("lista_rm"))
    ).sort("data_millis")
    return p1, p2, qtd_datas


def obter_geojson(
    ee: Any, colecao: Any, *, pagina: int = 50, limite: int = 50000
) -> dict:
    """Obtém feições por páginas. O GEE retorna EPSG:4326 em GeoJSON.

    Não usa fileFormat: formatos DataFrame fazem paginação interna diferente.
    """
    if not 1 <= pagina <= 1000:
        raise ErroAquisicao("A página precisa conter de 1 a 1000 feições.")
    feicoes: list[dict] = []
    token: str | None = None
    vistos: set[str] = set()
    while True:
        params: dict[str, Any] = {"expression": colecao, "pageSize": pagina}
        if token is not None:
            params["pageToken"] = token
        try:
            resposta = ee.data.computeFeatures(params)
        except Exception as exc:
            raise ErroAquisicao(
                f"Falha na exportação paginada, após {len(feicoes)} feições: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if (not isinstance(resposta, dict)
                or not isinstance(resposta.get("features"), list)):
            raise ErroAquisicao("Resposta inválida de computeFeatures.")
        feicoes.extend(resposta["features"])
        if len(feicoes) > limite:
            raise ErroAquisicao(
                f"Limite de {limite} feições excedido. "
                "A exportação em lotes precisará ser habilitada para esse evento."
            )
        proximo = resposta.get("next_page_token") or resposta.get("nextPageToken")
        if not proximo:
            break
        if proximo in vistos:
            raise ErroAquisicao("Paginação GEE repetiu um token.")
        vistos.add(str(proximo))
        token = str(proximo)
    if not feicoes:
        raise ErroAquisicao("Nenhuma feição obtida pelo GEE.")
    for indice, f in enumerate(feicoes):
        if (not isinstance(f, dict) or f.get("type") != "Feature"
                or not isinstance(f.get("geometry"), dict)
                or not isinstance(f.get("properties"), dict)):
            raise ErroAquisicao(f"Feição {indice} inválida na resposta GEE.")
    return {"type": "FeatureCollection", "features": feicoes}


def publicar_geojsons(
    pasta: Path, id_incendio: int, p1: dict, p2: dict,
) -> tuple[Path, Path, dict]:
    """Valida P1/P2 e publica sem deixar par incompleto na falha."""
    pasta.mkdir(parents=True, exist_ok=True)
    destinos = [
        pasta / f"P1_componentes_{id_incendio}.geojson",
        pasta / f"P2_regiao_movel_{id_incendio}.geojson",
    ]
    with TemporaryDirectory(prefix=".gee-", dir=pasta) as temp:
        temporarios = [Path(temp) / d.name for d in destinos]
        for entrada, caminho in zip((p1, p2), temporarios):
            caminho.write_text(
                json.dumps(entrada, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        try:
            resumo = verificar(*temporarios)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ErroAquisicao(
                f"P1/P2 exportados reprovados pelo validador: {exc}"
            ) from exc
        if resumo["id_incendio"] != id_incendio:
            raise ErroAquisicao("ID obtido diverge do solicitado.")
        backups = [Path(temp) / (d.name + ".backup") for d in destinos]
        existentes = [caminho.exists() for caminho in destinos]
        try:
            for destino, backup, tinha in zip(destinos, backups, existentes):
                if tinha:
                    os.replace(destino, backup)
            for origem, destino in zip(temporarios, destinos):
                os.replace(origem, destino)
        except OSError:
            for destino, backup, tinha in zip(destinos, backups, existentes):
                if tinha and backup.exists():
                    os.replace(backup, destino)
                elif not tinha and destino.exists():
                    destino.unlink()
            raise
    return destinos[0], destinos[1], resumo


def adquirir(
    id_incendio: int, pasta: Path, *,
    ano: int | None = None,
    projeto: str | None = None,
    autenticar: bool = False,
    pagina: int = 50,
    ee_modulo: Any | None = None,
    informar: Callable[[str], None] = print,
) -> tuple[Path, Path, dict]:
    """Executa consulta, geração e exportação P1/P2; ee_modulo permite mock."""
    if ee_modulo is None:
        config = carregar_configuracao_gee(projeto=projeto)
        ee_modulo = inicializar(config, solicitar_login=autenticar)
        projeto_usado = config.projeto
    else:
        projeto_usado = projeto or "teste-sem-rede"
    evento, ano_usado, n_registros = localizar_evento(
        ee_modulo, id_incendio, ano, informar=informar
    )
    informar(f"[GEE] ID={id_incendio}, ano={ano_usado}, registros={n_registros}")
    p1_ee, p2_ee, n_datas = construir_produtos(
        ee_modulo, evento, id_incendio, ano_usado
    )
    informar(f"[GEE] {n_datas} datas; exportando P1 e P2")
    p1 = obter_geojson(ee_modulo, p1_ee, pagina=pagina)
    p2 = obter_geojson(ee_modulo, p2_ee, pagina=pagina)
    if len(p2["features"]) != n_datas:
        raise ErroAquisicao(
            f"P2 contém {len(p2['features'])} geometrias e eram esperadas {n_datas}."
        )
    caminho_p1, caminho_p2, resumo = publicar_geojsons(
        pasta, id_incendio, p1, p2
    )
    metadados = {
        "id_incendio": id_incendio,
        "ano_dataset": ano_usado,
        "colecao": f"{ASSET}/{ano_usado}",
        "registros_fonte": n_registros,
        "datas": n_datas,
        "componentes_p1": len(p1["features"]),
        "regioes_p2": len(p2["features"]),
        "pagina": pagina,
        "max_erro_m": ERRO_GEOMETRICO_M,
        "projeto_google_cloud": projeto_usado,
        "momento_utc": datetime.now(timezone.utc).isoformat(),
        "validacao_estrutura": resumo,
        "validacao_independente": False,
        "metodo": "acumulado_union__p2_overlap_e_distancia_fallback",
    }
    (pasta / f"aquisicao_{id_incendio}.json").write_text(
        json.dumps(metadados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return caminho_p1, caminho_p2, metadados
