# Proveniência científica e escopo

As rotinas e testes da Etapa 7.1 foram importados do
[CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio),
mantendo os algoritmos anteriores para comparação de resultados.
O novo arquivo \`executar_pipeline.py\` coordena essa implementação.

- TR: trajetórias representativas do centroide e extremos N/S/L/O,
  adaptadas da metodologia de Priscila Backes de Oliveira (IME, 2024).
- IGT: incrementos geométricos temporais, com base nas diferenças de
  regiões discutidas por Barbosa e Oliveira (2022).
- P1: componentes queimados acumulados por data; P2: região principal
  rastreada ao longo do tempo.
- Fonte: JRC/GWIS GlobFire v2, derivado de MCD64A1.

**Atenção:** a conectividade por vértice aprovada para BurnGeoFlow
ainda não é a convenção canônica do P1 legado. Sua implementação
será uma camada derivada, com testes de regressão e sem modificar
silenciosamente os GeoJSONs originais.

Não declaramos validação física independente nem inferência causal
a partir de fusões, direções de centroides ou fases exploratórias.
