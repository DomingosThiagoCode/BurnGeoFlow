import { BASE_API, ErroAPI } from "./api";

export type OrigemJob = "auto" | "local" | "gee" | "brutos";
export type EstadoJob = "queued" | "running" | "completed" | "failed" | "interrupted";

export interface ExecucaoJob {
  id: string;
  incendio: number;
  origem: OrigemJob;
  ano: number | null;
  status: EstadoJob;
  pid: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  exit_code: number | null;
  error: string | null;
}

export interface PedidoJob {
  id_incendio: number;
  origem: OrigemJob;
  ano: number | null;
}

export interface LogsJob {
  job_id: string;
  lines: string[];
  truncated: boolean;
}

async function requisitar<T>(
  url: string, sinal?: AbortSignal, inicio?: RequestInit,
): Promise<T> {
  const resposta = await fetch(BASE_API + url, {
    ...inicio,
    headers: {
      Accept: "application/json",
      ...(inicio?.body ? { "Content-Type": "application/json" } : {}),
    },
    signal: sinal,
  });
  const body = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const erro = body?.error ?? {};
    throw new ErroAPI(
      resposta.status,
      erro.code ?? "HTTP_" + resposta.status,
      erro.message ?? body?.detail ?? "Falha na operação",
    );
  }
  return body as T;
}

export function listarJobs(signal?: AbortSignal) {
  return requisitar<ExecucaoJob[]>("/api/jobs", signal);
}

export function criarJob(pedido: PedidoJob, signal?: AbortSignal) {
  return requisitar<ExecucaoJob>("/api/jobs", signal, {
    method: "POST", body: JSON.stringify(pedido),
  });
}

export function logsJob(jobId: string, signal?: AbortSignal) {
  return requisitar<LogsJob>(
    "/api/jobs/" + encodeURIComponent(jobId) + "/logs", signal,
  );
}
