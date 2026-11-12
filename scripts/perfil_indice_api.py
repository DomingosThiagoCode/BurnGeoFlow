"""Benchmark de indexação e leitura por data do back-end novo.

Mesma amostra/ambiente do baseline legado, usando:
 python scripts/perfil_indice_api.py --base execucoes --id 24340828
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter
import tracemalloc

from backend.app.repositories.eventos import RepositorioEventos
from backend.app.repositories.geojson_index import IndiceGeoJSON


def medir(base: Path, evento: int, repeticoes: int):
    repo = RepositorioEventos(base)
    arquivos = repo._obrigatorios(evento)
    indice = IndiceGeoJSON(arquivos["raiz"])
    # Não exclui caches existentes. Para medir indexação fria, use uma cópia
    # da execução que ainda não possua a pasta .visualizador_index.
    inicio = perf_counter()
    tracemalloc.start()
    primeira = {}
    for layer in ("p1", "p2"):
        primeira[layer] = indice.obter(layer, arquivos[layer], evento)
    primeira_ms = 1000 * (perf_counter()-inicio)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    datas = sorted(primeira["p1"][1]["datas"])
    dia = datas[-1]
    amostras = []
    nbytes = 0
    for _ in range(repeticoes):
        start = perf_counter()
        for layer in ("p1", "p2"):
            pasta, meta = indice.obter(layer, arquivos[layer], evento)
            resposta = b"".join(indice.iterar_geojson(pasta, dia))
            assert json.loads(resposta)["type"] == "FeatureCollection"
            nbytes += len(resposta)
        amostras.append(1000 * (perf_counter() - start))
    return {
        "leitor": "api_streaming_index_date",
        "id": evento, "repeticoes": repeticoes,
        "indexacao_inicial_ms": round(primeira_ms, 3),
        "latencia_repetida_data_p1_p2_mediana_ms": round(median(amostras), 3),
        "bytes_data_p1_p2": round(nbytes/repeticoes),
        "pico_indexacao_tracemalloc_mb": round(peak/1048576, 3),
        "observacao": (
            "Índice reconstruível; fase fria não inclui rede/browser. "
            "Cache pode existir de execução anterior; medir cold em cópia."
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=Path("execucoes"))
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--repeticoes", type=int, default=5)
    a = ap.parse_args()
    print(json.dumps(medir(a.base, a.id, a.repeticoes),
                     indent=2, ensure_ascii=False))
