export type LinhaNumerica = Record<string, string | null>;

export function numero(r: LinhaNumerica | null | undefined, campo: string): number | null {
  const valor = r?.[campo];
  if (valor === undefined || valor === null || valor.trim() === "") return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

export function nomeDia(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return dia + "/" + mes + "/" + ano;
}

export function formatarNumero(n: number | null, casas = 2): string {
  return n === null
    ? "N/D"
    : n.toLocaleString("pt-BR", {
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      });
}
