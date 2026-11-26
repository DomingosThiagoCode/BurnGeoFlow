import json
from urllib.parse import urlencode
from urllib.request import urlopen
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from backend.app.api.jobs import verificacao_mutacao
from burngeoflow.aquisicao.catalogo import catalogo, total_evento

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])

class Consulta(BaseModel):
    geometria: dict | None = None
    origem: str = Field(default="", max_length=500)
    regiao: str | None = None
    inicio: str
    fim: str
    margem: int = Field(default=0, ge=0, le=365)
    atualizar: bool = False

BIOMAS = {"Pantanal", "Amazônia", "Cerrado", "Caatinga", "Mata Atlântica", "Pampa"}
BIOMAS_URL = "https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/vetores/Biomas_250mil.zip"

def resolver_regiao(nome, pasta):
    from io import BytesIO
    from pathlib import Path, PurePosixPath
    from zipfile import ZipFile
    from unicodedata import normalize
    from urllib.request import Request as URLRequest
    import shapefile
    from pyproj import CRS, Transformer
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union, transform

    def chave(v):
        return "".join(c for c in normalize("NFKD", str(v).strip().casefold()) if not __import__("unicodedata").combining(c))

    if nome not in BIOMAS:
        raise ValueError("Selecione um bioma brasileiro disponível.")
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / (nome + "_ibge2019_direto.json")
    if arquivo.is_file():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    zip_local = pasta / "Biomas_250mil.zip"
    try:
        if not zip_local.is_file():
            with urlopen(URLRequest(BIOMAS_URL, headers={"User-Agent": "BurnGeoFlow/1.0"}), timeout=120) as resposta:
                bruto = resposta.read(100 * 1024 * 1024 + 1)
            if len(bruto) > 100 * 1024 * 1024:
                raise ValueError("Arquivo de limites excede o tamanho permitido.")
            with ZipFile(BytesIO(bruto)) as z:
                if z.testzip() is not None:
                    raise ValueError("Arquivo ZIP corrompido.")
            with NamedTemporaryFile(dir=pasta, delete=False) as tmp:
                tmp.write(bruto)
                temp = Path(tmp.name)
            temp.replace(zip_local)
        with ZipFile(zip_local) as z:
            nomes = {n.lower(): n for n in z.namelist()}
            grupos = []
            esperados = {chave(n) for n in BIOMAS}
            for shp in (n for n in z.namelist() if n.lower().endswith(".shp")):
                base = shp[:-4].lower()
                if not all(base+ext in nomes for ext in (".dbf", ".prj")):
                    continue
                dbf = z.read(nomes[base+".dbf"])
                shp_bytes = z.read(shp)
                for enc in ("utf-8", "cp1252", "latin1"):
                    try:
                        with shapefile.Reader(shp=BytesIO(shp_bytes), dbf=BytesIO(dbf), encoding=enc) as leitor:
                            registros = leitor.records()
                            if not registros:
                                break
                            colunas = [i for i in range(len(registros[0]))
                                       if esperados.issubset({chave(r[i]) for r in registros})]
                            if not colunas:
                                break
                            idx = colunas[0]
                            origem_crs = CRS.from_wkt(z.read(nomes[base+".prj"]).decode("utf-8-sig"))
                            reprojetar = Transformer.from_crs(origem_crs, "EPSG:4326", always_xy=True).transform
                            geoms = [transform(reprojetar, shape(leitor.shape(i).__geo_interface__))
                                     for i,r in enumerate(registros) if chave(r[idx]) == chave(nome)]
                            if geoms:
                                grupos.append(unary_union(geoms))
                        break
                    except UnicodeDecodeError:
                        continue
            if len(grupos) != 1:
                raise ValueError("Não foi possível identificar inequivocamente a camada oficial dos seis biomas.")
            g = grupos[0]
        if g.is_empty or not g.is_valid or g.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError("Limite oficial inválido; importe outra delimitação.")
    except Exception as exc:
        raise RuntimeError("Falha ao obter/ler limites do IBGE (antes da consulta GEE): " + str(exc)) from exc
    dados = {"geometria": mapping(g), "origem": "IBGE Biomas 2019, 1:250.000 / " + nome + " / " + BIOMAS_URL}
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=pasta, delete=False) as tmp:
        json.dump(dados, tmp, ensure_ascii=False)
        temp = Path(tmp.name)
    temp.replace(arquivo)
    return dados

@router.post("", dependencies=[Depends(verificacao_mutacao)])
def consultar(req: Consulta, request: Request):
    repo = request.app.state.repositorio
    try:
        pedido = req.model_dump(exclude={"regiao"})
        if req.regiao:
            if req.geometria is not None:
                raise ValueError("Escolha região ou arquivo, não ambos.")
            try:
                pedido.update(resolver_regiao(req.regiao, repo.base / "catalogo_globfire" / "limites"))
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from exc
        elif req.geometria is None:
            raise ValueError("Selecione uma região ou importe um GeoJSON.")
        doc = catalogo(repo.base / "catalogo_globfire", **pedido)
        for e in doc["eventos"]:
            arquivos = repo.arquivos(e["id"])
            e["local"] = {k: arquivos[k].is_file() for k in ("p1", "p2", "serie")}
        return doc
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Falha no catálogo GEE/cache. Reduza a AOI ou o período e confira a autenticação: " + str(exc)) from exc

@router.post("/total/{ano}/{id_}", dependencies=[Depends(verificacao_mutacao)])
def total(ano: int, id_: int):
    if not 2001 <= ano <= 2020 or id_ <= 0:
        raise HTTPException(422, "Ano ou ID inválido")
    try:
        return {"id": id_, "ano": ano, "registros_totais": total_evento(id_, ano)}
    except Exception as exc:
        raise HTTPException(503, "Falha na consulta suplementar: " + str(exc)) from exc
