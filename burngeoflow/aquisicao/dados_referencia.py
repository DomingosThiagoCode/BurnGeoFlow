"""Obtém amostra pública de regressão do CDG_incendio, com SHA Git."""
from __future__ import annotations

from hashlib import sha1
from pathlib import Path
from urllib.request import urlopen

URL = ("https://raw.githubusercontent.com/DomingosThiagoCode/"
       "CDG_incendio/main/dados/estudo_caso_24340828/")
BLOBS = {
    "P1_componentes_24340828.geojson": "735135843c49113fdfd971a40ce869379a2aab74",
    "P2_regiao_movel_24340828.geojson": "772ab8a22500b8283b0f13b984399b34b64cd3c3",
}


def git_hash(dados: bytes) -> str:
    return sha1(f"blob {len(dados)}\0".encode() + dados).hexdigest()


def baixar_referencia(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    for nome, esperado in BLOBS.items():
        arquivo = destino / nome
        if arquivo.is_file() and git_hash(arquivo.read_bytes()) == esperado:
            continue
        if arquivo.exists():
            raise ValueError(f"Arquivo modificado: {arquivo}; não será sobrescrito.")
        with urlopen(URL + nome, timeout=90) as resposta:
            conteudo = resposta.read()
        if git_hash(conteudo) != esperado:
            raise ValueError(f"Hash inesperado no download de {nome}.")
        temporario = arquivo.with_suffix(".geojson.tmp")
        temporario.write_bytes(conteudo)
        temporario.replace(arquivo)
