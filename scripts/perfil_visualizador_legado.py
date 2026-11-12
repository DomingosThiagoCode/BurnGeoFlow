"""Perfil reproduzível do leitor legado de GeoJSON, sem alterar entradas.

Após executar o caso de referência:
 python scripts/perfil_visualizador_legado.py --base . --id 24340828
Para o cache local:
 python scripts/perfil_visualizador_legado.py --base execucoes --id 24340828

Os tempos dependem dos dados, disco e máquina: não são uma promessa de SLA.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burngeoflow.visualizacao.dados import carregar_evento, camada_dia


def medir(base: Path, evento: int, repeticoes: int) -> dict:
    if repeticoes < 1:
        raise ValueError("repetições devem ser positivas")
    fria, por_data, tamanhos = [], [], []
    peak = 0
    for _ in range(repeticoes):
        tracemalloc.start()
        t0 = perf_counter()
        registro = carregar_evento(base, evento)
        t1 = perf_counter()
        dia = registro["datas"][-1]
        bruto = json.dumps(
            camada_dia(registro, dia), separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        t2 = perf_counter()
        _, p = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        fria.append(1000 * (t1-t0))
        por_data.append(1000*(t2-t1))
        tamanhos.append(len(bruto))
        peak = max(peak, p)
    return {
        "leitor": "legacy_carregar_evento_json_load",
        "id": evento,
        "repeticoes": repeticoes,
        "abertura_frio_mediana_ms": round(median(fria), 3),
        "serializacao_ultima_data_mediana_ms": round(median(por_data), 3),
        "resposta_ultima_data_bytes": round(median(tamanhos)),
        "pico_tracemalloc_mb": round(peak/1048576, 3),
        "observacao": (
            "tracemalloc mede alocações Python; não mede GPU, browser,"
            " heap nativo ou latência HTTP."
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=ROOT/"execucoes")
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--repeticoes", type=int, default=3)
    args = ap.parse_args()
    print(json.dumps(
        medir(args.base, args.id, args.repeticoes),
        indent=2, ensure_ascii=False,
    ))
