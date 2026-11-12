"""Síntese exploratória P1/P2, TR/IGT e auditoria, sem reprocessar geometrias.

Produz leitura científica baseada exclusivamente nos CSV/JSON das Etapas
5 e 6 já concluídas. Não substitui observação independente nem prova
causalidade ou propagação física de frentes de fogo.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        raise ValueError(f"Relatório ausente: {caminho}")
    dado = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dado, dict):
        raise ValueError(f"Esperava JSON objeto: {caminho}")
    return dado


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        raise ValueError(f"Tabela ausente: {caminho}")
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    if not linhas:
        raise ValueError(f"Tabela vazia: {caminho}")
    return linhas


def numero(linha: dict, campo: str, *, opcional=False) -> float | None:
    bruto = linha.get(campo)
    if bruto in ("", None):
        if opcional:
            return None
        raise ValueError(f"Campo obrigatório ausente: {campo}")
    try:
        n = float(bruto)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{campo}: número inválido {bruto!r}") from exc
    if not isfinite(n):
        raise ValueError(f"{campo}: número não finito")
    return n


def fmt(valor, casas=3):
    return "indeterminado" if valor is None else f"{valor:.{casas}f}"


def ranking(transicoes: list[dict], campo: str, limite=4) -> list[dict]:
    ordenado = sorted(transicoes, key=lambda r: (-numero(r, campo), r["data_atual"]))
    return [
        {
            "inicio": r["data_anterior"],
            "fim": r["data_atual"],
            "dias": int(r["dias_intervalo"]),
            "valor": numero(r, campo),
            "lacuna_temporal": int(r["dias_intervalo"]) > 1,
            "eventos_convergencia": int(r["eventos_convergencia"]),
            "fracao_incremento_ja_queimado_pct": numero(
                r, "fracao_incremento_p2_ja_queimado_pct", opcional=True,
            ),
        }
        for r in ordenado[:limite]
    ]


def intervalo(r: dict) -> str:
    return f"{r['inicio']} a {r['fim']} ({r['dias']} dia(s))"


def verificar_proveniencia(raiz: Path, evento: int, resumo5: dict,
                          resumo6: dict, diarios: list[dict],
                          transicoes: list[dict]) -> dict:
    if int(resumo5["id_incendio"]) != evento or int(
        resumo6["id_incendio"]
    ) != evento:
        raise ValueError("Resumos de outro evento")
    if len(diarios) < 3 or len(transicoes) != len(diarios) - 1:
        raise ValueError("Número de observações/transições inconsistente")
    if any(int(r["id_incendio"]) != evento for r in diarios + transicoes):
        raise ValueError("ID dos CSVs não corresponde à análise")
    diarios.sort(key=lambda r: r["data"])
    transicoes.sort(key=lambda r: (r["data_anterior"], r["data_atual"]))
    datas = [r["data"] for r in diarios]
    if len(set(datas)) != len(datas):
        raise ValueError("Datas P1 repetidas")
    esperados = list(zip(datas, datas[1:]))
    realizados = [(r["data_anterior"], r["data_atual"]) for r in transicoes]
    if realizados != esperados:
        raise ValueError("Transições não correspondem à sequência de observações")
    for r in transicoes:
        intervalo_real = (
            date.fromisoformat(r["data_atual"])
            - date.fromisoformat(r["data_anterior"])
        ).days
        if intervalo_real < 1 or int(r["dias_intervalo"]) != intervalo_real:
            raise ValueError(f"Duração da transição incoerente: {r!r}")
    for s in (resumo5, resumo6):
        if int(s["observacoes"]) != len(diarios) or int(
            s["transicoes"]
        ) != len(transicoes):
            raise ValueError("Resumos e CSVs divergem em contagem")
    if resumo5.get("periodo_inicio") != datas[0] or resumo5.get(
        "periodo_fim"
    ) != datas[-1]:
        raise ValueError("Período da Etapa 5 não corresponde à série")
    # Há versões antigas do pipeline que podiam reutilizar CSVs desatualizados.
    # A comparação SHA dos insumos originais evita sintetizar execuções mistas.
    hashes = {}
    for nome, prefixo in (
        ("p1", "P1_componentes"),
        ("p2", "P2_regiao_movel"),
    ):
        caminho = raiz / "dados" / f"estudo_caso_{evento}" / (
            f"{prefixo}_{evento}.geojson"
        )
        if not caminho.is_file():
            raise ValueError(f"GeoJSON original ausente: {caminho}")
        digest = sha256(caminho.read_bytes()).hexdigest()
        if digest != resumo5.get(f"sha256_{nome}"):
            raise ValueError(
                f"GeoJSON {nome.upper()} diverge do SHA-256 da Etapa 5"
            )
        hashes[nome] = digest
    return hashes


def sintetizar(raiz: Path, evento: int, saida: Path) -> dict:
    etapa5 = raiz / "resultados" / "etapa5"
    etapa6 = raiz / "resultados" / "etapa6"
    resumo5 = ler_json(etapa5 / f"resumo_etapa5_{evento}.json")
    resumo6 = ler_json(etapa6 / f"resumo_validacao_{evento}.json")
    diarios = ler_csv(etapa5 / f"serie_diaria_integrada_{evento}.csv")
    transicoes = ler_csv(etapa5 / f"transicoes_integradas_{evento}.csv")
    hashes = verificar_proveniencia(
        raiz, evento, resumo5, resumo6, diarios, transicoes,
    )

    for r in transicoes:
        for f in (
            "taxa_nova_evento_km2_dia", "area_nova_evento_km2",
            "p2_incremento_geometrico_km2",
            "p2_incremento_ja_queimado_km2",
            "p2_incremento_nova_area_evento_km2",
            "eventos_convergencia", "igt_concentracao_direcional",
        ):
            numero(r, f, opcional=f == "igt_concentracao_direcional")
    datas_gap = [
        {"inicio": r["data_anterior"], "fim": r["data_atual"],
         "dias": int(r["dias_intervalo"])}
        for r in transicoes if int(r["dias_intervalo"]) > 1
    ]
    maior_taxa = ranking(transicoes, "taxa_nova_evento_km2_dia")
    maior_incorp = ranking(
        transicoes, "p2_incremento_ja_queimado_km2"
    )
    maior_converg = ranking(transicoes, "eventos_convergencia")
    max_patches = max(diarios, key=lambda r: numero(r, "numero_patches"))
    min_patches = min(diarios, key=lambda r: numero(r, "numero_patches"))
    p2_soma = sum(numero(r, "p2_incremento_geometrico_km2") for r in transicoes)
    p2_incorp = sum(numero(
        r, "p2_incremento_ja_queimado_km2"
    ) for r in transicoes)
    nova_p2 = sum(numero(
        r, "p2_incremento_nova_area_evento_km2"
    ) for r in transicoes)
    if abs(p2_soma - p2_incorp - nova_p2) > 1e-4:
        raise ValueError("Somas de áreas do P2 não fecham")
    comparaveis = []
    for r in transicoes:
        a = numero(r, "tr_azimute_centroide_graus", opcional=True)
        b = numero(r, "igt_azimute_ponderado_graus", opcional=True)
        c = numero(r, "igt_concentracao_direcional", opcional=True)
        nova = numero(r, "p2_incremento_nova_area_evento_km2")
        if (
            a is not None and b is not None and c is not None
            and c >= 0.5 and int(r["dias_intervalo"]) == 1
            and nova >= 0.25
        ):
            comparaveis.append({
                "inicio": r["data_anterior"], "fim": r["data_atual"],
                "diferenca_angular_graus": abs((a - b + 180) % 360 - 180),
                "concentracao_igt": c,
            })
    dias_alerta = list(resumo6.get("dias_sobreposicao_p1_acima_1m2", []))
    perdas = list(resumo6.get(
        "transicoes_com_perda_area_acumulada_acima_1m2", []
    ))
    externos = bool(resumo6.get("validacao_externa_concluida", False))
    diagnosticos_origem = []
    for arquivo in sorted(
        etapa5.glob(f"verificacao_origem_p1_{evento}_*.json")
    ):
        diag = ler_json(arquivo)
        if diag.get("sha256_p1") != hashes["p1"] or int(
            diag.get("id_incendio", -1)
        ) != evento:
            continue
        diagnosticos_origem.append({
            "data": diag.get("data"),
            "pares": [
                {
                    "ranks": [p["rank_principal"], p["rank_outro"]],
                    "classificacao": p["classificacao"],
                    "area_final_m2": p[
                        "projetada_laea_apos_reparo"
                    ]["area_m2"],
                }
                for p in diag.get("pares", [])
            ],
        })
    resultado = {
        "id_incendio": evento,
        "periodo_inicio": diarios[0]["data"],
        "periodo_fim": diarios[-1]["data"],
        "observacoes": len(diarios),
        "transicoes": len(transicoes),
        "sha256_entradas": hashes,
        "area_coberta_final_p1_km2": numero(
            diarios[-1], "area_total_laea_km2"
        ),
        "area_final_p2_km2": numero(diarios[-1], "p2_area_laea_km2"),
        "dominancia_p2_final_pct": numero(
            diarios[-1], "dominancia_cobertura_p2_pct"
        ),
        "maior_numero_patches": {
            "data": max_patches["data"],
            "numero": int(max_patches["numero_patches"]),
        },
        "menor_numero_patches": {
            "data": min_patches["data"],
            "numero": int(min_patches["numero_patches"]),
        },
        "top_taxa_area_nova_evento": maior_taxa,
        "top_incorporacao_prequeimada_p2": maior_incorp,
        "top_convergencias_geometricas": maior_converg,
        "numero_convergencias_geometricas": sum(
            int(r["eventos_convergencia"]) for r in transicoes
        ),
        "soma_incrementos_geometricos_p2_km2": p2_soma,
        "soma_incorporacao_ja_queimada_p2_km2": p2_incorp,
        "soma_nova_area_p2_km2": nova_p2,
        "fracao_incremento_prequeimado_pct": (
            100 * p2_incorp / p2_soma if p2_soma > 0 else None
        ),
        "intervalos_com_lacunas": datas_gap,
        "sensibilidade_contato_dias": int(
            resumo6["dias_com_contagem_sensivel"]
        ),
        "fases_exploratorias_bic": int(resumo5["numero_fases_bic"]),
        "cenarios_fases_avaliados": int(resumo6["n_cenarios_fases"]),
        "cenarios_que_alteram_inicios": int(resumo6["alteracoes_fases"]),
        "direcoes_tr_igt_comparaveis_criterio_exploratorio": len(
            comparaveis
        ),
        "mediana_diferenca_angular_tr_igt_filtrada_graus": (
            median(x["diferenca_angular_graus"] for x in comparaveis)
            if comparaveis else None
        ),
        "criterio_direcao_exploratorio": (
            "dias_intervalo = 1; concentracao_IGT >= 0.5; "
            "nova_area_no_P2 >= 0.25 km2; azimutes definidos. "
            "Limiares heurísticos, não validação de sensor."
        ),
        "dias_sobreposicao_p1_pendentes": dias_alerta,
        "max_excesso_sobreposicao_p1_m2": numero(
            resumo6, "sobreposicao_p1_maxima_m2"
        ),
        "transicoes_com_perdas_area_acumulada": perdas,
        "diagnosticos_origem_p1": diagnosticos_origem,
        "status_cientifico": resumo6["status_cientifico"],
        "validacao_externa_concluida": externos,
    }
    linhas = [
        f"# Síntese científica exploratória | GlobFire ID {evento}",
        "",
        "**Natureza:** leitura descritiva dos dados já processados. "
        "Não é validação externa, nem análise de fogo ativo.",
        "",
        "## 1. Pergunta de pesquisa",
        "Em que medida a integração de métricas de paisagem (P1) e "
        "indicadores de regiões móveis (P2) contribui para caracterizar "
        "a evolução espaço-temporal da área queimada, distinguindo "
        "crescimento espacial, conectividade e transformações geométricas?",
        "",
        "## 2. Evidências observadas",
        f"- Janela analisada: {resultado['periodo_inicio']} a "
        f"{resultado['periodo_fim']}, com {len(diarios)} observações "
        f"e {len(transicoes)} transições.",
        f"- Área coberta final do evento P1 (união LAEA): "
        f"{fmt(resultado['area_coberta_final_p1_km2'])} km².",
        f"- Área final da região rastreada P2: "
        f"{fmt(resultado['area_final_p2_km2'])} km²; "
        f"{fmt(resultado['dominancia_p2_final_pct'], 2)}% "
        "da cobertura espacial do evento na última observação.",
        f"- Número de patches: mínimo de "
        f"{resultado['menor_numero_patches']['numero']} em "
        f"{resultado['menor_numero_patches']['data']}; "
        f"máximo de {resultado['maior_numero_patches']['numero']} em "
        f"{resultado['maior_numero_patches']['data']}.",
        f"- Convergências **geométricas** indicadas pelo grafo temporal: "
        f"{resultado['numero_convergencias_geometricas']} "
        "(não são encontros físicos de frentes comprovados).",
        f"- Em {resultado['sensibilidade_contato_dias']} datas, "
        "a contagem de componentes se altera ao agrupar por contato vetorial. "
        "Esse número mede sensibilidade à conectividade escolhida.",
        "",
        "## 3. Crescimento do incêndio versus crescimento do P2",
        f"- Soma dos incrementos geométricos P2 entre observações: "
        f"{fmt(p2_soma)} km².",
        f"- Dessa soma, área que já pertencia ao evento em observação "
        f"anterior: {fmt(p2_incorp)} km² "
        f"({fmt(resultado['fracao_incremento_prequeimado_pct'], 2)}%).",
        f"- Área nova do evento incorporada nos incrementos P2: "
        f"{fmt(nova_p2)} km².",
        "",
        "**Interpretação:** o crescimento geométrico da região P2 "
        "pode incorporar superfícies já queimadas anteriormente. "
        "A soma de incrementos entre datas não é a área única total "
        "queimada, pois uma superfície pode entrar em mais de uma comparação.",
        "",
        "### Transições com maior taxa de área nova do evento",
        "| Período | km²/dia | Convergências |",
        "|---|---:|---:|",
    ]
    for r in maior_taxa:
        linhas.append(
            f"| {intervalo(r)} | {fmt(r['valor'])} | "
            f"{r['eventos_convergencia']} |"
        )
    linhas += [
        "",
        "### Transições com maior incorporação prequeimada pelo P2",
        "| Período | Área incorporada (km²) | % do incremento P2 |",
        "|---|---:|---:|",
    ]
    for r in maior_incorp:
        linhas.append(
            f"| {intervalo(r)} | {fmt(r['valor'])} | "
            f"{fmt(r['fracao_incremento_ja_queimado_pct'], 2)} |"
        )
    linhas += [
        "",
        "### Transições com maior número de convergências geométricas",
        "| Período | Convergências |",
        "|---|---:|",
    ]
    for r in maior_converg:
        linhas.append(f"| {intervalo(r)} | {int(r['valor'])} |")
    linhas += [
        "",
        "## 4. Direções: TR versus IGT",
        f"- Transições comparáveis pelo filtro exploratório: "
        f"{len(comparaveis)} de {len(transicoes)}.",
        f"- Mediana da diferença angular absoluta nessas transições: "
        f"{fmt(resultado['mediana_diferenca_angular_tr_igt_filtrada_graus'],1)}°.",
        "- Critério do filtro: 1 dia de intervalo; concentração IGT "
        ">= 0,5; nova área no P2 >= 0,25 km²; ambos azimutes definidos.",
        "- A diferença angular indica que os dois descritores "
        "não precisam apontar no mesmo sentido. Nenhum desses "
        "azimutes representa, por si só, direção física do fogo.",
        "",
        "## 5. Fases exploratórias e sensibilidade",
        f"- Segmentos descritivos escolhidos por BIC: "
        f"{resultado['fases_exploratorias_bic']}.",
        f"- Cenários de sensibilidade avaliados: "
        f"{resultado['cenarios_fases_avaliados']}; "
        f"{resultado['cenarios_que_alteram_inicios']} alteram os inícios.",
        "- Fases não foram validadas como regimes físicos. "
        "A série acumulada possui dependência temporal.",
        "",
        "## 6. Auditoria e limites",
        f"- Datas com sobreposição P1 acima do alerta interno de 1 m²: "
        f"{', '.join(dias_alerta) if dias_alerta else 'nenhuma'}.",
        f"- Maior excesso por sobreposição na data: "
        f"{fmt(resultado['max_excesso_sobreposicao_p1_m2'],6)} m².",
        f"- Transições com perda espacial de área acumulada superior a 1 m²: "
        f"{len(perdas)}.",
        f"- Lacunas maiores que um dia: {len(datas_gap)} "
        "(taxas são médias entre observações, não instantâneas).",
        f"- Estado da auditoria: {resumo6['status_cientifico']}.",
        f"- Validação externa concluída: {'sim' if externos else 'não'}.",
    ]
    for d in diagnosticos_origem:
        linhas.append(
            f"- Diagnóstico da fonte em {d['data']}: "
            + "; ".join(
                f"ranks {p['ranks'][0]}/{p['ranks'][1]} = "
                f"{p['classificacao']}"
                for p in d["pares"]
            )
            + "."
        )
    linhas += [
        "",
        "## 7. Encaminhamento científico",
        "1. Selecionar as transições com crescimento, incorporação "
        "e convergências mais relevantes para inspeção no QGIS.",
        "2. Comparar mapas P1/P2 antes/depois de cada transição selecionada. "
        "Usar a camada de convergências da Etapa 3, se disponível.",
        "3. Confrontar as transições escolhidas com imagens independentes "
        "e informações de qualidade do produto antes de atribuir processos físicos.",
        "4. Submeter ao orientador a decisão sobre conectividade, "
        "contatos pontuais, intervalos com lacunas e os alertas de sobreposição.",
        "",
        "## 8. Figuras já geradas no pipeline",
        "- Etapa 5: 01_areas_p1_p2.png",
        "- Etapa 5: 02_fragmentacao_dominancia.png",
        "- Etapa 5: 03_nova_area_evento.png",
        "- Etapa 5: 04_decomposicao_p2.png",
        "- Etapa 5: 05_convergencias.png",
        "- Etapa 6: revisao_qgis_<ID>.geojson (quando habilitado)",
        "",
        "**Status:** análise exploratória apoiada no processamento interno; "
        "não representa conclusão causal nem validação científica final.",
    ]
    saida.mkdir(parents=True, exist_ok=True)
    (saida / f"sintese_cientifica_{evento}.md").write_text(
        "\n".join(linhas) + "\n", encoding="utf-8",
    )
    (saida / f"indicadores_sintese_{evento}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    curto = [
        f"BurnGeoFlow {evento} | {resultado['observacoes']} datas / "
        f"{resultado['transicoes']} transições",
        f"P1 final (cobertura): "
        f"{fmt(resultado['area_coberta_final_p1_km2'])} km²",
        f"P2 final: {fmt(resultado['area_final_p2_km2'])} km² "
        f"({fmt(resultado['dominancia_p2_final_pct'], 2)}%)",
        f"Convergências geométricas: "
        f"{resultado['numero_convergencias_geometricas']}",
        f"Incremento geométrico acumulado entre transições do P2: "
        f"{fmt(p2_soma)} km²",
        f"Incorporação de áreas já queimadas (soma das transições): "
        f"{fmt(p2_incorp)} km² "
        f"({fmt(resultado['fracao_incremento_prequeimado_pct'],2)}%)",
        f"Maior taxa de área nova: {intervalo(maior_taxa[0])}, "
        f"{fmt(maior_taxa[0]['valor'])} km²/dia",
        f"Maior incorporação prequeimada: {intervalo(maior_incorp[0])}, "
        f"{fmt(maior_incorp[0]['valor'])} km²",
        f"Sensibilidade a contatos: "
        f"{resultado['sensibilidade_contato_dias']} datas",
        f"Fases BIC: {resultado['fases_exploratorias_bic']} "
        f"({resultado['cenarios_que_alteram_inicios']} cenários alteram inícios)",
        f"TR/IGT direção: {len(comparaveis)} transições filtradas, "
        f"mediana {fmt(resultado['mediana_diferenca_angular_tr_igt_filtrada_graus'],1)}°",
        f"Alertas: sobreposição em {dias_alerta}; "
        f"perdas em {len(perdas)} transições; "
        f"lacunas em {len(datas_gap)}",
        f"Status: {resumo6['status_cientifico']}; "
        f"validação externa: {'sim' if externos else 'não'}",
    ]
    curto_txt = "\n".join(curto) + "\n"
    (saida / f"resumo_para_chat_{evento}.txt").write_text(
        curto_txt, encoding="utf-8",
    )
    return {"resumo": resultado, "texto_para_chat": curto_txt, "saida": str(saida)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--raiz", type=Path)
    ap.add_argument("--saida", type=Path)
    a = ap.parse_args()
    raiz = a.raiz or ROOT / "execucoes" / str(a.id)
    saida = a.saida or raiz / "resultados" / "sintese_cientifica"
    try:
        r = sintetizar(raiz, a.id, saida)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        ap.exit(1, f"[ERRO SÍNTESE] {exc}\n")
    print(r["texto_para_chat"])
    print(f"[ARQUIVOS] {r['saida']}")


if __name__ == "__main__":
    main()
