# Coordenação de múltiplos agentes Codex — BurnGeoFlow

> **Aplicação:** agentes trabalhando simultaneamente no mesmo repositório.
> **Leia primeiro:** [AGENTS.md](../AGENTS.md), [ESTADO_EXECUCAO.md](ESTADO_EXECUCAO.md), [METODOLOGIA.md](METODOLOGIA.md), [ROTEIRO.md](ROTEIRO.md).
> **Objetivo:** paralelismo sem alterações conflitantes, reimplementação duplicada ou afirmações científicas não sustentadas.

## 1. Princípios de coordenação

1. **Um coordenador/integrador humano ou agente** decide ordem de merges, aprova a divisão por arquivos e atualiza a memória operacional. Agentes auxiliares não alteram a `main` nem fecham issues por conta própria.
2. **Uma issue/subtarefa tem apenas um dono de integração.** Testes e revisão podem vir de outros agentes, mas a PR já existente deve ser reaproveitada. NÃO criar PR duplicada sem diagnóstico de abandono e decisão explícita.
3. **Cada agente usa seu worktree e sua branch.** Nunca compartilhe diretório de trabalho, `venv`, build `node_modules`, arquivo de estado temporário ou processo de job pesado.
4. **Evite escrita concorrente no mesmo arquivo.** Reserve módulos e contratos antes de tocar em `executar_pipeline.py`, `linhagens.py`, `metodologia_v2.py`, `frontend/src/atlas-theme.css`, `docs/METODOLOGIA.md` ou `AGENTS.md`.
5. **`main` é a base instalada, mas não contém as PRs abertas.** Antes de propor código, leia os diffs das PRs #49, #51 e #52 e a versão atual das issues.
6. **CI verde não é homologação.** Não dizer que uma issue científica está concluída só porque passou no Chromium, em mocks ou em geometrias sintéticas.
7. **Não gastar recursos externos desnecessariamente:** verificar cache P1/P2 e estado local antes de qualquer aquisição GEE. Não disparar reprocessamento completo até ser seguro.
8. Agente em espera por autenticação, dados reais ou decisão metodológica deve entregar evidências/documentação e **liberar o escopo para outras frentes**, sem repetir tentativas idênticas.

## 2. Protocolo de reivindicação de trabalho (claim)

Antes de editar:

1. Ler `docs/ESTADO_EXECUCAO.md`, a issue e os PRs em andamento; conferir SHA e mudanças recentes.
2. Escolher uma subtarefa com limites claros e identificar arquivos impactados, entradas/saídas e critérios de aceite.
3. Registrar na **issue correspondente** (ou em canal compartilhado do coordenador) um claim simples:

```text
CLAIM: #44 / diagnóstico da causa após evidência
Agente: <identificador>
Branch: agente/44-analise-topologica
Base: fix/44-diagnostico-intersecoes (PR #51)
Arquivos reservados: [lista curta]
Depende de: acesso local ao P1 de 24194371
Entrega: análise + testes; NÃO alterar metodologia sem aprovação
Estado: EM EXECUÇÃO
```

4. Se houver claim ativo conflitante, não editar. Dividir por interface/contrato, oferecer revisão ou solicitar reassignment ao coordenador.
5. Ao terminar, publicar **handoff** curto com branch, commits, testes/CI, evidência, riscos, pendência e arquivos alterados; marcar claim concluído ou bloqueado.

**Atenção:** claims são um protocolo de colaboração, não uma trava distribuída automática. Agentes que operam offline devem reconciliar claims antes de enviar PRs. Não armazenar credenciais, dados pessoais, links privados ou arquivos grandes nos comentários.

## 3. Frentes independentes e dependências de integração

| Frente / responsável lógico | Issue(s), ponto de partida | Escopo de arquivos | Dependências; não duplicar |
| --- | --- | --- | --- |
| **A. Topologia** | #44; continuar PR #51 | `burngeoflow/validacao/diagnostico_linhagens.py`, `burngeoflow/processamento/linhagens.py`, testes e guia correspondente | Falha 24194371 ainda sem causa real confirmada. Não criar correção com buffers/tolerâncias arbitrárias. Coordenar alterações de `linhagens.py` com C. |
| **B. Aquisição/proveniência** | #2; módulo legado existente | `burngeoflow/aquisicao/*`, testes específicos e contratos de origem | Não readquirir 24340828/24194371; comparar hashes e insumos reais. Não mexer no núcleo P2 da PR #52 sem acordo. |
| **C. Núcleo P1/P2 v2** | #3 e #45; continuar PR #52 | `burngeoflow/processamento/metodologia_v2.py`, `executar_pipeline.py` quando autorizado, testes sintéticos | Dependência forte da causa #44, política de reparos/tolerâncias e contratos P2. UM dono para P1+P2 e ranks. |
| **D. Integração e checkpoints** | #34 e #46; ler PR #52 | `validacao/produtos.py`, `analises/regioes_moveis.py`, `incrementos.py`, `tr_igt.py`, `integracao.py`, `robustez.py`, API de estado | Alinhar contrato de entradas/saídas v2 com C antes de modificar. Não forçar datas P1=P2 nem preencher observações inexistentes com zero. |
| **E. QA e protocolos científicos** | #47; base `tests/` e `backend/tests/` | Novos testes de contrato, sintéticos, benchmarks e protocolo de evidências | Pode avançar paralelamente, mas critérios científicos devem vir de METODOLOGIA.md, nunca de conveniência de teste. |
| **F. Catálogo e UX** | #31; continuar PR #49. #40/#43/#42 somente após coordenação | `catalogo.py`, `limites_ibge.py`, `CatalogoPanel.tsx`, `AoiDrawMap.tsx`, depois UX | #49 já tem CI verde. Falta teste IBGE/GEE real; compartilhar mudança de `atlas-theme.css` com PR #52. Não reconstruir catálogo. |
| **G. Landing e comunicação** | #50; primeira versão já na main | `frontend/src/story/`, `frontend/public/story/`, `docs/LANDING_SCROLLYTELLING.md` | Pode refinar layout de forma independente; NÃO substituir dados/claims P2 antigos por v2 sem revisão científica C/D. |
| **H. Coordenação de merges/docs** | AGENTS/ESTADO/ROTEIRO e PRs | `AGENTS.md`, `docs/ESTADO_EXECUCAO.md`, `docs/COORDENACAO_AGENTES.md`, snapshots de status | Um dono de escrita, evitando merge conflicts e dezenas de ciclos de CI por atualização narrativa. |

**Não iniciar oito agentes simultâneos sobre o mesmo pipeline.** Um conjunto inicial eficiente: A (topologia), C (P1/P2, sujeito à A), D/E (contratos/testes) e F/G (produto, sem mexer no núcleo). Se #44 estiver bloqueada por dados locais, C/D podem preparar testes e interfaces, mas não homologar a integração científica.

### Arquivos com zona de exclusão mútua

- `AGENTS.md`, `docs/METODOLOGIA.md`, `docs/ROTEIRO.md`: somente coordenador, com revisão científica para decisões.
- `executar_pipeline.py`, `processamento/metodologia_v2.py`: proprietário de integração do núcleo.
- `processamento/linhagens.py`: dono topologia durante #44, depois handoff explícito ao integrador P1.
- `frontend/src/atlas-theme.css`: PRs #49 e #52 já modificam. Um único integrador deve reconciliar o CSS.
- `backend/app/api/routes.py`, `JobsPanel.tsx`: mudanças nos contratos com backend exigem revisão coordenada.

## 4. Criar worktrees sem misturar branches

O exemplo abaixo pressupõe que os PRs ainda existem. Ajustar refs após consultar o GitHub. Não usar o mesmo diretório de execução do servidor local.

```bash
git fetch origin --prune

# Agente da topologia usa a PR já existente como base de trabalho:
git worktree add ../bgf-topologia -b agente/44-causa origin/fix/44-diagnostico-intersecoes

# Agente do núcleo usa a PR v2 já existente:
git worktree add ../bgf-metodologia -b agente/45-integracao origin/feat/e2-metodologia-v2-checkpoints

# Agente de catálogo usa a PR existente:
git worktree add ../bgf-catalogo -b agente/31-homologacao origin/feat/31-catalogo-completo-aoi

# Agente de landing parte da main, sem copiar componentes científicos:
git worktree add ../bgf-landing -b agente/50-design origin/main
```

Essas branches auxiliares servem para isolamento; **não abrir novas PRs paralelas para resolver a mesma issue**. Integrar mudanças aprovadas no PR original por cherry-pick/merge realizado pelo responsável, com revisão do diff e CI. Nunca dar `git push --force` em branch compartilhada para resolver divergência.

## 5. Contratos antes de implementação paralela

### Novo P1/P2 (C -> D)

Antes de D integrar TR/IGT, C precisa definir e versionar:

- Qual arquivo é bruto imutável; qual é P1 derivado por contato; qual é P2 retrospectivo;
- convenção de rank, `ranks_origem`, geometria e fonte das áreas;
- P2 com datas subconjunto de P1 e o significado de início/ausência de ancestral;
- campos de representatividade e seu denominador P1;
- política de sobreposições/reparos; áreas de interseção e desempates;
- esquema/versão de produto e SHA-256 de código, entradas e saídas.

O integrador D deve **adaptar** validadores e leitores para P2 mais curto, preservar indicadores indefinidos/ausentes como ausência, e não fazer a v2 caber artificialmente no contrato legado.

### Estados de execução (C/D -> UI)

Distinguir `arquivo_ausente`, `arquivo_vazio`, `bruto_disponivel`, `em_execucao`, `etapa_concluida_legado`, `artefato_perdido`, `falha`, `input_alterado`, `codigo_alterado`, `dependencia_desatualizada`, `v2_preprocessado_nao_integrado`, `v2_integrado_validado` (este último **ainda não implementado**).

O estado de execução deve ser derivado de manifesto + arquivos + hashes + versão; o front não pode inferir validade científica de um `HTTP 200`, `job.completed` ou de um gráfico existente. A PR #52 tem primeiro leitor/checkpoint e deve ser reutilizada, não duplicada.

## 6. Testes, validação e condições de merge

- Desenvolvimento local: testes direcionados e de contrato, sem GEE.
- Integração: executar `python -m unittest discover -s tests`, `python -m unittest discover -s backend/tests`, `npm ci && npm test && npm run build` na pasta `frontend`; validar smoke Chromium conforme CI do projeto. Usar o workflow como referência para comandos exatos.
- Confirmar CI no **último SHA** da branch após rebase/merge; verde em SHA anterior não basta.
- Para geoprocessamento: validar invariantes topológicas e áreas, diferenças geométricas, acesso a insumos reais, proveniência de cada produto, comportamento em fusões e ausência de dados.
- A PR #51 é diagnóstico e não fecha #44 sem evidência real; a PR #52 é experimental e não conclui #3/#45/#46 por si só; a PR #49 não fecha #31 sem IBGE/GEE real.
- Proteger dados: arquivos brutos, caches, `execucoes/`, `.env`, credenciais e outputs científicos nunca devem ser commitados acidentalmente.
- Só o coordenador faz merge **quando autorizado**, depois de reconciliação de conflitos, revisão e testes. Atualizar `ESTADO_EXECUCAO.md` na integração para remover informação obsoleta.

## 7. Formato mínimo de entrega de cada agente

```text
ISSUE / PR: #... / #...
BRANCH / HEAD: ... / ...
STATUS: implementado em branch | CI aprovado | integrado | homologado | bloqueado
ARQUIVOS ALTERADOS: ...
TESTES: comando + resultado + SHA (não apenas "passou")
EVIDÊNCIAS: links para logs, artefatos e testes reais; onde reproduzir
NÃO FOI FEITO: ...
BLOQUEIOS: dados/autenticação/decisão/depende de outro PR
PRÓXIMO PASSO EXATO: ...
```

A documentação de estado não substitui a issue: registrar decisões metodológicas em `METODOLOGIA.md`, detalhes técnicos na PR/issue e somente o resumo de continuidade em `ESTADO_EXECUCAO.md`.

## 8. Primeiras ações sugeridas ao orquestrador Codex

1. Reconciliar os três PRs, a versão atual de `main` e seus testes. Não assumir que commits históricos já foram integrados.
2. Reservar #44 para diagnóstico REAL do patch 2020-09-10 rank 97 usando P1 local, sem GEE.
3. Reservar #3/#45 ao mesmo dono científico para revisar a PR #52 à luz das evidências #44 e dos critérios D-001–D-008.
4. Separar #46 em contrato/validação, análise TR/IGT e integração/atlas; travar os contratos de entrada com o dono v2 antes de implementar.
5. Reservar #47 para regressão contínua e planejamento de homologação dos dois IDs.
6. Entregar #31/#50 em paralelo só quando não houver colisões de CSS/rotas e sem declarar produtos não comprovados.
