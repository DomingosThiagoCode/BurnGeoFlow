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

## Visualizador interativo local (primeira versão)

O BurnGeoFlow possui um painel opcional em **Streamlit** para exploração
rápida dos dados já adquiridos e processados. Ele não substitui o
pipeline nem precisa de QGIS para visualizar séries e mapas.

### Instalação e execução

No PowerShell, a partir da raiz do repositório:

```powershell
python -m pip install -r requirements-viewer.txt
python -m streamlit run visualizador.py
```

O navegador abrirá o painel local. A interface identifica automaticamente
os eventos existentes em `execucoes/<ID>/dados/estudo_caso_<ID>/`.

### Funcionalidades já implementadas

- Selecionar um ID disponível e avançar/retroceder pelas datas.
- Exibir **P1 (todos os patches)** e **P2 (região rastreada)** no mapa,
  com cores distintas, sem alterar os GeoJSONs em EPSG:4326.
- Acompanhar área acumulada P1/P2, número de patches, dominância,
  nova área no evento e incorporação prequeimada pelo P2.
- Consultar indicadores da transição selecionada.
- Baixar o GeoJSON filtrado por data e a série temporal em CSV.
- Exibir o status da auditoria e a ausência de validação externa.
- Visualizar P1/P2 mesmo antes da integração, caso existam os GeoJSONs.

O painel reutiliza os dados locais e não faz consultas ao Earth Engine,
nem reexecuta o processamento a cada movimento do controle temporal.
Resultados da Etapa 5 são conferidos por SHA-256 contra os GeoJSONs de
origem; dados incompatíveis são bloqueados para não gerar gráficos
cientificamente enganosos. A aplicação usa cache por assinatura dos
arquivos, invalidado automaticamente quando eles mudam.

**Para um novo incêndio:** processe-o usando a CLI atual (com a opção
`--origem gee`), depois selecione seu ID no painel.
O acionamento do pipeline **dentro da interface** ainda não faz parte
desta primeira versão. A aquisição GEE depende de autenticação válida e
pode levar tempo; não deve ser disparada a cada atualização da página.

**Observação:** o mapa usa serviços de base cartográfica do visualizador;
a navegação pelos GeoJSONs/CSV não depende de nova aquisição no GEE.
O mapa pode exigir internet para carregar o fundo cartográfico.

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

### Verificar a origem das sobreposições, antes e depois dos reparos

Para o evento 24340828 e a data 18/09/2020, compare os ranks 1/10,
1/16 e 1/18 com a mesma projeção LAEA empregada no pipeline:

```powershell
python -m burngeoflow.validacao.sobreposicoes --id 24340828 --data 2020-09-18 --verificar-origem
```

Se a interseção entre duas geometrias originais for válida em
WGS84, o relatório registra sua **área em graus²** e a presença de
sobreposição areal antes da projeção. Área em graus² serve apenas para
detectar existência, **não** deve ser interpretada como m². Assim,
mesmo se a reprojeção da geometria de interseção produzir um polígono
inválido, a classificação pode confirmar que a sobreposição já estava
na fonte sem inventar uma medida métrica.

Esse modo registra para cada par a interseção (em m²) nos estados
**P1 original WGS84**, **LAEA antes de `make_valid`** e
**LAEA após `make_valid`**. O resultado vai para
`execucoes/24340828/resultados/etapa5/verificacao_origem_p1_24340828_2020-09-18.json`.
Permite trocar os ranks com `--principal N --outros X Y Z`.

O modo declara **indeterminada** a interseção de qualquer polígono
inválido. Se o estado intermediário LAEA for inválido, não se pode
isolar a contribuição da reprojeção da contribuição do reparo.
Essa verificação preserva os GeoJSONs e não chama o GEE,
mas não substitui a validação externa nem remove alertas científicos.
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

### Auditoria de sobreposição P1 e integração (Etapas 5 e 6)

Patches P1 distintos podem apresentar sobreposições de área após as
operações de reprojeção e reparo geométrico. A antiga Etapa 5 interrompia
a execução em qualquer dia com sobreposição acima de 1 m². Agora
**os componentes e seus ranks são preservados**, sem apagamento ou
dissolução nos GeoJSON de entrada.

A análise mantém **duas grandezas diferentes**:

- **Soma das áreas dos patches**: parâmetro usado nas métricas de P1
  e linhagens das Etapas 2 e 3, mesmo quando há dupla contagem.
- **Área espacial coberta pelo evento**: união dos patches em LAEA,
  sem contar duas vezes regiões de sobreposição.

A identidade de controle entre datas é:
**Δ(soma) = Δ(cobertura da união) + Δ(excesso por sobreposição)**.
A Etapa 5 confere essa identidade com as saídas das Etapas 2 e 3,
e registra por data a área excedente, os ranks dos pares sobrepostos
e a magnitude da maior interseção. Relatório:
`execucoes/<ID>/resultados/etapa5/auditoria_p1_sobreposicoes_<ID>.json`.

**Importante:** sobreposição acima de 1 m² continua marcada como
**pendência de revisão científica**, não como resultado validado.
A Etapa 6 propaga essas pendências e também sinaliza eventuais perdas
de área acumulada. A execução computacional pode ser concluída com
status de revisão pendente; isso não atesta qualidade espacial do
GlobFire nem autoriza conclusões físicas sobre o incêndio.

Reuso de dados: continue executando com `--origem local`. Não é
necessário refazer aquisição pelo Earth Engine.

O orquestrador agora só reutiliza uma etapa concluída quando seus
artefatos obrigatórios existem. As Etapas 4/5 exigem também seus
resumos e auditorias JSON, não apenas tabelas CSV. Em novas execuções,
o manifesto registra a assinatura SHA-256 do código relevante de cada
etapa. Se uma etapa for executada novamente, as suas sucessoras serão
recalculadas para evitar resultados misturados. Manifests anteriores
ao controle de versão do código mantêm o reuso legado até o primeiro
recálculo, e não devem ser tratados como comprovação de versão.


### Síntese científica exploratória (após o pipeline)

Quando as Etapas 5 e 6 estiverem concluídas, gere o dossiê interpretativo
**sem baixar dados do GEE nem refazer o pipeline**:

    python -m burngeoflow.relatorios.sintese_caso --id 24340828

Os produtos são gravados em execucoes/24340828/resultados/sintese_cientifica/:

- sintese_cientifica_24340828.md: leitura P1/P2, TR/IGT, conectividade,
  convergências geométricas, picos e ressalvas metodológicas;
- indicadores_sintese_24340828.json: dados estruturados e auditáveis;
- resumo_para_chat_24340828.txt: indicadores e datas centrais para revisão.

A rotina exige o mesmo ID, contagem de datas e transições e hashes SHA-256
dos GeoJSONs efetivamente usados na Etapa 5. Usa apenas os produtos das
Etapas 5/6 e os arquivos de origem disponíveis localmente. Se houver
verificacao_origem_p1_<ID>_<data>.json com SHA válido, a origem das
sobreposições aparece no dossiê. Não muda os dados de entrada nem
transforma pendências científicas em aprovação.

A comparação direcional exploratória considera apenas transições de 1 dia,
concentração IGT >= 0,5, nova área P2 >= 0,25 km² e azimutes definidos.
Esses limiares não são calibração do sensor e não validam propagação do fogo.

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
