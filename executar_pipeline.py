"""BurnGeoFlow 7.1: orquestrador do processamento local.

A aquisição automática pelo GEE será integrada na Etapa 7.2.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


class ErroPipeline(RuntimeError):
    pass


@dataclass(frozen=True)
class Etapa:
    nome: str
    comando: list[str]
    artefatos: tuple[Path, ...]
    stdout_json: Path | None = None


def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def salvar_json(path: Path, dados: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    tmp.replace(path)


def preparar_dados(id_: int, pasta: Path, p1_arg: Path | None,
                   p2_arg: Path | None, baixar_exemplo: bool) -> tuple[Path, Path, dict]:
    if (p1_arg is None) != (p2_arg is None):
        raise ErroPipeline("--p1 e --p2 devem ser usados juntos.")
    origem = ROOT / "dados" / f"estudo_caso_{id_}"
    p1 = (p1_arg or origem / f"P1_componentes_{id_}.geojson").resolve()
    p2 = (p2_arg or origem / f"P2_regiao_movel_{id_}.geojson").resolve()
    if baixar_exemplo:
        if id_ != 24340828 or p1_arg is not None:
            raise ErroPipeline("--baixar-exemplo é exclusivo do ID 24340828 sem --p1/--p2.")
        from burngeoflow.aquisicao.dados_referencia import baixar_referencia
        baixar_referencia(origem)
    faltam = [str(p) for p in (p1, p2) if not p.is_file()]
    if faltam:
        raise ErroPipeline("GeoJSON não encontrado: " + ", ".join(faltam)
                           + ". Informe --p1/--p2 ou use --baixar-exemplo.")
    local = pasta / "dados" / f"estudo_caso_{id_}"
    local.mkdir(parents=True, exist_ok=True)
    destinos = []
    for entrada, nome in (
        (p1, f"P1_componentes_{id_}.geojson"),
        (p2, f"P2_regiao_movel_{id_}.geojson")
    ):
        destino = local / nome
        if destino.resolve() != entrada:
            if not destino.is_file() or digest(destino) != digest(entrada):
                shutil.copy2(entrada, destino)
        destinos.append(destino)
    a, b = destinos
    return a, b, {"p1": digest(a), "p2": digest(b)}


def definir_etapas(id_: int, raiz: Path, p1: Path, p2: Path) -> tuple[Etapa, ...]:
    dirs = {n: raiz / "resultados" / f"etapa{n}" for n in range(1, 7)}
    def py(modulo: str) -> list[str]:
        return [sys.executable, "-m", f"burngeoflow.{modulo}"]
    e1, e2, e3, e4, e5, e6 = [dirs[n] for n in range(1, 7)]
    return (
        Etapa("validar", py("validacao.produtos") + [str(p1), str(p2)],
              (e1 / f"validacao_{id_}.json",), e1 / f"validacao_{id_}.json"),
        Etapa("auditar", py("validacao.espacial") + [str(p1), str(p2),
              "--saida-json", str(e1 / f"auditoria_{id_}.json")],
              (e1 / f"auditoria_{id_}.json",)),
        Etapa("regularizar_diagnostico", py("validacao.regularizacao") +
              [str(p1), str(p2), "--saida-json", str(e1 / f"regularizacao_{id_}.json")],
              (e1 / f"regularizacao_{id_}.json",)),
        Etapa("paisagem", py("analises.paisagem") +
              [str(p1), "--saida", str(e2)],
              (e2 / f"metricas_patches_{id_}.csv",
               e2 / f"metricas_temporais_{id_}.csv",
               e2 / f"sensibilidade_contato_{id_}.csv")),
        Etapa("linhagens", py("processamento.linhagens") +
              [str(p1), "--saida", str(e3)],
              (e3 / f"resumo_transicoes_{id_}.csv",)),
        Etapa("tr_igt", py("analises.tr_igt") +
              [str(p1), str(p2), "--saida", str(e4)],
              (e4 / f"indicadores_regiao_{id_}.csv",
               e4 / f"incrementos_temporais_{id_}.csv",
               e4 / f"comparacao_tr_igt_{id_}.csv")),
        Etapa("integrar", py("analises.integracao") +
              ["--id", str(id_), "--raiz", str(raiz), "--saida", str(e5)],
              (e5 / f"serie_diaria_integrada_{id_}.csv",
               e5 / f"transicoes_integradas_{id_}.csv",
               e5 / f"relatorio_interpretativo_{id_}.md")),
        Etapa("robustez", py("validacao.robustez") +
              ["--id", str(id_), "--raiz", str(raiz), "--saida", str(e6)],
              (e6 / f"resumo_validacao_{id_}.json",
               e6 / f"relatorio_validacao_{id_}.md")),
    )


def executar(id_: int, *, saida: Path, p1: Path | None = None, p2: Path | None = None,
            baixar_exemplo: bool = False, refazer: bool = False) -> dict:
    if id_ <= 0:
        raise ErroPipeline("ID deve ser positivo.")
    raiz = saida.resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    a, b, hashes = preparar_dados(id_, raiz, p1, p2, baixar_exemplo)
    manifesto_path = raiz / "execucao.json"
    anterior = {}
    if manifesto_path.is_file():
        try:
            anterior = json.loads(manifesto_path.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            raise ErroPipeline(f"Manifesto inválido: {exc}") from exc
        if anterior.get("id_incendio") != id_:
            raise ErroPipeline("Pasta já utilizada por outro incêndio.")
    etapas_anteriores = (
        anterior.get("etapas", {})
        if anterior.get("entradas_sha256") == hashes and not refazer else {}
    )
    manifesto = {
        "software": "BurnGeoFlow", "versao": "7.1.0",
        "id_incendio": id_, "origem": "GeoJSON local",
        "entradas_sha256": hashes, "inicio_utc": agora(),
        "ressalva": "Auditoria geométrica interna, não validação física por sensores.",
        "etapas": etapas_anteriores,
    }
    salvar_json(manifesto_path, manifesto)
    logs = raiz / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for etapa in definir_etapas(id_, raiz, a, b):
        estado = manifesto["etapas"].get(etapa.nome, {})
        if not refazer and estado.get("status") == "concluido" and all(
            f.is_file() and f.stat().st_size > 0 for f in etapa.artefatos
        ):
            print(f"[REUSO] {etapa.nome}", flush=True)
            continue
        print(f"[EXEC] {etapa.nome}", flush=True)
        for arquivo in etapa.artefatos:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            if arquivo.is_file():
                arquivo.unlink()  # Evita aceitar arquivo antigo se a etapa nao escrever novo.
        resultado = subprocess.run(
            etapa.comando, cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False
        )
        (logs / f"{etapa.nome}.log").write_text(
            "COMANDO: " + " ".join(etapa.comando) +
            "\n\nSTDOUT:\n" + resultado.stdout +
            "\n\nSTDERR:\n" + resultado.stderr, encoding="utf8"
        )
        erro_json = None
        if resultado.returncode == 0 and etapa.stdout_json is not None:
            try:
                salvar_json(etapa.stdout_json, json.loads(resultado.stdout))
            except (TypeError, ValueError) as exc:
                erro_json = str(exc)
        faltantes = [str(p) for p in etapa.artefatos
                    if not p.is_file() or p.stat().st_size == 0]
        if resultado.returncode != 0 or faltantes or erro_json:
            manifesto["etapas"][etapa.nome] = {
                "status": "falha", "codigo": resultado.returncode,
                "faltantes": faltantes, "erro_json": erro_json,
            }
            salvar_json(manifesto_path, manifesto)
            raise ErroPipeline(
                f"Falha em '{etapa.nome}'; consulte {logs / (etapa.nome + '.log')}"
            )
        manifesto["etapas"][etapa.nome] = {
            "status": "concluido",
            "artefatos": [str(p.relative_to(raiz)) for p in etapa.artefatos],
            "fim_utc": agora(),
        }
        salvar_json(manifesto_path, manifesto)
        print(f"[OK] {etapa.nome}", flush=True)
    manifesto["fim_utc"] = agora()
    salvar_json(manifesto_path, manifesto)
    print(f"[CONCLUIDO] {raiz}")
    return manifesto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--origem", choices=("local", "gee"), default="local")
    ap.add_argument("--p1", type=Path)
    ap.add_argument("--p2", type=Path)
    ap.add_argument("--saida", type=Path, help="Pasta da execução")
    ap.add_argument("--baixar-exemplo", action="store_true")
    ap.add_argument("--refazer", action="store_true")
    args = ap.parse_args(argv)
    if args.origem == "gee":
        print("[PENDENTE] Etapa 7.2: integração GEE ainda não implementada.",
              file=sys.stderr)
        return 2
    try:
        executar(args.id, saida=args.saida or ROOT / "execucoes" / str(args.id),
                 p1=args.p1, p2=args.p2,
                 baixar_exemplo=args.baixar_exemplo, refazer=args.refazer)
    except (ErroPipeline, OSError, ValueError) as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
