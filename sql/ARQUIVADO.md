# SQL/PostGIS — arquivo histórico (não canônico)

**Status: arquivado, desde 08/11/2026.**

Os três arquivos SQL continuam preservados por rastreabilidade e eventual
verificação cruzada, mas o processamento principal é Python/Shapely/PyProj.

A autora do estudo TR utilizou SQL como ferramenta de implementação, não como
restrição da metodologia. **As views adaptadas aqui ainda não foram executadas
em servidor PostGIS:** não reivindicamos equivalência numérica SQL × Python.

Caso se deseje uma auditoria cruzada no futuro, executar as views em uma base
PostGIS real, exportar os mesmos IDs/datas e conferir projeções, centroides e
azimutes antes de comparar números. Esse teste não bloqueia a etapa seguinte.

Referências e decisões: docs/fechamento_etapa4.md.
