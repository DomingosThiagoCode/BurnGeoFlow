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

## Aquisição automática GEE (Etapa 7.2)

O Earth Engine pode ser utilizado sem copiar JavaScript ou exportar manualmente pelo Google Drive.
O Python constrói P1 (componentes acumulados por data) e P2 (região principal contínua),
baixa GeoJSON por páginas e valida o par antes de executar as análises.
**A equivalência com os GeoJSONs históricos do Pantanal exige teste real autenticado.**

### Preparação no Windows / PowerShell

```powershell
pip install -r requirements-gee.txt
Copy-Item .env.example .env
# Edite EE_PROJECT_ID no .env com o ID do projeto Google Cloud
earthengine authenticate
```

### Adquirir e executar o pipeline

```powershell
python executar_pipeline.py --id 24340828 --ano 2020 --origem gee
```

Para adquirir e validar os GeoJSONs sem executar as análises:

```powershell
python executar_pipeline.py --id 24340828 --ano 2020 --origem gee --somente-aquisicao
```

O ano é opcional; se omitido, o programa consulta as coleções anuais de 2020 a 2001.
O comando mínimo `python executar_pipeline.py --id 24340828` opera em modo `auto`:
usa o par P1/P2 local se existir, caso contrário tenta obter pelo GEE.

O teste offline do caso de referência continua disponível:

```powershell
python executar_pipeline.py --id 24340828 --baixar-exemplo
```

As credenciais OAuth ficam no computador, nunca no repositório; `.env` está no
`.gitignore`. A exportação usa `ee.data.computeFeatures`, com paginação, sem
depender do Drive. Em eventos grandes a API pode exceder a capacidade ou
cotas e encerrar a aquisição com erro sem publicar entradas incompletas.
**A exportação em lotes por tarefas do GEE ainda não está implementada.**

Documentação oficial: [API Python](https://developers.google.com/earth-engine/guides/python_install),
[computeFeatures](https://developers.google.com/earth-engine/apidocs/ee-data-computefeatures)
e [GlobFire v2](https://developers.google.com/earth-engine/datasets/catalog/JRC_GWIS_GlobFire_v2_DailyPerimeters).

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
