import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ExternalLink, Pause, Play, SkipForward } from "lucide-react";
import "./story.css";

type Ponto = [number, number];
type NomeTR = "centroide" | "norte" | "sul" | "leste" | "oeste";
type Quadro = {
  date: string;
  area_km2: number;
  p2_km2: number;
  componentes: number;
  rank_p2: number;
  p1: string;
  p2: string;
  igt: string;
  tr: Partial<Record<NomeTR, Ponto>>;
};
type Estudo = {
  id: number;
  source: string;
  bbox_wgs84: [number, number, number, number];
  viewBox: [number, number, number, number];
  frames: Quadro[];
};
type Cena = {
  label: string;
  title: string;
  text: string;
  detail: string;
};

const CENAS: Cena[] = [
  {
    label: "01 / TERRITÓRIO",
    title: "O território não permanece imóvel.",
    text: "O Pantanal guarda marcas que se transformam ao longo do tempo. A cartografia permite observar essas mudanças, sem confundir o registro orbital com o fogo em atividade.",
    detail: "Pantanal brasileiro · 2020",
  },
  {
    label: "02 / PRIMEIRO REGISTRO",
    title: "Toda mudança deixa uma geometria.",
    text: "O primeiro perímetro mapeado registra uma parcela da área queimada. É uma observação histórica, não a posição exata da frente de chamas.",
    detail: "09 de agosto de 2020 · primeira observação",
  },
  {
    label: "03 / EVOLUÇÃO",
    title: "O mapa cresce com o tempo.",
    text: "Role para atravessar 57 observações reais. Novas manchas aparecem, componentes se ampliam e áreas inicialmente separadas podem passar a se conectar.",
    detail: "Cada quadro corresponde a uma data observada",
  },
  {
    label: "04 / P1",
    title: "Um incêndio. Diferentes componentes.",
    text: "P1 representa todos os componentes da área queimada acumulada. A extensão total não revela, sozinha, sua fragmentação e organização espacial.",
    detail: "P1 · evento completo",
  },
  {
    label: "05 / P2",
    title: "Uma região acompanhada ao longo do tempo.",
    text: "P2 segue um componente selecionado inicialmente por sua área e depois rastreado por continuidade geométrica. Não precisa ser o maior componente em todas as datas.",
    detail: "P2 · região móvel rastreada",
  },
  {
    label: "06 / TRAJETÓRIAS",
    title: "A forma muda. As posições também.",
    text: "Centroide e extremos norte, sul, leste e oeste formam cinco trajetórias representativas. Elas descrevem a geometria, não o caminho percorrido por uma partícula de fogo.",
    detail: "TR · cinco descritores espaciais",
  },
  {
    label: "07 / INCREMENTOS",
    title: "Nem todo crescimento significa fogo novo.",
    text: "Os incrementos geométricos temporais revelam alterações na região rastreada. Parte do crescimento pode decorrer da incorporação de áreas que já estavam queimadas.",
    detail: "IGT · diferenças entre observações",
  },
  {
    label: "08 / PLATAFORMA",
    title: "Da paisagem aos indicadores.",
    text: "O BurnGeoFlow transforma esses dados em mapas temporais, gráficos, trajetórias e análises de paisagem. Uma ferramenta para explorar evidências, hipóteses e limites.",
    detail: "Explore o atlas científico completo",
  },
];
const NOMES: { id: NomeTR; label: string; color: string }[] = [
  { id: "centroide", label: "Centroide", color: "#f8f3dd" },
  { id: "norte", label: "Norte", color: "#eaca89" },
  { id: "sul", label: "Sul", color: "#90c9b6" },
  { id: "leste", label: "Leste", color: "#f08a68" },
  { id: "oeste", label: "Oeste", color: "#b4a3d8" },
];
const limitar = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n));
const porExtenso = (d: string) => {
  if (!d) return "Carregando";
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(d + "T12:00:00Z"));
};
const numero = (n: number) => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });

function trilha(frames: Quadro[], fim: number, nome: NomeTR): string {
  const pontos = frames.slice(0, fim + 1).map(f => f.tr[nome]).filter((p): p is Ponto => Boolean(p));
  return pontos.map((p, i) => (i === 0 ? "M" : "L") + p[0] + "," + p[1]).join(" ");
}

function Relogio({ data, indice, total }: { data: string; indice: number; total: number }) {
  return <div className="story-clock" aria-live="off">
    <span>OBSERVAÇÃO / {String(indice + 1).padStart(2, "0")} DE {total}</span>
    <strong>{porExtenso(data)}</strong>
  </div>;
}

export default function StoryPage() {
  const raiz = useRef<HTMLElement>(null);
  const [estudo, setEstudo] = useState<Estudo | null>(null);
  const [erro, setErro] = useState(false);
  const [etapa, setEtapa] = useState(0);
  const [autoplay, setAutoplay] = useState(false);
  const [quadroPlay, setQuadroPlay] = useState(0);
  const [reduzirMovimento, setReduzirMovimento] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const atualizar = () => setReduzirMovimento(media.matches);
    atualizar();
    media.addEventListener("change", atualizar);
    return () => media.removeEventListener("change", atualizar);
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch("/story/24340828.json", { signal: ctrl.signal })
      .then(res => { if (!res.ok) throw new Error("Falha na leitura"); return res.json() as Promise<Estudo>; })
      .then(setEstudo)
      .catch(e => { if (e instanceof Error && e.name !== "AbortError") setErro(true); });
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    let raf = 0;
    const medir = () => {
      raf = 0;
      const el = raiz.current;
      if (!el) return;
      const passos = el.querySelector<HTMLElement>(".story-steps");
      if (!passos) return;
      const caixa = passos.getBoundingClientRect();
      const comprimento = Math.max(1, passos.clientHeight / CENAS.length);
      const deslocamento = window.matchMedia("(max-width: 720px)").matches ? window.innerHeight * 0.5 : 0;
      const valor = limitar((deslocamento - caixa.top) / comprimento, 0, CENAS.length - 0.001);
      setEtapa(v => Math.abs(v - valor) < 0.008 ? v : valor);
    };
    const aoScroll = () => { if (!raf) raf = requestAnimationFrame(medir); };
    medir();
    window.addEventListener("scroll", aoScroll, { passive: true });
    window.addEventListener("resize", aoScroll);
    return () => {
      window.removeEventListener("scroll", aoScroll);
      window.removeEventListener("resize", aoScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  useEffect(() => {
    if (!autoplay || !estudo || reduzirMovimento) return;
    const timer = window.setInterval(() => {
      setQuadroPlay(v => {
        if (v >= estudo.frames.length - 1) {
          setAutoplay(false);
          return v;
        }
        return v + 1;
      });
    }, 190);
    return () => window.clearInterval(timer);
  }, [autoplay, estudo, reduzirMovimento]);

  const cena = limitar(Math.floor(etapa), 0, CENAS.length - 1);
  const fracao = etapa - Math.floor(etapa);
  const n = estudo?.frames.length ?? 57;
  const indiceScroll = cena < 2 ? 0 : cena === 2 ? Math.round(fracao * (n - 1))
    : cena === 3 ? Math.round((n - 1) * 0.70)
    : cena === 4 ? Math.round((n - 1) * 0.82)
    : cena === 5 ? Math.round(fracao * (n - 1))
    : cena === 6 ? Math.round((n - 1) * (0.40 + 0.60 * fracao)) : n - 1;
  const indice = limitar(autoplay ? quadroPlay : indiceScroll, 0, n - 1);
  const atual = estudo?.frames[indice];
  const mostrarPoligonos = cena >= 1 || autoplay;
  const destacarP2 = cena === 4 || cena === 5 || cena === 6;
  const mostrarTr = cena === 5;
  const mostrarIgt = cena === 6;
  const viewBox = estudo?.viewBox.join(" ") ?? "0 0 1000 760";

  const linhas = useMemo(() => mostrarTr && estudo
    ? NOMES.map(item => ({ ...item, d: trilha(estudo.frames, indice, item.id), pos: atual?.tr[item.id] }))
    : [], [estudo, atual, indice, mostrarTr]);

  const avancar = () => {
    document.getElementById("story-final")?.scrollIntoView({ behavior: reduzirMovimento ? "auto" : "smooth" });
    setAutoplay(false);
  };
  const reproduzir = () => {
    if (autoplay) setAutoplay(false);
    else {
      setQuadroPlay(indice >= n - 1 ? 0 : indice);
      setAutoplay(true);
    }
  };

  return <div className="story-page">
    <a href="#conteudo" className="story-skip">Pular para o conteúdo</a>
    <header className="story-header">
      <a className="story-logo" href="/" aria-label="BurnGeoFlow, voltar ao atlas">
        <img src="/atlas-mark.svg" alt="" /><span>Burn<span>Geo</span>Flow</span>
      </a>
      <span className="story-header-sub">ATLAS / TERRITÓRIO / TEMPO</span>
      <nav aria-label="Navegação principal">
        <a href="#metodo">Método</a>
        <a href="#fontes">Dados e limites</a>
        <a className="story-header-link" href="/">Abrir atlas <ArrowRight size={15}/></a>
      </nav>
    </header>

    <main id="conteudo">
      <section className="story-layout" ref={raiz} aria-label="Narrativa cartográfica interativa">
        <div className="story-steps">
          {CENAS.map((item, i) => <article key={item.label} className={"story-step" + (cena === i ? " is-current" : "")}
            id={i === 7 ? "story-final" : undefined} aria-label={item.label}>
            <div className="story-step-inner">
              <div className="story-numeral">{String(i + 1).padStart(2, "0")} <span>/ 08</span></div>
              <div className="story-overline">{item.label}</div>
              {i === 0 && <div className="story-kicker">UMA HISTÓRIA DESENHADA PELO TERRITÓRIO</div>}
              <h1>{item.title}</h1>
              <p>{item.text}</p>
              <div className="story-detail">{item.detail}</div>
              {i === 0 && <div className="story-scroll-hint"><ArrowDown size={19}/> Role para acompanhar a transformação</div>}
              {i === 7 && <div className="story-cta-stack">
                <a className="story-cta" href="/">Explorar o BurnGeoFlow <ArrowRight size={19}/></a>
                <a className="story-source-inline" href="https://github.com/DomingosThiagoCode/BurnGeoFlow" target="_blank" rel="noreferrer">Ver código-fonte <ExternalLink size={14}/></a>
              </div>}
            </div>
          </article>)}
        </div>

        <aside className={"story-visual scene-" + cena} aria-label="Mapa temporal do estudo de caso">
          <div className="story-map-top">
            <div className="story-map-id"><span className="story-map-dot"/> PANTANAL / BRASIL</div>
            <span>GLOBFIRE V2 · ID 24340828</span>
          </div>
          <div className="story-map-plate">
            <svg viewBox={viewBox} role="img" aria-label={"Geometrias cartográficas observadas em " + (atual?.date ?? "2020")}>
              <defs>
                <pattern id="story-grid" width="50" height="50" patternUnits="userSpaceOnUse">
                  <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#e5eadc" strokeWidth=".55" opacity=".20" />
                </pattern>
                <pattern id="story-grid-major" width="250" height="250" patternUnits="userSpaceOnUse">
                  <path d="M 250 0 L 0 0 0 250" fill="none" stroke="#d7dfcc" strokeWidth="1" opacity=".24" />
                </pattern>
              </defs>
              <rect width="1000" height="760" fill="#1b3530"/>
              <rect width="1000" height="760" fill="url(#story-grid)"/>
              <rect width="1000" height="760" fill="url(#story-grid-major)"/>
              <path d="M50 50h42m-42 0v42 M950 50h-42m42 0v42 M50 710h42m-42 0v-42 M950 710h-42m42 0v-42"
                fill="none" stroke="#b3c6b3" strokeWidth="1.5" opacity=".6"/>
              {atual && mostrarPoligonos && <>
                <path className="story-p1" d={atual.p1} fillRule="evenodd"
                  fill="#bd6b52" fillOpacity={destacarP2 ? 0.20 : 0.67}
                  stroke="#d9987d" strokeWidth={destacarP2 ? 0.65 : 1.3} vectorEffect="non-scaling-stroke"/>
                {destacarP2 && <path className="story-p2" d={atual.p2} fillRule="evenodd"
                  fill="#3c9e91" fillOpacity={0.74} stroke="#9dddd0" strokeWidth="1.7" vectorEffect="non-scaling-stroke"/>}
                {mostrarIgt && <path className="story-igt" d={atual.igt} fillRule="evenodd"
                  fill="#f6d18d" fillOpacity=".91" stroke="#fff0bc" strokeWidth="1.1" vectorEffect="non-scaling-stroke"/>}
                {linhas.map(l => <g key={l.id}>
                  <path d={l.d} fill="none" stroke={l.color} strokeWidth={l.id === "centroide" ? 2.7 : 1.6}
                    strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
                  {l.pos && <circle cx={l.pos[0]} cy={l.pos[1]} r="4" fill={l.color} stroke="#162e2a" strokeWidth="1.5"/>}
                </g>)}
              </>}
              {cena === 0 && !autoplay && <g className="story-prelude" fill="none" stroke="#a7bcae" opacity=".65">
                <circle cx="505" cy="378" r="105" strokeWidth="1"/>
                <circle cx="505" cy="378" r="34" strokeWidth=".8"/>
                <path d="M505 245v266 M373 378h264" strokeWidth=".85" strokeDasharray="4 9"/>
                <circle cx="505" cy="378" r="3" fill="#c6d4bf" stroke="none"/>
              </g>}
            </svg>
            <div className="story-map-coordinate">GEOMETRIA HISTÓRICA / REFERENCIAL WGS 84</div>
          </div>
          <div className="story-map-bottom">
            <div className="story-map-readout">
              <Relogio data={atual?.date ?? ""} indice={indice} total={n}/>
              <div className="story-stats">
                <div><span>ÁREA P1</span><strong>{atual ? numero(atual.area_km2) + " km²" : "..."}</strong></div>
                <div><span>COMPONENTES</span><strong>{atual?.componentes ?? "..."}</strong></div>
                {destacarP2 && <div><span>ÁREA P2</span><strong>{atual ? numero(atual.p2_km2) + " km²" : "..."}</strong></div>}
              </div>
            </div>
            <div className="story-timeline"><div style={{ width: ((indice + 1) / n * 100) + "%" }} /></div>
            <div className="story-map-controls">
              <div className="story-legend">
                {mostrarTr ? NOMES.map(item => <span key={item.id}><i style={{ background: item.color }}/>{item.label}</span>)
                  : <><span><i className="legend-p1"/>P1 · componentes</span>
                    {destacarP2 && <span><i className="legend-p2"/>P2 · rastreada</span>}
                    {mostrarIgt && <span><i className="legend-igt"/>IGT</span>}</>}
              </div>
              <div className="story-buttons">
                <button type="button" disabled={!estudo || reduzirMovimento} onClick={reproduzir}
                  aria-label={autoplay ? "Pausar reprodução temporal" : "Reproduzir observações"} title="Reproduzir ou pausar observações">
                  {autoplay ? <Pause size={16}/> : <Play size={16}/>}
                </button>
                <button type="button" onClick={avancar} title="Pular narrativa" aria-label="Pular narrativa"><SkipForward size={16}/></button>
              </div>
            </div>
          </div>
          {erro && <div role="alert" className="story-map-error">Os dados de visualização não puderam ser carregados. O atlas científico continua disponível.</div>}
          {!estudo && !erro && <div className="story-map-loading" role="status">Preparando observações cartográficas...</div>}
          <p className="story-map-disclaimer">Áreas queimadas mapeadas. Não representa a frente ativa do fogo.</p>
        </aside>
      </section>

      <section className="story-explainer" id="metodo">
        <span className="story-section-index">CADERNO DE MÉTODO · 01</span>
        <div className="story-explainer-grid">
          <h2>Não basta saber <em>quanto</em> queimou.</h2>
          <div className="story-explainer-body">
            <p>Um único número de área não conta como os componentes surgiram, cresceram e se conectaram. O BurnGeoFlow reúne diferentes formas de observar essa mudança.</p>
            <div className="story-method-line"><span>01</span><strong>P1</strong><p>O conjunto dos componentes da área queimada acumulada em cada data.</p></div>
            <div className="story-method-line"><span>02</span><strong>P2</strong><p>O componente rastreado por continuidade geométrica entre observações.</p></div>
            <div className="story-method-line"><span>03</span><strong>TR</strong><p>Centroide e quatro extremos cardeais como séries de posições representativas.</p></div>
            <div className="story-method-line"><span>04</span><strong>IGT</strong><p>Incrementos geométricos temporais, analisados sem confundi-los com toda a queima nova.</p></div>
          </div>
        </div>
      </section>

      <section className="story-provenance" id="fontes">
        <div>
          <span className="story-section-index">CADERNO DE CAMPO · 02</span>
          <h2>O que o mapa mostra.<br/><em>E o que ele não mostra.</em></h2>
        </div>
        <div className="story-source-text">
          <p>Os polígonos provêm do estudo histórico do evento 24340828, a partir do JRC/GWIS GlobFire v2, baseado no MODIS MCD64A1. A resolução do produto impõe limites à identificação de detalhes espaciais.</p>
          <p>A sequência animada mostra as observações disponíveis, sem criar datas intermediárias. As geometrias exibidas foram simplificadas apenas para esta visualização; os dados científicos originais permanecem preservados.</p>
          <p>Trajetórias e incrementos são descritores geométricos, não medições diretas da dinâmica física das chamas. Uma validação independente é necessária antes de inferências causais.</p>
          <a href="https://github.com/DomingosThiagoCode/CDG_incendio" target="_blank" rel="noreferrer">Consultar a origem dos dados <ExternalLink size={15}/></a>
        </div>
      </section>

      <footer className="story-footer">
        <div className="story-footer-kicker">BURNGEOFLOW / ENGENHARIA CARTOGRÁFICA / IME</div>
        <h2>O mapa é o começo<br/>da investigação.</h2>
        <div className="story-footer-actions">
          <a className="story-footer-main" href="/">Entrar no atlas científico <ArrowRight size={20}/></a>
          <a href="https://github.com/DomingosThiagoCode/BurnGeoFlow" target="_blank" rel="noreferrer">Repositório <ExternalLink size={15}/></a>
        </div>
        <div className="story-footer-bottom"><span>BurnGeoFlow · pesquisa acadêmica</span><span>Dados históricos, não monitoramento em tempo real</span><a href="#conteudo">Voltar ao início <ArrowLeft size={13}/></a></div>
      </footer>
    </main>
  </div>;
}
