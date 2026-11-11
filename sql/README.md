> **ARQUIVADO EM 08/11/2026:** esta documentação descreve uma
> implementação SQL histórica que **não foi executada em um servidor PostGIS**
> neste projeto. O método canônico agora está em Python; ver
> [ARQUIVADO.md](ARQUIVADO.md) e
> [fechamento científico](../docs/fechamento_etapa4.md).
>
# SQL/PostGIS — métodos TR e IGT (generalização multi-ID)

Dois descritores complementares da **região móvel P2** de área queimada
acumulada, com nomes científicos e sem títulos militares:

| Sigla | Nome | Pergunta respondida | Referência/estado |
| --- | --- | --- | --- |
| **TR** | **Trajetórias Representativas** | Como variam os extremos N/S/L/O e o centroide do polígono acumulado? | Adaptação da metodologia de **Oliveira e Barbosa (2025)**. |
| **IGT** | **Incrementos Geométricos Temporais** | Onde está a área **nova** de `R(t+1) \ R(t)` e qual é sua distribuição direcional? | Operacionalização da **diferença geométrica** do organograma fornecido; equivalência detalhada ao artigo do INPE **pendente de leitura**. |

IGT não calcula nem afirma velocidades de avanço da **frente ativa** do fogo.
Uma componente IGT é uma parte topologicamente conexa da área incremental
**detectada** e não necessariamente um foco independente.

## Fontes originais — rastreabilidade

Os códigos da autora [Priscila-IME/Trajetoria-furacao](https://github.com/Priscila-IME/Trajetoria-furacao)
foram verificados **byte a byte** com os três exemplares disponibilizados ao
projeto; os hashes Git *blob* coincidiram:

| Código histórico | SHA Git blob | O que foi aproveitado |
| --- | --- | --- |
| [`20240822 vertices.sql`](https://github.com/Priscila-IME/Trajetoria-furacao/blob/main/20240822%20vertices.sql) | `4af62be9da521d17987c5949ef8141be08b52848` | extremos de vértices e centroide |
| [`20240823criatraj.sql`](https://github.com/Priscila-IME/Trajetoria-furacao/blob/main/20240823criatraj.sql) | `e41a920bdf7cf950799b91164e9ebaa48937f3ce` | cinco linhas de trajetória |
| [`20240823 metricas.sql`](https://github.com/Priscila-IME/Trajetoria-furacao/blob/main/20240823%20metricas.sql) | `a644be8a5921837a04d88fa0dc641ec79c78c988` | distância geodésica, azimute, diferenças orientadas |

As fontes originais são específicas do esquema `furacao`, dataset Beryl,
não particionam por ID, usam `EPSG:3857` para alguns deltas e contêm uma
consulta **inacabada** ao final de `20240823 metricas.sql` (sequência `ELSE`
inválida). Os scripts neste diretório são **adaptações independentes** e
corrigem esses pontos; não reproduzem literalmente saídas numéricas históricas.
Não copiamos os arquivos originais para este repositório: os links e hashes
preservam a proveniência no projeto da autora.

Outras referências:

- OLIVEIRA, P. B.; BARBOSA, I. *Proposta de modelagem de trajetórias de regiões móveis*. Revista Brasileira de Geomática, 13(1), 52–76, 2025. [DOI:10.3895/rbgeo.v13n1.19241](https://doi.org/10.3895/rbgeo.v13n1.19241).
- [Referência INPE encaminhada pelo orientador](http://mtc-m16c.sid.inpe.br/col/sid.inpe.br/mtc-m16c/2022/12.16.16.26/doc/thisInformationItemHomePage.html). O endereço não disponibilizou o documento durante esta etapa; **autoria, título, equações e correspondência com IGT não foram validados**. Solicitar PDF para comparação científica formal.

## Contrato de entrada e generalização

No PostgreSQL com **PostGIS 3+**, importar **P2**, sem agregá-lo com P1.
O contrato de entrada é uma tabela chamada `public.p2_regiao_movel`:

| Campo | Tipo esperado | Regra |
| --- | --- | --- |
| `id_incendio` | `bigint` | identifica o evento |
| `data` | `date` | observação temporal, sem duplicatas por ID |
| `rank_global` | `integer` | rank no P1 do dia (pode ser maior que 1) |
| `geom` | `geometry(Polygon ou MultiPolygon, 4326)` | geometria válida em WGS84; pode ser multipartes |

No QGIS, importe o GeoJSON `P2_regiao_movel_<ID>.geojson` com
**Banco de Dados → Gerenciador BD → Importar camada**; nomeie a tabela
`public.p2_regiao_movel` e confira os quatro tipos acima. Para múltiplos
eventos, acrescente novas linhas a essa mesma tabela; não sobrescreva o
evento antigo. Se o importador criar `data` como texto, converta para
`date` em uma **tabela nova revisada**, antes de executar as views.

Consultas diagnósticas de leitura, a serem executadas **antes** das views:

```sql
SELECT id_incendio, COUNT(*) AS registros, COUNT(DISTINCT data) AS datas
FROM public.p2_regiao_movel
GROUP BY id_incendio;

SELECT id_incendio, data, COUNT(*) AS duplicadas
FROM public.p2_regiao_movel
GROUP BY id_incendio, data HAVING COUNT(*) <> 1;

SELECT id_incendio, data, ST_SRID(geom) AS srid,
       ST_IsValid(geom) AS valido, GeometryType(geom) AS tipo
FROM public.p2_regiao_movel
WHERE geom IS NULL OR ST_SRID(geom) <> 4326
   OR NOT ST_IsValid(geom)
   OR GeometryType(geom) NOT IN ('POLYGON', 'MULTIPOLYGON');
```

**Critério de entrada:** as duas últimas consultas retornam **zero linhas**,
e `registros = datas` para cada ID. Verifique também dias em ordem e ID de
origem. Não executar as views sobre geometrias inválidas ou repetidas.

## Ordem de execução

Execute os SQLs na sequência, com QGIS/DB Manager ou `psql` (sem apagar dados):

1. [`01_trajetorias_representativas.sql`](01_trajetorias_representativas.sql): três views `analise.tr_pontos`, `analise.tr_segmentos`, `analise.tr_linhas`.
2. [`02_incrementos_geometricos_temporais.sql`](02_incrementos_geometricos_temporais.sql): views `analise.igt_geometrias`, `analise.igt_componentes`, `analise.igt_indicadores`.
3. [`03_comparacao.sql`](03_comparacao.sql): view `analise.tr_igt_comparacao`.

Exemplo para **qualquer** ID, sem alterar os SQLs:

```sql
SELECT * FROM analise.tr_igt_comparacao
WHERE id_incendio = 24340828 ORDER BY data_atual;

SELECT * FROM analise.tr_linhas WHERE id_incendio = 24340828;
SELECT data_atual, geom FROM analise.igt_indicadores
WHERE id_incendio = 24340828 ORDER BY data_atual;
```

`ST_Difference` atua topologicamente em geometrias **WGS84** no SQL;
as áreas e distâncias SQL usam **geography / elipsoide WGS84**. A auditoria
independente em Python projeta as geometrias para uma **LAEA local** antes
da diferença/área. Por isso há uma divergência metodológica residual a
medir: os dois caminhos **não produzem números rigorosamente idênticos**.
O SQL não fixa `3857` ou zona UTM e isola eventos com `PARTITION BY id_incendio`.
O desempate dos extremos é determinístico e usa proximidade ao centroide.

O azimute IGT usa **média circular ponderada por área** dos vetores do
centroide anterior para o centroide de cada componente nova. A concentração
direcional varia de 0 a 1; quando menor que **0,01** o azimute médio fica
`NULL`, por cancelamento, limite operacional a discutir com o orientador.

## Validação disponível e limites

Uma implementação **independente** Shapely/PyProj de IGT, com testes
analíticos e caso real, está em
[`scripts/analisar_incrementos_geometricos.py`](../scripts/analisar_incrementos_geometricos.py).
Comando de reprodução:

```bash
python -m pip install -r requirements-auditoria.txt
python scripts/analisar_incrementos_geometricos.py \
  dados/estudo_caso_24340828/P1_componentes_24340828.geojson \
  dados/estudo_caso_24340828/P2_regiao_movel_24340828.geojson \
  --saida resultados/etapa4
python -m unittest discover -s tests -v
```

**Resultado para ID 24340828:** 57 datas, 56 transições, 506 componentes
geométricas de incremento (inclui nove partes menores que 1 m²),
**949,843489 km² de acréscimos** acumulados entre transições e perda de
0,000000526 km². Erro máximo de fechamento por transição de
**0,00000180 m²** na LAEA. Saídas CSV, GeoJSON e JSON em
[`resultados/etapa4/`](../resultados/etapa4/).

**Limite de evidência: o SQL PostGIS ainda NÃO foi executado em um servidor
real neste ambiente.** Foram testadas a lógica de diferença espacial por
implementação independente, a sintaxe estrutural por inspeção e as regras
de generalização por verificações estáticas — isso **não** equivale ao
teste integral das views no banco. Resta executar as três views no PostGIS,
exportar os resultados do mesmo ID e confrontar contagens, áreas e azimutes
com tolerâncias ajustadas à diferença WGS84/LAEA.
