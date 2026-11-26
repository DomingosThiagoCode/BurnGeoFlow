from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from backend.app.api.jobs import verificacao_mutacao
from burngeoflow.aquisicao.catalogo import catalogo, total_evento

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])

class Consulta(BaseModel):
    geometria: dict
    origem: str = Field(min_length=1, max_length=500)
    inicio: str
    fim: str
    margem: int = Field(default=0, ge=0, le=365)
    atualizar: bool = False

@router.post("", dependencies=[Depends(verificacao_mutacao)])
def consultar(req: Consulta, request: Request):
    repo = request.app.state.repositorio
    try:
        doc = catalogo(repo.base / "catalogo_globfire", **req.model_dump())
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
