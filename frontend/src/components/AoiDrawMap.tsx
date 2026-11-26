import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MapGL } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

export type PoligonoAOI = { type: "Polygon"; coordinates: number[][][] };

type Props = {
  onChange: (geometria: PoligonoAOI | null) => void;
};

const COLLECTION_VAZIA = { type: "FeatureCollection", features: [] };

function geojsonPontos(pontos: number[][]) {
  return {
    type: "FeatureCollection",
    features: pontos.map((coord, i) => ({
      type: "Feature", properties: { ordem: i + 1 },
      geometry: { type: "Point", coordinates: coord },
    })),
  };
}

function geojsonLinha(pontos: number[][]) {
  return pontos.length < 2 ? COLLECTION_VAZIA : {
    type: "FeatureCollection",
    features: [{
      type: "Feature", properties: {},
      geometry: { type: "LineString", coordinates: pontos },
    }],
  };
}

function geojsonPoligono(pontos: number[][]) {
  return pontos.length < 3 ? COLLECTION_VAZIA : {
    type: "FeatureCollection",
    features: [{
      type: "Feature", properties: {},
      geometry: { type: "Polygon", coordinates: [[...pontos, pontos[0]]] },
    }],
  };
}

/** Carregado sob demanda: o catálogo não importa WebGL enquanto fechado. */
export default function AoiDrawMap({ onChange }: Props) {
  const alvo = useRef<HTMLDivElement>(null);
  const instancia = useRef<MapGL | null>(null);
  const callback = useRef(onChange);
  callback.current = onChange;
  const [pontos, setPontos] = useState<number[][]>([]);

  useEffect(() => {
    if (!alvo.current) return;
    const mapa = new maplibregl.Map({
      container: alvo.current,
      style: {
        version: 8, sources: {},
        layers: [{
          id: "fundo", type: "background",
          paint: { "background-color": "#e5e7dd" },
        }],
      },
      center: [-57.5, -17.7], zoom: 5,
      dragRotate: false, pitchWithRotate: false,
      attributionControl: false,
    });
    instancia.current = mapa;
    mapa.addControl(new maplibregl.NavigationControl({
      showCompass: false,
    }), "top-right");
    mapa.addControl(new maplibregl.AttributionControl({
      compact: true,
    }), "bottom-right");

    mapa.on("load", () => {
      mapa.addSource("osm", {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256, attribution: "© OpenStreetMap contributors",
      });
      mapa.addLayer({ id: "osm", type: "raster", source: "osm",
        paint: { "raster-opacity": 0.67 } });
      for (const nome of ["vertices", "linha", "poligono"]) {
        mapa.addSource(nome, { type: "geojson", data: COLLECTION_VAZIA });
      }
      mapa.addLayer({
        id: "area", type: "fill", source: "poligono",
        paint: { "fill-color": "#b95735", "fill-opacity": 0.22 },
      });
      mapa.addLayer({
        id: "borda", type: "line", source: "poligono",
        paint: { "line-color": "#a4452c", "line-width": 2.5 },
      });
      mapa.addLayer({
        id: "aberta", type: "line", source: "linha",
        paint: { "line-color": "#204a40", "line-width": 2,
          "line-dasharray": [3, 2] },
      });
      mapa.addLayer({
        id: "marcadores", type: "circle", source: "vertices",
        paint: { "circle-color": "#204a40", "circle-radius": 5,
          "circle-stroke-color": "#fff", "circle-stroke-width": 2 },
      });
    });
    mapa.on("click", (evento) => {
      const { lng, lat } = evento.lngLat;
      setPontos(prev => prev.length >= 200 ? prev :
        [...prev, [Number(lng.toFixed(6)), Number(lat.toFixed(6))]]);
    });
    return () => {
      mapa.remove();
      instancia.current = null;
    };
  }, []);

  useEffect(() => {
    const mapa = instancia.current;
    const mudarFonte = (nome: string, geo: unknown) => {
      const fonte = mapa?.getSource(nome) as GeoJSONSource | undefined;
      if (fonte) fonte.setData(geo as Parameters<GeoJSONSource["setData"]>[0]);
    };
    const atualizar = () => {
      mudarFonte("vertices", geojsonPontos(pontos));
      mudarFonte("linha", geojsonLinha(pontos));
      mudarFonte("poligono", geojsonPoligono(pontos));
    };
    if (mapa?.isStyleLoaded()) atualizar();
    else mapa?.once("load", atualizar);

    const geometria: PoligonoAOI | null = pontos.length < 3 ? null : {
      type: "Polygon",
      coordinates: [[...pontos, pontos[0]]],
    };
    callback.current(geometria);
  }, [pontos]);

  return (
    <div className="catalog-draw">
      <p className="catalog-note">
        Clique no mapa para marcar pelo menos três vértices da área de estudo.
        O contorno é fechado automaticamente. A busca considera os perímetros
        GlobFire que intersectam essa área.
      </p>
      <div ref={alvo} className="catalog-draw-map" role="application"
        aria-label="Mapa interativo para desenhar o polígono de consulta"/>
      <div className="catalog-draw-actions">
        <span aria-live="polite">{pontos.length} vértices
          {pontos.length >= 200 ? " (limite atingido)" :
            pontos.length < 3 ? " (mínimo: 3)" : " (área pronta para consulta)"}
        </span>
        <button type="button" className="secondary-button"
          disabled={!pontos.length}
          onClick={() => setPontos(prev => prev.slice(0, -1))}>Desfazer último</button>
        <button type="button" className="secondary-button"
          disabled={!pontos.length}
          onClick={() => setPontos([])}>Limpar desenho</button>
      </div>
      <p className="catalog-note">
        Polígono para descoberta de IDs, não delimitação oficial de bioma
        ou referência científica. Evite autointerseções.
      </p>
    </div>
  );
}
