# Metodologia científica — registro de decisões

Este documento registra as decisões acordadas da pesquisa, independentemente da implementação. Em caso de divergência entre código e decisão registrada, investigar e corrigir a implementação, não alterar silenciosamente a metodologia. Novas decisões devem ser acrescentadas com justificativa e estado de validação.

## P1 e P2: objetos complementares

- P1: todos os componentes da área queimada acumulada em cada data observada; métricas de paisagem, conectividade e fusões.
- P2: uma única região (componente do P1) por data, destinada à análise geométrica temporal por TR/IGT. Não é uma reconstrução de todos os ancestrais nem necessariamente o maior componente em todas as datas.

## D-001 — Seleção retrospectiva do P2

**Estado:** decisão conceitual acordada em 26/11/2026; implementação e validação pendentes.

1. Ordenar as datas observadas do P1.
2. Na última data, escolher o maior componente por área (rank 1 na ordenação do P1).
3. Retroceder para a observação imediatamente anterior. Selecionar o componente do P1 cuja interseção espacial com o componente já escolhido na observação posterior tenha a maior área.
4. Repetir até a primeira observação, quando existir continuidade verificável.
5. Reordenar cronologicamente os componentes selecionados para as análises TR/IGT.
6. Registrar rank e participação da área do P2 na área total do P1 por data. Não trocar de componente simplesmente porque outro se tornou maior.

**Justificativa:** reconstruir uma linhagem espacial principal que termina no componente dominante final do incêndio histórico, mantendo apenas um componente por data. Em fusões, o maior ancestral imediato por interseção é escolhido; os demais são tratados na análise de linhagens do P1. Não confundir esta regra local (gulosa) com otimização global da linhagem.

**Exemplo:** em t−2, A=30 e B=60 km²; em t−1, A=80 e B=65 km²; em t, ambos se fundem em 150 km². Admitindo inclusão espacial de cada ancestral, o rastreamento seleciona A em t−1 e A em t−2, embora B seja maior nesta última data.

**Alternativas não adotadas:** rastreamento progressivo a partir do maior componente inicial (pode permanecer em um componente residual); selecionar o maior patch a cada data (pode romper a continuidade); incluir todos os ancestrais do maior componente final (desvirtua a distinção P1/P2 e amplia a complexidade da análise).

**Evidência da necessidade da revisão:** evento 24194371, 128 datas, área final total 17.908,2595 km² e P2 progressivo final 26,4019 km², conforme aquisição reportada. A implementação atual de aquisição em `burngeoflow/aquisicao/earth_engine.py` usa o maior componente inicial e rastreamento progressivo; portanto diverge desta decisão. O P2 retrospectivo ainda precisa ser implementado e testado, incluindo no caso original 24340828. Resultados dependentes de P2 antigo devem ser identificados como tal e recalculados após a revisão, preservando proveniência.

**Ainda em discussão:** regra de empate, ausência de sobreposição (não autorizar salto automático sem decisão), critério topológico de conectividade do P1, tolerâncias geométricas, interpretação de fusões e representatividade ao longo do tempo. Não confundir crescimento do P2 por incorporação de áreas anteriormente queimadas com nova área queimada. Não fixar limiar de representatividade sem justificativa.

## Próximas decisões

Discutir individualmente, sem antecipar consenso:
- Conectividade dos componentes (contato pontual versus borda).
- Empates e ausência de sobreposição no rastreamento.
- Fusões e distinção entre incorporação e expansão.
- Regularização, tolerâncias e auditoria topológica (issue #44).
- Representatividade, interpretação e seleção de indicadores TR/IGT.
- Segmentação temporal/BIC, validação e generalização.
