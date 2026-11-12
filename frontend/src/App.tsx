import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, AlertCircle, ArrowDownToLine, BarChart3, CheckCircle2,
  ChevronLeft, ChevronRight, Database, Flame, Layers, LoaderCircle,
  Menu, Pause, Play, RefreshCw, Search, X,
} from "lucide-react";
import { LineChart, type SerieGrafico } from "./components/LineChart";
import { MapPanel } from "./components/MapPanel";
import { JobsPanel } from "./components/JobsPanel";
import {
  carregarGeometria, carregarResumo, carregarSerie, carregarTransicoes,
  formatarNumero, listarEventos, nomeDia, numero, urlSerieCSV,
} from "./services/api";
import type { Camada, Colecao, EventoListado, Linha, VisaoEvento } from "./types";

const CORES = { p1: "#db8750", p2: "#168f86", suporte: "#5276a8" };

function textoErro(erro: unknown): string {
  return erro instanceof Error ? erro.message : "Falha inesperada";
}

function Kpi({
  rotulo, valor, detalhe, classe,
}: {
  rotulo: string; valor: string; detalhe?: string; classe?: string;
}) {
  return (
    <div className={"kpi-card " + (classe ?? "")}>
      <span className="kpi-label">{rotulo}</span>
      <strong className="kpi-value">{valor}</strong>
      {detalhe && <span className="kpi-detail">{detalhe}</span>}
    </div>
  );
}

export default function App() {
  const [lista, setLista] = useState<EventoListado[]>([]);
  const [id, setId] = useState<number | null>(null);
  const [revisao, setRevisao] = useState(0);
  const [buscaId, setBuscaId] = useState("");
  const [buscando, setBuscando] = useState(true);
  const [painelAberto, setPainelAberto] = useState(false);
  const [resumo, setResumo] = useState<VisaoEvento | null>(null);
  const [serie, setSerie] = useState<Linha[]>([]);
  const [transicoes, setTransicoes] = useState<Linha[]>([]);
  const [data, setData] = useState("");
  const [p1Ativo, setP1Ativo] = useState(true);
  const [p2Ativo, setP2Ativo] = useState(true);
  const [mapaBase, setMapaBase] = useState(true);
  const [p1, setP1] = useState<Colecao | null>(null);
  const [p2, setP2] = useState<Colecao | null>(null);
  const [carregandoEvento, setCarregandoEvento] = useState(false);
  const [carregandoMapa, setCarregandoMapa] = useState(false);
  const [erroEvento, setErroEvento] = useState<string | null>(null);
  const [erroMapa, setErroMapa] = useState<string | null>(null);
  const [mensagem, setMensagem] = useState("");
  const [tocando, setTocando] = useState(false);
  const cache = useRef(new Map<string, Colecao>());

  const atualizarLista = useCallback(() => {
    const abort = new AbortController();
    setBuscando(true);
    listarEventos(abort.signal)
      .then((itens) => {
        setLista(itens);
        setErroEvento(null);
        setId((prev) => prev ?? (itens.length ? itens[0].id_incendio : null));
      })
      .catch((err) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setErroEvento("Não foi possível acessar a API: " + textoErro(err));
      })
      .finally(() => setBuscando(false));
    return () => abort.abort();
  }, []);

  useEffect(() => {
    return atualizarLista();
  }, [atualizarLista]);

  useEffect(() => {
    if (id === null) return;
    const abort = new AbortController();
    setCarregandoEvento(true);
    setErroEvento(null);
    setResumo(null);
    setSerie([]);
    setTransicoes([]);
    setP1(null);
    setP2(null);
    setData("");
    setTocando(false);
    Promise.all([
      carregarResumo(id, abort.signal),
      carregarSerie(id, abort.signal),
      carregarTransicoes(id, abort.signal),
    ])
      .then(([info, rows, trs]) => {
        if (abort.signal.aborted) return;
        setResumo(info);
        setSerie(rows);
        setTransicoes(trs);
        setData(info.datas[info.datas.length - 1] ?? "");
      })
      .catch((err) => {
        if (abort.signal.aborted) return;
        setErroEvento(textoErro(err));
      })
      .finally(() => {
        if (!abort.signal.aborted) setCarregandoEvento(false);
      });
    return () => abort.abort();
  }, [id, revisao]);

  const obterCamada = useCallback(async (
    identificador: number, dia: string, camada: Camada,
    signal?: AbortSignal,
  ): Promise<Colecao> => {
    const chave = identificador + ":" + dia + ":" + camada;
    const valor = cache.current.get(chave);
    if (valor) return valor;
    const dados = await carregarGeometria(identificador, dia, camada, signal);
    // Cache de poucas datas para não reter todas as coordenadas em RAM.
    cache.current.set(chave, dados);
    if (cache.current.size > 12) {
      const primeira = cache.current.keys().next().value;
      if (primeira !== undefined) cache.current.delete(primeira);
    }
    return dados;
  }, []);

  useEffect(() => {
    if (id === null || !data || !resumo) return;
    const ctrl = new AbortController();
    setCarregandoMapa(true);
    setErroMapa(null);
    setP1(null);
    setP2(null);
    Promise.all([
      p1Ativo ? obterCamada(id, data, "p1", ctrl.signal) : Promise.resolve(null),
      p2Ativo ? obterCamada(id, data, "p2", ctrl.signal) : Promise.resolve(null),
    ])
      .then(([a, b]) => {
        if (!ctrl.signal.aborted) {
          setP1(a);
          setP2(b);
        }
      })
      .catch((erro) => {
        if (ctrl.signal.aborted) return;
        setErroMapa("Falha no mapa: " + textoErro(erro));
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setCarregandoMapa(false);
      });
    return () => ctrl.abort();
  }, [id, data, resumo, p1Ativo, p2Ativo, obterCamada]);

  useEffect(() => {
    if (!tocando || !resumo || !data) return;
    const timer = window.setInterval(() => {
      setData((dia) => {
        const indice = resumo.datas.indexOf(dia);
        if (indice < 0 || indice >= resumo.datas.length-1) {
          setTocando(false);
          return dia;
        }
        return resumo.datas[indice+1];
      });
    }, 1300);
    return () => window.clearInterval(timer);
  }, [tocando, resumo, data]);

  const indice = resumo ? resumo.datas.indexOf(data) : -1;
  const linha = useMemo(
    () => serie.find((r) => r.data === data) ?? null, [serie, data],
  );
  const transicao = useMemo(
    () => transicoes.find((r) => r.data_atual === data) ?? null,
    [transicoes, data],
  );
  const areaP1 = numero(linha, "area_total_laea_km2");
  const areaP2 = numero(linha, "p2_area_laea_km2");
  const dominancia = numero(linha, "dominancia_cobertura_p2_pct");
  const patches = numero(linha, "numero_patches");

  const linhasArea: SerieGrafico[] = useMemo(() => [
    { label: "Cobertura P1", cor: CORES.p1, valores: serie.map(r => numero(r, "area_total_laea_km2")) },
    { label: "Região P2", cor: CORES.p2, valores: serie.map(r => numero(r, "p2_area_laea_km2")) },
  ], [serie]);
  const linhasPatches: SerieGrafico[] = useMemo(() => [
    { label: "Nº de patches", cor: CORES.suporte, valores: serie.map(r => numero(r, "numero_patches")) },
  ], [serie]);
  const linhasIncrementos: SerieGrafico[] = useMemo(() => [
    { label: "Área nova no evento", cor: CORES.p1, valores: transicoes.map(r => numero(r, "area_nova_evento_km2")) },
    { label: "Já queimada incorporada ao P2", cor: CORES.p2, valores: transicoes.map(r => numero(r, "p2_incremento_ja_queimado_km2")) },
  ], [transicoes]);

  function escolherId(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const n = Number(buscaId.trim());
    if (!Number.isSafeInteger(n) || n <= 0) {
      setMensagem("Informe um ID inteiro positivo.");
      return;
    }
    setId(n);
    setMensagem("");
    setPainelAberto(false);
  }

  async function exportarGeoJSON() {
    if (id === null || !data) return;
    try {
      setMensagem("Preparando download das duas camadas...");
      const [a, b] = await Promise.all([
        obterCamada(id, data, "p1"),
        obterCamada(id, data, "p2"),
      ]);
      const geo: Colecao = {
        type: "FeatureCollection", features: [...a.features, ...b.features],
      };
      const url = URL.createObjectURL(new Blob(
        [JSON.stringify(geo)], { type: "application/geo+json" },
      ));
      const link = document.createElement("a");
      link.href = url;
      link.download = "BurnGeoFlow_" + id + "_" + data + "_P1_P2.geojson";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 5000);
      setMensagem("GeoJSON preparado.");
    } catch (erro) {
      setMensagem("Falha no download: " + textoErro(erro));
    }
  }

  const aoConcluirJob = useCallback((incendio: number) => {
    cache.current.clear();
    setId(incendio);
    setRevisao(n => n + 1);
    atualizarLista();
  }, [atualizarLista]);

  const cmd = id ? "python executar_pipeline.py --id " + id + " --origem gee" : "";
  const existeErro = Boolean(erroEvento);
  const navegaPara = (passo: number) => {
    if (!resumo) return;
    setData(resumo.datas[Math.max(0, Math.min(
      resumo.datas.length-1, indice + passo,
    ))]);
  };

  return (
    <div className="application">
      <header className="global-header">
        <div className="brand">
          <span className="brand-icon"><Flame size={21} strokeWidth={2.2}/></span>
          <div>
            <strong>BurnGeoFlow</strong>
            <small>Plataforma geoespacial</small>
          </div>
        </div>
        <span className="header-context">Análise espaço-temporal de áreas queimadas</span>
        <div className="header-actions">
          <span className={"connection " + (existeErro ? "connection-error" : "")}>
            <i /> {buscando ? "Conectando" : existeErro ? "API indisponível" : "API local"}
          </span>
          <button className="mobile-menu icon-btn" type="button"
            aria-label={painelAberto ? "Fechar menu" : "Abrir menu"}
            onClick={() => setPainelAberto(v => !v)}>
            {painelAberto ? <X size={21}/> : <Menu size={21}/>}
          </button>
        </div>
      </header>

      <div className="page-layout">
        <aside className={"sidebar " + (painelAberto ? "sidebar-open" : "")}>
          <div className="sidebar-group">
            <div className="section-heading">
              <span>GERENCIAMENTO</span>
              <Database size={15}/>
            </div>
            <label htmlFor="event-select" className="form-label">Incêndio ativo</label>
            <select id="event-select" className="field"
              value={id !== null && lista.some(v => v.id_incendio === id) ? id : ""}
              onChange={e => {
                const n = Number(e.target.value);
                if (n > 0) setId(n);
              }}>
              {id !== null && !lista.some(v => v.id_incendio === id) &&
                <option value="">ID {id} (não listado)</option>}
              {lista.length === 0 && <option value="">Nenhum evento local</option>}
              {lista.map(v => <option key={v.id_incendio} value={v.id_incendio}>
                Evento {v.id_incendio}
              </option>)}
            </select>
            <form className="find-event" onSubmit={escolherId}>
              <label htmlFor="event-id" className="form-label">Consultar outro ID</label>
              <div className="inline-field">
                <input id="event-id" className="field" type="text"
                  inputMode="numeric" placeholder="Digite um ID"
                  value={buscaId} onChange={e => setBuscaId(e.target.value)}/>
                <button type="submit" className="field-action"
                  aria-label="Consultar ID"><Search size={17}/></button>
              </div>
            </form>
          </div>

          <div className="sidebar-group">
            <div className="section-heading">
              <span>NAVEGAÇÃO TEMPORAL</span>
              <Activity size={15}/>
            </div>
            <div className="selected-day">
              <span>DATA SELECIONADA</span>
              <strong>{data ? nomeDia(data) : "Sem data"}</strong>
              <small>{resumo ? (indice+1) + " de " + resumo.total_datas + " observações" : "Selecione um evento"}</small>
            </div>
            <label className="form-label" htmlFor="date-range">Linha do tempo</label>
            <input id="date-range" className="date-slider" type="range"
              min={0} max={Math.max(0,(resumo?.datas.length ?? 1)-1)}
              value={Math.max(0,indice)} disabled={!resumo?.datas.length}
              onChange={e => { setData(resumo?.datas[Number(e.target.value)] ?? ""); setTocando(false); }}/>
            <div className="range-labels">
              <span>{resumo?.periodo_inicio?.slice(5) ?? "..."}</span>
              <span>{resumo?.periodo_fim?.slice(5) ?? "..."}</span>
            </div>
            <div className="transport-controls">
              <button type="button" className="square-btn" aria-label="Data anterior"
                onClick={() => { navegaPara(-1); setTocando(false); }}
                disabled={indice <= 0}><ChevronLeft size={18}/></button>
              <button type="button" className="play-btn"
                disabled={!resumo?.datas.length || indice === (resumo?.datas.length ?? 0)-1}
                onClick={() => setTocando(v => !v)}>
                {tocando ? <Pause size={16}/> : <Play size={16}/>}
                {tocando ? "Pausar" : "Reproduzir"}
              </button>
              <button type="button" className="square-btn" aria-label="Próxima data"
                disabled={!resumo || indice >= resumo.datas.length-1}
                onClick={() => { navegaPara(1); setTocando(false); }}>
                <ChevronRight size={18}/>
              </button>
            </div>
          </div>

          <div className="sidebar-group">
            <div className="section-heading"><span>CAMADAS</span><Layers size={15}/></div>
            <label className="layer-toggle">
              <span><i className="swatch swatch-p1"/> P1 · Componentes</span>
              <input type="checkbox" checked={p1Ativo}
                onChange={e=>setP1Ativo(e.target.checked)}/>
            </label>
            <label className="layer-toggle">
              <span><i className="swatch swatch-p2"/> P2 · Região móvel</span>
              <input type="checkbox" checked={p2Ativo}
                onChange={e=>setP2Ativo(e.target.checked)}/>
            </label>
            <label className="layer-toggle">
              <span>Mapa-base OSM</span>
              <input type="checkbox" checked={mapaBase}
                onChange={e=>setMapaBase(e.target.checked)}/>
            </label>
          </div>

          <div className="sidebar-group sidebar-note">
            <strong>Outro evento?</strong>
            <p>O processamento por ID ainda utiliza o CLI existente.</p>
            <code>{cmd || "python executar_pipeline.py --id ID --origem gee"}</code>
            <button type="button" className="text-button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(cmd);
                  setMensagem("Comando copiado.");
                } catch {
                  setMensagem("Copie o comando exibido acima.");
                }
              }}>Copiar comando</button>
          </div>
        </aside>

        {painelAberto && <button className="sidebar-scrim"
          aria-label="Fechar menu" onClick={() => setPainelAberto(false)}/>}

        <main className="main-content">
          <div className="workspace-heading">
            <div>
              <span className="eyebrow">PAINEL DE EXPLORAÇÃO</span>
              <h1>Visão geral do incêndio</h1>
              <p>Observe a evolução dos componentes e da região móvel ao longo do tempo.</p>
            </div>
            <div className="workspace-actions">
              <button className="secondary-button" type="button"
                aria-label="Atualizar lista de eventos"
                onClick={() => atualizarLista()}><RefreshCw size={16}/> Atualizar</button>
            </div>
          </div>

          <JobsPanel eventoId={id} onConcluiu={aoConcluirJob} />

          {mensagem && <div className="message-box" role="status">
            <span>{mensagem}</span><button aria-label="Fechar mensagem"
              onClick={()=>setMensagem("")}><X size={15}/></button>
          </div>}
          {erroEvento && <div className="error-panel" role="alert">
            <AlertCircle size={22}/>
            <div><strong>Dados indisponíveis</strong><p>{erroEvento}</p></div>
          </div>}
          {carregandoEvento && <div className="loading-inline" aria-live="polite">
            <LoaderCircle size={19} className="spin"/> Carregando evento e séries temporais...
          </div>}
          {!resumo && !carregandoEvento && !erroEvento && (
            <div className="empty-state">
              <Database size={32}/>
              <h2>Nenhum incêndio selecionado</h2>
              <p>Selecione um evento já processado ou informe um ID local.</p>
            </div>
          )}

          {resumo && id !== null && (
            <>
              <div className="section-title-row">
                <div className="event-identifier">
                  <span className="event-dot"/>
                  <strong>Evento {id}</strong>
                  <span className="date-label">· {data ? nomeDia(data) : "..."}</span>
                </div>
                <span className="period-label">
                  {resumo.total_datas} observações · {resumo.periodo_inicio} a {resumo.periodo_fim}
                </span>
              </div>

              <div className="kpi-grid">
                <Kpi rotulo="Área acumulada (P1)"
                  valor={formatarNumero(areaP1) + (areaP1 !== null ? " km²" : "")}
                  detalhe="Cobertura espacial do evento" classe="kpi-accent"/>
                <Kpi rotulo="Região móvel (P2)"
                  valor={formatarNumero(areaP2) + (areaP2 !== null ? " km²" : "")}
                  detalhe="Componente rastreado"/>
                <Kpi rotulo="Participação P2 / P1"
                  valor={formatarNumero(dominancia,1) + (dominancia !== null ? "%" : "")}
                  detalhe="Na data selecionada"/>
                <Kpi rotulo="Componentes P1"
                  valor={formatarNumero(patches,0)}
                  detalhe="Patches desta observação"/>
              </div>

              <section className="panel map-panel">
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">GEOMETRIA ACUMULADA</span>
                    <h2>Mapa temporal do evento</h2>
                  </div>
                  <span className="panel-date">{data ? nomeDia(data) : ""}</span>
                </div>
                {erroMapa && <div className="map-warning" role="alert">
                  <AlertCircle size={18}/>{erroMapa}
                </div>}
                {carregandoMapa && <div className="map-loader" aria-live="polite">
                  <LoaderCircle className="spin" size={18}/> Atualizando geometrias...
                </div>}
                <MapPanel id={id} data={data} p1={p1} p2={p2}
                  mostrarP1={p1Ativo} mostrarP2={p2Ativo}
                  mapaBase={mapaBase}/>
                <div className="map-footer">
                  <p>Geometrias originais em EPSG:4326. Contatos e incrementos não representam frentes ativas do fogo.</p>
                  <button type="button" onClick={exportarGeoJSON}
                    disabled={!data} className="secondary-button compact">
                    <ArrowDownToLine size={15}/> Exportar GeoJSON
                  </button>
                </div>
              </section>

              {transicao && <div className="transitions-grid">
                <div className="transition-card">
                  <span>Área nova nesta transição</span>
                  <strong>{formatarNumero(numero(transicao,"area_nova_evento_km2"),3)} km²</strong>
                </div>
                <div className="transition-card">
                  <span>Incorporação prequeimada pelo P2</span>
                  <strong>{formatarNumero(numero(transicao,"p2_incremento_ja_queimado_km2"),3)} km²</strong>
                </div>
                <div className="transition-card">
                  <span>Convergências geométricas</span>
                  <strong>{formatarNumero(numero(transicao,"eventos_convergencia"),0)}</strong>
                </div>
                {numero(transicao, "dias_intervalo") !== 1 &&
                  <div className="transition-alert">Intervalo entre observações maior que um dia.</div>}
              </div>}

              <div className="charts-title">
                <div><BarChart3 size={20}/><h2>Indicadores temporais</h2></div>
                {resumo.tem_series && <a className="download-link" href={urlSerieCSV(id)}
                  download><ArrowDownToLine size={16}/> Série CSV</a>}
              </div>
              {!resumo.tem_series && <div className="empty-chart">
                O evento possui geometria, mas a análise integrada ainda não foi realizada.
              </div>}
              {resumo.tem_series && <div className="charts-grid">
                <LineChart titulo="Evolução da área" datas={serie.map(s=>s.data ?? "")}
                  series={linhasArea} dataAtual={data} onSelect={setData}/>
                <LineChart titulo="Fragmentação do evento" datas={serie.map(s=>s.data ?? "")}
                  series={linhasPatches} unidade="patches" dataAtual={data}
                  onSelect={setData}/>
                <div className="full-chart">
                  <LineChart titulo="Área nova × incorporação do P2"
                    datas={transicoes.map(t=>t.data_atual ?? "")}
                    series={linhasIncrementos} dataAtual={data}
                    onSelect={setData}/>
                </div>
              </div>}

              <section className="panel details-panel">
                <div className="panel-heading">
                  <div>
                    <span className="eyebrow">INSPEÇÃO LOCAL</span>
                    <h2>Patches da data selecionada</h2>
                  </div>
                  <span className="subtle-pill">
                    {p1?.features.length ?? 0} feições carregadas
                  </span>
                </div>
                {p1Ativo && p1?.features.length ? (
                  <div className="table-scroll"><table>
                    <thead><tr><th>Rank</th><th>Data</th><th>Área GEE</th></tr></thead>
                    <tbody>{p1.features.slice().sort(
                      (a,b)=>Number(a.properties.rank ?? 0)-Number(b.properties.rank ?? 0)
                    ).slice(0,100).map((f,i)=><tr key={i}>
                      <td>#{f.properties.rank ?? "?"}</td>
                      <td>{f.properties.data ?? data}</td>
                      <td>{formatarNumero(Number(f.properties.area_km2 ?? 0),3)} km²</td>
                    </tr>)}</tbody>
                  </table></div>
                ) : <p className="muted">Habilite P1 para consultar os componentes.</p>}
                {(p1?.features.length ?? 0) > 100 && <p className="muted">
                  Exibindo os primeiros 100 patches. Exporte o GeoJSON para consultar todos.
                </p>}
              </section>

              <div className="audit-banner">
                {resumo.validacao_externa_concluida
                  ? <CheckCircle2 size={19}/>
                  : <AlertCircle size={19}/>}
                <div>
                  <strong>Auditoria: {resumo.status_cientifico.replaceAll("_", " ")}</strong>
                  <p>{resumo.validacao_externa_concluida
                    ? "Relatório aponta validação externa concluída."
                    : "Dados processados, sem validação externa comprovada."}
                    {resumo.dias_sobreposicao_p1_pendentes.length > 0 &&
                      " Sobreposição P1 pendente: " +
                        resumo.dias_sobreposicao_p1_pendentes.join(", ") + "."}
                  </p>
                </div>
              </div>
            </>
          )}
          <footer className="footer">
            <span>BurnGeoFlow · Exploração de dados, não monitoramento de fogo ativo</span>
            <span>Armazenamento local · GEE GlobFire v2</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
