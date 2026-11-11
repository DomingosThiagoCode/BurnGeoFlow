#!/usr/bin/env python3
"""Etapa 6: robustez interna do estudo GlobFire; nao equivale a validacao externa."""
from __future__ import annotations
import argparse
import csv
from datetime import date
import json
from math import isfinite
from pathlib import Path
from statistics import median
import pyproj
import shapely
from shapely.geometry import mapping
from integrar_etapa5 import ler_tabela, ler_geometrias, segmentar_fases

def num(r,c,optional=False):
    s=r.get(c)
    if s is None or s=="":
        if optional:return None
        raise ValueError("Campo ausente: "+c)
    v=float(s)
    if not isfinite(v):raise ValueError("Nao finito: "+c)
    return v

def angular(a,b):
    if a is None or b is None:return None
    return abs((a-b+180)%360-180)

def direcoes(trans):
    tab=[];res=[]
    for minimo in (0,.3,.5,.7,.9):
        comparaveis=[]
        for r in trans:
            c=num(r,"igt_concentracao_direcional",True)
            a=num(r,"tr_azimute_centroide_graus",True)
            b=num(r,"igt_azimute_ponderado_graus",True)
            d=angular(a,b)
            valido=(c is not None and c>=minimo and d is not None)
            if valido:comparaveis.append(d)
            tab.append(dict(
                id_incendio=r["id_incendio"],data_anterior=r["data_anterior"],
                data_atual=r["data_atual"],concentracao_direcional=c,
                azimute_centroide_TR_graus=a,azimute_resumo_IGT_graus=b,
                diferenca_angular_graus=d,concentracao_minima=minimo,
                comparavel=valido))
        res.append(dict(concentracao_minima=minimo,
            n_comparaveis=len(comparaveis),
            mediana_diferenca_graus=median(comparaveis) if comparaveis else None))
    return tab,res

def contatos(tab,diarios):
    if set(tab)!={(r["data"],) for r in diarios}:raise ValueError("Datas de contato")
    linhas=[]
    for r in diarios:
        x=tab[(r["data"],)]
        original=int(x["numero_patches_original"])
        grupos=int(x["numero_grupos_por_contato_vetorial"])
        if original!=int(r["numero_patches"]) or grupos>original or grupos<=0:
            raise ValueError("Patches incoerentes: "+r["data"])
        dom=num(x,"dominancia_original_pct")
        if abs(dom-num(r,"dominancia_maior_patch_pct"))>1e-6:
            raise ValueError("Dominancia incoerente")
        linhas.append(dict(
            id_incendio=r["id_incendio"],data=r["data"],
            patches_originais=original,grupos_por_contato=grupos,
            reducao_pct=100*(original-grupos)/original,
            dominancia_original_pct=dom,
            dominancia_apos_contato_pct=num(x,"dominancia_apos_agrupar_contatos_pct"),
            diferenca_dominancia_pp=num(x,"dominancia_apos_agrupar_contatos_pct")-dom,
            pares_pontuais=int(x["pares_contato_pontual"])))
    return linhas

def fases_sensiveis(diarios):
    bas,_=segmentar_fases(diarios,min_obs=7,max_fases=3)
    inicio_base=tuple(x["data_inicio"] for x in bas)
    cenarios=[("base",7,3,None)]
    cenarios += [("min_obs_"+str(m),m,3,None) for m in (5,9,11)]
    cenarios += [("maximo_duas_fases",7,2,None)]
    candidatos=("2020-09-03","2020-09-04","2020-09-10","2020-09-11",
                "2020-09-13","2020-09-14","2020-09-24","2020-10-09")
    datas={r["data"] for r in diarios}
    cenarios += [("remover_"+d,7,3,d) for d in candidatos if d in datas]
    saida=[]
    for nome,minimo,maximo,retirado in cenarios:
        dados=[r for r in diarios if r["data"]!=retirado]
        fases,_=segmentar_fases(dados,min_obs=minimo,max_fases=maximo)
        inicio=tuple(x["data_inicio"] for x in fases)
        saida.append(dict(
            cenario=nome,min_obs=minimo,max_fases=maximo,
            data_excluida=retirado,n_fases=len(fases),
            inicios=";".join(inicio),finais=";".join(x["data_fim"] for x in fases),
            b_i_c=fases[0]["criterio_bic"],alterou_inicios=inicio!=inicio_base))
    return saida

def evidencias():
    return [
        dict(afirmacao="Area P1/P2 internamente coerente",categoria="computacional",
             status="auditada_internamente",limite="Acuracia de sensor nao avaliada",
             proxima_acao="Confrontar com imagens e BurnDate/QA"),
        dict(afirmacao="Incorporacao de area ja queimada ao P2",categoria="geometrica",
             status="auditada_internamente",limite="Fusao fisica nao demonstrada",
             proxima_acao="Revisar 09-11 de setembro com cenas independentes"),
        dict(afirmacao="72 convergencias representam encontros reais de frentes",categoria="fisica",
             status="nao_validada_externamente",limite="Grafo de intersecoes apenas",
             proxima_acao="Amostragem independente de casos de convergencia"),
        dict(afirmacao="Tres fases identificam regimes fisicos de fogo",categoria="causal",
             status="exploratoria",limite="BIC sobre serie acumulada e dependente",
             proxima_acao="Confrontar com series independentes e orientador"),
        dict(afirmacao="TR descreve cinco pontos da regiao movel",categoria="metodologica",
             status="reproduzida_com_adaptacoes",limite="Nao mede frente ativa",
             proxima_acao="Conferir desempates e escala com orientador"),
        dict(afirmacao="IGT descreve partes acrescentadas e reduzidas",categoria="metodologica",
             status="reproduzida_com_adaptacoes",limite="Media ponderada e sintese propria",
             proxima_acao="Conferir interpretacao direcional com orientador"),
        dict(afirmacao="Azimutes indicam propagacao fisica",categoria="fisica",
             status="nao_validada_externamente",limite="Sem fogo ativo independente",
             proxima_acao="Confrontar com observacoes independentes"),
    ]

def csv_write(path,rows):
    if not rows:raise ValueError("Sem linhas: "+str(path))
    with path.open("w",encoding="utf-8",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        wr.writeheader();wr.writerows(rows)

def qgis(raiz,evento,saida):
    pasta=raiz/"dados"/("estudo_caso_"+str(evento))
    totais,p2,_,projecao=ler_geometrias(pasta/("P1_componentes_"+str(evento)+".geojson"),
        pasta/("P2_regiao_movel_"+str(evento)+".geojson"),evento)
    inverso=pyproj.Transformer.from_crs(
        pyproj.CRS.from_proj4(projecao["definicao_laea_proj4"]),
        "EPSG:4326",always_xy=True)
    output=[]
    for d0,d1 in (("2020-09-09","2020-09-10"),("2020-09-10","2020-09-11")):
        if d0 not in totais or d1 not in totais:continue
        total0,total1=totais[d0],totais[d1]
        r0,r1=p2[d0],p2[d1]
        incremento=r1.difference(r0)
        geoms=[
            ("p2_anterior",r0),("p2_atual",r1),
            ("p2_incorporacao_ja_queimada",incremento.intersection(total0)),
            ("p2_nova_area_evento",incremento.difference(total0)),
            ("nova_area_evento_fora_p2",total1.difference(total0).difference(r1))]
        for classe,g in geoms:
            if g.is_empty:continue
            ll=shapely.transform(g,inverso.transform,interleaved=False)
            output.append({"type":"Feature","geometry":mapping(ll),"properties":{
                "id_incendio":evento,"data_anterior":d0,"data_atual":d1,
                "classe":classe,"area_laea_km2":g.area/1e6,
                "nota":"Inspecao dos mesmos dados P1/P2; nao e verificacao externa"}})
    saida.write_text(json.dumps({"type":"FeatureCollection","features":output},
                               ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    return len(output)

def executar(raiz:Path,evento:int,saida:Path,*,sem_mapa=False):
    dir5=raiz/"resultados"/"etapa5"
    dias=ler_tabela(dir5/("serie_diaria_integrada_"+str(evento)+".csv"),
                    campos_chave=("data",))
    trans=ler_tabela(dir5/("transicoes_integradas_"+str(evento)+".csv"),
                     campos_chave=("data_anterior","data_atual"))
    c=ler_tabela(raiz/"resultados"/"etapa2"/
                ("sensibilidade_contato_"+str(evento)+".csv"),
                campos_chave=("data",))
    diarios=[{**x,"area_total_laea_km2":num(x,"area_total_laea_km2")} for x in sorted(dias.values(),key=lambda x:x["data"])]
    transicoes=sorted(trans.values(),key=lambda x:x["data_anterior"])
    datas=[r["data"] for r in diarios]
    if len(diarios)<3 or len(transicoes)!=len(diarios)-1:raise ValueError("N datas/transicoes")
    if set(trans)!={tuple(p) for p in zip(datas,datas[1:])}:raise ValueError("Transicoes")
    if any(int(r["id_incendio"])!=evento for r in diarios+transicoes):raise ValueError("ID")
    for r in transicoes:
        dias_reais=(date.fromisoformat(r["data_atual"])-date.fromisoformat(r["data_anterior"])).days
        if int(r["dias_intervalo"])!=dias_reais:raise ValueError("Intervalo")
        p2delta=num(r,"p2_incremento_geometrico_km2")
        if abs(p2delta-num(r,"p2_incremento_ja_queimado_km2")-
               num(r,"p2_incremento_nova_area_evento_km2"))>1e-6:
            raise ValueError("Fechamento P2")
        if abs(num(r,"area_nova_evento_km2")-
               num(r,"p2_incremento_nova_area_evento_km2")-
               num(r,"nova_area_fora_p2_km2"))>1e-6:
            raise ValueError("Fechamento total")
        if num(r,"area_perdida_evento_km2")>1e-6:
            raise ValueError("Area acumulada perdida acima de 1 m2")
    ds,agregado=direcoes(transicoes)
    cs=contatos(c,diarios)
    fs=fases_sensiveis(diarios)
    ev=evidencias()
    saida.mkdir(parents=True,exist_ok=True)
    for prefixo,rows in (
        ("direcoes_sensibilidade",ds),("contato_sensibilidade",cs),
        ("fases_sensibilidade",fs),("quadro_evidencias",ev)):
        csv_write(saida/(prefixo+"_"+str(evento)+".csv"),rows)
    n_geo=0 if sem_mapa else qgis(raiz,evento,
        saida/("revisao_qgis_"+str(evento)+".geojson"))
    inc=sum(num(r,"p2_incremento_ja_queimado_km2") for r in transicoes)
    soma=sum(num(r,"p2_incremento_geometrico_km2") for r in transicoes)
    resumo=dict(
        id_incendio=evento,observacoes=len(diarios),transicoes=len(transicoes),
        alteracoes_fases=sum(x["alterou_inicios"] for x in fs),
        n_cenarios_fases=len(fs),cenarios_fases=fs,
        dias_com_contagem_sensivel=sum(x["patches_originais"]!=x["grupos_por_contato"] for x in cs),
        pares_pontuais=sum(x["pares_pontuais"] for x in cs),
        aumento_max_dominancia_por_contato_pp=max(x["diferenca_dominancia_pp"] for x in cs),
        sensibilidade_direcoes=agregado,
        lacunas=sum(int(r["dias_intervalo"])>1 for r in transicoes),
        soma_incorporacao_ja_queimada_km2=inc,
        soma_incrementos_p2_km2=soma,
        frac_incorporada_pct=100*inc/soma if soma>0 else None,
        transicao_10_11_set=next((r for r in transicoes if r["data_atual"]=="2020-09-11"),None),
        geojson_feicoes=n_geo,
        validacao_externa_concluida=False)
    (saida/("resumo_validacao_"+str(evento)+".json")).write_text(
        json.dumps(resumo,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    relatorio(resumo,saida/("relatorio_validacao_"+str(evento)+".md"))
    return resumo

def relatorio(r,path):
    fases="\n".join("| "+x["cenario"]+" | "+str(x["n_fases"])+" | "+x["inicios"]+" |"
        for x in r["cenarios_fases"])
    direcoes="\n".join("| "+str(x["concentracao_minima"])+" | "+
        str(x["n_comparaveis"])+" | "+str(x["mediana_diferenca_graus"])+" |"
        for x in r["sensibilidade_direcoes"])
    exemplar=r["transicao_10_11_set"]
    d=exemplar or {}
    texto=f"""# Etapa 6: auditoria científica interna (evento {r["id_incendio"]})

**Não é validação empírica independente**. São testes de consistência e
sensibilidade sobre produtos derivados do mesmo GlobFire/MCD64A1.

## Quadro de achados

- {r["observacoes"]} observações, {r["transicoes"]} transições;
  {r["lacunas"]} intervalos com mais de um dia.
- {r["dias_com_contagem_sensivel"]} das {r["observacoes"]} datas mudam de
  contagem sob agrupamento por contato vetorial; {r["pares_pontuais"]}
  pares de contato pontual somados entre observações.
- Diferença máxima de dominância por agrupamento:
  {r["aumento_max_dominancia_por_contato_pp"]:.2f} pontos percentuais.
- Incrementos geométricos P2 somados: {r["soma_incrementos_p2_km2"]:.3f} km²;
  incorporação de áreas anteriormente queimadas: {r["soma_incorporacao_ja_queimada_km2"]:.3f}
  km² ({r["frac_incorporada_pct"]:.1f}% desses incrementos).
  Não confundir com área queimada nova no evento.
- Em 10–11/09, P2 incorporou {float(d.get("p2_incremento_ja_queimado_km2",0)):.3f}
  km² anteriormente queimados, segundo os mesmos dados de entrada.

## Sensibilidade das fases da Etapa 5

Cenários determinísticos: diferentes observações mínimas, máximo de segmentos
e exclusão individual de datas críticas; **não são intervalos de confiança**.
{r["alteracoes_fases"]}/{r["n_cenarios_fases"]} cenários alteram os
inícios das fases em relação à base. A série usa área acumulada e tem
dependência serial; BIC não comprova regimes físicos de fogo.

| Cenário | Fases | Inícios |
|---|---:|---|
{fases}

## Sensibilidade das direções TR e IGT

TR: centroide e N/S/E/O de Priscila Backes de Oliveira.
IGT: diferenças geométricas conforme Barbosa e Oliveira (2022). O azimute
médio ponderado é **síntese nossa**, e não equação literal do artigo.

| Concentração mínima IGT | N de comparações definidas | Mediana da diferença angular |
|---:|---:|---:|
{direcoes}

Mudanças de direções entre descritores não são erros de método. A dispersão
pode tornar uma direção média pouco representativa.

## Validação externa: pendências obrigatórias

Fonte: GlobFire v2 é baseado no MCD64A1; este informa data de queima
aproximada, incerteza temporal e QA em grade nominal de 500 m. A qualidade
da interseção geométrica até 1 m² **não corresponde à acurácia de imagem**.

**Revisão recomendada para 09–11/09:** no QGIS, sobrepor a camada produzida
de P2 anterior e atual, área anteriormente queimada incorporada, área nova
P2 e nova área fora do P2. É apenas uma decomposição **interna**, não
uma fonte de validação independente.

Protocolo a ser aplicado com o orientador:
1. Selecionar cenas independentes, de resolução superior e datas próximas,
   registrar nuvens, sensor, processamento e ajuste geométrico;
2. Confrontar com BurnDate, Uncertainty e QA do MCD64A1, verificando as
   diferenças de datas e pontos não mapeados;
3. Registrar amostra com acertos, omissões, falsas detecções, casos ambíguos,
   **sem assumir que uma única imagem prova a data física da fusão**;
4. Só atribuir influência de vento, rios, topografia ou combustível após
   evidência ambiental externa e revisão científica.

Fontes de documentação do produto:
- https://developers.google.com/earth-engine/datasets/catalog/JRC_GWIS_GlobFire_v2_DailyPerimeters
- https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD64A1
- https://gwis.jrc.ec.europa.eu/about-gwis/technical-background/burnt-areas

## Questões para o orientador

1. Preservar patches P1 originais e manter contatos pontuais como sensibilidade?
2. Quais evidências externas sustentam os eventos de convergência?
3. Como apresentar fases BIC sem interpretações causais indevidas?
4. Quais indicadores TR e IGT são suficientes para a pergunta científica?
5. Qual amostragem de imagens independentes e quais critérios de incerteza
   podemos executar no prazo da pesquisa?

**Estado:** auditoria interna documentada. Validação externa e aprovação
científica pelo orientador ainda pendentes.
"""
    path.write_text(texto,encoding="utf-8")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id",type=int,required=True)
    ap.add_argument("--raiz",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--saida",type=Path,default=None)
    ap.add_argument("--sem-mapa",action="store_true")
    args=ap.parse_args()
    out=args.saida or args.raiz/"resultados"/"etapa6"
    res=executar(args.raiz,args.id,out,sem_mapa=args.sem_mapa)
    print(json.dumps({k:res[k] for k in (
        "id_incendio","observacoes","transicoes","alteracoes_fases",
        "n_cenarios_fases","dias_com_contagem_sensivel",
        "validacao_externa_concluida")},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
