# BurnGeoFlow

**Pipeline Geoespacial Automatizado para Análise Espaço-Temporal de Áreas Queimadas**

*An Automated Geospatial Pipeline for Spatiotemporal Analysis of Burned Areas*

> Etapa 7.1: orquestração local dos métodos científicos legados.
> A aquisição diretamente pelo Google Earth Engine será implementada na Etapa 7.2.

## Pergunta científica

Em que medida a integração de métricas de paisagem e indicadores de regiões
móveis permite caracterizar a evolução espaço-temporal de áreas queimadas,
considerando o crescimento, a conectividade e as transformações geométricas
de seus componentes?

## Instalação (PowerShell)

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
~~~

## Uso

Para reproduzir a amostra do Pantanal, ID GlobFire 24340828:

~~~powershell
python executar_pipeline.py --id 24340828 --baixar-exemplo
~~~

O parâmetro \`--baixar-exemplo\` transfere os GeoJSONs históricos de
[CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio),
verificando hashes de integridade antes de processar. Após esse primeiro
download, basta executar:

~~~powershell
python executar_pipeline.py --id 24340828
~~~

Para outros IDs já exportados em GeoJSON:

~~~powershell
python executar_pipeline.py --id 123456 --p1 C:\dados\P1_componentes_123456.geojson --p2 C:\dados\P2_regiao_movel_123456.geojson
~~~

Use \`--refazer\` para forçar uma nova execução. Use \`--saida .\` caso queira
gravar os arquivos de saída na raiz do checkout, formato consumido pelos
testes herdados.

## Produtos

Cada execução é isolada em \`execucoes/<ID>/\` com diretórios
\`dados/estudo_caso_<ID>/\`, \`resultados/etapa1/\` a
\`resultados/etapa6/\`, \`logs/\` e \`execucao.json\`.

O manifesto mantém hashes SHA-256 das entradas e estado das oito tarefas
de processamento. Etapas concluídas podem ser reutilizadas enquanto as
entradas não mudarem. Depois de alterar o código, utilize \`--refazer\`.

Os módulos importados processam P1 (componentes da área acumulada),
linhagens e P2 (região móvel), indicadores TR/IGT, síntese e auditoria interna.

## Estado do projeto

- [x] Orquestração local, logs, manifesto, caminhos isolados por evento
- [x] Importação dos scripts e testes anteriores
- [ ] Integração da aquisição pela API Python do GEE (7.2)
- [ ] Política derivada de conectividade por vértice e teste com múltiplos IDs (7.3)
- [ ] Divulgação e apresentação do software (7.4)

**Limitações:** os cálculos medem evolução geométrica de áreas queimadas
acumuladas, não necessariamente a propagação física do fogo. A fonte
GlobFire/MCD64A1 tem resolução nominal de 500 m. O produto não realizou
validação externa com imagens independentes. O critério de contatos por
vértice será introduzido em etapa separada e documentado.

Veja [proveniência e escopo](docs/PROVENIENCIA.md).
