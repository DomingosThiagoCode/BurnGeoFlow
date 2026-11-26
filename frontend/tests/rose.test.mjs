import test from "node:test";
import assert from "node:assert/strict";
import {
  indiceDirecional, distribuicaoDirecional, intervaloSetor, filtrarIntervalo,
} from "../src/utils/rose.ts";

test("16 setores, azimutes negativos, 360° e limites", () => {
  assert.equal(indiceDirecional(0),0);
  assert.equal(indiceDirecional(360),0);
  assert.equal(indiceDirecional(-1),0);
  assert.equal(indiceDirecional(11.24),0);
  assert.equal(indiceDirecional(11.25),1);
  assert.equal(indiceDirecional(348.75),0);
  assert.equal(indiceDirecional(90),4);
  assert.equal(indiceDirecional(180),8);
  assert.equal(intervaloSetor(0),"348.75° a 11.25°");
});
test("soma ponderada, direção média, concentração e dados inválidos",()=>{
  const r=distribuicaoDirecional([
    {angulo:90,peso:2,data:"2020-01-02"},
    {angulo:90,peso:3,data:"2020-01-03"},
    {angulo:270,peso:1,data:"2020-01-04"},
    {angulo:0,peso:0,data:"2020-01-05"},
    {angulo:Number.NaN,peso:10,data:"2020-01-06"},
    {angulo:45,peso:-2,data:"2020-01-07"},
  ]);
  assert.equal(r.total,6);
  assert.equal(r.pesos[4],5);
  assert.equal(r.pesos[12],1);
  assert.ok(Math.abs(r.media-90)<1e-10);
  assert.ok(Math.abs(r.concentracao-2/3)<1e-10);
  assert.equal(r.validos.length,3);
  assert.equal(distribuicaoDirecional([]).media,null);
  assert.equal(distribuicaoDirecional([]).concentracao,0);
  assert.equal(distribuicaoDirecional([
    {angulo:0,peso:1,data:"a"},{angulo:180,peso:1,data:"b"},
  ]).media,null);
});
test("filtro inclusivo recorta registros sem inventar observações",()=>{
  const d=[
    {data:"2020-08-09",peso:1},
    {data:"2020-08-12",peso:2},
    {data:"2020-08-15",peso:3},
  ];
  assert.deepEqual(filtrarIntervalo(d,"2020-08-10","2020-08-14"),[d[1]]);
  assert.deepEqual(filtrarIntervalo(d,"2020-08-13","2020-08-14"),[]);
  assert.deepEqual(filtrarIntervalo(d,"",""),d);
});
