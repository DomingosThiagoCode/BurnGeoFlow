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

**Ainda em discussão:** tratamento de contato exclusivamente pontual entre datas, tolerâncias geométricas, interpretação de fusões e representatividade ao longo do tempo. Não confundir crescimento do P2 por incorporação de áreas anteriormente queimadas com nova área queimada. Não fixar limiar de representatividade sem justificativa.

## D-002 — Conectividade por borda ou vértice no P1

**Estado:** decisão conceitual aprovada pelo usuário; implementação e validação pendentes.

Polígonos que compartilham uma borda ou um vértice pertencem ao mesmo patch. Polígonos separados permanecem distintos. A relação é transitiva: A tocando B e B tocando C formam um único componente, ainda que A e C não se toquem diretamente.

**Justificativa:** o produto MODIS de origem tem resolução espacial nominal de 500 m. O contato pontual possui área de interseção nula, mas a ausência de contato por borda não permite inferir desconexão física nessa escala. Trata-se de uma convenção de conectividade vetorial análoga conceitualmente à vizinhança 8, não de reconstrução exata da grade raster original nem de evidência de propagação física.

**Consequências:** agrupar os polígonos sem adicionar área artificial, sem buffer para unir componentes separados e sem alterar os dados brutos. Um patch lógico pode ser representado por MultiPolygon quando seus interiores são separados e suas fronteiras se tocam em pontos. Recalcular contagem, áreas, ranking, métricas, linhagens e P2 retrospectivo (D-001) sobre o P1 resultante. Verificar a compatibilidade dos indicadores TR/IGT com essa representação. Preservar o cenário sem agrupamento pontual para comparação de sensibilidade, quando viável.

**Validação pendente:** casos sintéticos de toque pontual, borda compartilhada, cadeias de contatos e separação; casos reais 24194371 e 24340828. Tolerâncias de precisão, reparos e sobreposições reais permanecem em discussão (issue #44). Não confundir agrupamento por contato com correção de sobreposições.

## D-003 — Ausência de continuidade espacial no rastreamento retrospectivo

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

Não criar saltos espaciais por proximidade para prolongar artificialmente o P2. Quando o componente rastreado não possuir ancestral espacial na observação anterior, após verificar a consistência geométrica e temporal dos dados, encerrar o rastreamento retrospectivo. O P2 começa na primeira data da linhagem reconstruída e pode ter menos observações que P1.

**Justificativa:** a região que se torna dominante ao final pode ter surgido depois do início do incêndio. A proximidade de outro patch não demonstra ancestralidade. A duração distinta de P1 e P2 não constitui, por si só, erro.

**Implicações:** não preencher datas anteriores com geometrias fictícias ou zeros; distinguir ausência de P2 de ausência de incêndio. Adequar validação, interface, indicadores e integração às datas efetivamente disponíveis. Registrar motivo de encerramento, data inicial do P2 e diagnóstico de eventuais inconsistências. Não interpretar falhas geométricas como nascimento confirmado. O tratamento específico de contato exclusivamente pontual entre observações sem área de interseção permanece por decidir, distinguindo a conectividade intradata D-002 da ancestralidade temporal.

## D-004 — Desempate entre ancestrais do P2

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

A seleção retrospectiva usa a maior área de interseção como critério principal (D-001). Em caso de empate entre candidatos elegíveis, priorizar a maior área total do componente anterior. Persistindo o empate, priorizar a menor distância entre os centroides do candidato e do componente posterior rastreado.

**Justificativa:** manter uma regra simples para casos potencialmente raros, sem introduzir uma otimização global ou análise adicional do histórico de crescimento apenas para desempatar.

**Rastreabilidade:** registrar candidatos empatados, áreas de interseção e totais, distâncias e critério aplicado. A tolerância numérica para identificar empates e o critério residual para igualdade em todos os critérios ainda devem ser especificados na implementação e documentados. A regra não autoriza saltos sem continuidade espacial (D-003).

## Próximas decisões

Discutir individualmente, sem antecipar consenso:
- Contato exclusivamente pontual entre datas no rastreamento; tolerância numérica e desempate residual.
- Fusões e distinção entre incorporação e expansão.
- Regularização, tolerâncias e auditoria topológica (issue #44).
- Representatividade, interpretação e seleção de indicadores TR/IGT.
- Segmentação temporal/BIC, validação e generalização.
