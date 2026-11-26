"""Pré-processamento científico v2: P1 por contato e P2 retrospectivo.

D-001/D-002/D-003/D-004/D-007. Entradas originais imutáveis. Produtos
versionados em diretório separado; NÃO substituem automaticamente os insumos
do pipeline legado antes da adaptação/validação de todas as etapas seguintes.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pyproj
import shapely
from shapely.geometry import mapping, shape

from burngeoflow.processamento.conectividade import grupos_conectados

VERSAO = "p1-contato-v2_p2-retro-v2"
class ErroMetodologia(ValueError):
    def __init__(self, mensagem: str, diagnostico: dict | None = None):
        super().__init__(mensagem)
        self.diagnostico = diagnostico or {}


def _hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _salvar_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                            delete=False) as arquivo:
        json.dump(obj, arquivo, ensure_ascii=False, separators=(",", ":"))
        temporario = Path(arquivo.name)
    temporario.replace(path)


def _carregar(p1_path: Path) -> tuple[int, dict[str, list], dict]:
    colecao = json.loads(p1_path.read_text(encoding="utf-8"))
    if colecao.get("type") != "FeatureCollection":
        raise ErroMetodologia("P1 de origem não é FeatureCollection.")
    grupos = defaultdict(list)
    ids = set()
    for i, feat in enumerate(colecao.get("features", [])):
        props = feat.get("properties") or {}
        data = props.get("data")
        try:
            datetime.strptime(data, "%Y-%m-%d")
            identidade = int(props["id_incendio"])
            rank = int(props["rank"])
            geom = shape(feat["geometry"])
        except (TypeError, KeyError, ValueError) as exc:
            raise ErroMetodologia(f"P1 bruto, feição {i}: campos inválidos.") from exc
        if geom.geom_type not in ("Polygon", "MultiPolygon") or geom.is_empty:
            raise ErroMetodologia(f"P1 bruto, feição {i}: geometria não poligonal.")
        ids.add(identidade)
        grupos[data].append((rank, geom))
    if len(ids) != 1 or not grupos:
        raise ErroMetodologia("P1 bruto deve representar um único evento não vazio.")
    for data, itens in grupos.items():
        ranks = sorted(rank for rank, _ in itens)
        if ranks != list(range(1, len(itens)+1)):
            raise ErroMetodologia(f"{data}: ranks originais repetidos ou ausentes.")
    all_bounds = [g.bounds for group in grupos.values() for _, g in group]
    west, south = min(b[0] for b in all_bounds), min(b[1] for b in all_bounds)
    east, north = max(b[2] for b in all_bounds), max(b[3] for b in all_bounds)
    if east - west > 180:
        raise ErroMetodologia("Evento cruza antimeridiano; projeção requer revisão.")
    center = ((west+east)/2, (south+north)/2)
    crs = pyproj.CRS.from_proj4(
        f"+proj=laea +lon_0={center[0]:.10f} +lat_0={center[1]:.10f} "
        "+datum=WGS84 +units=m +no_defs"
    )
    to_laea = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    to_wgs84 = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    return next(iter(ids)), dict(sorted(grupos.items())), {
        "crs_laea": crs.to_proj4(),
        "to_laea": to_laea,
        "to_wgs84": to_wgs84,
    }


def _preparar_componentes(originais: dict[str, list], transforms: dict,
                          informar=None, auditoria=None) -> dict:
    saida = {}
    total_datas = len(originais)
    for indice_data, (dia, itens) in enumerate(originais.items(), start=1):
        patches = []
        for rank, geom in itens:
            geo = shapely.transform(
                geom, transforms["to_laea"].transform, interleaved=False
            )
            if not geo.is_valid or geo.is_empty or geo.area <= 0:
                raise ErroMetodologia(
                    f"{dia} rank {rank}: geometria inválida após projeção. "
                    "Revisar origem/reparo antes de reconstruir P1.",
                    {"data": dia, "rank": rank, "motivo": shapely.is_valid_reason(geo)},
                )
            patches.append((rank, geo))
        componentes = grupos_conectados([g for _, g in patches])
        novos = []
        for grupo in componentes:
            membros = [patches[j] for j in grupo]
            # D-002: cada grupo conectado é a cobertura da UNIÃO dos
            # membros. Uma interseção areal é contada uma única vez, sem
            # escolher um rank "dono", alterar P1 bruto nem usar buffer.
            # Não aplicar limiar derivado da resolução MODIS (D-013).
            geo = shapely.union_all([g for _, g in membros])
            if geo.geom_type not in ("Polygon", "MultiPolygon") or not geo.is_valid:
                raise ErroMetodologia(
                    f"{dia}: união por contato produziu {geo.geom_type} inválido."
                )
            soma_original_m2 = sum(g.area for _, g in membros)
            area_duplicada_m2 = soma_original_m2 - geo.area
            # Guardar o resíduo assinado, inclusive arredondamento numérico.
            # Somente indicar overlap positivo; sem corrigir área por epsilon.
            if auditoria is not None and area_duplicada_m2 > 0:
                auditoria.append({
                    "data": dia, "ranks_origem": sorted(rank for rank, _ in membros),
                    "area_somada_m2": soma_original_m2,
                    "area_uniao_m2": geo.area,
                    "area_contada_repetidamente_m2": area_duplicada_m2,
                    "interpretacao": "sobreposicao_ou_precisao_numerica_a_investigar",
                })
            novos.append({
                "geometria": geo,
                "ranks_origem": sorted(rank for rank, _ in membros),
                "area_m2": geo.area,
                "residuo_soma_menos_uniao_m2": area_duplicada_m2,
            })
        novos.sort(key=lambda x: (-x["area_m2"], x["ranks_origem"]))
        saida[dia] = novos
        if informar and (
            indice_data == total_datas or indice_data == 1 or indice_data % 10 == 0
        ):
            informar(indice_data, total_datas, dia)
    return saida


def _retroceder(
    componentes: dict, desempate_critico: bool = True
) -> tuple[list[dict], list[dict]]:
    datas = sorted(componentes)
    atual = componentes[datas[-1]][0]
    selecionados = [(datas[-1], 0, atual, "dominante_final")]
    desempates = []
    for dia, data_posterior in zip(reversed(datas[:-1]), reversed(datas[1:])):
        candidatos = []
        for rank, candidato in enumerate(componentes[dia]):
            inter = candidato["geometria"].intersection(atual["geometria"]).area
            if inter > 0:
                candidatos.append({
                    "rank": rank, "item": candidato, "intersecao_m2": inter,
                    "area_m2": candidato["area_m2"],
                    "distancia_centroides_m": candidato["geometria"].centroid.distance(
                        atual["geometria"].centroid
                    ),
                })
        if not candidatos:
            # D-003: encerrar no primeiro ponto sem ancestral espacial.
            break
        candidatos.sort(key=lambda c: (
            -c["intersecao_m2"], -c["area_m2"], c["distancia_centroides_m"],
            c["rank"],
        ))
        primeiro = candidatos[0]
        empatados = [
            c for c in candidatos if c["intersecao_m2"] == primeiro["intersecao_m2"]
        ]
        if len(empatados) > 1:
            segundo = empatados[1]
            if primeiro["area_m2"] != segundo["area_m2"]:
                criterio = "maior_area_total"
            elif primeiro["distancia_centroides_m"] != segundo["distancia_centroides_m"]:
                criterio = "menor_distancia_centroides"
            else:
                criterio = "empate_integral" if desempate_critico else "menor_rank"
            desempates.append({
                "data": dia,
                "data_posterior": data_posterior,
                "criterio": criterio,
                "rank_escolhido": (
                    None if criterio == "empate_integral" else primeiro["rank"] + 1
                ),
                "candidatos": [
                    {
                        "rank": candidato["rank"] + 1,
                        "intersecao_m2": candidato["intersecao_m2"],
                        "area_total_m2": candidato["area_m2"],
                        "distancia_centroides_m": candidato["distancia_centroides_m"],
                    }
                    for candidato in empatados
                ],
            })
            if criterio == "empate_integral":
                ranks = [primeiro["rank"] + 1, segundo["rank"] + 1]
                raise ErroMetodologia(
                    f"{dia}: empate integral de ancestralidade entre "
                    f"ranks {ranks[0]}/{ranks[1]}. "
                    "Critério residual ainda não aprovado (D-004/D-013).",
                    {"data": dia, "ranks": ranks, "desempates_p2": desempates},
                )
        escolhido = primeiro
        atual = escolhido["item"]
        selecionados.append((dia, escolhido["rank"], atual, "maior_intersecao_retro"))
    selecionados.reverse()
    saida = []
    for dia, idx, componente, metodo in selecionados:
        saida.append({
            "data": dia, "rank": idx+1, "item": componente,
            "metodo": metodo,
        })
    return saida, desempates


def reconstruir(p1_path: Path, pasta_saida: Path, *, id_esperado: int | None = None) -> dict:
    """Gera cópias experimentais versionadas; nunca sobrescreve o P1 antigo."""
    p1_path = Path(p1_path)
    incendio, originais, transforms = _carregar(p1_path)
    if id_esperado is not None and incendio != id_esperado:
        raise ErroMetodologia(
            f"P1 local contém ID {incendio}, mas foi solicitado {id_esperado}."
        )
    pasta = Path(pasta_saida) / VERSAO
    pasta.mkdir(parents=True, exist_ok=True)
    estado_path = pasta/"estado_preprocessamento.json"
    codigo_sha = _hash(Path(__file__))
    _salvar_json(estado_path, {
        "id_incendio":incendio, "versao":VERSAO, "estado":"executando",
        "etapa":"conectividade_p1", "datas_concluidas":0,
        "datas_total":len(originais),
    })
    def progresso(indice, total, dia):
        _salvar_json(estado_path, {
            "id_incendio":incendio, "versao":VERSAO, "estado":"executando",
            "etapa":"conectividade_p1", "datas_concluidas":indice,
            "datas_total":total, "ultima_data":dia,
        })
        print(f"[V2] Conectividade P1 {indice}/{total} datas (até {dia})",
              flush=True)

    auditoria_cobertura = []
    try:
        componentes = _preparar_componentes(
            originais, transforms, progresso, auditoria_cobertura
        )
        _salvar_json(estado_path, {
            "id_incendio":incendio, "versao":VERSAO, "estado":"executando",
            "etapa":"rastreamento_retro_p2", "datas_concluidas":len(componentes),
            "datas_total":len(componentes),
        })
        p2, desempates = _retroceder(componentes)
    except ErroMetodologia as exc:
        _salvar_json(pasta / "diagnostico_bloqueio.json", {
            "id_incendio": incendio, "versao": VERSAO,
            "sha256_p1_origem": _hash(p1_path),
            "erro": str(exc), "detalhes": exc.diagnostico,
            "status": "bloqueado_revisao_topologica",
        })
        _salvar_json(estado_path, {
            "id_incendio":incendio, "versao":VERSAO,
            "estado":"bloqueado_topologia", "erro":str(exc),
        })
        raise
    if not p2:
        raise ErroMetodologia("P2 retrospectivo não encontrou componente final.")
    # Atributos oficiais do produto NOVO calculados na LAEA (não área EE).
    totais = {d:sum(c["area_m2"] for c in v)/1e6 for d,v in componentes.items()}
    features_p1 = []
    for dia, lista in componentes.items():
        for i, c in enumerate(lista, start=1):
            geo = shapely.transform(
                c["geometria"], transforms["to_wgs84"].transform,
                interleaved=False
            )
            features_p1.append({
                "type":"Feature", "geometry":mapping(geo),
                "properties":{
                    "id_incendio": incendio, "data": dia, "rank": i,
                    "area_km2": c["area_m2"]/1e6,
                    "numero_componentes": len(lista),
                    "area_total_km2": totais[dia],
                    "ranks_origem": c["ranks_origem"],
                    "residuo_soma_menos_uniao_m2": c["residuo_soma_menos_uniao_m2"],
                    "metodologia": VERSAO,
                    "area_atributo_fonte": "LAEA_local",
                },
            })
    features_p2 = []
    anterior = None
    for ordem, item in enumerate(p2, start=1):
        dia, rank, c = item["data"], item["rank"], item["item"]
        geo = shapely.transform(
            c["geometria"], transforms["to_wgs84"].transform,
            interleaved=False
        )
        total = totais[dia]
        a = c["area_m2"]/1e6
        features_p2.append({
            "type":"Feature", "geometry":mapping(geo),
            "properties":{
                "id_incendio": incendio, "data": dia, "rank": rank,
                "rank_global": rank, "ordem_temporal": ordem,
                "area_km2": a, "numero_componentes":len(componentes[dia]),
                "area_total_km2":total,
                "delta_area_km2":0.0 if anterior is None else a-anterior[1],
                "delta_area_total_km2":0.0 if anterior is None else total-anterior[2],
                "representatividade_pct":100*a/total if total else None,
                "metodo_continuidade":item["metodo"],
                "residuo_soma_menos_uniao_m2": c["residuo_soma_menos_uniao_m2"],
                "metodologia":VERSAO, "area_atributo_fonte":"LAEA_local",
            },
        })
        anterior = (dia, a, total)
    manifesto = {
        "id_incendio": incendio, "metodologia": VERSAO,
        "estado":"preprocessado_nao_integrado",
        "origem_p1":str(p1_path),
        "sha256_p1_origem":_hash(p1_path),
        "codigo_sha256":codigo_sha,
        "datas_p1":len(componentes), "datas_p2":len(p2),
        "primeira_data_p2":p2[0]["data"],
        "ultima_data_p2":p2[-1]["data"],
        "desempates_p2": desempates,
        "politica_cobertura_intradata": "uniao_sem_duplicacao_com_ranks_origem",
        "componentes_com_residuo_positivo": len(auditoria_cobertura),
        "residuo_positivo_total_m2": sum(
            x["area_contada_repetidamente_m2"] for x in auditoria_cobertura
        ),
        "observacao":(
            "Pré-processamento geométrico experimental; requer adaptação "
            "dos validadores e análises dependentes de P2 e homologação."
        ),
    }
    p1_v2 = pasta/f"P1_componentes_{incendio}.geojson"
    p2_v2 = pasta/f"P2_regiao_movel_{incendio}.geojson"
    _salvar_json(p1_v2, {
        "type":"FeatureCollection","features":features_p1,
    })
    _salvar_json(p2_v2, {
        "type":"FeatureCollection","features":features_p2,
    })
    manifesto.update({
        "sha256_p1_v2":_hash(p1_v2),
        "sha256_p2_v2":_hash(p2_v2),
    })
    auditoria_path = pasta/"auditoria_cobertura_p1.json"
    _salvar_json(auditoria_path, {
        "id_incendio": incendio,
        "metodologia": VERSAO,
        "criterio": "area_da_uniao_sem_duplicacao",
        "requer_revisao_qualitativa": bool(auditoria_cobertura),
        "componentes": auditoria_cobertura,
    })
    manifesto["sha256_auditoria_cobertura_p1"] = _hash(auditoria_path)
    _salvar_json(pasta/"manifesto_metodologia.json",manifesto)
    _salvar_json(estado_path, {
        "id_incendio":incendio, "versao":VERSAO,
        "estado":"preprocessado_nao_integrado",
        "datas_p1":len(componentes), "datas_p2":len(p2),
    })
    return manifesto
