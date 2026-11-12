export type Camada = "p1" | "p2";

export interface EventoListado {
  id_incendio: number;
}

export interface VisaoEvento {
  id_incendio: number;
  datas: string[];
  periodo_inicio: string | null;
  periodo_fim: string | null;
  total_datas: number;
  tem_series: boolean;
  tem_transicoes: boolean;
  status_cientifico: string;
  validacao_externa_concluida: boolean;
  dias_sobreposicao_p1_pendentes: string[];
  observacao: string;
}

export interface Propriedades {
  id_incendio?: number;
  data?: string;
  rank?: number;
  rank_global?: number;
  area_km2?: number;
  [chave: string]: unknown;
}

export interface Feicao {
  type: "Feature";
  properties: Propriedades;
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: unknown;
  };
}

export interface Colecao {
  type: "FeatureCollection";
  features: Feicao[];
}

export type Linha = Record<string, string | null>;

export interface DadosDia {
  data: string;
  metricas: Linha | null;
  transicao: Linha | null;
}

export interface AnaliseEtapa4 {
  disponivel: boolean;
  pontos: Linha[];
  segmentos: Linha[];
  indicadores: Linha[];
}
