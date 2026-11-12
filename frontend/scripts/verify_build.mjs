import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

// O painel inicial deve ser pequeno: MapLibre é carregado por import().
const raiz = resolve(import.meta.dirname, "..");
const html = readFileSync(resolve(raiz, "dist/index.html"), "utf8");
const principal = html.match(/<script[^>]*src="\/assets\/([^"]+\.js)"/);
if (!principal) {
  throw new Error("HTML compilado sem entrada JavaScript identificável");
}
const arquivos = readdirSync(resolve(raiz, "dist/assets"));
const bytesPrincipal = statSync(
  resolve(raiz, "dist/assets", principal[1]),
).size;
const mapaDiferido = arquivos.some(n => /^MapPanel-[^.]+\.js$/.test(n));
console.log(JSON.stringify({
  main_bundle_bytes: bytesPrincipal,
  main_bundle_kib: Math.round(bytesPrincipal / 1024),
  map_lazily_bundled: mapaDiferido,
}));
if (!mapaDiferido) {
  throw new Error("MapLibre não foi separado do carregamento inicial");
}
if (bytesPrincipal > 550_000) {
  throw new Error("Bundle de entrada excede orçamento de 550 KB (sem gzip)");
}
