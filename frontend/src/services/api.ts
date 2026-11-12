import type {
  Camada, Colecao, DadosDia, EventoListado, Linha, VisaoEvento,
} from "../types";

export const BASE_API = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ErroAPI extends Error {
  constructor(
    readonly status: number,
    readonly codigo: string,
    mensagem: string,
  ) {
    super(mensagem);
    this.name = "ErroAPI";
  }
}

async function buscarJSON<T>(
  recurso: string,
  sinal?: AbortSignal,
): Promise<T> {
  const resposta = await fetch(BASE_API + recurso, {
    signal: sinal,
    headers: { Accept: "application/json" },
  });
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const codigo = corpo?.error?.code ?? "HTTP_" + resposta.status;
    const mensagem = corpo?.error?.message ?? "Erro HTTP " + resposta.status;
    throw new ErroAPI(resposta.status, codigo, mensagem);
  }
  return corpo as T;
}

export const listarEventos = (sinal?: AbortSignal) =>
  buscarJSON<EventoListado[]>("/api/events", sinal);

export const carregarResumo = (id: number, sinal?: AbortSignal) =>
  buscarJSON<VisaoEvento>("/api/events/" + id + "/overview", sinal);

export const carregarSerie = (id: number, sinal?: AbortSignal) =>
  buscarJSON<Linha[]>("/api/events/" + id + "/series", sinal);

export const carregarTransicoes = (id: number, sinal?: AbortSignal) =>
  buscarJSON<Linha[]>("/api/events/" + id + "/transitions", sinal);

export const carregarDia = (id: number, dia: string, sinal?: AbortSignal) =>
  buscarJSON<DadosDia>(
    "/api/events/" + id + "/dates/" + encodeURIComponent(dia), sinal,
  );

export const carregarGeometria = (
  id: number, dia: string, camada: Camada, sinal?: AbortSignal,
) => buscarJSON<Colecao>(
  "/api/events/" + id + "/dates/" + encodeURIComponent(dia)
  + "/geometry?layer=" + camada, sinal,
);

export const urlSerieCSV = (id: number) =>
  BASE_API + "/api/events/" + id + "/downloads/series.csv";

export function numero(r: Linha | null | undefined, campo: string): number | null {
  const valor = r?.[campo];
  if (valor === undefined || valor === null || valor.trim() === "") return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

export function nomeDia(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return dia + "/" + mes + "/" + ano;
}

export function formatarNumero(n: number | null, casas = 2): string {
  return n === null
    ? "N/D"
    : n.toLocaleString("pt-BR", {
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      });
}
