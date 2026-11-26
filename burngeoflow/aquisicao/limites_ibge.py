"""Limites administrativos oficiais IBGE (UF e Brasil) para descoberta GlobFire.

A consulta baixa apenas a malha vetorial pública IBGE 2024 uma vez; não
consulta o Earth Engine, não altera geometrias P1/P2 e não executa análise.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen
from zipfile import ZipFile

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

URL_IBGE_UF = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2024/"
    "Brasil/BR_UF_2024.zip"
)
UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}
CODIGOS_IBGE = {
    "AC": "12", "AL": "27", "AP": "16", "AM": "13", "BA": "29",
    "CE": "23", "DF": "53", "ES": "32", "GO": "52", "MA": "21",
    "MT": "51", "MS": "50", "MG": "31", "PA": "15", "PB": "25",
    "PR": "41", "PE": "26", "PI": "22", "RJ": "33", "RN": "24",
    "RS": "43", "RO": "11", "RR": "14", "SC": "42", "SP": "35",
    "SE": "28", "TO": "17",
}
LIMITE_ZIP_BYTES = 50 * 1024 * 1024
LIMITE_MEMBRO_BYTES = 100 * 1024 * 1024


def _gravar_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as arq:
        json.dump(obj, arq, ensure_ascii=False)
        temp = Path(arq.name)
    temp.replace(path)


def _arquivo_ibge(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "BR_UF_2024.zip"
    if destino.is_file():
        return destino
    # Leitura com limite. ZIP nunca é descompactado no filesystem:
    # impede path traversal e arquivos escritos fora da pasta do catálogo.
    with urlopen(
        Request(URL_IBGE_UF, headers={"User-Agent": "BurnGeoFlow/1.0"}),
        timeout=120,
    ) as resposta:
        bruto = resposta.read(LIMITE_ZIP_BYTES + 1)
    if len(bruto) > LIMITE_ZIP_BYTES:
        raise ValueError("Malha IBGE ultrapassou o limite de 50 MiB compactados.")
    with ZipFile(BytesIO(bruto)) as z:
        if z.testzip():
            raise ValueError("Arquivo ZIP da malha IBGE está corrompido.")
    with NamedTemporaryFile(dir=pasta, delete=False) as arq:
        arq.write(bruto)
        temp = Path(arq.name)
    temp.replace(destino)
    return destino


def _shapefile_ibge(zip_path: Path):
    with ZipFile(zip_path) as z:
        arquivos = {n.lower(): n for n in z.namelist()}
        candidatos = [
            n for n in z.namelist() if n.lower().endswith("br_uf_2024.shp")
        ]
        if len(candidatos) != 1:
            raise ValueError("ZIP IBGE não contém uma única camada BR_UF_2024.")
        raiz = candidatos[0][:-4].lower()
        necessarios = {e: arquivos.get(raiz + e) for e in (".shp", ".dbf", ".prj")}
        if not all(necessarios.values()):
            raise ValueError("ZIP IBGE sem SHP, DBF ou PRJ da camada de estados.")
        for nome in necessarios.values():
            if z.getinfo(nome).file_size > LIMITE_MEMBRO_BYTES:
                raise ValueError("Membro ZIP da malha IBGE excede 100 MiB.")
        shp = z.read(necessarios[".shp"])
        dbf = z.read(necessarios[".dbf"])
        crs = CRS.from_wkt(z.read(necessarios[".prj"]).decode("utf-8-sig"))
    return shp, dbf, crs


def resolver_uf_ou_brasil(regiao: str, pasta: Path) -> dict:
    """Região = Brasil ou UF:RJ (somente unidades oficiais do Brasil)."""
    if regiao != "Brasil":
        if not regiao.startswith("UF:") or regiao[3:] not in UFS:
            raise ValueError("Escolha Brasil ou uma UF válida (UF:RJ, por exemplo).")
        uf = regiao[3:]
    else:
        uf = None
    etiqueta = "brasil" if uf is None else "uf_" + uf.lower()
    destino = pasta / f"malha_ibge_2024_{etiqueta}.json"
    if destino.is_file():
        resultado = json.loads(destino.read_text(encoding="utf-8"))
        if (
            not isinstance(resultado, dict)
            or "geometria" not in resultado
            or "origem" not in resultado
        ):
            raise ValueError("Cache de limite IBGE inválido.")
        return resultado

    shp, dbf, crs = _shapefile_ibge(_arquivo_ibge(pasta))
    projetar = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    shapes = []
    with shapefile.Reader(shp=BytesIO(shp), dbf=BytesIO(dbf), encoding="latin1") as leitor:
        for registro in leitor.iterShapeRecords():
            props = {k.upper(): str(v).strip() for k, v in registro.record.as_dict().items()}
            if uf is not None and not (
                props.get("SIGLA_UF", "").upper() == uf
                or props.get("CD_UF", "") == CODIGOS_IBGE[uf]
            ):
                continue
            geom = transform(projetar, shape(registro.shape.__geo_interface__))
            if not geom.is_empty:
                shapes.append(geom)
    if not shapes:
        raise ValueError("A malha IBGE não contém a UF solicitada.")
    geometria = unary_union(shapes)
    if (
        geometria.geom_type not in ("Polygon", "MultiPolygon")
        or geometria.is_empty or not geometria.is_valid
    ):
        raise ValueError("Limite IBGE inválido após reprojeção.")
    descricao = "Brasil" if uf is None else f"{UFS[uf]} ({uf})"
    resultado = {
        "geometria": mapping(geometria),
        "origem": "IBGE Malha Territorial 2024 / " + descricao + " / " + URL_IBGE_UF,
    }
    _gravar_json(destino, resultado)
    return resultado
