"""Catálogo de metadados GlobFire, independente da aquisição geométrica."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from burngeoflow.aquisicao.earth_engine import ASSET, ANO_MINIMO, ANO_MAXIMO, inicializar
from burngeoflow.config import carregar_configuracao_gee

def janela(inicio, fim, margem):
    a, b = date.fromisoformat(inicio), date.fromisoformat(fim)
    if a > b or not 0 <= margem <= 365:
        raise ValueError("Período ou margem inválidos.")
    if a.year < ANO_MINIMO or b.year > ANO_MAXIMO:
        raise ValueError("Período deve estar entre 2001 e 2020.")
    x = max(date(ANO_MINIMO, 1, 1), a - timedelta(days=margem))
    y = min(date(ANO_MAXIMO, 12, 31), b + timedelta(days=margem))
    return x, y, range(x.year, y.year + 1)

def agregar(ano, pares):
    grupos = defaultdict(list)
    for chave, quantidade in pares.items():
        id_, millis = chave.split(":")
        dia = datetime.fromtimestamp(int(millis)/1000, timezone.utc).date()
        grupos[int(id_)].append((dia, int(quantidade)))
    saida = []
    for id_, linhas in grupos.items():
        datas = sorted({d for d, _ in linhas})
        duracao = (datas[-1] - datas[0]).days + 1
        saida.append(dict(id=id_, ano=ano, registros_na_aoi=sum(n for _, n in linhas),
            registros_totais=None, datas_distintas=len(datas), primeira_data=str(datas[0]),
            ultima_data=str(datas[-1]), dias_periodo=duracao, lacunas=duracao-len(datas)))
    return saida

def consultar_gee(geometria, inicio, fim, anos):
    ee = inicializar(carregar_configuracao_gee())
    aoi = ee.Geometry(geometria)
    def millis(d):
        return int(datetime.combine(d, datetime.min.time(), timezone.utc).timestamp()*1000)
    eventos = []
    for ano in anos:
        fc = ee.FeatureCollection(f"{ASSET}/{ano}").filterBounds(aoi).filter(
            ee.Filter.gte("IDate", millis(inicio))).filter(
            ee.Filter.lt("IDate", millis(fim + timedelta(days=1)))).filter(
            ee.Filter.notNull(["Id", "IDate"]))
        # Uma agregação de propriedades por coleção; nenhuma geometria exportada.
        def chave(f):
            return ee.Feature(None, {"par": ee.Number(f.get("Id")).format("%.0f").cat(":").cat(
                ee.Number(f.get("IDate")).format("%.0f"))})
        eventos.extend(agregar(ano, fc.map(chave).aggregate_histogram("par").getInfo()))
    return sorted(eventos, key=lambda e: (e["ano"], e["id"]))

def catalogo(base, geometria, origem, inicio, fim, margem=0, atualizar=False, consulta=consultar_gee):
    from shapely.geometry import shape
    g = shape(geometria)
    if g.geom_type not in ("Polygon", "MultiPolygon") or g.is_empty or not g.is_valid:
        raise ValueError("AOI deve ser um Polygon ou MultiPolygon válido.")
    if not (-180 <= g.bounds[0] <= g.bounds[2] <= 180 and -90 <= g.bounds[1] <= g.bounds[3] <= 90):
        raise ValueError("AOI deve estar em longitude/latitude WGS84.")
    if not origem.strip():
        raise ValueError("Informe a origem da delimitação.")
    x,y,anos = janela(inicio,fim,margem)
    pedido = dict(esquema=1, fonte=ASSET, aoi_sha256=sha256(json.dumps(geometria,sort_keys=True).encode()).hexdigest(),
        origem_aoi=origem, inicio=inicio,fim=fim,margem=margem, inicio_efetivo=str(x),fim_efetivo=str(y),
        regra="intersecao_AOI_IDate_UTC")
    chave = sha256(json.dumps(pedido,sort_keys=True).encode()).hexdigest()
    pasta = Path(base); pasta.mkdir(parents=True,exist_ok=True)
    arquivo = pasta / (chave+".json")
    if arquivo.is_file() and not atualizar:
        return {**json.loads(arquivo.read_text(encoding="utf-8")), "origem":"cache local"}
    eventos = consulta(geometria,x,y,anos)
    doc = {**pedido,"consultado_utc":datetime.now(timezone.utc).isoformat(),"eventos":eventos}
    with NamedTemporaryFile(mode="w",encoding="utf-8",dir=pasta,delete=False) as tmp:
        json.dump(doc,tmp,ensure_ascii=False); nome=tmp.name
    Path(nome).replace(arquivo)
    return {**doc,"origem":"GEE"}

def total_evento(id_, ano):
    from burngeoflow.aquisicao.earth_engine import selecionar_evento
    ee = inicializar(carregar_configuracao_gee())
    return int(selecionar_evento(ee,id_,ano).size().getInfo())
