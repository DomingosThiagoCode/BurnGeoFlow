# Backlog incremental BurnGeoFlow

Abordagem Kanban, PRs pequenos e reversíveis; ordenação por dependências.

| ID | Prioridade | Tarefa | Aceite | Status |
|---|---|---|---|---|
| BG-01 | P0 | Auditoria, baseline e ADR | Diagnóstico documentado, script instrumentado, CI | Concluído (PR #20) |
| BG-02 | P0 | Back-end FastAPI leitura | Lista, datas, séries, GeoJSON por data/camada, downloads; API tests | Concluído (PR #21) |
| BG-03 | P0 | Cache geográfico por data | Índice derivado sem modificar P1/P2, validade por hash e assinatura; benchmark | Concluído (PR #21) |
| BG-04 | P1 | Frontend React/TS | Mapas P1/P2, timeline, indicadores, loading/erro, exportação | Em revisão (PR #22) |
| BG-05 | P1 | QA e UX | Mobile/Desktop, teste de navegação, p50/p95, contraste e feedback | Pendente |
| BG-06 | P1 | Tarefas operacionais | Processar ID, status/progresso com logs, sem duplicar CLI | Pendente |
| BG-07 | P2 | SQLite de jobs | Migração aditiva e backup, estados robustos, recuperação | Pendente |
| BG-08 | P2 | Empacotamento e release | pyproject/README/ADR, builds verificáveis e versão estável | Pendente |
| BG-09 | P3 | Revisão científica interna | Decompor módulos grandes sem mudar fórmulas e com contratos | Pendente |

**DoD por PR:** mudanças pequenas, testes de regressão, risco documentado,
sem quebra CLI e sem alterações destrutivas ao cache `execucoes/`.
