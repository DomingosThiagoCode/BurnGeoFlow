# BurnGeoFlow

**Pipeline Geoespacial Automatizado para Análise Espaço-Temporal de Áreas Queimadas**

*An Automated Geospatial Pipeline for Spatiotemporal Analysis of Burned Areas*

## Objetivo científico

Em que medida a integração de métricas de paisagem e indicadores de regiões
móveis permite caracterizar a evolução espaço-temporal de áreas queimadas,
considerando o crescimento, a conectividade e as transformações geométricas
de seus componentes?

## Arquitetura

O BurnGeoFlow utiliza o pacote `burngeoflow/`, com responsabilidades isoladas:

```text
BurnGeoFlow/
├── executar_pipeline.py
├── burngeoflow/
│   ├── config.py
│   ├── aquisicao/
│   │   ├── earth_engine.py
│   │   └── dados_referencia.py
│   ├── processamento/
│   │   ├── componentes.py
│   │   ├── conectividade.py
│   │   └── linhagens.py
│   ├── analises/
│   │   ├── paisagem.py
│   │   ├── regioes_moveis.py
│   │   ├── incrementos.py
│   │   ├── tr_igt.py
│   │   └── integracao.py
│   ├── validacao/
│   └── relatorios/
├── tests/
└── dados/                    # entradas locais (ignorar GeoJSONs grandes)
```

Os SQLs e o JavaScript antigo do GEE pertencem ao repositório histórico
[CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio),
não a este pacote.

## Instalação local (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Para executar o caso de referência já exportado e testar as seis etapas:

```powershell
python executar_pipeline.py --id 24340828 --baixar-exemplo
```

Para outro evento com os GeoJSONs P1/P2 disponíveis:

```powershell
python executar_pipeline.py --id 123456 --p1 C:\dados\P1_componentes_123456.geojson --p2 C:\dados\P2_regiao_movel_123456.geojson
```

Os arquivos gerados ficam em `execucoes/<ID>/`, incluindo resultados
de cada etapa, logs e um manifesto com SHA-256 das entradas. A opção
`--refazer` força nova execução após modificações no código.

## Integração GEE

A API Python do Earth Engine ficará em `burngeoflow/aquisicao/earth_engine.py`.
A consulta da coleção e a autenticação estão estruturadas, mas **gerar e
exportar P1/P2 sem intervenção ainda é pendência da Etapa 7.2**. Portanto
`--origem gee` ainda não processa um evento.

Instalação das dependências opcionais:

```powershell
pip install -r requirements-gee.txt
```

Preencha a variável `EE_PROJECT_ID` em um `.env` local a partir de
`.env.example`. Não versione tokens ou credenciais.

## Escopo e qualidade

Os indicadores medem evolução geométrica de áreas queimadas acumuladas,
não necessariamente a trajetória física da frente de fogo. Dados GlobFire
são derivados do MODIS MCD64A1, com resolução nominal de 500 m.
A validação interna não substitui validação independente por satélite.

A conectividade por vértice é uma convenção geométrica assumida no projeto.
Sua utilização integrada no pipeline, preservando P1/P2 originais,
será tratada separadamente na Etapa 7.3.

Mais detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md) e
[docs/PROVENIENCIA.md](docs/PROVENIENCIA.md).
