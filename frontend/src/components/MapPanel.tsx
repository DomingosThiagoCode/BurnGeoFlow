import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MapaGL } from "maplibre-gl";
import type { Colecao } from "../types";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre GL JS v6 exige URL explícita do worker no build Vite.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
maplibregl.setWorkerUrl(workerUrl);

type Props = {
  id: number;
  data: string;
  p1: Colecao | null;
  p2: Colecao | null;
  mostrarP1: boolean;
  mostrarP2: boolean;
  mapaBase: boolean;
  destaque?: {coordenadas:[[number,number],[number,number]];rotulo:string}|null;
};

const VAZIO: Colecao = { type: "FeatureCollection", features: [] };

function limites(colecoes: (Colecao | null)[]): [number, number, number, number] | null {
  let oeste = Infinity, sul = Infinity, leste = -Infinity, norte = -Infinity;
  function visitar(estrutura: unknown): void {
    if (!Array.isArray(estrutura)) return;
    if (estrutura.length >= 2 && typeof estrutura[0] === "number" &&
        typeof estrutura[1] === "number") {
      const [x, y] = estrutura as number[];
      if (Number.isFinite(x) && Number.isFinite(y)) {
        oeste = Math.min(oeste, x);
        sul = Math.min(sul, y);
        leste = Math.max(leste, x);
        norte = Math.max(norte, y);
      }
      return;
    }
    for (const filho of estrutura) visitar(filho);
  }
  for (const colecao of colecoes) {
    for (const f of colecao?.features ?? []) visitar(f.geometry.coordinates);
  }
  return oeste !== Infinity ? [oeste, sul, leste, norte] : null;
}

function atualizarFonte(mapa: MapaGL, nome: string, dados: Colecao | null): void {
  const fonte = mapa.getSource(nome) as GeoJSONSource | undefined;
  if (fonte) {
    fonte.setData((dados ?? VAZIO) as unknown as Parameters<GeoJSONSource["setData"]>[0]);
  }
}

export function MapPanel({
  id, data, p1, p2, mostrarP1, mostrarP2, mapaBase, destaque,
}: Props) {
  const alvo = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const dadosMaisRecentes = useRef({ p1, p2, destaque });
  const eventoAjustado = useRef<number | null>(null);
  dadosMaisRecentes.current = { p1, p2, destaque };

  useEffect(() => {
    if (!alvo.current) return;
    const instancia = new maplibregl.Map({
      container: alvo.current,
      style: {
        version: 8,
        sources: {},
        layers: [{
          id: "fundo",
          type: "background",
          paint: { "background-color": "#e3e1d5" },
        }],
      },
      center: [-56.3, -17.0],
      zoom: 5,
      attributionControl: false,
      pitchWithRotate: false,
      dragRotate: false,
    });
    mapa.current = instancia;
    instancia.addControl(new maplibregl.NavigationControl({
      showCompass: false,
    }), "top-right");
    instancia.addControl(new maplibregl.AttributionControl({
      compact: true,
    }), "bottom-right");
    instancia.on("load", () => {
      instancia.addSource("osm", {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors",
      });
      instancia.addLayer({
        id: "osm-raster", type: "raster", source: "osm",
        paint: { "raster-opacity": 0.76 },
      });
      instancia.addSource("p1", {
        type: "geojson", data: VAZIO as unknown as Parameters<GeoJSONSource["setData"]>[0],
      });
      instancia.addSource("p2", {
        type: "geojson", data: VAZIO as unknown as Parameters<GeoJSONSource["setData"]>[0],
      });
      instancia.addLayer({
        id: "p1-fill", type: "fill", source: "p1",
        paint: { "fill-color": "#b86040", "fill-opacity": 0.32 },
      });
      instancia.addLayer({
        id: "p1-line", type: "line", source: "p1",
        paint: { "line-color": "#9a432f", "line-width": 1.5 },
      });
      instancia.addLayer({
        id: "p2-fill", type: "fill", source: "p2",
        paint: { "fill-color": "#397e76", "fill-opacity": 0.28 },
      });
      instancia.addLayer({
        id: "p2-line", type: "line", source: "p2",
        paint: { "line-color": "#2a5f5b", "line-width": 2.7 },
      });
      instancia.addSource("destaque-tr", {
        type: "geojson", data: {
          type:"FeatureCollection",features:[],
        },
      });
      instancia.addLayer({
        id:"destaque-tr-line",type:"line",source:"destaque-tr",
        paint:{"line-color":"#e2be6b","line-width":5,"line-opacity":0.96},
      });
      instancia.addSource("destaque-tr-pontos", {
        type:"geojson",data:{type:"FeatureCollection",features:[]},
      });
      instancia.addLayer({
        id:"destaque-tr-circles",type:"circle",source:"destaque-tr-pontos",
        paint:{"circle-color":"#e2be6b","circle-radius":7,
          "circle-stroke-width":2,"circle-stroke-color":"#224c3b"},
      });
      atualizarFonte(instancia, "p1", dadosMaisRecentes.current.p1);
      atualizarFonte(instancia, "p2", dadosMaisRecentes.current.p2);
    });
    instancia.on("click", (evento) => {
      const alvos = ["p2-fill", "p1-fill"].filter((c) =>
        Boolean(instancia.getLayer(c)),
      );
      const feature = instancia.queryRenderedFeatures(evento.point, { layers: alvos })[0];
      if (!feature) return;
      const props = feature.properties ?? {};
      const rotulo = document.createElement("div");
      rotulo.className = "map-popup";
      const rank = props.rank_global ?? props.rank ?? "?";
      rotulo.textContent = "Patch de rank " + rank + " | " + (props.data ?? "");
      new maplibregl.Popup({ closeButton: true })
        .setLngLat(evento.lngLat).setDOMContent(rotulo).addTo(instancia);
    });
    return () => {
      instancia.remove();
      mapa.current = null;
    };
  }, []);

  useEffect(() => {
    const instancia = mapa.current;
    if (!instancia) return;
    const atualizar = () => {
      atualizarFonte(instancia, "p1", p1);
      atualizarFonte(instancia, "p2", p2);
      const trecho=destaque?.coordenadas;
      const linha = trecho?{type:"FeatureCollection",features:[{
        type:"Feature",properties:{rotulo:destaque.rotulo},
        geometry:{type:"LineString",coordinates:trecho},
      }]}:{type:"FeatureCollection",features:[]};
      const pontos = trecho?{type:"FeatureCollection",features:trecho.map((coord,i)=>({
        type:"Feature",properties:{extremo:i===0?"anterior":"atual"},
        geometry:{type:"Point",coordinates:coord},
      }))}:{type:"FeatureCollection",features:[]};
      (instancia.getSource("destaque-tr") as GeoJSONSource|undefined)
        ?.setData(linha as Parameters<GeoJSONSource["setData"]>[0]);
      (instancia.getSource("destaque-tr-pontos") as GeoJSONSource|undefined)
        ?.setData(pontos as Parameters<GeoJSONSource["setData"]>[0]);
      const visibilidade = (flag: boolean) => flag ? "visible" : "none";
      for (const nome of ["p1-fill", "p1-line"]) {
        if (instancia.getLayer(nome)) {
          instancia.setLayoutProperty(nome, "visibility", visibilidade(mostrarP1));
        }
      }
      for (const nome of ["p2-fill", "p2-line"]) {
        if (instancia.getLayer(nome)) {
          instancia.setLayoutProperty(nome, "visibility", visibilidade(mostrarP2));
        }
      }
      if (instancia.getLayer("osm-raster")) {
        instancia.setLayoutProperty(
          "osm-raster", "visibility", visibilidade(mapaBase),
        );
      }
    };
    if (instancia.isStyleLoaded()) atualizar();
    else instancia.once("load", atualizar);
  }, [p1, p2, mostrarP1, mostrarP2, mapaBase, destaque]);

  useEffect(() => {
    if (eventoAjustado.current === id) return;
    const mapaAtual = mapa.current;
    const ext = limites([p1, p2]);
    if (!mapaAtual || !ext) return;
    if (ext[0] === ext[2] || ext[1] === ext[3]) return;
    eventoAjustado.current = id;
    mapaAtual.fitBounds([[ext[0], ext[1]], [ext[2], ext[3]]], {
      padding: 55, duration: 550, maxZoom: 12,
    });
  }, [id, p1, p2]);

  return (
    <section className="map-frame" aria-label={"Mapa de polígonos em " + data}>
      <div className="map-viewport" ref={alvo} />
      <div className="map-legend" aria-hidden="true">
        <span><i className="swatch swatch-p1" /> Componentes P1</span>
        <span><i className="swatch swatch-p2" /> Região móvel P2</span>
        {destaque&&<span><i style={{background:"#e2be6b"}}/> TR · {destaque.rotulo}</span>}
      </div>
    </section>
  );
}
