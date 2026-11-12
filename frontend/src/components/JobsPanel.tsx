import {
  type FormEvent, useCallback, useEffect, useRef, useState,
} from "react";
import {
  Activity, AlertCircle, CheckCircle2, ChevronDown, Clock3,
  Database, LoaderCircle, Play, RefreshCw, Terminal,
} from "lucide-react";
import {
  criarJob, listarJobs, logsJob, type ExecucaoJob, type OrigemJob,
} from "../services/jobs";

type Props = {
  eventoId: number | null;
  onConcluiu: (idIncendio: number) => void;
};

const NOMES: Record<ExecucaoJob["status"], string> = {
  queued: "Na fila",
  running: "Executando",
  completed: "Concluído",
  failed: "Falhou",
  interrupted: "Interrompido",
};

const ESTADOS_ATIVOS = new Set(["queued", "running"]);

export function JobsPanel({ eventoId, onConcluiu }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [idDigitado, setIdDigitado] = useState("");
  const [origem, setOrigem] = useState<OrigemJob>("auto");
  const [ano, setAno] = useState("");
  const [jobs, setJobs] = useState<ExecucaoJob[]>([]);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [linhas, setLinhas] = useState<string[]>([]);
  const [truncado, setTruncado] = useState(false);
  const [criando, setCriando] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const ultimoEstado = useRef(new Map<string, string>());
  const callback = useRef(onConcluiu);
  callback.current = onConcluiu;

  useEffect(() => {
    if (eventoId !== null) setIdDigitado(String(eventoId));
  }, [eventoId]);

  const atualizar = useCallback(async (signal?: AbortSignal) => {
    const resposta = await listarJobs(signal);
    if (signal?.aborted) return;
    for (const job of resposta) {
      const anterior = ultimoEstado.current.get(job.id);
      if (
        anterior && ESTADOS_ATIVOS.has(anterior)
        && job.status === "completed"
      ) {
        callback.current(job.incendio);
        setAviso(
          "Pipeline do incêndio " + job.incendio
          + " concluído. Resultados atualizados.",
        );
      }
      ultimoEstado.current.set(job.id, job.status);
    }
    setJobs(resposta);
    setSelecionado((prev) => prev ?? resposta[0]?.id ?? null);
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    setCarregando(true);
    atualizar(ctrl.signal).catch((err: unknown) => {
      if (ctrl.signal.aborted) return;
      setErro(
        err instanceof Error ? err.message
        : "Não foi possível consultar execuções.",
      );
    }).finally(() => {
      if (!ctrl.signal.aborted) setCarregando(false);
    });
    return () => ctrl.abort();
  }, [atualizar]);

  useEffect(() => {
    if (!expanded) return;
    const ctrl = new AbortController();
    const polling = () => {
      atualizar(ctrl.signal).catch(() => undefined);
    };
    polling();
    const intervalo = window.setInterval(polling, 2500);
    return () => {
      ctrl.abort();
      window.clearInterval(intervalo);
    };
  }, [expanded, atualizar]);

  useEffect(() => {
    if (!expanded || !selecionado) return;
    const ctrl = new AbortController();
    const polling = async () => {
      try {
        const dados = await logsJob(selecionado, ctrl.signal);
        if (ctrl.signal.aborted) return;
        setLinhas(dados.lines);
        setTruncado(dados.truncated);
      } catch (err) {
        if (!ctrl.signal.aborted) setErro(
          err instanceof Error ? err.message : "Falha lendo os logs",
        );
      }
    };
    polling();
    const intervalo = window.setInterval(polling, 3000);
    return () => {
      ctrl.abort();
      window.clearInterval(intervalo);
    };
  }, [expanded, selecionado]);

  const atual = jobs.find(j => j.id === selecionado) ?? null;
  const emExecucao = jobs.some(j => ESTADOS_ATIVOS.has(j.status));

  async function iniciar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = Number(idDigitado.trim());
    const anoValido = !ano.trim() || (
      Number.isSafeInteger(Number(ano)) &&
      Number(ano) >= 2001 && Number(ano) <= 2020
    );
    if (!Number.isSafeInteger(id) || id <= 0 || id > 2147483647) {
      setErro("O ID precisa ser um inteiro positivo.");
      return;
    }
    if (!anoValido) {
      setErro("Ano opcional deve estar entre 2001 e 2020.");
      return;
    }
    setErro(null);
    setAviso(null);
    setCriando(true);
    try {
      const req = {
        id_incendio: id, origem,
        ano: ano.trim() && (origem === "auto" || origem === "gee")
          ? Number(ano) : null,
      };
      const novo = await criarJob(req);
      ultimoEstado.current.set(novo.id, novo.status);
      setSelecionado(novo.id);
      setExpanded(true);
      setAviso("Tarefa criada. Acompanhe o estado e os logs abaixo.");
      await atualizar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao criar execução");
    } finally {
      setCriando(false);
    }
  }

  return (
    <section className="jobs-panel">
      <button
        type="button" className="jobs-head"
        aria-expanded={expanded}
        aria-controls="jobs-body"
        onClick={() => setExpanded(v => !v)}
      >
        <div className="jobs-head-icon"><Database size={20}/></div>
        <span className="jobs-head-copy">
          <strong>Processar e acompanhar eventos</strong>
          <small>
            Aquisição GEE, reuso do cache e execução das análises, sem sair do painel
          </small>
        </span>
        {emExecucao && <span className="jobs-active-badge">
          <Activity size={13}/> Execução em andamento
        </span>}
        <ChevronDown size={19} className={expanded ? "jobs-open-arrow" : ""}/>
      </button>
      {expanded && <div className="jobs-body" id="jobs-body">
        <form onSubmit={iniciar} className="jobs-form">
          <div className="jobs-form-field">
            <label htmlFor="job-fire-id">ID GlobFire</label>
            <input id="job-fire-id" required inputMode="numeric"
              value={idDigitado} onChange={e => setIdDigitado(e.target.value)}
              placeholder="Ex.: 24340828"/>
          </div>
          <div className="jobs-form-field">
            <label htmlFor="job-origin">Origem dos dados</label>
            <select id="job-origin" value={origem}
              onChange={e => setOrigem(e.target.value as OrigemJob)}>
              <option value="auto">Automática (reusar cache ou consultar GEE)</option>
              <option value="local">Somente dados locais</option>
              <option value="gee">Consultar Earth Engine</option>
              <option value="brutos">Revalidar extração GEE bruta</option>
            </select>
          </div>
          <div className="jobs-form-field jobs-year">
            <label htmlFor="job-year">Ano (opcional)</label>
            <input id="job-year" type="number" inputMode="numeric"
              min={2001} max={2020} placeholder="Ex.: 2020"
              value={ano} onChange={e => setAno(e.target.value)}
              disabled={origem === "local" || origem === "brutos"}/>
          </div>
          <button type="submit" className="job-start"
            disabled={criando || emExecucao}>
            {criando ? <LoaderCircle className="spin" size={16}/> :
              <Play size={15}/>}
            {criando ? "Iniciando" : "Executar"}
          </button>
        </form>

        <p className="jobs-warning">
          <AlertCircle size={15}/>
          Uma execução ativa por vez. A autenticação do GEE precisa estar
          configurada previamente no computador. Os logs não fornecem um
          percentual confiável do processamento remoto.
        </p>
        {erro && <div className="job-error" role="alert">{erro}</div>}
        {aviso && <div className="job-success" role="status">{aviso}</div>}
        <div className="jobs-history-head">
          <div><Clock3 size={16}/><strong>Histórico operacional</strong></div>
          <button type="button" className="jobs-refresh" disabled={carregando}
            onClick={() => atualizar().catch(err=>setErro(String(err)))}>
            <RefreshCw size={15}/> Atualizar
          </button>
        </div>
        {!jobs.length && <p className="jobs-empty">
          Nenhuma execução cadastrada. A CLI continua disponível para uso manual.
        </p>}
        {jobs.length > 0 && (
          <div className="jobs-history">
            {jobs.slice(0,8).map(j => <button
              key={j.id} type="button"
              className={"job-history-item " + (selecionado === j.id ? "job-selected" : "")}
              onClick={() => setSelecionado(j.id)}
            >
              <span>ID {j.incendio} · {j.origem}</span>
              <strong className={"job-status job-status-" + j.status}>
                {j.status === "completed" && <CheckCircle2 size={13}/>}
                {j.status === "running" && <LoaderCircle className="spin" size={13}/>}
                {NOMES[j.status]}
              </strong>
            </button>)}
          </div>
        )}
        {atual && <div className="job-log-area">
          <div className="jobs-history-head">
            <div><Terminal size={16}/><strong>Log da tarefa {atual.id.slice(0,8)}</strong></div>
            <span className="job-exit">Código: {atual.exit_code ?? "em andamento"}</span>
          </div>
          <pre aria-label="Mensagens da execução" className="job-logs">
            {truncado && "... parte inicial omitida ...\n"}
            {linhas.length ? linhas.join("\n") : "Aguardando mensagens do processo..."}
          </pre>
          {atual.error && <div className="job-error">{atual.error}</div>}
        </div>}
      </div>}
    </section>
  );
}
