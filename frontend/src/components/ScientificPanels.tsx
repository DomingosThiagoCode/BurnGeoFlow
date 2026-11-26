import { useMemo, useState, type ReactNode } from "react";
import { LineChart, type SerieGrafico } from "./LineChart";
import { formatarNumero, numero } from "../services/api";
import type { AnaliseEtapa4, Linha } from "../types";
import {
  type ContribuicaoDirecional, DIRECOES, distribuicaoDirecional,
  indiceDirecional, intervaloSetor,
} from "../utils/rose";

export type AbaCientifica = "paisagem" | "expansao" | "movimento" | "direcoes" | "forma";

interface Props {
  aba: AbaCientifica;
  serie: Linha[];
  transicoes: Linha[];
  dia: string;
  selecionarData: (dia: string) => void;
  mostrarSegmento: (ponto: string, dataAtual: string) => void;
  analise: AnaliseEtapa4 | null;
  carregando: boolean;
  erro: string | null;
}

const cores = {
  laranja: "#aa4b36", verde: "#35756d", azul: "#4d7088",
  roxo: "#786a87", amarelo: "#a48852", vermelho: "#ad5f58",
};

function linha(rotulo: string, cor: string, registros: Linha[], campo: string): SerieGrafico {
  return { label: rotulo, cor, valores: registros.map(r => numero(r, campo)) };
}

function Introducao({ titulo, texto }: { titulo: string; texto: string }) {
  return <div className="analysis-intro">
    <div><span className="eyebrow">ANÁLISE EXPLORATÓRIA</span><h2>{titulo}</h2></div>
    <p>{texto}</p>
  </div>;
}

function Aviso({ children }: { children: ReactNode }) {
  return <p className="analysis-caution">{children}</p>;
}

type AnguloPonderado = ContribuicaoDirecional;

function RosaDirecional({
  titulo, dados, subtitulo, unidade, escalaComum, selecionarData,
  ponto, mostrarSegmento,
}: {
  titulo:string;
  dados:AnguloPonderado[];
  subtitulo:string;
  unidade:"km"|"km²";
  escalaComum?:number;
  selecionarData:(data:string)=>void;
  ponto?:string;
  mostrarSegmento?:(ponto:string, dataAtual:string)=>void;
}) {
  const [hover,setHover]=useState<number|null>(null);
  const [selecionado,setSelecionado]=useState<number|null>(null);
  const [ampliado,setAmpliado]=useState(false);
  const distribuicao=useMemo(()=>distribuicaoDirecional(dados),[dados]);
  const {pesos,total,maximo,media,concentracao,validos}=distribuicao;
  const maximoRadial = escalaComum && escalaComum>0 ? escalaComum : maximo;
  const ativo = hover??selecionado;
  const destaques = ativo===null?[]:
    validos.filter(d=>indiceDirecional(d.angulo)===ativo)
      .sort((a,b)=>a.data.localeCompare(b.data));
  const pesoSetor = ativo===null?0:pesos[ativo];
  const centro = ativo===null?null:ativo*22.5;
  const raio=75;
  const ponto = (az:number,r:number) => {
    const a=(az-90)*Math.PI/180;
    return [110+Math.cos(a)*r,112+Math.sin(a)*r];
  };
  const setor = (i:number,r:number) => {
    const a=ponto(i*22.5-10.7,r);
    const b=ponto(i*22.5+10.7,r);
    return "M 110 112 L "+a[0].toFixed(2)+" "+a[1].toFixed(2)+
      " A "+r.toFixed(2)+" "+r.toFixed(2)+" 0 0 1 "+
      b[0].toFixed(2)+" "+b[1].toFixed(2)+" Z";
  };
  const selecionar=(i:number)=>{
    setSelecionado(prev=>prev===i?null:i);
    const primeira=validos.filter(d=>indiceDirecional(d.angulo)===i)
      .sort((a,b)=>a.data.localeCompare(b.data))[0];
    if(primeira?.data) selecionarData(primeira.data);
  };
  return <section className={"rose-card "+(ampliado?"rose-card-expanded":"")}>
    <div className="rose-heading">
      <div><h3>{titulo}</h3><p>{subtitulo}</p></div>
      <button type="button" className="secondary-button compact"
        aria-label={(ampliado?"Reduzir":"Ampliar")+" rosácea "+titulo}
        aria-pressed={ampliado} onClick={()=>setAmpliado(v=>!v)}>
        {ampliado?"Reduzir":"Ampliar"}
      </button>
    </div>
    {total===0?<div className="rose-empty">Sem azimutes válidos para este período.</div>:
      <svg viewBox="0 0 220 232" className="rose-svg" role="group"
        aria-label={"Rosácea interativa: "+titulo}>
        {[0.25,0.5,0.75,1].map(fracao=>
          <g key={fracao}>
            <circle cx="110" cy="112" r={raio*fracao} fill="none"
              stroke="#e4e0d5" strokeWidth="1"/>
            <text x="117" y={108-raio*fracao} className="rose-tick">
              {formatarNumero(maximoRadial*fracao,2)}
            </text>
          </g>)}
        {[0,45,90,135].map(a=>{
          const p=ponto(a,raio),q=ponto(a+180,raio);
          return <line key={a} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]}
            stroke="#d9d6c9" strokeWidth="1"/>;
        })}
        {pesos.map((valor,i)=>{
          if(valor<=0)return null;
          const rad=Math.max(2,raio*valor/Math.max(maximoRadial,valor));
          return <path key={i} d={setor(i,rad)} role="button" tabIndex={0}
            aria-label={DIRECOES[i]+", "+intervaloSetor(i)+", "+
              formatarNumero(valor,2)+" "+unidade+", "+
              formatarNumero(valor/total*100,1)+"%. Selecionar setor"}
            aria-pressed={selecionado===i}
            className={"rose-sector "+(ativo===i?"rose-sector-highlight":"")}
            fill={ativo===i?"#ab4e38":"#35756d"}
            fillOpacity={ativo!==null&&ativo!==i?0.38:0.78}
            stroke="#fff" strokeWidth=".9"
            onMouseEnter={()=>setHover(i)} onMouseLeave={()=>setHover(null)}
            onFocus={()=>setHover(i)} onBlur={()=>setHover(null)}
            onClick={()=>selecionar(i)}
            onKeyDown={e=>{
              if(e.key==="Enter"||e.key===" "){e.preventDefault();selecionar(i);}
            }}>
            <title>{DIRECOES[i]}: {formatarNumero(valor,2)} {unidade} ({formatarNumero(valor/total*100,1)}%)</title>
          </path>;
        })}
        {media!==null&&(()=>{
          const p=ponto(media,raio+5);
          return <line x1="110" y1="112" x2={p[0]} y2={p[1]}
            stroke="#aa4b36" strokeWidth="2.6" strokeLinecap="round"/>;
        })()}
        <circle cx="110" cy="112" r="2.5" fill="#26483d"/>
        <text x="110" y="22" textAnchor="middle">N</text>
        <text x="203" y="116" textAnchor="middle">L</text>
        <text x="110" y="207" textAnchor="middle">S</text>
        <text x="17" y="116" textAnchor="middle">O</text>
      </svg>}
    <div className="rose-result">
      <span>Direção média <strong>{media===null?"indefinida":formatarNumero(media,1)+"°"}</strong></span>
      <span>Concentração <strong>{total===0?"—":formatarNumero(concentracao,2)}</strong></span>
      <span>Escala radial <strong>{formatarNumero(maximoRadial,2)} {unidade}</strong></span>
    </div>
    {ativo!==null&&<div className="rose-tooltip" role="status">
      <strong>{DIRECOES[ativo]} · {intervaloSetor(ativo)}</strong>
      <p>{formatarNumero(pesoSetor,3)} {unidade} · {total?formatarNumero(pesoSetor/total*100,1):0}% do peso</p>
      {centro!==null&&<small>Setor centrado em {centro}° a partir do norte, sentido horário.</small>}
    </div>}
    {selecionado!==null&&<div className="rose-contributions">
      <div className="rose-contrib-head">
        <strong>Transições do setor {DIRECOES[selecionado]}</strong>
        <button type="button" className="secondary-button compact"
          onClick={()=>{setSelecionado(null);setHover(null);}}>Limpar seleção</button>
      </div>
      {destaques.length===0?<p>Sem contribuições neste período.</p>:
        <ul>{destaques.slice(0,20).map((d,i)=><li key={d.data+":"+i}>
          <button type="button" onClick={()=>selecionarData(d.data)}>
            {d.data||"Data não informada"} · {formatarNumero(d.peso,3)} {unidade}
          </button>
        </li>)}</ul>}
      {destaques.length>20&&<small>Exibindo 20 de {destaques.length} contribuições.</small>}
      {ponto&&mostrarSegmento&&destaques[0]?.data&&
        <button type="button" className="secondary-button rose-map-link"
          onClick={()=>mostrarSegmento(ponto,destaques[0].data)}>
          Ver deslocamento selecionado no mapa
        </button>}
    </div>}
  </section>;
}

const TRAJETORIAS = [
  { id: "centroide", rotulo: "Centroide", cor: cores.laranja },
  { id: "norte", rotulo: "Norte", cor: cores.azul },
  { id: "sul", rotulo: "Sul", cor: cores.verde },
  { id: "leste", rotulo: "Leste", cor: cores.roxo },
  { id: "oeste", rotulo: "Oeste", cor: cores.vermelho },
];

function CincoTrajetorias({ pontos, dia }: { pontos: Linha[]; dia: string }) {
  const validos = pontos.map(p => ({
    x: numero(p, "x_laea_m"), y: numero(p, "y_laea_m"),
    ponto: p.ponto, data: p.data,
  })).filter((p): p is { x: number; y: number; ponto: string | null; data: string | null } =>
    p.x !== null && p.y !== null);
  if (!validos.length) return <div className="empty-chart">Pontos representativos indisponíveis.</div>;
  const xs = validos.map(p => p.x), ys = validos.map(p => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const alcanceX = Math.max(1, x1-x0), alcanceY = Math.max(1, y1-y0);
  const escala = Math.min(700/alcanceX, 350/alcanceY);
  const largura = alcanceX * escala, altura = alcanceY * escala;
  const X = (n: number) => 55 + (700 - largura)/2 + (n-x0)*escala;
  const Y = (n: number) => 38 + (350 - altura)/2 + (y1-n)*escala;
  return <section className="chart-panel full-chart">
    <div className="chart-heading"><h3>Cinco trajetórias representativas</h3><span>LAEA local · proporção espacial preservada</span></div>
    <svg className="trajectory-svg" viewBox="0 0 810 440" role="img"
      aria-label="Trajetórias do centroide e extremos norte, sul, leste e oeste">
      <rect x="40" y="22" width="730" height="385" rx="9" fill="#f7faf8"/>
      {TRAJETORIAS.map(t => {
        const traj = validos.filter(v => v.ponto === t.id)
          .sort((a,b) => (a.data ?? "").localeCompare(b.data ?? ""));
        const d = traj.map((p,i) => (i ? "L " : "M ") + X(p.x).toFixed(2) + " " + Y(p.y).toFixed(2)).join(" ");
        const atual = traj.find(p => p.data === dia);
        return <g key={t.id}>
          {traj.length > 1 && <path d={d} fill="none" stroke={t.cor}
            strokeWidth={t.id === "centroide" ? 3 : 1.9} opacity=".9"
            strokeLinejoin="round" strokeLinecap="round"/>}
          {atual && <circle cx={X(atual.x)} cy={Y(atual.y)} r="5"
            fill={t.cor} stroke="#fff" strokeWidth="2"/>}
        </g>;
      })}
      <text x="749" y="43" fill="#657468" fontSize="12" textAnchor="end">N ↑</text>
      <text x="52" y="427" fill="#777e70" fontSize="10">Extremos descritivos, não trajetórias de partículas ou frentes ativas.</text>
    </svg>
    <div className="chart-legend">
      {TRAJETORIAS.map(t => <span key={t.id}><i style={{backgroundColor:t.cor}}/>{t.rotulo}</span>)}
    </div>
  </section>;
}

export function ScientificPanels({ aba, serie, transicoes, dia, selecionarData, mostrarSegmento, analise, carregando, erro }: Props) {
  const [inicioFiltro,setInicioFiltro]=useState("");
  const [fimFiltro,setFimFiltro]=useState("");
  const datas = useMemo(() => serie.map(r => r.data ?? ""), [serie]);
  const datasTransicao = useMemo(() => transicoes.map(r => r.data_atual ?? ""), [transicoes]);
  const indicadores = analise?.indicadores ?? [];
  const segmentos = analise?.segmentos ?? [];
  const pontos = analise?.pontos ?? [];
  const datasIndicadores = indicadores.map(r => r.data_atual ?? "");

  if (aba === "paisagem") return <>
    <Introducao titulo="Paisagem e componentes"
      texto="Cobertura acumulada, dominância e fragmentação do evento P1. P2 acompanha a componente rastreada ao longo das observações."/>
    <div className="charts-grid">
      <LineChart titulo="Evolução da área acumulada" datas={datas} dataAtual={dia}
        onSelect={selecionarData} series={[
          linha("Cobertura P1", cores.laranja, serie, "area_total_laea_km2"),
          linha("Região P2", cores.verde, serie, "p2_area_laea_km2"),
        ]}/>
      <LineChart titulo="Fragmentação do evento" datas={datas} dataAtual={dia}
        onSelect={selecionarData} unidade="patches" series={[
          linha("Número de componentes P1", cores.azul, serie, "numero_patches"),
        ]}/>
      <LineChart titulo="Dominância da maior componente" datas={datas}
        dataAtual={dia} onSelect={selecionarData} unidade="%" series={[
          linha("Maior patch / P1", cores.verde, serie, "dominancia_maior_patch_pct"),
        ]}/>
      <LineChart titulo="Índice de forma ponderado do P1" datas={datas}
        dataAtual={dia} onSelect={selecionarData} unidade="adimensional" series={[
          linha("Média ponderada por área", cores.roxo, serie, "indice_forma_medio_ponderado_area"),
        ]}/>
    </div>
    <Aviso>A quantidade de componentes depende da regra de conectividade adotada. As feições acumuladas não representam focos ativos independentes.</Aviso>
  </>;

  if (aba === "expansao") return <>
    <Introducao titulo="Expansão e incorporação geométrica"
      texto="Separa área realmente nova, crescimento do P2 sobre área já queimada e convergência entre componentes. Os valores correspondem a intervalos observados, que podem ter durações diferentes."/>
    <div className="charts-grid">
      <div className="full-chart">
        <LineChart titulo="Área nova × área pré-queimada incorporada ao P2"
          datas={datasTransicao} dataAtual={dia} onSelect={selecionarData} series={[
            linha("Nova no evento", cores.laranja, transicoes, "area_nova_evento_km2"),
            linha("Previamente queimada incorporada ao P2", cores.verde, transicoes, "p2_incremento_ja_queimado_km2"),
          ]}/>
      </div>
      <LineChart titulo="Taxa média de nova área por dia"
        datas={datasTransicao} dataAtual={dia} onSelect={selecionarData}
        unidade="km²/dia" series={[
          linha("Taxa no intervalo", cores.laranja, transicoes, "taxa_nova_evento_km2_dia"),
        ]}/>
      <LineChart titulo="Área nova fora do P2"
        datas={datasTransicao} dataAtual={dia} onSelect={selecionarData} series={[
          linha("Novos componentes fora de P2", cores.azul, transicoes, "nova_area_fora_p2_km2"),
        ]}/>
      <LineChart titulo="Composição do incremento do P2"
        datas={datasTransicao} dataAtual={dia} onSelect={selecionarData} series={[
          linha("Nova no evento", cores.laranja, transicoes, "p2_incremento_nova_area_evento_km2"),
          linha("Já queimada", cores.verde, transicoes, "p2_incremento_ja_queimado_km2"),
        ]}/>
      <LineChart titulo="Convergências e surgimentos"
        datas={datasTransicao} dataAtual={dia} onSelect={selecionarData}
        unidade="eventos geométricos" series={[
          linha("Convergências", cores.roxo, transicoes, "eventos_convergencia"),
          linha("Surgimentos sem sobreposição", cores.azul, transicoes, "eventos_surgimento_sem_sobreposicao"),
        ]}/>
    </div>
    <Aviso>Convergência é uma propriedade geométrica do produto espacial, não prova de encontro entre frentes de fogo. Confira intervalos maiores que um dia antes de interpretar picos.</Aviso>
  </>;

  if (carregando) return <div className="empty-chart">Carregando os indicadores originais da Etapa 4...</div>;
  if (erro) return <div className="empty-chart" role="alert">Análise da Etapa 4 indisponível: {erro}</div>;

  if (aba === "movimento") return <>
    <Introducao titulo="Movimento e cinco trajetórias"
      texto="Centroide e quatro extremos cardeais da região P2. O deslocamento desses descritores registra alterações do envelope espacial, não o percurso físico de uma frente de fogo."/>
    {!analise?.disponivel ? <div className="empty-chart">
      A Etapa 4 ainda não está disponível para este ID. Execute o pipeline completo para produzir pontos, segmentos e indicadores de trajetória.
    </div> : <div className="charts-grid">
      <CincoTrajetorias pontos={pontos} dia={dia}/>
      <LineChart titulo="Deslocamento entre centroides" datas={datasIndicadores}
        dataAtual={dia} onSelect={selecionarData} unidade="km" series={[
          linha("Distância do centroide", cores.laranja, indicadores, "deslocamento_centroide_km"),
        ]}/>
      <LineChart titulo="Variação da amplitude espacial" datas={datasIndicadores}
        dataAtual={dia} onSelect={selecionarData} unidade="km" series={[
          linha("Δ Norte-Sul", cores.azul, indicadores, "delta_amplitude_ns_km"),
          linha("Δ Leste-Oeste", cores.roxo, indicadores, "delta_amplitude_lo_km"),
        ]}/>
      <div className="full-chart">
        <LineChart titulo="Avanço dos extremos cardeais" datas={datasIndicadores}
          dataAtual={dia} onSelect={selecionarData} unidade="km" series={[
            linha("Norte", cores.azul, indicadores, "avanco_norte_km"),
            linha("Sul", cores.verde, indicadores, "avanco_sul_km"),
            linha("Leste", cores.roxo, indicadores, "avanco_leste_km"),
            linha("Oeste", cores.vermelho, indicadores, "avanco_oeste_km"),
          ]}/>
      </div>
    </div>}
    <Aviso>Saltos dos extremos podem decorrer de mudança do vértice selecionado ou fusão de componentes. A interpretação física exige confrontar o mapa e outras fontes.</Aviso>
  </>;

  if (aba === "direcoes") {
    const datasDisponiveis=Array.from(new Set([
      ...transicoes.map(t=>t.data_atual??""),
      ...segmentos.map(t=>t.data_atual??""),
    ].filter(Boolean))).sort();
    const periodo = (r:Linha) => {
      const data=r.data_atual??"";
      return data!==""&&(!inicioFiltro||data>=inicioFiltro)&&(!fimFiltro||data<=fimFiltro);
    };
    const transicoesPeriodo=transicoes.filter(periodo);
    const segmentosPeriodo=segmentos.filter(periodo);
    const tr=transicoesPeriodo.map(r=>({
      angulo: numero(r,"tr_azimute_centroide_graus"),
      peso: numero(r,"tr_deslocamento_centroide_km"),
      data: r.data_atual??"",
    })).filter((v):v is AnguloPonderado=>v.angulo!==null&&v.peso!==null&&v.peso>0);
    const igt=transicoesPeriodo.map(r=>({
      angulo:numero(r,"igt_azimute_ponderado_graus"),
      peso:numero(r,"p2_incremento_geometrico_km2"),
      data:r.data_atual??"",
    })).filter((v):v is AnguloPonderado=>v.angulo!==null&&v.peso!==null&&v.peso>0);
    const feixes=TRAJETORIAS.map(t=>({
      ...t,
      dados:segmentosPeriodo.filter(s=>s.ponto===t.id).map(s=>({
        angulo:numero(s,"azimute_geodesico_graus"),
        peso:numero(s,"distancia_geodesica_km"),
        data:s.data_atual??"",
      })).filter((v):v is AnguloPonderado=>
        v.angulo!==null&&v.peso!==null&&v.peso>0),
    }));
    const escalaKm=Math.max(0,distribuicaoDirecional(tr).maximo,
      ...feixes.map(f=>distribuicaoDirecional(f.dados).maximo));
    return <>
      <Introducao titulo="Direções e rosáceas"
        texto="Distribuições azimutais com 16 setores. Compare direções apenas entre ponderações com a mesma unidade; selecione setores e datas para sincronizar a linha do tempo."/>
      <div className="rose-period-control">
        <label htmlFor="rose-from">A partir de
          <select id="rose-from" value={inicioFiltro} onChange={e=>setInicioFiltro(e.target.value)}>
            <option value="">Primeira observação</option>
            {datasDisponiveis.map(d=><option value={d} key={d}>{d}</option>)}
          </select>
        </label>
        <label htmlFor="rose-to">Até
          <select id="rose-to" value={fimFiltro} onChange={e=>setFimFiltro(e.target.value)}>
            <option value="">Última observação</option>
            {datasDisponiveis.map(d=><option value={d} key={d}>{d}</option>)}
          </select>
        </label>
        <button className="secondary-button compact" type="button"
          disabled={!inicioFiltro&&!fimFiltro}
          onClick={()=>{setInicioFiltro("");setFimFiltro("");}}>Limpar período</button>
        <span role="status">
          {inicioFiltro&&fimFiltro&&inicioFiltro>fimFiltro?
            "Intervalo invertido. Ajuste as datas.":
            transicoesPeriodo.length+" transições observadas no recorte"}
        </span>
      </div>
      <div className="rose-grid">
        <RosaDirecional key={"tr:"+inicioFiltro+":"+fimFiltro}
          titulo="TR · Centroide" dados={tr} unidade="km" ponto="centroide"
          escalaComum={escalaKm} selecionarData={selecionarData}
          mostrarSegmento={mostrarSegmento}
          subtitulo="Ponderação: distância do centroide (km)"/>
        <RosaDirecional key={"igt:"+inicioFiltro+":"+fimFiltro}
          titulo="IGT · Incremento P2" dados={igt} unidade="km²"
          selecionarData={selecionarData}
          subtitulo="Ponderação: incremento geométrico do P2 (km²)"/>
      </div>
      {analise?.disponivel?<>
        <h3 className="analysis-subtitle">Cinco feixes representativos</h3>
        <div className="rose-grid">
          {feixes.map(t=><RosaDirecional
            key={t.id+":"+inicioFiltro+":"+fimFiltro}
            titulo={t.rotulo} dados={t.dados} unidade="km" ponto={t.id}
            escalaComum={escalaKm} selecionarData={selecionarData}
            mostrarSegmento={mostrarSegmento}
            subtitulo="Ponderação: distância geodésica (km)"/>)}
        </div>
      </>:<div className="empty-chart">As rosáceas dos cinco extremos requerem os arquivos da Etapa 4.</div>}
      <Aviso>Os setores descrevem variações geométricas. Para TR, abra o deslocamento de uma transição no mapa quando os dois pontos geográficos existirem. IGT não é representado por uma seta de movimento. Não infira vento ou propagação de fogo ativo.</Aviso>
    </>;
  }

  return <>
    <Introducao titulo="Forma e deformação"
      texto="Índice de forma, similaridade e alterações da extensão da região P2. Estes descritores detectam mudanças de geometria, sem atribuir automaticamente uma causa física."/>
    {!analise?.disponivel ? <div className="empty-chart">
      A Etapa 4 não está disponível neste evento; a análise de forma exige seus indicadores.
    </div> : <div className="charts-grid">
      <LineChart titulo="Índice de forma do P2" datas={datasIndicadores}
        dataAtual={dia} onSelect={selecionarData} unidade="adimensional" series={[
          linha("Forma P2", cores.verde, indicadores, "indice_forma_atual"),
        ]}/>
      <LineChart titulo="Similaridade de Jaccard P2" datas={datasIndicadores}
        dataAtual={dia} onSelect={selecionarData} unidade="0 a 1" series={[
          linha("Interseção / união", cores.azul, indicadores, "jaccard_geometrico"),
        ]}/>
      <LineChart titulo="Variação do índice de forma" datas={datasIndicadores}
        dataAtual={dia} onSelect={selecionarData} unidade="adimensional" series={[
          linha("Δ forma", cores.roxo, indicadores, "delta_indice_forma"),
        ]}/>
      <LineChart titulo="Perímetro do P2" datas={datasIndicadores}
        dataAtual={dia} onSelect={selecionarData} unidade="km" series={[
          linha("Perímetro na data", cores.laranja, indicadores, "perimetro_atual_km"),
        ]}/>
    </div>}
    <Aviso>O índice de forma depende da resolução e do tratamento dos contornos. Uma mudança abrupta pode refletir fragmentação, contato entre polígonos ou artefatos de representação.</Aviso>
  </>;
}
