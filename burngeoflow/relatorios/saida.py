"""Síntese do manifesto de execução."""
from __future__ import annotations

def resumo_etapas(manifesto: dict) -> dict:
    etapas = manifesto.get("etapas", {})
    return {
        "id_incendio": manifesto.get("id_incendio"),
        "concluidas": sorted(n for n, r in etapas.items() if r.get("status") == "concluido"),
        "com_falha": sorted(n for n, r in etapas.items() if r.get("status") == "falha")
    }
