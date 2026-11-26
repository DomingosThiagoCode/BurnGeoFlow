import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const story = JSON.parse(readFileSync(new URL("../public/story/24340828.json", import.meta.url), "utf8"));

test("o estudo narrativo preserva 57 observações sem datas inventadas", () => {
  assert.equal(story.id, 24340828);
  assert.equal(story.frames.length, 57);
  assert.equal(story.frames[0].date, "2020-08-09");
  assert.equal(story.frames.at(-1).date, "2020-10-09");
  assert.equal(new Set(story.frames.map(f => f.date)).size, 57);
  assert.ok(story.frames.every((f, i, a) => i === 0 || a[i - 1].date < f.date));
});

test("P1, P2, cinco trajetórias e incrementos usam a mesma base temporal", () => {
  assert.ok(story.frames.every(f => f.p1.startsWith("M") && f.p2.startsWith("M")));
  assert.ok(story.frames.every(f =>
    ["centroide", "norte", "sul", "leste", "oeste"].every(k => f.tr[k]?.length === 2)
  ));
  assert.ok(story.frames.slice(1).some(f => f.igt.startsWith("M")));
  assert.ok(story.frames.at(-1).area_km2 > story.frames[0].area_km2);
  assert.ok(story.frames.every(f => f.area_km2 >= f.p2_km2 && f.componentes >= 1));
});

test("representação SVG é identificada como visualização derivada, não fonte analítica", () => {
  assert.match(story.method, /Não usar para medidas analíticas/);
  assert.match(story.source, /GlobFire v2/);
  assert.deepEqual(story.viewBox, [0, 0, 1000, 760]);
});
