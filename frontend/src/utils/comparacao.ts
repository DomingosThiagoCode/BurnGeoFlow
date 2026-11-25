/** Comparação observacional entre incêndios distintos.
 * Não produz inferências físicas nem preenche dias sem observação.
 * Áreas são da LAEA local de CADA evento; comparar contagens e tendências,
 * não assumir que áreas de eventos distintos compartilhem a mesma geometria.
 */
export type RegistroComparacao = Record<string, string | null>;

export type ModoComparacao = "absoluta" | "relativa" | "dominancia";

export interface ObservacaoComparacao {
  data: string;
  diaRelativo: number;
  areaP1: number;
  areaP2: number | null;
  participacaoP2: number | null;
  componentes: number | null;
}

export interface PerfilComparacao {
  id: number;
  inicio: string;
  fim: string;
  duracaoDias: number;
  numeroObservacoes: number;
  intervalosMultidia: number;
  areaInicial: number;
  areaFinal: number;
  participacaoFinal: number | null;
  maximoComponentes: number | null;
  observacoes: ObservacaoComparacao[];
}

function dataUTC(iso: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) throw new Error("Data inválida na série: " + iso);
  const epoch = Date.parse(iso + "T00:00:00Z");
  if (!Number.isFinite(epoch) || new Date(epoch).toISOString().slice(0, 10) !== iso) {
    throw new Error("Data inválida na série: " + iso);
  }
  return epoch;
}

function valor(registro: RegistroComparacao, campo: string): number | null {
  const texto = registro[campo];
  if (texto == null || texto.trim() === "") return null;
  const n = Number(texto);
  if (!Number.isFinite(n)) throw new Error("Número inválido em " + campo);
  return n;
}

export function construirPerfil(
  id: number, serie: RegistroComparacao[],
): PerfilComparacao | null {
  if (!serie.length) return null;
  const registros = serie.map((registro) => {
    const data = registro.data;
    if (!data) throw new Error("Série sem data");
    const tempo = dataUTC(data);
    const areaP1 = valor(registro, "area_total_laea_km2");
    const areaP2 = valor(registro, "p2_area_laea_km2");
    const componentes = valor(registro, "numero_patches");
    if (areaP1 === null) {
      throw new Error("Área P1 indisponível em " + data);
    }
    if (areaP1 < 0 || (areaP2 !== null && (areaP2 < 0 || areaP2 > areaP1 + 0.001))) {
      throw new Error("Áreas incoerentes em " + data);
    }
    if (componentes !== null && (!Number.isInteger(componentes) || componentes < 0)) {
      throw new Error("Número de componentes incoerente em " + data);
    }
    return { data, tempo, areaP1, areaP2, componentes };
  }).sort((a, b) => a.tempo - b.tempo);
  for (let i = 1; i < registros.length; i++) {
    if (registros[i].tempo === registros[i-1].tempo) {
      throw new Error("Data repetida na série: " + registros[i].data);
    }
  }
  const t0 = registros[0].tempo;
  const final = registros[registros.length - 1];
  const observacoes = registros.map((registro) => ({
    data: registro.data,
    diaRelativo: Math.round((registro.tempo - t0) / 86400000),
    areaP1: registro.areaP1,
    areaP2: registro.areaP2,
    participacaoP2: registro.areaP2 !== null && registro.areaP1 > 0
      ? 100 * registro.areaP2 / registro.areaP1 : null,
    componentes: registro.componentes,
  }));
  const componentes = observacoes.map(x => x.componentes)
    .filter((n): n is number => n !== null);
  return {
    id,
    inicio: registros[0].data,
    fim: final.data,
    duracaoDias: observacoes[observacoes.length-1].diaRelativo,
    numeroObservacoes: observacoes.length,
    intervalosMultidia: observacoes.slice(1)
      .filter((o, i) => o.diaRelativo - observacoes[i].diaRelativo > 1).length,
    areaInicial: registros[0].areaP1,
    areaFinal: final.areaP1,
    participacaoFinal: observacoes[observacoes.length - 1].participacaoP2,
    maximoComponentes: componentes.length ? Math.max(...componentes) : null,
    observacoes,
  };
}

export function valorComparacao(
  observacao: ObservacaoComparacao, perfil: PerfilComparacao, modo: ModoComparacao,
): number | null {
  if (modo === "dominancia") return observacao.participacaoP2;
  if (modo === "relativa") return perfil.areaFinal > 0
    ? 100 * observacao.areaP1 / perfil.areaFinal : null;
  return observacao.areaP1;
}

/** Dados pontuais; os dias ausentes nunca viram valores inventados. */
export function serieComparacao(
  perfil: PerfilComparacao, modo: ModoComparacao,
): { dia: number; valor: number }[] {
  return perfil.observacoes.flatMap((obs) => {
    const v = valorComparacao(obs, perfil, modo);
    return v === null ? [] : [{ dia: obs.diaRelativo, valor: v }];
  });
}
