import json
from urllib.parse import urlencode
from urllib.request import urlopen
from tempfile import NamedTemporaryFile
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
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
BIOMAS_URL = "https://pamgia.ibama.gov.br/server/rest/services/01_Publicacoes_Bases/biomas_ibge_250k_2019/FeatureServer/2/query"

def resolver_regiao(nome, pasta):
    if nome not in BIOMAS:
        raise ValueError("Selecione um bioma brasileiro disponível.")
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / (nome + "_ibge2019.json")
    if arquivo.is_file():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    url = BIOMAS_URL + "?" + urlencode({"where": "bioma = '" + nome + "'",
        "outFields": "bioma", "returnGeometry": "true", "outSR": "4326", "f": "geojson"})
    with urlopen(url, timeout=90) as resposta:
        doc = json.load(resposta)
    if doc.get("type") != "FeatureCollection" or not doc.get("features") or doc.get("exceededTransferLimit"):
        raise ValueError("Limite oficial indisponível ou incompleto; tente novamente ou importe GeoJSON.")
    g = unary_union([shape(f["geometry"]) for f in doc["features"]])
    if g.is_empty or not g.is_valid or g.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Limite oficial inválido; importe outra delimitação.")
    dados = {"geometria": mapping(g), "origem": "IBGE Biomas 2019, 1:250.000 / IBAMA PAMGIA / " + nome + " / " + BIOMAS_URL}
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=pasta, delete=False) as tmp:
        json.dump(dados, tmp, ensure_ascii=False)
        from pathlib import Path
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
            pedido.update(resolver_regiao(req.regiao, repo.base / "catalogo_globfire" / "limites"))
        elif req.geometria is None:
            raise ValueError("Selecione uma região ou importe um GeoJSON.")
        doc = catalogo(repo.base / "catalogo_globfire", **pedido)
        for e in doc["eventos"]:
            arquivos = repo.arquivos(e["id"])
            e["local"] = {k: arquivos[k].is_file() for k in ("p1", "p2", "serie")}
        return doc
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
