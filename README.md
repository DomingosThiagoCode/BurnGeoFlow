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
### Acompanhamento enquanto o GEE calcula

A avaliação de geometrias pelo Earth Engine é síncrona e não informa
percentual de conclusão nem tempo restante confiável. Por isso, a cada
página solicitada o programa imprime imediatamente **extraindo dados, aguarde...**
e, a cada **30 segundos**, informa o tempo decorrido enquanto aguarda.
Quando uma página retorna, mostra quantas feições já foram recebidas e
indica o início de P2 quando P1 termina.

Os avisos significam apenas que o **Python ainda está esperando o servidor**;
não comprovam que o processamento remoto está avançando. Se o GEE retornar
uma falha, ela será informada. O programa não cria GeoJSONs incompletos.
Uma execução iniciada antes dessa atualização não passa a emitir os avisos.
### Preservação dos dados e tratamento geométrico

Cada página P1/P2 recebida fica em
`execucoes/<ID>/dados/estudo_caso_<ID>/brutos_gee/paginas_P1/`
ou `paginas_P2/`. Uma execução interrompida pode recuperar as páginas
já recebidas, com checagem de identidade da consulta e token de paginação.
Após completar cada produto, uma cópia GeoJSON **bruta e imutável** é
guardada em `brutos_gee/`, antes da validação científica.

Se o servidor produzir uma `GeometryCollection` com parte poligonal,
o pipeline extrai somente a componente areal e registra essa intervenção.
Geometrias estritamente não poligonais **com área declarada zero** são
excluídas do conjunto de patches e têm ranks e contagens recompostos.
A lista completa de intervenções fica em
`brutos_gee/diagnostico_geometrias.json`. Qualquer geometria
não poligonal com área positiva/desconhecida bloqueia a publicação
para revisão. Isso não deve ser interpretado como propagação física.

Para reprocessar **sem chamar o Earth Engine** os GeoJSONs já recebidos:

```powershell
python executar_pipeline.py --id 24340828 --origem brutos --somente-aquisicao
```

Esse comando só funciona quando ambos os GeoJSONs brutos já estão
presentes em disco. Se você executou uma versão anterior à correção,
os temporários daquele processamento foram apagados automaticamente
e precisarão ser extraídos outra vez. A nova versão não descartará
os dados recebidos em caso de erro de validação.



Documentação oficial: [API Python](https://developers.google.com/earth-engine/guides/python_install),
[computeFeatures](https://developers.google.com/earth-engine/apidocs/ee-data-computefeatures)
e [GlobFire v2](https://developers.google.com/earth-engine/datasets/catalog/JRC_GWIS_GlobFire_v2_DailyPerimeters).


### Reconciliação geométrica P2 para TR/IGT

Os produtos P1/P2 finais não são editados pelas análises. A análise espacial
de P1 utiliza geometria em projeção LAEA, com `make_valid` condicional
já registrado nos resumos. A análise P2 pode receber polígonos cuja
projeção revela auto-interseções, mesmo após a validação estrutural.

TR e IGT verificam agora o P2 com a mesma projeção do P1.

### Diagnosticar sobreposições em P1 sem refazer as etapas

Se a integração acusar "Patches P1 sobrepoem em area", não elimine a
verificação e não gere outros polígonos automaticamente. Audite a data:

```powershell
python -m burngeoflow.validacao.sobreposicoes --id 24340828 --data 2020-09-18
```

O diagnóstico salva
`execucoes/24340828/resultados/etapa5/diagnostico_sobreposicoes_p1_24340828.json`
e imprime a diferença entre soma das áreas individuais e união, os
pares sobrepostos, os ranks, a área exata de interseção em m²,
fração da área do menor patch e indicadores de reparo LAEA.

Para auditar todas as datas, omita `--data`. A operação lê
o cache local de P1 e **não altera os dados, não chama GEE e não prossegue
com a integração**. A diferença soma/união não necessariamente é igual
à soma das interseções por pares quando há sobreposição tripla.

### Etapa 5 com geometrias P1/P2 regularizadas

A integração da Etapa 5 não deve rejeitar automaticamente um P1 que
precisou de `make_valid` após projeção. Ela reconstrói a geometria LAEA
pelo **mesmo procedimento de TR/IGT**, verifica a correspondência P1/P2
por data e rank, e confere os relatórios de TR, IGT e consolidação da
Etapa 4 quando houver reparos. As verificações exigem hashes SHA-256
de ambos os GeoJSONs, contagens de reparos e identidade dos registros
reparados (data/rank); falhas continuam bloqueadas.

Uma auditoria detalhada é incluída no `resumo_etapa5_<ID>.json`,
mantendo os GeoJSONs originais intocados. Trata-se de **consistência
computacional interna**, não de validação geométrica independente
das imagens GlobFire/MODIS.
**Definição geométrica comum TR/IGT:** a área nova é `área(R(t+1) \\ R(t))`
e a área reduzida é `área(R(t) \\ R(t+1))`, ambas calculadas por
diferença espacial explícita em LAEA (não como subtração de áreas
totais e interseções). A conferência cruzada mantém o limite de **0,1 m²**
e informa datas e valores em caso de discrepância. Nenhuma divergência
é ignorada. Falhas das etapas aparecem também no terminal, além dos logs.

**A consolidação `tr_igt.py` usa a mesma geometria P1 LAEA canônica** para
o cálculo das diferenças entre datas, depois de reconciliar cada P2 com
seu componente correspondente. Assim, não reintroduz os P2 inválidos no
fechamento das métricas. A auditoria consta também do resumo consolidado.

 Se o P2 ficar
inválido, a sua geometria para comparação é reparada apenas em memória.
Esse reparo **só é aceito se a diferença simétrica de área em relação ao
componente P1 correspondente não ultrapassar `max(1 m², 10⁻⁸ × área_P1)`**.
Se houver divergência maior, a análise é interrompida e registra
número da feição, data, rank, motivo topológico e magnitude da divergência.
Os reparos aceitos são contabilizados nos resumos de TR e IGT; não
constituem validação independente da fonte GlobFire.

Para retomar a execução local após atualizar o código:

```powershell
git pull origin main
python executar_pipeline.py --id 24340828 --origem local
```

Os arquivos do GEE continuam no cache e as etapas anteriores concluídas
são reutilizadas quando os hashes P1/P2 permanecem inalterados.
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
