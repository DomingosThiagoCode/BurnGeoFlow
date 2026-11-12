import test from "node:test";
import assert from "node:assert/strict";
import { numero, nomeDia, formatarNumero } from "../src/utils/format.ts";

test("leitor não transforma ausência de dado em zero", () => {
  assert.equal(numero({ area: "" }, "area"), null);
  assert.equal(numero({ area: null }, "area"), null);
  assert.equal(numero({ area: "NaN" }, "area"), null);
  assert.equal(numero({ area: "0" }, "area"), 0);
  assert.equal(numero({ area: "107.824" }, "area"), 107.824);
});

test("formatador local respeita datas e casas decimais", () => {
  assert.equal(nomeDia("2020-09-11"), "11/09/2020");
  assert.equal(formatarNumero(null), "N/D");
  assert.equal(formatarNumero(1234.5, 1), "1.234,5");
});
