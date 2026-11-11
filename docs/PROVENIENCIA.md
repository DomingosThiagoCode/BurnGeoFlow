# Proveniência científica

O código científico do BurnGeoFlow foi inicialmente desenvolvido no projeto
[CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio)
e migrado para um pacote Python com responsabilidades modulares.

- TR: trajetórias representativas do centroide e dos extremos N/S/L/O,
  adaptadas do método de Priscila Backes de Oliveira (IME, 2024).
- IGT: incrementos geométricos temporais por diferença de regiões;
  referência metodológica: Barbosa e Oliveira (2022).
- P1: análise das componentes de áreas queimadas acumuladas.
- P2: região principal selecionada por continuidade geométrica.
- Dados: JRC/GWIS GlobFire v2, derivados do MODIS MCD64A1.

O código original de experimentação (JavaScript GEE e SQLs PostGIS)
permanece disponível no CDG_incendio para rastreabilidade, mas não é
dependência do produto computacional.

A interpretação dos indicadores está restrita à evolução geométrica das
áreas queimadas; testes internos não equivalem à validação de campo.

## Portabilidade da aquisição

A geração Python aplica as decisões do JavaScript no CDG_incendio:
união acumulada por IDate, componentes classificados por área e P2
selecionado pela maior sobreposição com a observação anterior, com
fallback por distância. O processamento não representa movimento
físico da frente de fogo. A equivalência numérica e geométrica com
a exportação histórica requer teste autenticado, ainda não realizado.
