import { useEffect, useId, useMemo, useRef, useState } from "react";
import { formatarNumero, nomeDia } from "../services/api";

export type SerieGrafico = {
  label: string;
  cor: string;
  valores: (number | null)[];
};

type Props = {
  titulo: string;
  datas: string[];
  series: SerieGrafico[];
  unidade?: string;
  onSelect?: (data: string) => void;
  dataAtual?: string;
};

export function LineChart({
  titulo, datas, series, unidade = "km²", onSelect, dataAtual,
}: Props) {
  const uid = useId().replace(/:/g, "_");
  const recipiente = useRef<HTMLDivElement>(null);
  const [largura, setLargura] = useState(740);
  // Renderiza eixos e rótulos em pixels legíveis no tamanho real do cartão.
  // O viewBox fixo anterior reduzia também a tipografia em telas pequenas.
  useEffect(() => {
    const el = recipiente.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const w = Math.round(entry.contentRect.width);
      if (w > 0) setLargura(Math.max(320, w));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const altura = 210;
  const margem = { topo: 15, direita: 22, inferior: 35, esquerda: 54 };
  const xMin = margem.esquerda, xMax = largura - margem.direita;
  const yMin = margem.topo, yMax = altura - margem.inferior;
  const valores = series.flatMap((s) => s.valores)
    .filter((n): n is number => n !== null && Number.isFinite(n));
  const max = Math.max(1, ...valores), min = Math.min(0, ...valores);
  const dominio = max === min ? 1 : max - min;
  const X = (i: number) => xMin + (datas.length < 2 ? 0 : i/(datas.length-1)) * (xMax-xMin);
  const Y = (v: number) => yMax - ((v-min)/dominio)*(yMax-yMin);
  const selected = Math.max(0, datas.indexOf(dataAtual ?? ""));
  const paths = useMemo(() => series.map((serie) => {
    const d = serie.valores.map((n, i) => n === null
      ? null : { x: X(i), y: Y(n) });
    let desenho = "", aberto = false;
    for (const p of d) {
      if (!p) { aberto = false; continue; }
      desenho += (aberto ? " L" : " M") + p.x.toFixed(2) + " " + p.y.toFixed(2);
      aberto = true;
    }
    return desenho.trim();
  }), [series, datas, largura]);
  if (!datas.length || !valores.length) {
    return <div className="empty-chart">Sem valores para o gráfico {titulo}.</div>;
  }
  return (
    <section className="chart-panel">
      <div className="chart-heading">
        <h3>{titulo}</h3>
        <span>{unidade}</span>
      </div>
      <div className="chart-scroll" ref={recipiente}>
        <svg viewBox={"0 0 " + largura + " " + altura} role="img"
          aria-label={titulo + ". Consulte a legenda para séries."}
          className="chart-svg">
          <defs>
            <clipPath id={uid}>
              <rect x={xMin} y={yMin} width={xMax-xMin} height={yMax-yMin}/>
            </clipPath>
          </defs>
          {[0, 0.25, 0.5, 0.75, 1].map((fra, i) => {
            const yy = yMax - fra*(yMax-yMin), val = min + fra*dominio;
            return <g key={i}>
              <line x1={xMin} x2={xMax} y1={yy} y2={yy}
                stroke="#e3e0d5" strokeWidth="1"/>
              <text x={xMin-10} y={yy+4} textAnchor="end"
                fill="#818477" fontSize="11">{formatarNumero(val, 0)}</text>
            </g>;
          })}
          <line x1={xMin} y1={yMax} x2={xMax} y2={yMax}
            stroke="#bcbdb1"/>
          {datas.filter((_,i) => i===0 || i===datas.length-1 ||
            i===Math.floor((datas.length-1)/2)).map((iso) => {
            const i = datas.indexOf(iso);
            return <text key={iso} x={X(i)} y={altura-11}
              textAnchor={i===0?"start":i===datas.length-1?"end":"middle"}
              fill="#818477" fontSize="11">{nomeDia(iso).slice(0,5)}</text>;
          })}
          <g clipPath={"url(#" + uid + ")"}>
            {series.map((serie, i) =>
              <path key={serie.label} d={paths[i]} fill="none"
                stroke={serie.cor} strokeWidth="2.6"
                strokeLinecap="round" strokeLinejoin="round"/> )}
            {datas.includes(dataAtual ?? "") && <line
              x1={X(selected)} x2={X(selected)} y1={yMin} y2={yMax}
              stroke="#aa4b36" strokeDasharray="4 4" strokeWidth="1.4" />}
            {series.map((s) => {
              const v = s.valores[selected];
              return v !== null && v !== undefined ? <circle
                key={s.label} cx={X(selected)} cy={Y(v)} r="4"
                fill={s.cor} stroke="white" strokeWidth="1.6" /> : null;
            })}
          </g>
          {onSelect && <rect x={xMin} y={yMin}
            width={xMax-xMin} height={yMax-yMin} fill="transparent"
            style={{cursor:"crosshair"}}
            onClick={e => {
              const bounds=e.currentTarget.getBoundingClientRect();
              const fraction=(e.clientX-bounds.left)/bounds.width;
              const index=Math.max(0,Math.min(datas.length-1,
                Math.round(fraction*(datas.length-1))));
              onSelect(datas[index]);
            }}/>}
        </svg>
      </div>
      <div className="chart-legend">
        {series.map(s => <span key={s.label}>
          <i style={{backgroundColor:s.cor}}/> {s.label}
          {s.valores[selected] != null && (
            <b>{formatarNumero(s.valores[selected])}</b>
          )}
        </span>)}
      </div>
    </section>
  );
}
