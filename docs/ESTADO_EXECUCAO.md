# Estado de execução e mapa anti-retrabalho — BurnGeoFlow

> **Última reconciliação:** 2026-11-26 (revisão manual do GitHub, sem acesso ao disco local do operador).
> **Tipo:** fotografia operacional que DEVE ser reconciliada com issues, PRs, commits e arquivos a cada nova sessão.
> **Regra:** `main` ≠ PR aberto ≠ experimento validado ≠ conclusão científica.
> **Ponto de entrada para agentes:** [AGENTS.md](../AGENTS.md), [COORDENACAO_AGENTES.md](COORDENACAO_AGENTES.md), [METODOLOGIA.md](METODOLOGIA.md) e [ROTEIRO.md](ROTEIRO.md).

## Marco multiagente de 26/11/2026

O checkout `/workspace/BurnGeoFlow` permaneceu limpo em `work` (`2e0dba6`). O protocolo e o estado foram lidos em `origin/main` (`a2aeda5`). Os dois agentes usaram branches, worktrees e ambientes isolados. As seções abaixo preservam o inventário anterior ao marco.

| Frente | Estado e evidência |
| --- | --- |
| #44 / PR #51 | HEAD `f226caa5` reaproveitado. Cinco testes dirigidos passaram. No P1 local de 24340828, as seis saídas de linhagens foram idênticas às legadas, com 56 transições, 963 vínculos, 1,27 s e pico de RSS de 83.276 KiB. As branches adicionais de diagnóstico não trazem evidência do patch de 24194371. |
| #2 / PR #53 | Rascunho em `df2ead8`, sobre a branch de proveniência existente. Páginas GEE passam por validação antes de serem gravadas em cache. As duas cópias locais de cada produto legado de 24340828 são byte a byte idênticas. A validação confirmou 57 datas e 978/57 feições em P1/P2. Passaram 34 testes direcionados. |
| #3, #45, #34, #46 e #47 / PR #52 | HEAD `5535416` adiciona evidência de desempates de ancestralidade, verificação de proveniência de checkpoints, validação estrutural com calendário próprio de P2 e testes sintéticos de conectividade, continuidade e representatividade. O pré-processador continua experimental. |
| #34 / índice espacial | Branch existente `f5cf9c7`, 11 testes aprovados. As quatro saídas de métricas comparadas foram idênticas à busca exaustiva. Medianas no P1 de 24340828 de 0,2152 s e 0,2167 s, respectivamente. Em 900 patches sintéticos no mesmo dia, 0,5432 s e 0,0371 s. Script em `/workspace/scratch/bgf-34/benchmark.py`. |
| #46 / D-005 | Protótipo local `ff3c6c0` em `agente/46-expansao`, também na integração de verificação. No P2 experimental de 24340828, as 56 transições apresentaram erro máximo de partição de `1,49e-7 m²` e área máxima do P2 anterior fora do P1 de `0 m²`. A produção depende dos contratos finais de P1/P2. |

O marco local `agente/integracao-e2` (`ab73580`, código testado) passou 190 testes científicos e 26 de API. O frontend passou cinco testes, build, verificação de bundle e smoke de atlas e landing com Chromium do sistema. No caso 24340828, a execução legada isolada concluiu em 35,45 s, com pico de RSS de 129.444 KiB. A segunda execução reutilizou as oito etapas. O pré-processamento experimental gerou 369 componentes P1 e 57 datas em P1 e P2, com desvio absoluto máximo de área diária de `1,25e-12 km²` em relação à união dos componentes legados reprojetados. Os hashes dos derivados permaneceram iguais após adicionar a auditoria de desempates. Logs e manifestos dessa execução ficam em `/workspace/bgf-integracao/.git-evidencias`.

O CI foi aprovado nos HEADs publicados de #52 (`5535416`, execução `45833662550`) e #53 (`df2ead8`, execução `45833126995`). [CI #52](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45833662550) · [CI #53](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45833126995)

O P1 legado de 24194371 e os brutos GEE não foram localizados no ambiente. A próxima ação é disponibilizar uma cópia do P1 de 24194371 para leitura, registrar o SHA-256 e usar o [diagnóstico da PR #51](DIAGNOSTICO_TOPOLOGIA_LINHAGENS.md) com uma pasta de saída isolada. A equivalência GEE/local de #2 requer os brutos e seu manifesto. O diagnóstico real de #44 precede a homologação de #3/#45/#46 e a regressão científica integral de #47. A autorização de merge na `main` permanece pendente.

## 0. Resumo executivo, sem ambiguidades

1. **A metodologia científica D-001 a D-016 está documentada e conceitualmente aprovada**, mas sua implementação integral e validação NÃO estão concluídas.
2. **A `main` ainda executa o pipeline científico legado:** P1 sem o agrupamento por contato da D-002 como produto oficial e P2 progressivo a partir do maior componente inicial, incompatível com a D-001. NÃO declarar saída antiga como resultado da nova metodologia.
3. **PR #52 (DRAFT, fora da `main`):** primeiro pré-processador P1 conectado/P2 retrospectivo + inspeção de checkpoints no painel. Experimental, não integrado aos validadores/etapas finais; NÃO permite reprocessamento científico completo.
4. **PR #51 (DRAFT, fora da `main`):** diagnóstico da falha topológica de linhagens do ID 24194371. Não contém correção científica da causa.
5. **PR #49 (DRAFT, fora da `main`):** amplia o catálogo por UF/Brasil e AOI desenhada; faltam testes reais dos limites IBGE e consulta GEE autenticada.
6. **Landing narrativa:** primeira versão JÁ EXISTE na `main`, em `/apresentacao/`. Issue #50 trata da evolução e homologação, NÃO de criar outra landing do zero.
7. **Não reexecutar aquisição GEE dos IDs 24340828 e 24194371** só para testar uma mudança de pipeline. Primeiro localizar/verificar os insumos locais e seus hashes. Não presumir que os arquivos locais estão presentes nesta sessão.

## 1. Estado da `main` (comprovado pelos arquivos do repositório)

| Área | Já na `main` | Ainda NÃO é |
| --- | --- | --- |
| Aquisição | Consulta GlobFire v2/GEE, caminhos interativo e batch, exportações e cache/retomada em assets, P1/P2 legados | Aquisição universalmente robusta para eventos enormes; metodologia P2 retrospectiva |
| Orquestrador | `executar_pipeline.py`, oito etapas, `execucao.json`, hashes das entradas, assinatura de código e reaproveitamento de etapas | Motor integralmente atualizado à D-001/D-002, auditoria completa de perdas/versões ou retomada fina de todos os subpassos |
| API | FastAPI, leitura de eventos/GeoJSONs/séries, jobs SQLite e logs | Inspeção explícita de integridade/checkpoints por ID da PR #52 |
| Atlas | React/TypeScript, mapa, P1/P2 legados, séries e indicadores, execução por ID | Navegação final modular (#43), rosáceas interativas (#42), design definitivo |
| Catálogo | Consulta leve por bioma, filtro temporal, cache JSON e encaminhamento para processamento | UF/Brasil oficial e desenho no mapa da PR #49; paginação de 5 por página (#40) |
| Landing | `frontend/src/story/`, `frontend/public/story/24340828.json`, oito cenas em `/apresentacao/` | Homepage definitiva, dados P2 revisados, design final da issue #50 |
| Testes | CI de API, frontend, Chromium, regressão do código legado | Validação independente de satélite, execução científica v2 completa nos dois casos |

Documentos de referência já existentes: `docs/ARQUITETURA.md`, `docs/REFERENCIA_OPERACIONAL.md`, `docs/PROVENIENCIA.md`, `docs/LANDING_SCROLLYTELLING.md` e `docs/BACKLOG_REFACTOR.md`.

**Atenção:** existência de teste automatizado aprovado ou visualização bonita NÃO prova validade física das observações MODIS nem validade científica dos indicadores.

## 2. Trabalho já desenvolvido fora da `main`: NÃO duplicar

| PR e issue(s) | Branch e HEAD inspecionado | Entrega técnica efetiva | Evidência CI no HEAD | O que NÃO foi entregue |
| --- | --- | --- | --- | --- |
| [#51](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/51), issue #44 | `fix/44-diagnostico-intersecoes`, `f226caa5` | `burngeoflow/validacao/diagnostico_linhagens.py`; modifica `processamento/linhagens.py` para emitir JSON com soma/união, área duplicada, ranks, SHA e LAEA. Testes sintéticos em `tests/test_diagnostico_linhagens.py`. Guia `docs/DIAGNOSTICO_TOPOLOGIA_LINHAGENS.md`. | [Aprovado](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45828297827) | Diagnóstico nos dados reais; explicação causal; correção topológica; reprocessamento 24194371 |
| [#52](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/52), issues #3/#45/#34/#46 (parcial) | `feat/e2-metodologia-v2-checkpoints`, `79c42fb8` | `processamento/metodologia_v2.py`: agrupamento P1 por contato e P2 retrospectivo, bloqueio de sobreposições; `--preparar-metodologia-v2` só local; derivados versionados; manifesto e progresso por data; SHA do código/insumos/saídas; API `/api/events/{id}/pipeline-status`; `frontend/src/components/PipelineStatusPanel.tsx`, testes. | [Aprovado](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45830497673) | Pipeline v2 oficial; TR/IGT e integração adaptados à duração menor de P2; recuperação completa de checkpoints; validação nos dois IDs reais; tratamento científico definitivo de todas as inconsistências |
| [#49](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/49), issue #31 | `feat/31-catalogo-completo-aoi`, `3ebdc062` | Limites estaduais e Brasil IBGE 2024, cache de malhas, seleção de UF, polígono desenhado via `AoiDrawMap.tsx`, filtros e testes de contrato | [Aprovado](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45822318498) | Homologação dos arquivos oficiais reais/consultas GEE para novas AOIs; integração/merge; paginação #40 |

**Todos os três PRs permanecem DRAFT, abertos e não mesclados**, conforme consulta de 26/11/2026. CI verde indica regressão automatizada no HEAD indicado, não aceitação científica ou aprovação de merge. Antes de retomar, verificar se ainda estão abertos, os SHA e o CI mais recente.

### Arquivos com provável colisão

- PR #51 é dona temporária de `burngeoflow/processamento/linhagens.py`.
- PR #52 usa `executar_pipeline.py`, `burngeoflow/processamento/metodologia_v2.py`, `backend/app/api/routes.py`, `backend/app/services/estado_pipeline.py`, `frontend/src/components/JobsPanel.tsx`, `PipelineStatusPanel.tsx` e `frontend/src/atlas-theme.css`.
- PR #49 usa `backend/app/api/catalogo.py`, `burngeoflow/aquisicao/catalogo.py`, `limites_ibge.py`, `frontend/src/components/CatalogoPanel.tsx`, `AoiDrawMap.tsx` e `atlas-theme.css`.
- **Colisão real de CSS:** PRs #49 e #52 alteram `frontend/src/atlas-theme.css`. Integração sequencial e resolução manual são necessárias.
- **Colisão científica potencial:** #3 (P1/linhagens) e #45 (P2) compartilham contratos; um único responsável deve integrar a versão científica e revisar a PR #51 antes de adaptar linhagens.

## 3. Casos de desenvolvimento, sem novas aquisições

| Evento | Estado histórico observado | Estado sob D-001/D-002 |
| --- | --- | --- |
| **24340828**, Pantanal/2020 | 947 registros de fonte GlobFire, 57 datas; P1 legado com 978 feições, P2 legado com 57; pipeline antigo concluiu no ambiente local do usuário | **Não reprocessado integralmente nem validado**. Necessário conferir arquivos locais e regenerar produtos v2, sem substituição silenciosa. |
| **24194371**, 2020 | 18.175 registros de fonte, 128 datas; P1 legado com 30.795 feições. Aquisição anterior chegou a gerar produtos. `linhagens` falhou em 2020-09-10, **rank 97**, porque a soma das interseções superou a área do patch | **Bloqueado** até diagnóstico/correção justificada #44 e compatibilização científica v2. **Não** é um caso de validação independente. |

Números acima são **histórico documentado**, não garantia de que arquivos ainda existem no computador do usuário. O manifesto e os arquivos efetivos no disco local são a fonte para disponibilidade e integridade atual.

**Distinção científica:** os dados representam evolução de área QUEIMADA ACUMULADA, não movimento medido de uma frente de fogo. Crescimento geométrico de P2 pode incluir fusão/incorporação de área previamente queimada.

## 4. Pendências reais e bloqueios, na ordem de dependências

| Fila | Issue | Trabalho restante | Bloqueio / critério |
| --- | --- | --- | --- |
| P0 | [#44](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/44) | Executar diagnóstico #51 no P1 real, identificar origem da sobreposição/excesso, aprovar política de reparo sem apagar evidência | Acesso aos arquivos reais 24194371; D-013/D-014 |
| P0 | [#2](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/2) | Conferir aquisição, fontes locais, hashes e equivalência GEE/local; casos limítrofes | Evidência em dados reais; não baixar de novo sem necessidade |
| P0 | [#3](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/3) | Consolidar P1 por contato, auditoria intradata, rank/métricas, grafo/linhagens e testes reais | #44, D-002/D-013/D-014; aproveitar #52 |
| P0 | [#45](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/45) | Concluir/validar P2 retrospectivo, desempates, ausência de ancestrais, representatividade; integrar no fluxo | P1 final validado #3, D-001/D-003/D-004/D-007; aproveitar #52 |
| P1 | [#34](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/34) | Checkpoints reproduzíveis completos, invalidação por dependência, estado de subtarefas, desempenho/memória e arquivo de diagnóstico em falhas | #52 é apenas inspeção e progresso preliminar; não é solução completa |
| P1 | [#46](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/46) | Adequar validadores e `analises/regioes_moveis.py`, `incrementos.py`, `tr_igt.py`, `integracao.py`, `robustez.py`, API e atlas a P2 com menos datas; D-005–D-012 | Antes, diversos contratos exigem `set(datas_p1)==set(datas_p2)`. NÃO forçar o mesmo período |
| P1 | [#47](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/47) | Ampliar testes sintéticos, medir invariantes, regressão real e avaliação exploratória TR/IGT | Correção E2 não é validação científica E4 |
| P2 | [#31](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/31) | Homologação real da #49, merge após aprovação | IBGE/GEE real |
| P2 | [#40](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/40), [#43](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/43), [#42](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/42) | Paginação, navegação modular, rosáceas interativas | Evitar colisão com #49/#52 e terminologia antes de #46 |
| P2 | [#41](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/41), [#50](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/50) | README/documentação e polimento da landing existente | Landing deve ser atualizada com P2 v2 só após validade metodológica |
| P3 | [#48](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/48), [#4](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/4) | Estudo com novos incêndios, validação e distribuição | E2/E3/E4 antes da avaliação independente E5 |

## 5. Inventário dos arquivos de checkpoints e respectivos limites

**Na `main` (legado):**
- `execucoes/<ID>/dados/estudo_caso_<ID>/brutos_gee/`: arquivos originais quando a aquisição GEE foi realizada. Nem toda execução possui esse diretório.
- `execucoes/<ID>/dados/estudo_caso_<ID>/P1_componentes_<ID>.geojson` e `P2_regiao_movel_<ID>.geojson`: produtos locais, atualmente **legados**, que NÃO devem ser sobrescritos.
- `execucoes/<ID>/execucao.json`: manifesto de etapas legadas; `resultados/etapa1...etapa6/`: relatórios e derivados; `logs/`: logs por etapa. Testar SHA, assinatura do código, presença e integridade dos artefatos antes de afirmar que estão atuais.
- `execucoes/.burngeoflow/jobs.sqlite3` e `execucoes/.burngeoflow/logs/`: histórico de jobs e logs de execução. Histórico de job concluído não comprova validade sob D-001/D-002.

**Somente na PR #52, até merge:**
- `--preparar-metodologia-v2`: usa P1 local; **não invoca GEE** e **não executa o pipeline científico final**.
- `execucoes/<ID>/dados/estudo_caso_<ID>/derivados_v2/<versao>/`: P1/P2 experimentais separados; `manifesto_metodologia.json`, `estado_preprocessamento.json` e, se falhar, `diagnostico_bloqueio.json`.
- `GET /api/events/<ID>/pipeline-status` e o botão `Inspecionar arquivos` no painel: leitura sob demanda de brutos, hash, versão, faltantes, etapas legadas e erros. O progresso registrado por datas **não é barra de progresso de execução integral nem garante processo ativo**.
- O botão principal `Executar` **continua usando o pipeline legado**; mesmo após a PR #52, NÃO o anunciar como botão de reprocessamento v2.

**Somente na PR #51, até merge:**
- `resultados/etapa3/diagnostico_topologia_<ID>_<data>_<lado>_r<rank>.json`: evidência quando a soma de interseções viola o limite existente.

## 6. Definição explícita de “feito” e “não feito”

**FEITO no código e na CI, mas AINDA NÃO INTEGRADO:** componentes e testes das PRs #49/#51/#52, conforme seção 2.

**FEITO na `main`:** API/atlas/landing inicial/catálogo bioma/worker GEE batch/estágios científicos legados, conforme seção 1.

**NÃO FEITO / NÃO COMPROVADO:**
- Aprovação da política numérica de tolerâncias e reparação em todos os casos;
- Diagnóstico real da origem topológica em 24194371 e correção;
- P1 conectado e P2 retrospectivo como **único fluxo oficial de ponta a ponta**;
- Suporte integral a P2 com menos datas em validação, TR/IGT, integração, robustez, API, gráficos e série;
- Recuperação seletiva completa, com dependências e backup dos derivados antigos;
- Reprocessamento científico integral dos IDs 24340828 e 24194371 sob a metodologia v2;
- Homologação visual/operacional da landing final e do catálogo ampliado com serviços externos;
- Validação científica independente por outros eventos/sensores; publicação/release final.

## 7. Retomada recomendada: ação exata, evitando retrabalho

1. Verificar issues e PRs vivos: `gh pr view 49`, `gh pr view 51`, `gh pr view 52` e `gh issue view 44`, `gh issue view 3`, `gh issue view 45`, `gh issue view 46`.
2. Abrir a [PR #51](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/51) e usar o diagnóstico nos **arquivos locais** de 24194371, sem adquirir GEE novamente; preservar SHA de entrada e registrar evidência real em #44.
3. Em paralelo, revisar/continuar o código e testes da [PR #52](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/52) para contratos P2 com início próprio; **não gerar indicadores finais pela v2 até compatibilizar #46**.
4. Submeter o catálogo da [PR #49](https://github.com/DomingosThiagoCode/BurnGeoFlow/pull/49) a homologação IBGE/GEE apenas quando houver ambiente, sem abrir outra implementação de catálogo.
5. Após revisão/homologação e autorização de merge, integrar PRs de modo sequencial; resolver colisões e repetir CI no HEAD integrado.
6. **Só depois:** reprocessar os dois IDs a partir dos insumos locais válidos, com backup/versionamento, checkpoints, relatórios e testes reais.

### Regras anti-retrabalho para todos os agentes

- **Antes de escrever código:** verificar esta tabela, a issue e PR associadas, SHA atual e proprietário do conjunto de arquivos em [COORDENACAO_AGENTES.md](COORDENACAO_AGENTES.md).
- **Uma tarefa, um dono de integração.** Não abrir PR paralela duplicada sobre trabalho em curso. Agentes auxiliares fornecem testes, análise ou commits para o dono.
- Separar no relatório: `Implementado na branch`, `CI aprovado`, `Integrado na main`, `Homologado em dados reais`, `Validado cientificamente`. Esses estados NÃO são equivalentes.
- Nunca falsificar testes concluídos, status de tarefas do GEE ou existência de dados locais.
- Atualizar este documento **apenas em marcos** (merge, erro real diagnosticado, mudança de escopo/estado), conciliando com GitHub, e evitar commits de status a cada execução de CI.

## Evidências preservadas da integração local

| Medição em 24340828 | Resultado |
| --- | --- |
| Execução legada isolada | 35,449 s, pico de RSS de 129.444 KiB |
| Retomada legada | 8 de 8 etapas reutilizadas |
| Pré-processamento experimental | 978 feições P1 legadas, 369 componentes P1 v2, 57 datas em P1 e P2 |
| Maior diferença de área diária em LAEA | 1,25056 × 10⁻¹² km² entre a união do P1 legado e o total publicado no P1 v2 |
| Partição D-005 | 56 transições, erro máximo de 1,49012 × 10⁻⁷ m² e área máxima de P2 anterior fora de P1 igual a 0 m² |
| SHA-256 P1 v2 | `386aee3aac89c43873ff26faa851d8d80fb961fff1b9056d62f8e89ce672d0da` |
| SHA-256 P2 v2 | `21f7e61547c1b661eb27fd23e559e28e98cd8fc1080633930d6a09cde8b57b79` |

## Triagem dos anexos de aquisição

Os manifestos históricos declaram GlobFire v2 DailyPerimeters 2020, exportação em lote e P2 progressivo. Os anexos não incluem hashes de aquisição registrados na origem. Os hashes abaixo identificam os arquivos recebidos nesta sessão.

| Evento | Arquivo | SHA-256 recebido |
| --- | --- | --- |
| 24340828 | `aquisicao_24340828.json` | `dd349db0b12abf70122b080609ff7e7c29604b7b890fa743bc9ffb32d1e3a603` |
| 24340828 | `P1_componentes_24340828.geojson` | `9e0808c6b9be8ab0fb62c09c84304f898481ac704104a2003be2f35dc707c157` |
| 24340828 | `P2_regiao_movel_24340828.geojson` | `d3def85764d5597dd02775beb9e013c956e156ba4de6c1d43ac98adbe4d2b5ae` |
| 24194371 | `aquisicao_24194371.json` | `cad4f3c842b95a90e4e1824081f50b0250ed92fe0a34fe107246556757509f30` |
| 24194371 | `P2_regiao_movel_24194371.geojson` | `d12c6773220a29e52c7e8367cbb27362c5dd63bef918dde2ab8e0ff3ab431f8e` |

Em 24340828, P1 e P2 passam na validação estrutural e reproduzem os totais do manifesto (978/57 feições em 57 datas). As propriedades coincidem com a cópia do checkout por data/rank. As coordenadas e os hashes diferem. Em Shapely, todas as geometrias anexadas são válidas, enquanto a cópia do checkout apresenta autointerseções em 172 feições P1 e 55 feições P2. Entre os pares válidos de P1, a maior distância de Hausdorff foi 755,74 m e a maior área de diferença simétrica foi 8,15 m². A equivalência geométrica está pendente.

O P2 de 24194371 tem 128 polígonos válidos em 128 datas (14/07 a 19/11/2020). As áreas finais arredondadas do P1 total e do P2, conforme os atributos do P2, conferem com o manifesto (17.908,2595 e 26,4019 km²). A transferência do P1 publicado excedeu o limite de 32 MiB do executor. O diagnóstico do rank 97 e a validação conjunta aguardam uma cópia integral no workspace ou um anexo compactado que respeite esse limite. Para reconstituir a proveniência, também faltam os dois GeoJSONs originais e o relatório geométrico histórico de `brutos_gee/`.

O P1 anexado de 24340828 foi submetido ao pré-processamento experimental no HEAD `5535416` da PR #52. A execução terminou com código 1 na data 2020-08-15, rank 1. Nesse registro do anexo, o polígono era válido em WGS84 e apresentou autointerseção após a transformação para LAEA. Na cópia do checkout, a geometria na mesma chave é diferente e passou de autointerseção em WGS84 a válida em LAEA. A definição de LAEA coincide nas duas entradas. A etapa não aplicou reparo e o anexo gerou apenas o estado e o diagnóstico de bloqueio. As 369 feições P1 v2 registradas acima se referem à cópia do checkout.

Para reproduzir o bloqueio com o P1 anexado, use `python executar_pipeline.py --id 24340828 --origem local --p1 "$p1" --saida "$(mktemp -d)" --preparar-metodologia-v2`. O procedimento de revalidação dos brutos está em [PROVENIENCIA.md](PROVENIENCIA.md).

## Diagnóstico real de 24194371 e projeção de 24340828

O RAR5 foi extraído com libarchive e continha um único membro GeoJSON de 116.262.255 bytes. O SHA-256 do P1 é `3e864ab33eb87eaa56a5c82aae2b39c85ae4c724db7a7af9fe48320e1a87c234`. O P1 e o P2 conferem com os hashes de `execucao.json`. A validação estrutural reproduziu os indicadores históricos (30.795 feições P1, 128 feições P2, 128 datas), com diferença apenas na codificação do texto do aviso. O RAR original tem SHA-256 `03ab149fbc4065751da93666cb230778c765e4251c903bc285801b8bac8921aa`.

**#44 / PR #51.** Com HEAD `f226caa`, Shapely 2.2.0, GEOS 3.14.1 e PyProj 3.8.0, a etapa de linhagens reproduziu a falha de 2020-09-10, rank 97, para 2020-09-11. O alvo mede 855.479,909819 m². As interseções com os sucessores 83 e 3 somam 855.481,100055 m² e a união mede 855.479,909819 m². O par 3/83 produz isoladamente 1,190237 m² de dupla contagem, acima do limite vigente de 1 m². A execução levou 76,9 s, com pico de RSS de 655.384 KiB. O alvo e o rank 83 não passaram por reparo no fluxo legado. O rank 3 ficou inválido após projeção e foi reparado pelo fluxo legado. A sobreposição 3/83 já existe no P1 WGS84 válido, inteiramente dentro do alvo, com área positiva de 1,0084 × 10⁻¹⁰ graus². O overlay antes do reparo em LAEA fica indeterminado. A evidência estabelece que a sobreposição antecede a transformação, sem atribuir sua origem à fonte GlobFire, à exportação ou à normalização. Essa atribuição depende dos brutos históricos de #2.

**#3 / PR #52.** No P1 anexado de 24340828, todas as 978 feições são válidas em WGS84 e 51 ficam inválidas ao projetar os vértices e ligá-los por retas em LAEA. Em 15/08/2020, rank 1, dois pares originalmente disjuntos passam a se cruzar. Um quadrilátero sintético reproduz o mecanismo e verifica que o pré-processador bloqueia com diagnóstico e preserva a entrada (PR #52, `d1b34db`). A densificação foi avaliada somente em cópias experimentais. Ela recuperou a validade individual em certas resoluções, mas alterou a área do alvo e deixou sobreposições. Dos 734 pares com contato intradata em WGS84, 299 já têm interseção de área positiva. Após a densificação experimental, 217 ultrapassaram 1 m² em LAEA, com máximo de 4,97 m². Nenhuma resolução foi adotada como política científica.

Passaram 26 testes direcionados de diagnóstico, auditoria, v2, contratos e desempates. O módulo de v2 também passou com a nova regressão sintética. Preservaram-se os dois conjuntos de entrada de 24340828. O erro de 24194371 e os bloqueios da v2 são reproduzíveis sem GEE; a homologação e a escolha de tratamento dependem de estabelecer a origem dos brutos e de uma política justificada para sobreposições e projeção.

A interseção dos sucessores 3 e 83, calculada em WGS84 e só depois projetada para a LAEA da etapa de linhagens, mede 1,190236657 m². A diferença em relação ao overlay após o reparo legado é de aproximadamente 9,9 × 10⁻⁹ m². As geometrias dos ranks 97 e 83 são exatamente iguais em WGS84. A sobreposição intradata dos sucessores explica o excesso, e o cruzamento direto do rank 3 projetado e ainda inválido não permite separar quantitativamente projeção e reparo.

No P1 integral de 24194371, o modo `--preparar-metodologia-v2` da PR #52 (`d1b34db`) encontrou um bloqueio anterior ao de setembro, em 2020-07-30, rank 7. A feição de 42 coordenadas era válida em WGS84 e ficou autointersectada em LAEA. A execução local levou 7,081 s, atingiu 657.456 KiB de RSS e gravou somente o diagnóstico e o estado de bloqueio. O SHA-256 do P1 foi preservado. Os três jobs de CI passaram no HEAD da PR. [CI da PR #52](https://github.com/DomingosThiagoCode/BurnGeoFlow/actions/runs/45836798813)

**#34 / medição integral de 24194371.** Em `f5cf9c7`, usando o P1 integral conferido com `execucao.json`, as quatro saídas de `calcular_metricas` foram iguais às do pai do commit. Carga e projeção comuns levaram 62,93 s e incluíram os 393 reparos registrados pela rotina legada. No evento inteiro, uma medição por variante passou de 112,995 s (busca exaustiva) para 99,600 s (STRtree), redução de 11,85% só no cálculo. Nas cinco datas mais densas (2.019 feições, incluindo 10/09), as medianas de três medições foram 4,379 s e 3,124 s. O pico acumulado de 655.944 KiB inclui a preparação comum e não mede diferença de memória por variante. Shapely 2.2.0, GEOS 3.14.1 e PyProj 3.8.0. O script e o log local ficam em `/workspace/scratch/bgf-34/benchmark-24194371.py` e `.log`. [Branch de desempenho](https://github.com/DomingosThiagoCode/BurnGeoFlow/tree/codex/issue-34-indice-vizinhanca)

## Fechamento da cadeia offline dos arquivos brutos do GEE

A extração RAR5 identificou 24340828 no arquivo unitário e 24194371 nos dois volumes. Foram extraídos apenas o P1 e o P2 da exportação e o diagnóstico geométrico histórico de cada evento. A revalidação com `--origem brutos --somente-aquisicao` ocorreu em cópias isoladas, com conferência dos quatro hashes registrados no diagnóstico novo de cada caso.

| Evento | SHA-256 P1 bruto | SHA-256 P2 bruto |
| --- | --- | --- |
| 24340828 | `862ae7e7edc3533015d6e66edb1d41908a3d77e5d10248b7089a8821edd5f779` | `32be1ecd10f090346a9a2704388194248720f585a3eb9790ba7f8a9f7b1bb0cc` |
| 24194371 | `b9d0a9cfef144107dd759312a143ffd486b71724831193640c7244bf1b9249d1` | `9bde475b36e7f13dbcd9677e388d81610e2c3e80ca39b0f2f2c364a52d49a48d` |

**#2 / PR #53.** A revalidação dos arquivos brutos reproduziu integralmente o conteúdo dos quatro GeoJSONs publicados anexados. A única diferença de bytes é a quebra de linha final (CRLF no histórico, LF na revalidação). Os diagnósticos reproduziram as listas históricas de 102 e 459 conversões geométricas, respectivamente, sem exclusões por área nula. A equivalência da revalidação offline está demonstrada para esses insumos. A cópia de 24340828 do checkout continua sendo uma referência geométrica distinta. Uma nova execução remota e a equivalência dos produtos científicos v2 permanecem fora desta verificação.

**#44 / PR #51.** O P1 exportado pelo GEE de 24194371 já apresenta a sobreposição 3/83. Os polígonos de 10/09 rank 97 e 11/09 rank 83 são idênticos nos arquivos bruto e publicado. A normalização do rank 3 de 11/09 retirou duas LineStrings da GeometryCollection e preservou exatamente as coordenadas do único Polygon. As propriedades das três feições coincidem. A interseção das partes poligonais dos sucessores, recortada pelo antecessor em WGS84 e depois projetada em LAEA, mede 1,190236657347 m². Após a regularização legada, mede 1,190236667220 m². A sobreposição, portanto, antecede a normalização e a regularização locais. Como o P1 exportado já contém os componentes construídos no GEE, ele não permite atribuir a origem aos perímetros DailyPerimeters ou a uma operação remota específica.

Evidências locais em `/workspace/scratch/bgf-brutos` e `/workspace/scratch/bgf-24194371-brutos-topologia.daD20C`. O GitHub preserva hashes e resultados agregados. Os GeoJSONs, caches e metadados específicos do ambiente ficaram fora dos commits.

### Comparação focal dos métodos de reprojeção (#3 / PR #52)

A aproximação vigente projeta apenas os vértices e liga-os em LAEA por cordas. A alternativa experimental interpola linearmente cada borda em WGS84, projeta os pontos de 1/4, 1/2 e 3/4 do intervalo e subdivide em metades quando alguma amostra excede o desvio observado da corda. Reutilizar a mesma sequência em orientação inversa garante discretização igual para segmentos idênticos. Trechos parcialmente coincidentes exigem nós comuns antes da projeção. O desvio baseado em três amostras não constitui limite analítico global.

| Caso focal | Precisão e estabilidade | Área |
| --- | --- | --- |
| 24340828, 15/08 rank 1 | Quatro perturbações direcionais de 1 ULP (máximo 3,64 × 10⁻¹² m) e arredondamentos ponto a ponto de 1 nm a 1 mm mantiveram a feição inválida. Na densificação, 1 cm manteve a falha e 1 mm recuperou a validade de 16/16 feições, mantendo os seis pares de contato observados em WGS84. | Cordas −161,724 m² e desvio amostrado de 1 mm −1,310 m², frente à aproximação de 2,5 µm. A diferença entre 2,5 e 0,625 µm foi 0,003755 m². |
| 24340828, 09/10 rank 1 | A feição continuou inválida a 10 µm e ficou válida a 2,5 µm. A 2,5 µm, 15/15 feições válidas e os 15 pares de contato coincidem com WGS84. | Cordas −865,249 m² frente a 2,5 µm. Diferença de área entre 2,5 e 0,625 µm de 0,003185 m². |
| 24194371, 10/09 rank 97 e sucessores 3/83 de 11/09 | O sucessor 3 continuou inválido até 10 µm, ficando válido a 2,5 µm. Os três polígonos eram válidos em WGS84, com sobreposição tripla de área positiva. | A área duplicada ficou em aproximadamente 1,190234 m² com densificação sem `make_valid`, comparada a 1,190237 m² no diagnóstico legado. |

O teste de contatos compara pares que se intersectam, sem provar estabilidade da dimensão, área ou forma das respectivas interseções. A convergência de área não garante estabilidade topológica, como mostra 09/10. Como verificação adicional da área, foram amostradas uniformemente 16, 32, 64, 128 e 256 posições por segmento, com soma compensada da área orientada dos anéis em LAEA. A extrapolação de Richardson `A_2n + (A_2n - A_n)/3` deu 121.297.899,200495 m² e 951.342.467,338192 m² para os dois alvos de 24340828. As duas extrapolações mais finas diferiram em menos de 8 × 10⁻⁶ m² em ambos. Trata-se de evidência numérica para a mesma projeção e a mesma interpretação das bordas, sem homologação topológica ou limite rigoroso de erro.

Um exame das interseções no refinamento de 2,5 µm preservou a dimensão em todos os pares das duas datas. Em 15/08, foram cinco contatos de dimensão 0 e uma interseção de área. Em 09/10, foram seis contatos de dimensão 0, um de dimensão 1 e oito interseções de área. A maior diferença de área entre sobrepor as feições projetadas e projetar a interseção WGS84 foi de 4,75 × 10⁻⁷ m² e 4,62 × 10⁻⁴ m², respectivamente. Esta comparação é focal e usa o mesmo refinamento para ambos os caminhos.

Os valores de refinamento são parâmetros experimentais, sem efeito em produção. Para retomar, especifique um orçamento de erro e teste nós compartilhados em bordas parcialmente coincidentes antes de ampliar a amostra. A sobreposição real da exportação GEE exige uma decisão separada sobre o tratamento científico. Para atribuir a causa a montante de #44, são necessários os perímetros-fonte ou estados intermediários das operações remotas de dissolução, união acumulada e decomposição. Os P1/P2 v2 e a regressão integral continuam bloqueados.

Passaram 10 testes de geometrias de aquisição e quatro de metodologia v2. A regressão sintética de autointerseção e o CI aprovado seguem na PR #52 (`d1b34db`). Scripts experimentais e logs locais em `/workspace/scratch/bgf-projecao-aquisicao/`; as entradas não foram modificadas.
