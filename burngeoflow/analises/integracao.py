#!/usr/bin/env python3
"""Etapa 5: integra P1, linhagens, TR e IGT; distingue crescimento de incorporacao.

Entrada: os P1/P2 validados e CSVs de etapas 2-4 do mesmo evento.
Saida: tabelas, diagnostico quantitativo, figuras e relatorio de interpretacao.
A geometria representa area queimada ACUMULADA, nao frente ativa de fogo.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
from math import isfinite, log
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pyproj
import shapely
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union

from burngeoflow.analises.paisagem import carregar_p1, projetar_patches, salvar_csv
from burngeoflow.validacao.topologia_p2 import reconciliar_p2


CAMPOS_TRANSICOES = [
    "id_incendio", "data_anterior", "data_atual", "dias_intervalo",
    "area_total_anterior_km2", "area_total_atual_km2",
    "excesso_sobreposicao_anterior_km2", "excesso_sobreposicao_atual_km2",
    "delta_excesso_sobreposicao_km2", "area_nova_evento_km2",
    "taxa_nova_evento_km2_dia", "area_perdida_evento_km2",
    "p2_area_anterior_km2", "p2_area_atual_km2",
    "p2_incremento_geometrico_km2", "p2_incremento_ja_queimado_km2",
    "p2_incremento_nova_area_evento_km2", "nova_area_fora_p2_km2",
    "fracao_incremento_p2_ja_queimado_pct",
    "numero_patches_anterior", "numero_patches_atual",
    "eventos_convergencia", "eventos_surgimento_sem_sobreposicao",
    "tr_deslocamento_centroide_km", "tr_azimute_centroide_graus",
    "igt_azimute_ponderado_graus", "igt_concentracao_direcional",
    "desvio_fechamento_p2_m2", "desvio_fechamento_evento_m2",
    "lacuna_temporal", "alerta_escala_sensor"
]
CAMPOS_DIARIOS = [
    "id_incendio", "data", "fase_descritiva", "dias_desde_inicio",
    "area_total_laea_km2", "area_soma_patches_laea_km2",
    "excesso_sobreposicao_p1_km2", "dominancia_cobertura_p2_pct",
    "area_principal_laea_km2", "area_secundaria_laea_km2",
    "dominancia_maior_patch_pct", "numero_patches", "indice_forma_medio_ponderado_area",
    "delta_area_total_km2", "delta_area_cobertura_km2",
    "delta_excesso_sobreposicao_p1_km2", "taxa_media_intervalo_km2_dia",
    "eventos_convergencia_intervalo", "p2_area_laea_km2",
]
CAMPOS_FASE = [
    "fase_descritiva", "data_inicio", "data_fim", "observacoes",
    "taxa_tendencia_laea_km2_dia", "incremento_area_laea_km2",
    "numero_convergencias_nas_transicoes", "modelo_segmentos",
    "criterio_bic", "nota",
]


def ler_tabela(caminho: Path, *, campos_chave: tuple[str, ...]) -> dict:
    if not caminho.is_file():
        raise ValueError(f"Arquivo nao encontrado: {caminho}")
    with caminho.open(encoding="utf-8-sig", newline="") as arq:
        leitor = csv.DictReader(arq)
        dados = list(leitor)
    if not dados:
        raise ValueError(f"Tabela vazia: {caminho}")
    retorno = {}
    for l in dados:
        chave = tuple(l[c] for c in campos_chave)
        if chave in retorno:
            raise ValueError(f"Chave duplicada em {caminho.name}: {chave}")
        retorno[chave] = l
    return retorno


def valor(linha, campo):
    v = linha.get(campo)
    if v in (None, ""):
        return None
    f = float(v)
    if not isfinite(f):
        raise ValueError(f"{campo}: numero nao finito")
    return f


def conferir_proximo(a, b, etiqueta, *, tolerancia_km2=1e-5):
    if a is None or b is None or abs(a-b) > tolerancia_km2:
        raise ValueError(f"Inconsistencia em {etiqueta}: {a} != {b}")



def calcular_cobertura_componentes(grupos: dict[str, list]) -> tuple[dict, dict]:
    """Area coberta pela uniao P1, com auditoria de sobreposicoes.

    A soma de areas dos patches e preservada para conferencia com as
    Etapas 2/3. A area espacial do evento NAO pode contar duas vezes uma
    mesma superficie. Sobreposicoes acima de 1m2 sao pendencias cientificas.
    Nao alteramos qualquer GeoJSON de origem nem eliminamos patches.
    """
    totais, linhas = {}, []
    for dia, geometrias in sorted(grupos.items()):
        if not geometrias:
            raise ValueError(f"P1 {dia}: nenhuma geometria")
        if any(g.is_empty or not g.is_valid or g.area <= 0 for g in geometrias):
            raise ValueError(f"P1 {dia}: poligono invalido antes da uniao")
        try:
            uniao = unary_union(geometrias)
            area_soma = sum(g.area for g in geometrias)
            excesso = area_soma - uniao.area
        except shapely.GEOSException as exc:
            raise ValueError(
                f"P1 {dia}: falha na uniao de componentes: {exc}"
            ) from exc
        if uniao.is_empty or not uniao.is_valid or uniao.area <= 0:
            raise ValueError(f"P1 {dia}: uniao de componentes invalida")
        if excesso < -0.001:
            raise ValueError(
                f"P1 {dia}: area da uniao supera soma individual "
                f"em {-excesso:.6f} m2"
            )
        excesso = max(0.0, excesso)
        pares = []
        for i, g1 in enumerate(geometrias):
            for j in range(i + 1, len(geometrias)):
                g2 = geometrias[j]
                if not g1.intersects(g2):
                    continue
                area = g1.intersection(g2).area
                if area > 0.0001:
                    pares.append({
                        "indice_p1_a": i, "indice_p1_b": j,
                        "intersecao_m2": area,
                    })
        pares.sort(key=lambda x: -x["intersecao_m2"])
        totais[dia] = uniao
        linhas.append({
            "data": dia, "numero_componentes": len(geometrias),
            "soma_patches_m2": area_soma,
            "cobertura_uniao_m2": uniao.area,
            "excesso_sobreposicao_m2": excesso,
            "pares_com_intersecao_area": len(pares),
            "maior_intersecao_entre_pares_m2": (
                pares[0]["intersecao_m2"] if pares else 0.0
            ),
            "pares_exemplos": pares[:30],
            "revisao_cientifica_necessaria": excesso > 1.0,
        })
    revisao = [r for r in linhas if r["revisao_cientifica_necessaria"]]
    relatorio = {
        "criterio": "Area coberta = area da uniao; soma de patches "
                    "mantida para comparacao com etapas anteriores",
        "limite_alerta_sobreposicao_m2": 1.0,
        "datas": linhas,
        "datas_com_sobreposicao_acima_1m2": [r["data"] for r in revisao],
        "max_excesso_sobreposicao_m2": max(
            (r["excesso_sobreposicao_m2"] for r in linhas), default=0
        ),
        "interpretacao": "Sobreposicao P1 nao prova encontros de frentes "
                         "fisicas. Revisar conectividade das datas sinalizadas.",
        "validacao_geoespacial_externa": False,
    }
    return totais, relatorio


def conferir_balanco_componentes(
    cobertura_atual_km2: float, cobertura_anterior_km2: float,
    excesso_atual_km2: float, excesso_anterior_km2: float,
    reportado_km2: float, descricao: str,
) -> float:
    """Delta soma = delta cobertura + delta excesso por dupla contagem."""
    delta_cobertura = cobertura_atual_km2 - cobertura_anterior_km2
    delta_excesso = excesso_atual_km2 - excesso_anterior_km2
    conferir_proximo(
        delta_cobertura + delta_excesso, reportado_km2, descricao
    )
    return delta_cobertura


def ler_geometrias(p1: Path, p2: Path, incendio: int, *,
                   diagnostico: dict | None = None):
    """Reprojeta P1 e reconcilia P2 pelo mesmo critério TR/IGT.

    Reparos são condicionais e em memória; as entradas são preservadas.
    Quando fornecido, diagnostico recebe evidências de data/rank e tolerâncias.
    """
    patches = carregar_p1(p1)
    if {p.incendio for p in patches} != {incendio}:
        raise ValueError("P1 contem IDs inesperados")
    crs, reparos = projetar_patches(patches)
    reparados_p1 = [
        {"data": p.data, "rank": p.rank,
         "area_projetada_m2": p.area_m2}
        for p in patches if p.reparado_apos_projecao
    ]
    if len(reparados_p1) != reparos:
        raise ValueError("Inconsistencia na contagem de reparos P1 em LAEA")
    grupos = defaultdict(list)
    chaves = {}
    indice = {}
    for p in patches:
        grupos[p.data].append(p.geometria)
        if (p.data,p.rank) in chaves:
            raise ValueError("P1 tem rank/data duplicado")
        chaves[(p.data,p.rank)] = p.geometria
        indice[(p.data,p.rank)] = p
    proj = pyproj.Transformer.from_crs(
        "EPSG:4326", pyproj.CRS.from_proj4(crs["definicao_laea_proj4"]),
        always_xy=True,
    )
    with p2.open(encoding="utf-8") as arq:
        produto = json.load(arq)
    selecionados = {}
    auditorias_p2 = []
    for numero_registro, feat in enumerate(produto.get("features", [])):
        try:
            prop = feat["properties"]
            dia, rank = prop["data"], int(prop["rank_global"])
            id_lido = int(prop["id_incendio"])
            original = shape(feat["geometry"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"P2 registro {numero_registro} invalido: {exc}"
            ) from exc
        if id_lido != incendio or prop["id_incendio"] != id_lido or prop["rank_global"] != rank:
            raise ValueError(f"P2 registro {numero_registro}: ID/rank incoerente")
        if dia in selecionados or (dia,rank) not in chaves:
            raise ValueError(
                f"P2 registro {numero_registro} ({dia}, rank {rank}): "
                "rank ou data duplicado/inexistente no P1"
            )
        if original.geom_type not in ("Polygon", "MultiPolygon") or original.is_empty:
            raise ValueError(
                f"P2 registro {numero_registro}: geometria nao poligonal"
            )
        _geom, evidencia = reconciliar_p2(
            original, indice[(dia, rank)], proj, registro=numero_registro,
            data=dia, rank=rank,
        )
        auditorias_p2.append(evidencia)
        selecionados[dia] = chaves[(dia,rank)]
    if diagnostico is not None:
        diagnostico.update({
            "crs_laea": crs["definicao_laea_proj4"],
            "geometrias_p1_reparadas_apos_projecao": reparos,
            "reparos_p1": reparados_p1,
            "numero_reparos_p2_para_comparacao": sum(
                a["reparo_p2_necessario"] for a in auditorias_p2
            ),
            "reparos_p2": [
                a for a in auditorias_p2 if a["reparo_p2_necessario"]
            ],
            "maior_diferenca_simetrica_p1_p2_m2": max(
                (a["diferenca_simetrica_m2"] for a in auditorias_p2), default=0,
            ),
            "politica": "reconciliar P2 com P1 LAEA, make_valid condicionado "
                       "a max(1 m2, 1e-8 x area P1)",
        })
    if set(selecionados) != set(grupos):
        raise ValueError("Datas distintas entre P1 e P2")
    totais, relatorio_cobertura = calcular_cobertura_componentes(grupos)
    if diagnostico is not None:
        diagnostico["cobertura_p1"] = relatorio_cobertura
    return totais, selecionados, grupos, crs



def conferir_auditoria_previa(
    raiz: Path, incendio: int, p1: Path, p2: Path, diagnostico: dict,
) -> None:
    """Confere proveniência e reparos de P1/P2 nas Etapas 1 e 4.

    Os relatórios de TR, IGT e consolidação são evidências de processamento,
    não de validade científica independente. Nunca basta sua existência:
    SHA, contagens e datas/ranks dos reparos têm de coincidir.
    """
    e4 = raiz / "resultados" / "etapa4"
    caminhos = {
        "tr": e4 / f"resumo_regiao_movel_{incendio}.json",
        "igt": e4 / f"resumo_incrementos_{incendio}.json",
        "consolidado": e4 / f"resumo_consolidado_tr_igt_{incendio}.json",
    }
    reparos = (
        diagnostico["geometrias_p1_reparadas_apos_projecao"] > 0
        or diagnostico["numero_reparos_p2_para_comparacao"] > 0
    )
    if not reparos:
        diagnostico["auditoria_etapa4_conferida"] = "sem_reparos"
        return
    hashes = {
        "p1": sha256(p1.read_bytes()).hexdigest(),
        "p2": sha256(p2.read_bytes()).hexdigest(),
    }
    esperados_p2 = {
        (item["data"], int(item["rank"]))
        for item in diagnostico["reparos_p2"]
    }
    for origem, caminho in caminhos.items():
        if not caminho.is_file():
            raise ValueError(
                f"Etapa 5 exige auditoria previa dos reparos: "
                f"relatorio da Etapa 4 ausente ({caminho}). "
                "Nao use --refazer nem edite P1/P2."
            )
        with caminho.open(encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        for produto, atual in hashes.items():
            chave = (
                f"hash_sha256_{produto}" if origem == "consolidado"
                else f"sha256_{produto}"
            )
            if dados.get(chave) != atual:
                raise ValueError(
                    f"Auditoria Etapa 4 ({origem}): hash de {produto} "
                    "diverge da entrada; reparos nao podem ser reutilizados."
                )
        auditado = (
            dados.get("auditoria_geometrica_consolidacao", {})
            if origem == "consolidado" else dados
        )
        chave_p1 = (
            "geometrias_reparadas_apos_projecao" if origem == "tr"
            else "geometrias_p1_reparadas_apos_projecao"
        )
        if auditado.get(chave_p1) != diagnostico[
            "geometrias_p1_reparadas_apos_projecao"
        ]:
            raise ValueError(f"Auditoria Etapa 4 ({origem}): reparos P1 divergentes")
        if auditado.get("numero_reparos_p2_para_comparacao") != diagnostico[
            "numero_reparos_p2_para_comparacao"
        ]:
            raise ValueError(f"Auditoria Etapa 4 ({origem}): reparos P2 divergentes")
        encontrados_p2 = {
            (item["data"], int(item["rank"]))
            for item in (
                auditado.get("reparos_p2_para_comparacao", [])
            )
        }
        if encontrados_p2 != esperados_p2:
            raise ValueError(
                f"Auditoria Etapa 4 ({origem}): datas/ranks dos reparos "
                "P2 nao conferem"
            )
    diagnostico["auditoria_etapa4_conferida"] = "hashes_contagens_e_ranks"
    diagnostico["relatorios_conferidos"] = [
        str(caminho) for caminho in caminhos.values()
    ]


def decompor_transicao(total0, total1, p20, p21):
    """Identidade geometrica: P2 acrescido = area antes queimada + area nova."""
    incremento_p2 = p21.difference(p20)
    velha_incorporada = incremento_p2.intersection(total0)
    nova_p2 = incremento_p2.difference(total0)
    nova_total = total1.difference(total0)
    perda_total = total0.difference(total1)
    nova_fora_p2 = nova_total.difference(p21)
    erro_p2 = abs(incremento_p2.area-velha_incorporada.area-nova_p2.area)
    erro_total = abs(nova_total.area-nova_p2.area-nova_fora_p2.area)
    # P2 pode mudar identidade: area nova em P2 deve continuar contida em area nova do evento.
    if nova_p2.difference(nova_total).area > 1:
        raise ValueError("Nova area P2 nao contida na nova area do evento")
    if max(erro_p2,erro_total) > 1:
        raise ValueError("Decomposicao geometrica nao fecha (tolerancia de 1 m2)")
    return {
        "area_nova_evento_km2":nova_total.area/1e6,
        "area_perdida_evento_km2":perda_total.area/1e6,
        "p2_incremento_geometrico_km2":incremento_p2.area/1e6,
        "p2_incremento_ja_queimado_km2":velha_incorporada.area/1e6,
        "p2_incremento_nova_area_evento_km2":nova_p2.area/1e6,
        "nova_area_fora_p2_km2":nova_fora_p2.area/1e6,
        "desvio_fechamento_p2_m2":erro_p2,
        "desvio_fechamento_evento_m2":erro_total,
    }


def ajuste_linear(xs, ys):
    n=len(xs)
    if n < 2: raise ValueError("Segmento com menos de duas datas")
    mx=sum(xs)/n;my=sum(ys)/n
    soma=sum((x-mx)**2 for x in xs)
    m=(sum((x-mx)*(y-my) for x,y in zip(xs,ys))/soma) if soma else 0
    b=my-m*mx
    sse=sum((y-(m*x+b))**2 for x,y in zip(xs,ys))
    return m,b,sse


def segmentar_fases(linhas, *, min_obs=7, max_fases=3):
    """Regressao linear por partes escolhida por BIC, sem interpretacao causal.

    Segmentos independentes; max 3; data de quebra observada, nunca interpolada.
    """
    n=len(linhas)
    xs=[(date.fromisoformat(r["data"])-date.fromisoformat(linhas[0]["data"])).days
        for r in linhas]
    ys=[r["area_total_laea_km2"] for r in linhas]
    candidatas=[]
    if n >= 2:
        candidatas.append(([0,n],ajuste_linear(xs,ys)[2]))
    if n >= 2*min_obs:
        for i in range(min_obs,n-min_obs+1):
            candidatas.append(([0,i,n],ajuste_linear(xs[:i],ys[:i])[2]+
                               ajuste_linear(xs[i:],ys[i:])[2]))
    if n >= 3*min_obs and max_fases >= 3:
        for i in range(min_obs,n-2*min_obs+1):
            for j in range(i+min_obs,n-min_obs+1):
                candidatas.append(([0,i,j,n],sum(
                    ajuste_linear(xs[a:b],ys[a:b])[2]
                    for a,b in ((0,i),(i,j),(j,n)))))
    def bic(br,sse):
        m=len(br)-1
        # 2 parametros por segmento + (m-1) quebras escolhidas.
        return n*log(max(sse/n,1e-12))+(3*m-1)*log(n)
    br,sse=min(candidatas,key=lambda a:(bic(*a),len(a[0])))
    segmentos=[]
    for i,(a,b) in enumerate(zip(br,br[1:]),start=1):
        slope,_,_=ajuste_linear(xs[a:b],ys[a:b])
        segmentos.append({
            "fase_descritiva":f"F{i}",
            "data_inicio":linhas[a]["data"], "data_fim":linhas[b-1]["data"],
            "observacoes":b-a, "taxa_tendencia_laea_km2_dia":slope,
            "incremento_area_laea_km2":ys[b-1]-ys[a],
            "numero_convergencias_nas_transicoes":0,
            "modelo_segmentos":len(br)-1, "criterio_bic":bic(br,sse),
            "nota":"Segmentacao exploratoria da curva acumulada; sem inferir causalidade."
        })
    return segmentos, br


def marcar_fases(diarias, fases, limites):
    for i,(a,b) in enumerate(zip(limites,limites[1:])):
        for r in diarias[a:b]:
            r["fase_descritiva"]=f"F{i+1}"


def _figura_linhas(caminho, datas, series, ylabel, titulo):
    fig,ax=plt.subplots(figsize=(11,4.6))
    for nome,valores in series:
        ax.plot(datas,valores,label=nome,linewidth=1.8)
    ax.set(title=titulo,ylabel=ylabel,xlabel="Data da observacao")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.grid(alpha=.25);ax.legend(loc="best")
    fig.autofmt_xdate();fig.tight_layout()
    fig.savefig(caminho,dpi=155);plt.close(fig)


def _figura_barras(caminho,datas, valores, ylabel,titulo):
    fig,ax=plt.subplots(figsize=(11,4.6))
    ax.bar(datas,valores,width=.85)
    ax.set(title=titulo,ylabel=ylabel,xlabel="Data da observacao")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.grid(axis="y",alpha=.25)
    fig.autofmt_xdate();fig.tight_layout()
    fig.savefig(caminho,dpi=155);plt.close(fig)


def figuras_temporais(diarias,transicoes,saida):
    datas=[date.fromisoformat(r["data"]) for r in diarias]
    _figura_linhas(saida/"01_areas_p1_p2.png",datas,[
        ("Area total do evento - P1",[r["area_total_laea_km2"] for r in diarias]),
        ("Area do patch rastreado - P2",[r["p2_area_laea_km2"] for r in diarias]),
    ],"Area LAEA (km2)","Areas queimadas acumuladas: evento e componente principal")
    # Duas escalas independentes: contagem nao e percentagem.
    fig,ax=plt.subplots(figsize=(11,4.6))
    eixo_pct=ax.twinx()
    ax.plot(datas,[r["numero_patches"] for r in diarias],
            label="Numero de patches P1",linewidth=1.8)
    eixo_pct.plot(datas,[r["dominancia_maior_patch_pct"] for r in diarias],
                  label="Dominancia maior patch (%)",linestyle="--",linewidth=1.8)
    ax.set(title="Estrutura da paisagem: patches e dominancia",
           ylabel="Numero de patches",xlabel="Data da observacao")
    eixo_pct.set(ylabel="Dominancia do maior patch (%)",ylim=(0,100))
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(alpha=.25)
    fig.legend(loc="upper center",ncol=2,bbox_to_anchor=(.5,.99))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(saida/"02_fragmentacao_dominancia.png",dpi=155)
    plt.close(fig)
    tds=[date.fromisoformat(r["data_atual"]) for r in transicoes]
    _figura_barras(saida/"03_nova_area_evento.png",tds,
        [r["area_nova_evento_km2"]/r["dias_intervalo"] for r in transicoes],
        "Area nova (km2/dia, media do intervalo)","Taxa media observada de area nova do evento")
    _figura_linhas(saida/"04_decomposicao_p2.png",tds,[
        ("Area nova no evento incluida no P2",[r["p2_incremento_nova_area_evento_km2"] for r in transicoes]),
        ("Area anteriormente queimada incorporada ao P2",[r["p2_incremento_ja_queimado_km2"] for r in transicoes]),
    ],"Area por transicao (km2)","Decomposicao do incremento geometrico do patch principal")
    _figura_barras(saida/"05_convergencias.png",tds,
                   [r["eventos_convergencia"] for r in transicoes],
                   "Eventos geometricos por transicao","Convergencias de patches por intersecao de area")


def _poligonos(geom):
    if geom.geom_type == "Polygon":return [geom]
    if geom.geom_type == "MultiPolygon":return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        return [p for g in geom.geoms for p in _poligonos(g)]
    return []


def mapa_dia(dia, grupo, selecionado, saida):
    fig,ax=plt.subplots(figsize=(8,7))
    for geom in grupo:
        for p in _poligonos(geom):
            xs,ys=p.exterior.xy
            ax.fill([v/1000 for v in xs],[v/1000 for v in ys],alpha=.25)
            for ring in p.interiors:
                rx,ry=ring.xy
                ax.fill([v/1000 for v in rx],[v/1000 for v in ry],
                        facecolor="white")
    for p in _poligonos(selecionado):
        xs,ys=p.exterior.xy
        ax.plot([v/1000 for v in xs],[v/1000 for v in ys],linewidth=1)
    ax.set_aspect("equal",adjustable="box")
    ax.set(title=f"Evento: {dia} | preenchimento=P1; contorno=P2",
           xlabel="X LAEA local (km)",ylabel="Y LAEA local (km)")
    ax.grid(alpha=.18)
    fig.tight_layout();fig.savefig(saida,dpi=155);plt.close(fig)


def executar(raiz:Path,incendio:int,saida:Path):
    dados=raiz/"dados"/f"estudo_caso_{incendio}"
    p1=dados/f"P1_componentes_{incendio}.geojson"
    p2=dados/f"P2_regiao_movel_{incendio}.geojson"
    temporais=ler_tabela(raiz/"resultados/etapa2"/f"metricas_temporais_{incendio}.csv",
                         campos_chave=("data",))
    linhagens=ler_tabela(raiz/"resultados/etapa3"/f"resumo_transicoes_{incendio}.csv",
                         campos_chave=("data_anterior","data_atual"))
    igt=ler_tabela(raiz/"resultados/etapa4"/f"incrementos_temporais_{incendio}.csv",
                   campos_chave=("data_anterior","data_atual"))
    tr=ler_tabela(raiz/"resultados/etapa4"/f"indicadores_regiao_{incendio}.csv",
                  campos_chave=("data_anterior","data_atual"))
    auditoria_reparos = {}
    totais,selecionados,grupos,crs=ler_geometrias(
        p1,p2,incendio,diagnostico=auditoria_reparos)
    saida.mkdir(parents=True, exist_ok=True)
    caminho_auditoria = saida / f"auditoria_p1_sobreposicoes_{incendio}.json"
    def salvar_auditoria():
        caminho_auditoria.write_text(
            json.dumps(auditoria_reparos, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    # Persiste antes de validar os demais resultados para facilitar diagnósticos.
    salvar_auditoria()
    conferir_auditoria_previa(raiz,incendio,p1,p2,auditoria_reparos)
    salvar_auditoria()
    sobreposicoes_por_dia = {
        row["data"]: row
        for row in auditoria_reparos["cobertura_p1"]["datas"]
    }
    dias=sorted(totais)
    if set(temporais)!={(d,) for d in dias}:
        raise ValueError("Tabela temporal nao corresponde as datas de P1")
    pares=list(zip(dias,dias[1:]))
    if any(set(tab)!={tuple(par) for par in pares} for tab in (linhagens,igt,tr)):
        raise ValueError("CSV das transicoes nao corresponde as datas de P1")
    diarias=[]
    for d in dias:
        r=temporais[(d,)]
        if int(r["id_incendio"])!=incendio:
            raise ValueError("Outro ID na tabela temporal")
        total_km2=totais[d].area/1e6
        p2_km2=selecionados[d].area/1e6
        soma_km2 = sobreposicoes_por_dia[d]["soma_patches_m2"]/1e6
        excesso_km2 = sobreposicoes_por_dia[d]["excesso_sobreposicao_m2"]/1e6
        conferir_proximo(soma_km2,valor(r,"area_total_laea_km2"),
                         f"soma patches P1 (Etapa 2) {d}")
        if p2_km2>total_km2+1e-6:raise ValueError("P2 excede area P1")
        if int(r["numero_patches"])!=len(grupos[d]):
            raise ValueError(f"Contagem P1 nao confere em {d}")
        diarias.append({
            "id_incendio":incendio, "data":d,"fase_descritiva":None,
            "dias_desde_inicio":(date.fromisoformat(d)-date.fromisoformat(dias[0])).days,
            "area_total_laea_km2":total_km2,
            "area_soma_patches_laea_km2":soma_km2,
            "excesso_sobreposicao_p1_km2":excesso_km2,
            "dominancia_cobertura_p2_pct":100*p2_km2/total_km2,
            "area_principal_laea_km2":valor(r,"area_maior_patch_laea_km2"),
            "area_secundaria_laea_km2":valor(r,"area_patches_secundarios_laea_km2"),
            "dominancia_maior_patch_pct":valor(r,"dominancia_maior_patch_pct"),
            "numero_patches":len(grupos[d]),
            "indice_forma_medio_ponderado_area":valor(r,"indice_forma_medio_ponderado_area"),
            "delta_area_total_km2":valor(r,"area_nova_intervalo_laea_km2"),
            "delta_area_cobertura_km2": (
                total_km2 - diarias[-1]["area_total_laea_km2"]
                if diarias else None
            ),
            "delta_excesso_sobreposicao_p1_km2": (
                excesso_km2 - diarias[-1]["excesso_sobreposicao_p1_km2"]
                if diarias else None
            ),
            "taxa_media_intervalo_km2_dia":valor(r,"taxa_media_intervalo_km2_dia"),
            "eventos_convergencia_intervalo":0,"p2_area_laea_km2":p2_km2,
        })
    transicoes=[]
    for d0,d1 in pares:
        key=(d0,d1)
        lt,li,lr=linhagens[key],igt[key],tr[key]
        if any(int(r["id_incendio"])!=incendio for r in (lt,li,lr)):
            raise ValueError(f"ID inconsistente em {key}")
        intervalo=(date.fromisoformat(d1)-date.fromisoformat(d0)).days
        if any(int(r["dias_intervalo"])!=intervalo for r in (lt,li,lr)):
            raise ValueError(f"Intervalo inconsistente em {key}")
        decomp=decompor_transicao(totais[d0],totais[d1],selecionados[d0],selecionados[d1])
        delta_cobertura = (
            decomp["area_nova_evento_km2"]-decomp["area_perdida_evento_km2"]
        )
        excesso0 = sobreposicoes_por_dia[d0]["excesso_sobreposicao_m2"]/1e6
        excesso1 = sobreposicoes_por_dia[d1]["excesso_sobreposicao_m2"]/1e6
        conferir_balanco_componentes(
            totais[d1].area/1e6, totais[d0].area/1e6, excesso1, excesso0,
            valor(temporais[(d1,)],"area_nova_intervalo_laea_km2"),
            f"delta soma patches P1 (Etapa 2) {key}",
        )
        conferir_balanco_componentes(
            totais[d1].area/1e6, totais[d0].area/1e6, excesso1, excesso0,
            valor(lt,"crescimento_liquido_km2"),
            f"delta soma patches P1 (Etapa 3) {key}",
        )
        conferir_proximo(
            delta_cobertura, totais[d1].area/1e6-totais[d0].area/1e6,
            f"delta cobertura geometrica {key}",
        )
        conferir_proximo(decomp["p2_incremento_geometrico_km2"],
                         valor(li,"area_nova_km2"),f"IGT {key}")
        conferir_proximo(decomp["p2_incremento_geometrico_km2"],
                         valor(lr,"area_nova_p2_km2"),f"TR {key}")
        conferir_proximo(decomp["area_total_anterior_km2"] if
                         "area_total_anterior_km2" in decomp else totais[d0].area/1e6,
                         valor(lt,"area_acumulada_anterior_km2"),f"area Etapa3 {key}")
        incremento=decomp["p2_incremento_geometrico_km2"]
        row={
            "id_incendio":incendio,"data_anterior":d0,"data_atual":d1,
            "dias_intervalo":intervalo,
            "area_total_anterior_km2":totais[d0].area/1e6,
            "area_total_atual_km2":totais[d1].area/1e6,
            "excesso_sobreposicao_anterior_km2":excesso0,
            "excesso_sobreposicao_atual_km2":excesso1,
            "delta_excesso_sobreposicao_km2":excesso1-excesso0,
            **decomp,
            "taxa_nova_evento_km2_dia":decomp["area_nova_evento_km2"]/intervalo,
            "p2_area_anterior_km2":selecionados[d0].area/1e6,
            "p2_area_atual_km2":selecionados[d1].area/1e6,
            "fracao_incremento_p2_ja_queimado_pct":(
                100*decomp["p2_incremento_ja_queimado_km2"]/incremento
                if incremento>0 else None),
            "numero_patches_anterior":len(grupos[d0]),
            "numero_patches_atual":len(grupos[d1]),
            "eventos_convergencia":int(lt["eventos_convergencia"]),
            "eventos_surgimento_sem_sobreposicao":int(lt["eventos_surgimento_sem_sobreposicao"]),
            "tr_deslocamento_centroide_km":valor(lr,"deslocamento_centroide_km"),
            "tr_azimute_centroide_graus":valor(lr,"azimute_centroide_graus"),
            "igt_azimute_ponderado_graus":valor(li,"azimute_medio_ponderado_graus"),
            "igt_concentracao_direcional":valor(li,"concentracao_direcional"),
            "lacuna_temporal":intervalo>1,
            "alerta_escala_sensor":decomp["area_nova_evento_km2"]<.25,
        }
        transicoes.append(row)
        diarias[dias.index(d1)]["eventos_convergencia_intervalo"]=int(lt["eventos_convergencia"])

    fases,limites=segmentar_fases(diarias)
    marcar_fases(diarias,fases,limites)
    for fase in fases:
        fase["numero_convergencias_nas_transicoes"]=sum(
            r["eventos_convergencia"] for r in transicoes
            if fase["data_inicio"]<=r["data_atual"]<=fase["data_fim"])
    mudancas=sorted(transicoes,key=lambda r:r["taxa_nova_evento_km2_dia"],reverse=True)
    incorporacoes=sorted(transicoes,key=lambda r:r["p2_incremento_ja_queimado_km2"],reverse=True)
    maior_convergencia=max(transicoes,key=lambda r:r["eventos_convergencia"])
    nota=next((r for r in transicoes if r["data_atual"]=="2020-09-11"),None)
    resumo={
        "id_incendio":incendio,"observacoes":len(dias),"transicoes":len(transicoes),
        "periodo_inicio":dias[0],"periodo_fim":dias[-1],
        "area_total_inicial_laea_km2":diarias[0]["area_total_laea_km2"],
        "area_total_final_laea_km2":diarias[-1]["area_total_laea_km2"],
        "area_p2_final_laea_km2":diarias[-1]["p2_area_laea_km2"],
        "dominancia_p2_final_pct":100*diarias[-1]["p2_area_laea_km2"]/diarias[-1]["area_total_laea_km2"],
        "total_convergencias_geometricas":sum(r["eventos_convergencia"] for r in transicoes),
        "soma_area_nova_evento_observada_km2":sum(r["area_nova_evento_km2"] for r in transicoes),
        "soma_nova_area_dentro_p2_km2":sum(r["p2_incremento_nova_area_evento_km2"] for r in transicoes),
        "soma_incorporacao_area_ja_queimada_no_p2_km2":sum(r["p2_incremento_ja_queimado_km2"] for r in transicoes),
        "picos_crescimento":mudancas[:8],
        "picos_incorporacao":incorporacoes[:8],
        "pico_convergencia":maior_convergencia,
        "transicao_2020_09_11":nota,
        "fases_exploratorias":fases,
        "numero_fases_bic":len(fases),
        "transicoes_com_lacunas":sum(r["lacuna_temporal"] for r in transicoes),
        "datas_lacunas":[r["data_atual"] for r in transicoes if r["lacuna_temporal"]],
        "maximo_erro_fechamento_m2":max(max(r["desvio_fechamento_evento_m2"],
                                            r["desvio_fechamento_p2_m2"]) for r in transicoes),
        "crs":crs,
        "auditoria_reparos_geometricos":auditoria_reparos,
        "dias_p1_sobreposicao_pendente": auditoria_reparos[
            "cobertura_p1"]["datas_com_sobreposicao_acima_1m2"
        ],
        "status_topologia_p1": (
            "revisao_cientifica_pendente"
            if auditoria_reparos["cobertura_p1"]["datas_com_sobreposicao_acima_1m2"]
            else "sem_sobreposicoes_significativas"
        ),
        "validacao_independente":False,
        "sha256_p1":sha256(p1.read_bytes()).hexdigest(),
        "sha256_p2":sha256(p2.read_bytes()).hexdigest(),
        "premissas":[
          "Dados de area queimada acumulada; nao representam frente de fogo nem velocidade fisica",
          "Incorporacao pre-queimada: (P2_atual\\P2_anterior) intersecao P1_total_anterior",
          "Area realmente nova no evento: P1_total_atual\\P1_total_anterior",
          "Fases estimadas por segmentos lineares BIC sao exploratorias, nao periodos causais",
          "Convergencias sao definidas pelo grafo de intersecoes de area, nao fusoes fisicas comprovadas",
          "Comparacao TR/IGT combina descritores geometricos complementares",
          "Todos os calculos de area utilizam LAEA local do estudo de caso"
        ],
    }
    saida.mkdir(parents=True,exist_ok=True)
    salvar_csv(saida/f"serie_diaria_integrada_{incendio}.csv",CAMPOS_DIARIOS,diarias)
    salvar_csv(saida/f"transicoes_integradas_{incendio}.csv",CAMPOS_TRANSICOES,transicoes)
    salvar_csv(saida/f"fases_descritivas_{incendio}.csv",CAMPOS_FASE,fases)
    (saida/f"resumo_etapa5_{incendio}.json").write_text(
        json.dumps(resumo,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")
    figuras_temporais(diarias,transicoes,saida)
    datas_mapa=list(dict.fromkeys([dias[0],"2020-09-10","2020-09-11",dias[-1]]))
    for d in datas_mapa:
        if d in grupos:
            mapa_dia(d,grupos[d],selecionados[d],saida/f"mapa_{d}.png")
    # Relatorio gerado dos dados, sem atribuicao causal automatica
    texto_relatorio(resumo,saida/f"relatorio_interpretativo_{incendio}.md")
    return resumo


def texto_relatorio(r,caminho):
    topo=r["picos_crescimento"][0]
    inc=r["picos_incorporacao"][0]
    fases="\n".join(
        f'| {f["fase_descritiva"]} | {f["data_inicio"]} a {f["data_fim"]} | '
        f'{f["taxa_tendencia_laea_km2_dia"]:.2f} km²/dia | {f["numero_convergencias_nas_transicoes"]} |'
        for f in r["fases_exploratorias"])
    d=r["transicao_2020_09_11"]
    caso=(f'- Área nova no evento: {d["area_nova_evento_km2"]:.3f} km².\n'
          f'- P2, aumento geométrico: {d["p2_incremento_geometrico_km2"]:.3f} km².\n'
          f'- Desse aumento, já queimada no evento anterior: {d["p2_incremento_ja_queimado_km2"]:.3f} km².\n'
          f'- Nova área realmente detectada dentro do P2: {d["p2_incremento_nova_area_evento_km2"]:.3f} km².\n'
          f'- Convergências da Etapa 3 nessa transição: {d["eventos_convergencia"]}.\n'
          if d else "Transição não presente no evento.\n")
    texto=f"""# Etapa 5 — Síntese integrada de áreas queimadas (ID {r["id_incendio"]})

**Gerado automaticamente dos P1/P2 e das saídas versionadas das Etapas 2–4.**
As observações são acumuladas e não representam frente ativa de fogo.

## Indicadores do estudo de caso

- Período: {r["periodo_inicio"]} a {r["periodo_fim"]}; {r["observacoes"]} observações e {r["transicoes"]} transições.
- Área final P1 em LAEA (união espacial, sem dupla contagem): {r["area_total_final_laea_km2"]:.3f} km².
- Diagnóstico de P1: {len(r["dias_p1_sobreposicao_pendente"])} datas com sobreposição acima de 1 m² entre patches. Consultar a auditoria espacial da Etapa 5.
- Área final P2 em LAEA: {r["area_p2_final_laea_km2"]:.3f} km²; participação {r["dominancia_p2_final_pct"]:.2f}%.
- Convergências geométricas ao longo das transições: {r["total_convergencias_geometricas"]}.
- Maior taxa média de área nova entre observações: {topo["taxa_nova_evento_km2_dia"]:.3f} km²/dia no intervalo encerrado em {topo["data_atual"]}.
- Maior incorporação de área anteriormente queimada ao P2: {inc["p2_incremento_ja_queimado_km2"]:.3f} km² no intervalo encerrado em {inc["data_atual"]}.
- Lacunas temporais maiores que um dia: {r["transicoes_com_lacunas"]}.

## Exemplo de 10 a 11/09/2020

{caso}
Este contraste é explicável pela incorporação ao P2 de áreas que já existiam em outros patches do evento.
Não é correto igualar todo o crescimento geométrico de P2 à nova área queimada.

## Fases matematicamente descritivas (exploratórias)

Foram ajustadas até três regressões lineares independentes da curva de área total P1
contra o número de dias desde a primeira observação. Os pontos de quebra foram
procurados exaustivamente, exigindo ao menos sete observações por segmento.
Escolha do número de segmentos por BIC: n ln(SSE/n) + (3m-1) ln(n), onde m
é o número de segmentos. **Não equivale a afirmar fases físicas ou causas.**

| Fase | Observações no período | Inclinação da área acumulada | Convergências |
|---|---|---:|---:|
{fases}

## Leitura conjunta da paisagem e das regiões móveis

- O P1 descreve a área acumulada do evento e seus componentes por data.
- O grafo temporal registra relações por sobreposição de área; não comprova
  que os focos físicos de incêndio se fundiram na mesma data.
- O P2 acompanha um componente de área queimada; pode ganhar área
  anteriormente queimada quando incorpora outros componentes.
- TR descreve trajetórias de pontos representativos e IGT identifica porções
  acrescentadas e suas direções. Discordância entre azimutes não demonstra erro.
- Direções de incremento com baixa concentração devem ser interpretadas com cautela.
- Frações subpixel, contatos de vértice e intervalos maiores que um dia não
  devem ser confundidos com movimentos físicos precisos do fogo.

## Produtos

- serie_diaria_integrada: valores e fases por data.
- transicoes_integradas: decomposição geométrica do crescimento e indicadores combinados.
- fases_descritivas: quebra e inclinação das fases exploratórias.
- Figuras 01–05: evolução de áreas, estrutura espacial, crescimento, incorporação e convergências.
- Mapas de datas-chave: contorno P2 e todos os patches P1, sem base externa.

## Limitações

A geometria é derivada do GlobFire/MODIS e registra **área queimada acumulada**.
As taxas são médias entre observações, não velocidades da frente do incêndio.
O período inclui lacunas temporais. As interpretações precisam de confronto com
imagens da fonte, hidrografia/relevo e orientação científica antes de serem
atribuídas a processos físicos específicos. A classificação automática de
fases é exploratória, sensível à janela e ao modelo ajustado.

## Execução e proveniência

Script: burngeoflow.analises.integracao. CLI parametrizada por ID, exige P1/P2,
Etapa 2, Etapa 3 e Etapa 4 já processados para o evento.
Resultados não são calculados a partir dos CSVs históricos do Beryl.
As verificações usam equivalência geométrica P1/P2 e conservação de área,
sem modificar GeoJSON originais.
"""
    caminho.write_text(texto,encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id",type=int,required=True,help="ID do evento GlobFire")
    parser.add_argument("--raiz",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--saida",type=Path,default=None)
    args=parser.parse_args()
    pasta=args.saida or (args.raiz/"resultados"/"etapa5")
    resultado=executar(args.raiz,args.id,pasta)
    print(json.dumps({
        "id":resultado["id_incendio"],
        "observacoes":resultado["observacoes"],
        "transicoes":resultado["transicoes"],
        "area_final_p1_km2":resultado["area_total_final_laea_km2"],
        "soma_incorporada_previamente_km2":resultado["soma_incorporacao_area_ja_queimada_no_p2_km2"],
        "fases":[x["fase_descritiva"] for x in resultado["fases_exploratorias"]],
        "saida":str(pasta)
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
