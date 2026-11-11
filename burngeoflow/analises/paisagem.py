#!/usr/bin/env python3
"""Etapa 2: metricas vetoriais reprodutiveis para todos os patches do P1.

Nao modifica geometrias nem redefine patches. Reprojeta primeiro para uma
LAEA local, valida no plano projetado e so usa make_valid condicionalmente.
As linhas P1 sao *componentes por data*, nunca identidades persistentes.

Dependencias: shapely>=2, pyproj>=3.6 (requirements-auditoria.txt).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from math import isclose, isfinite, pi, sqrt
from pathlib import Path
from statistics import median
import sys

import pyproj
import shapely
from shapely import make_valid
from shapely.geometry import shape


@dataclass
class Patch:
    data: str
    incendio: int
    rank: int
    area_gee_km2: float
    geometria: object
    area_m2: float = 0.0
    perimetro_m: float = 0.0
    reparado_apos_projecao: bool = False


CAMPOS_PATCH = [
    "id_incendio", "data", "rank", "area_gee_km2", "area_laea_km2",
    "perimetro_laea_km", "indice_forma_vetorial",
    "distancia_vizinho_mais_proximo_km", "participacao_area_queimada_pct",
]

CAMPOS_TEMPORAIS = [
    "id_incendio", "data", "dias_desde_observacao_anterior", "numero_patches",
    "area_total_gee_km2", "area_total_laea_km2",
    "area_nova_intervalo_laea_km2", "taxa_media_intervalo_km2_dia",
    "area_maior_patch_laea_km2", "area_patches_secundarios_laea_km2",
    "dominancia_maior_patch_pct", "perimetro_somado_patches_km",
    "indice_forma_medio_ponderado_area",
]

CAMPOS_SENSIBILIDADE = [
    "id_incendio", "data", "numero_patches_original",
    "numero_grupos_por_contato_vetorial", "reducoes_na_contagem",
    "pares_contato_pontual", "pares_contato_borda",
    "dominancia_original_pct", "dominancia_apos_agrupar_contatos_pct",
]


def numero_positivo(valor: object, contexto: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{contexto}: numero obrigatorio, recebido {valor!r}")
    resultado = float(valor)
    if not isfinite(resultado) or resultado <= 0:
        raise ValueError(f"{contexto}: deve ser finito e maior que zero")
    return resultado


def inteiro_positivo(valor: object, contexto: str) -> int:
    numero = numero_positivo(valor, contexto)
    if not numero.is_integer():
        raise ValueError(f"{contexto}: numero inteiro obrigatorio")
    return int(numero)


def carregar_p1(caminho: Path) -> list[Patch]:
    with caminho.open(encoding="utf-8") as arquivo:
        produto = json.load(arquivo)
    if produto.get("type") != "FeatureCollection" or not produto.get("features"):
        raise ValueError("P1 deve ser FeatureCollection com feicoes")
    patches = []
    ids = set()
    por_data = defaultdict(list)
    for indice, feicao in enumerate(produto["features"]):
        propriedades = feicao.get("properties") or {}
        try:
            data = propriedades["data"]
            date.fromisoformat(data)
            incendio = inteiro_positivo(propriedades["id_incendio"], "ID")
            rank = inteiro_positivo(propriedades["rank"], "rank")
            area_gee = numero_positivo(propriedades["area_km2"], "area_km2")
            numero_componentes = inteiro_positivo(
                propriedades["numero_componentes"], "numero_componentes")
            area_total_gee = numero_positivo(
                propriedades["area_total_km2"], "area_total_km2")
            geom = shape(feicao["geometry"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"P1 feicao {indice} invalida: {exc}") from exc
        if geom.geom_type not in ("Polygon", "MultiPolygon") or geom.is_empty:
            raise ValueError(f"P1 feicao {indice}: geometria nao poligonal")
        p = Patch(data, incendio, rank, area_gee, geom)
        patches.append(p)
        ids.add(incendio)
        por_data[data].append((p, numero_componentes, area_total_gee))
    if len(ids) != 1:
        raise ValueError(f"P1 mistura eventos GlobFire: {sorted(ids)}")
    for dia, registros in por_data.items():
        n = len(registros)
        if sorted(p.rank for p, _, _ in registros) != list(range(1, n + 1)):
            raise ValueError(f"{dia}: ranks nao consecutivos ou repetidos")
        total_gee = sum(p.area_gee_km2 for p, _, _ in registros)
        for _, esperado_n, esperado_area in registros:
            if esperado_n != n or not isclose(
                esperado_area, total_gee, rel_tol=1e-8, abs_tol=1e-6
            ):
                raise ValueError(f"{dia}: metadados inconsistentes em P1")
    return patches


def indice_forma_vetorial(area_m2: float, perimetro_m: float) -> float:
    """Normalizacao circular vetorial, diferente do SHAPE raster/FRAGSTATS."""
    if area_m2 <= 0 or perimetro_m <= 0:
        raise ValueError("Area e perimetro precisam ser positivos")
    return perimetro_m / (2 * sqrt(pi * area_m2))


def projetar_patches(patches: list[Patch]) -> tuple[dict, int]:
    limites = [p.geometria.bounds for p in patches]
    oeste, sul = min(b[0] for b in limites), min(b[1] for b in limites)
    leste, norte = max(b[2] for b in limites), max(b[3] for b in limites)
    if leste - oeste > 180:
        raise ValueError("Evento cruza antimeridiano: revisar projecao LAEA")
    lon0, lat0 = (oeste + leste) / 2, (sul + norte) / 2
    definicao = (f"+proj=laea +lat_0={lat0:.10f} +lon_0={lon0:.10f} "
                 "+datum=WGS84 +units=m +no_defs")
    proj = pyproj.CRS.from_proj4(definicao)
    transformador = pyproj.Transformer.from_crs(
        "EPSG:4326", proj, always_xy=True
    )
    reparados = 0
    for p in patches:
        metrico = shapely.transform(
            p.geometria, transformador.transform, interleaved=False
        )
        if not metrico.is_valid:
            metrico = make_valid(metrico)
            p.reparado_apos_projecao = True
            reparados += 1
        if metrico.geom_type not in ("Polygon", "MultiPolygon") or not metrico.is_valid:
            raise ValueError(
                f"{p.data} rank {p.rank}: reparo produziu geometria "
                f"{metrico.geom_type}; exige revisao manual"
            )
        if metrico.area <= 0 or metrico.length <= 0:
            raise ValueError(f"{p.data} rank {p.rank}: geometria degenerada")
        p.geometria = metrico
        p.area_m2 = metrico.area
        p.perimetro_m = metrico.length
    return {
        "crs": "LAEA local / WGS84",
        "centro_lon": round(lon0, 8), "centro_lat": round(lat0, 8),
        "limites_lonlat": [oeste, sul, leste, norte],
        "definicao_laea_proj4": definicao,
    }, reparados


def examinar_contatos(patches: list[Patch]) -> dict:
    """Diagnostico vetorial: so ponto, borda comum ou sobreposicao real."""
    indice = shapely.STRtree([p.geometria for p in patches])
    resultado = {"contatos_pontuais": 0, "contatos_por_borda": 0,
                 "sobreposicoes_maiores_1m2": 0, "amostras": []}
    for i, p in enumerate(patches):
        for j in indice.query(p.geometria, predicate="intersects"):
            j = int(j)
            if j <= i:
                continue
            outro = patches[j]
            if p.geometria.touches(outro.geometria):
                tipo = ("contatos_por_borda" if
                        p.geometria.intersection(outro.geometria).length > 1e-6
                        else "contatos_pontuais")
                resultado[tipo] += 1
            elif p.geometria.intersection(outro.geometria).area > 1.0:
                tipo = "sobreposicoes_maiores_1m2"
                resultado[tipo] += 1
            else:
                continue
            if len(resultado["amostras"]) < 15:
                resultado["amostras"].append(
                    {"rank_a": p.rank, "rank_b": outro.rank, "tipo": tipo}
                )
    return resultado


def sensibilidade_contato_vetorial(patches: list[Patch]) -> dict:
    """Agrupamento exploratorio por *qualquer* toque, sem resegmentar raster.

    O resultado NAO representa uma reconstrucao exata de vizinhanca 8 em
    MCD64A1, pois opera nas fronteiras vetoriais ja processadas pelo GlobFire.
    """
    parent = list(range(len(patches)))

    def raiz(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def unir(i: int, j: int) -> None:
        a, b = raiz(i), raiz(j)
        if a != b:
            parent[b] = a

    arvore = shapely.STRtree([p.geometria for p in patches])
    for i, p in enumerate(patches):
        for j in arvore.query(p.geometria, predicate="intersects"):
            j = int(j)
            if j > i and p.geometria.touches(patches[j].geometria):
                unir(i, j)
    areas_por_grupo = defaultdict(float)
    for i, p in enumerate(patches):
        areas_por_grupo[raiz(i)] += p.area_m2
    total = sum(p.area_m2 for p in patches)
    return {
        "numero_grupos_por_contato_vetorial": len(areas_por_grupo),
        "dominancia_apos_agrupar_contatos_pct": (
            100 * max(areas_por_grupo.values()) / total
        ),
    }


def calcular_metricas(patches: list[Patch]) -> tuple[
    list[dict], list[dict], list[dict], dict
]:
    if any(p.area_m2 <= 0 for p in patches):
        raise ValueError("Projete e valide as geometrias antes do calculo")
    por_data = defaultdict(list)
    for p in patches:
        por_data[p.data].append(p)
    linhas_patch = []
    linhas_temporais = []
    linhas_sensibilidade = []
    contatos = {"contatos_pontuais": 0, "contatos_por_borda": 0,
                "sobreposicoes_maiores_1m2": 0, "amostras": []}
    divergencias_rank_modelo = []
    dia_anterior = None
    area_anterior = None
    for dia in sorted(por_data):
        grupo = sorted(por_data[dia], key=lambda p: p.rank)
        area_total = sum(p.area_m2 for p in grupo)
        area_total_gee = sum(p.area_gee_km2 for p in grupo)
        maior = max(grupo, key=lambda p: p.area_m2)
        # O rank do GEE e a ordem da area declarada; diferencas entre modelos
        # de area nao devem trocar a identidade do componente principal.
        if maior.rank != 1:
            divergencias_rank_modelo.append(
                {"data": dia, "maior_rank_laea": maior.rank}
            )
        formato_ponderado = 0.0
        perimetro_total = 0.0
        for p in grupo:
            forma = indice_forma_vetorial(p.area_m2, p.perimetro_m)
            formato_ponderado += forma * p.area_m2 / area_total
            perimetro_total += p.perimetro_m
            vizinhos = [q.geometria.distance(p.geometria) for q in grupo if q is not p]
            distancia = min(vizinhos) / 1000 if vizinhos else None
            linhas_patch.append({
                "id_incendio": p.incendio,
                "data": p.data,
                "rank": p.rank,
                "area_gee_km2": p.area_gee_km2,
                "area_laea_km2": p.area_m2 / 1e6,
                "perimetro_laea_km": p.perimetro_m / 1000,
                "indice_forma_vetorial": forma,
                "distancia_vizinho_mais_proximo_km": distancia,
                "participacao_area_queimada_pct": 100 * p.area_m2 / area_total,
            })
        dias = ((date.fromisoformat(dia) - date.fromisoformat(dia_anterior)).days
                if dia_anterior else None)
        if dias is not None and dias <= 0:
            raise ValueError("Datas precisam ser estritamente crescentes")
        # Primeira observacao e ponto inicial, nao representa crescimento zero.
        aumento = ((area_total - area_anterior) / 1e6
                   if area_anterior is not None else None)
        if aumento is not None and aumento < -1e-6:
            raise ValueError(f"{dia}: area acumulada diminuiu em LAEA")
        linhas_temporais.append({
            "id_incendio": grupo[0].incendio,
            "data": dia,
            "dias_desde_observacao_anterior": dias,
            "numero_patches": len(grupo),
            "area_total_gee_km2": area_total_gee,
            "area_total_laea_km2": area_total / 1e6,
            "area_nova_intervalo_laea_km2": aumento,
            "taxa_media_intervalo_km2_dia": aumento / dias if dias else None,
            "area_maior_patch_laea_km2": maior.area_m2 / 1e6,
            "area_patches_secundarios_laea_km2": (area_total - maior.area_m2) / 1e6,
            "dominancia_maior_patch_pct": 100 * maior.area_m2 / area_total,
            "perimetro_somado_patches_km": perimetro_total / 1000,
            "indice_forma_medio_ponderado_area": formato_ponderado,
        })
        diagnostico = examinar_contatos(grupo)
        alternativa = sensibilidade_contato_vetorial(grupo)
        linhas_sensibilidade.append({
            "id_incendio": grupo[0].incendio,
            "data": dia,
            "numero_patches_original": len(grupo),
            **alternativa,
            "reducoes_na_contagem": (
                len(grupo) - alternativa["numero_grupos_por_contato_vetorial"]
            ),
            "pares_contato_pontual": diagnostico["contatos_pontuais"],
            "pares_contato_borda": diagnostico["contatos_por_borda"],
            "dominancia_original_pct": 100 * maior.area_m2 / area_total,
        })
        for campo in ("contatos_pontuais", "contatos_por_borda",
                      "sobreposicoes_maiores_1m2"):
            contatos[campo] += diagnostico[campo]
        if len(contatos["amostras"]) < 15:
            contatos["amostras"].extend(
                {"data": dia, **a} for a in diagnostico["amostras"]
            )
            contatos["amostras"] = contatos["amostras"][:15]
        area_anterior, dia_anterior = area_total, dia
    taxas = [l for l in linhas_temporais
             if l["taxa_media_intervalo_km2_dia"] is not None]
    maior_taxa = max(taxas, key=lambda l: l["taxa_media_intervalo_km2_dia"]) if taxas else None
    variacoes_area = [100 * (l["area_total_laea_km2"] /
                             l["area_total_gee_km2"] - 1)
                       for l in linhas_temporais]
    distancias = [p["distancia_vizinho_mais_proximo_km"]
                  for p in linhas_patch
                  if p["distancia_vizinho_mais_proximo_km"] is not None]
    resumo = {
        "id_incendio": patches[0].incendio,
        "numero_registros_patch_data": len(linhas_patch),
        "numero_datas": len(linhas_temporais),
        "data_inicial": linhas_temporais[0]["data"],
        "data_final": linhas_temporais[-1]["data"],
        "area_final_laea_km2": linhas_temporais[-1]["area_total_laea_km2"],
        "area_final_gee_km2": linhas_temporais[-1]["area_total_gee_km2"],
        "mediana_desvio_area_laea_vs_gee_pct": median(variacoes_area),
        "maximo_patches_por_data": max(l["numero_patches"] for l in linhas_temporais),
        "datas_maior_rank_difere_entre_gee_e_laea": divergencias_rank_modelo,
        "porcentagem_enn_zero_por_contato": (
            100 * sum(d < 1e-9 for d in distancias) / len(distancias)
            if distancias else None
        ),
        "maior_taxa_media_intervalo": (
            {"data_final_intervalo": maior_taxa["data"],
             "km2_dia": maior_taxa["taxa_media_intervalo_km2_dia"],
             "dias_intervalo": maior_taxa["dias_desde_observacao_anterior"]}
            if maior_taxa else None
        ),
        "lacunas_maiores_1_dia": [
            {"data": l["data"], "dias": l["dias_desde_observacao_anterior"]}
            for l in linhas_temporais if (l["dias_desde_observacao_anterior"] or 0) > 1
        ],
        "contatos_entre_patches": contatos,
        "sensibilidade_contato_vetorial": {
            "soma_grupos_por_contato_patch_data": sum(
                l["numero_grupos_por_contato_vetorial"]
                for l in linhas_sensibilidade
            ),
            "datas_com_reducao_de_contagem": sum(
                l["reducoes_na_contagem"] > 0 for l in linhas_sensibilidade
            ),
            "maior_reducao_patches_em_uma_data": max(
                l["reducoes_na_contagem"] for l in linhas_sensibilidade
            ),
            "soma_reducoes_patch_data": sum(
                l["reducoes_na_contagem"] for l in linhas_sensibilidade
            ),
            "ultimo_dia": linhas_sensibilidade[-1],
            "limite": (
                "Simulacao topologica de agrupamento de feicoes por contato "
                "vetorial; NAO corresponde diretamente a vizinhanca raster "
                "8 e NAO substitui P1."
            ),
        },
        "observacao": (
            "Patches fixados pelo P1 vetorial: nenhum algoritmo de vizinhanca "
            "raster 4/8 aplicado. Areas/perimetros em LAEA, nao idênticos "
            "aos calculos originais do Google Earth Engine. Taxas medias "
            "entre observacoes; nao medem velocidade da frente ativa."
        ),
    }
    return linhas_patch, linhas_temporais, linhas_sensibilidade, resumo


def salvar_csv(caminho: Path, campos: list[str], registros: list[dict]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        for registro in registros:
            escritor.writerow({
                chave: ("" if registro[chave] is None else
                        f"{registro[chave]:.9f}" if isinstance(registro[chave], float)
                        else registro[chave])
                for chave in campos
            })


def executar(caminho_p1: Path, pasta_saida: Path) -> dict:
    patches = carregar_p1(caminho_p1)
    projecao, reparados = projetar_patches(patches)
    tabela_patch, tabela_temporal, tabela_sensibilidade, resumo = calcular_metricas(patches)
    resumo["projecao"] = projecao
    resumo["geometrias_reparadas_apos_projecao"] = reparados
    resumo["origem_p1"] = str(caminho_p1)
    resumo["sha256_p1"] = sha256(caminho_p1.read_bytes()).hexdigest()
    pasta_saida.mkdir(parents=True, exist_ok=True)
    id_incendio = resumo["id_incendio"]
    salvar_csv(pasta_saida / f"metricas_patches_{id_incendio}.csv",
               CAMPOS_PATCH, tabela_patch)
    salvar_csv(pasta_saida / f"metricas_temporais_{id_incendio}.csv",
               CAMPOS_TEMPORAIS, tabela_temporal)
    salvar_csv(pasta_saida / f"sensibilidade_contato_{id_incendio}.csv",
               CAMPOS_SENSIBILIDADE, tabela_sensibilidade)
    (pasta_saida / f"resumo_metricas_{id_incendio}.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    return resumo


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("p1", type=Path, help="GeoJSON P1 do evento")
    cli.add_argument("--saida", type=Path, required=True,
                     help="Diretorio dos resultados gerados")
    args = cli.parse_args()
    try:
        print(json.dumps(executar(args.p1, args.saida),
                         ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError, pyproj.ProjError) as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
