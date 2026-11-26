/** Geometria descritiva das 16 direções; não representa frente ativa de fogo. */
export type ContribuicaoDirecional = {
  angulo: number;
  peso: number;
  data: string;
};
export const DIRECOES = [
  "N","NNE","NE","ENE","E","ESE","SE","SSE",
  "S","SSO","SO","OSO","O","ONO","NO","NNO",
] as const;

export function indiceDirecional(angulo: number): number {
  return Math.floor((((angulo % 360) + 360 + 11.25) % 360) / 22.5);
}

export function distribuicaoDirecional(dados: ContribuicaoDirecional[]) {
  const pesos = Array.from({length:16},()=>0);
  const validos = dados.filter(d =>
    Number.isFinite(d.angulo) && Number.isFinite(d.peso) && d.peso > 0
  );
  let cs=0, sn=0, total=0;
  for(const p of validos) {
    const rad = p.angulo*Math.PI/180;
    pesos[indiceDirecional(p.angulo)] += p.peso;
    cs += p.peso * Math.cos(rad);
    sn += p.peso * Math.sin(rad);
    total += p.peso;
  }
  const modulo = Math.hypot(cs,sn);
  return {
    pesos, total,
    maximo: Math.max(0,...pesos),
    media: total>0 && modulo > 1e-8
      ? (Math.atan2(sn,cs)*180/Math.PI+360)%360 : null,
    concentracao: total>0?modulo/total:0,
    validos,
  };
}

export function intervaloSetor(indice:number):string {
  const a = ((indice*22.5-11.25)+360)%360;
  const b = (indice*22.5+11.25)%360;
  return a.toFixed(2)+"° a "+b.toFixed(2)+"°";
}

export function filtrarIntervalo<T extends {data:string}>(
  registros:T[], inicio:string, fim:string
):T[] {
  return registros.filter(r => r.data &&
    (!inicio||r.data>=inicio) && (!fim||r.data<=fim));
}
