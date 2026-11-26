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

**Ainda em discussão:** tolerâncias geométricas, interpretação dos indicadores durante fusões. Não confundir crescimento do P2 por incorporação de áreas anteriormente queimadas com nova área queimada. A representatividade é tratada na D-006.

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

**Implicações:** não preencher datas anteriores com geometrias fictícias ou zeros; distinguir ausência de P2 de ausência de incêndio. Adequar validação, interface, indicadores e integração às datas efetivamente disponíveis. Registrar motivo de encerramento, data inicial do P2 e diagnóstico de eventuais inconsistências. Não interpretar falhas geométricas como nascimento confirmado. A elegibilidade por área de interseção positiva está definida na D-007.

## D-004 — Desempate entre ancestrais do P2

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

A seleção retrospectiva usa a maior área de interseção como critério principal (D-001). Em caso de empate entre candidatos elegíveis, priorizar a maior área total do componente anterior. Persistindo o empate, priorizar a menor distância entre os centroides do candidato e do componente posterior rastreado.

**Justificativa:** manter uma regra simples para casos potencialmente raros, sem introduzir uma otimização global ou análise adicional do histórico de crescimento apenas para desempatar.

**Rastreabilidade:** registrar candidatos empatados, áreas de interseção e totais, distâncias e critério aplicado. A tolerância numérica para identificar empates e o critério residual para igualdade em todos os critérios ainda devem ser especificados na implementação e documentados. A regra não autoriza saltos sem continuidade espacial (D-003).

## D-005 — Separar expansão observada e incorporação por fusão no P2

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

Manter a geometria integral do componente selecionado como P2 após uma fusão. Usar a área acumulada total do P1 da observação anterior para distinguir área recém-mapeada como queimada de área anteriormente queimada incorporada ao P2.

Se R0 e R1 representam o P2 anterior e atual, e U0 é a união dos componentes do P1 anterior, calcular:
- Expansão geométrica bruta: área(R1 ∖ R0).
- Área nova observada no P2: área(R1 ∖ U0).
- Área previamente queimada incorporada: área((R1 ∖ R0) ∩ U0).
- Diagnóstico de perda geométrica: área(R0 ∖ R1); a variação líquida de área é a expansão bruta menos essa perda.

Como R0 integra U0, a expansão bruta corresponde à soma da área nova e da área incorporada, ressalvadas inconsistências geométricas e tolerâncias a definir. Não atribuir automaticamente toda a área nova do P1 ao P2: ela pode pertencer a outros componentes. Calcular em sistema de referência de área adequado, com união para evitar dupla contagem.

**Justificativa:** o P1 já contém o histórico espacial necessário. A distinção evita interpretar crescimento geométrico por fusão como queima nova no intervalo. A área nova representa mudança observada no produto acumulado, não medição independente da combustão ou do instante exato de queima.

**Exemplo:** P2 anterior com 80 km² incorpora um patch de 40 km² já queimado e 5 km² recém-mapeados, resultando em 125 km². Crescimento bruto de 45 km², dos quais 40 incorporados e 5 novos.

**Implicações:** manter TR/IGT sobre a região selecionada, identificar intervalos com incorporação/fusão para contextualizar seus resultados e não confundir deslocamento geométrico com propagação física. Validar conservação das áreas em casos sintéticos e reais, incluindo perdas e lacunas entre datas.

## D-006 — Representatividade do P2 como indicador, não como filtro

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

Não excluir observações ou interromper o rastreamento do P2 apenas porque sua área absoluta ou sua participação na área total do incêndio é pequena. Calcular e disponibilizar a representatividade R(t) = 100 × área(P2(t)) / área(P1(t)), utilizando áreas comparáveis e a união dos componentes do P1 na mesma data.

**Justificativa:** o objeto do P2 é a linhagem espacial principal do componente dominante final (D-001), não o incêndio inteiro em todas as datas. Uma pequena participação relativa não invalida a observação nem justifica uma troca de componente. Os indicadores descrevem o P2; sua extrapolação para o evento completo deve ser contextualizada pela representatividade e pelas análises do P1.

**Limites:** não estabelecer percentual mínimo arbitrário; distinguir ausência de P2 de participação zero; sinalizar indicadores matematicamente indefinidos, geometrias inválidas e limitações de resolução independentemente da representatividade. Não inventar valores para observações ausentes.

## D-007 — Ancestralidade temporal exige sobreposição de área

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

Para selecionar um ancestral do P2, exigir área de interseção positiva entre o componente da observação anterior e o componente posterior rastreado. Contatos exclusivamente por vértice ou borda, sem área de interseção, não são suficientes para estabelecer ancestralidade temporal.

**Justificativa:** distinguir a conectividade espacial intradata (D-002), que inclui contatos pontuais, da continuidade temporal de uma região queimada acumulada, para a qual se espera a preservação de área anteriormente queimada. Investigar inconsistências topológicas ou numéricas antes de interpretar ausência de sobreposição como surgimento de um novo componente. Na ausência de ancestral elegível após diagnóstico, aplicar D-003, sem fallback por distância.

**Validação pendente:** casos de interseção positiva, contato pontual, contato por borda, ausência de contato e pequenas interseções sujeitas à precisão geométrica. Tolerâncias numéricas ainda devem ser justificadas; não confundir área positiva com comprovação de causalidade física.

## D-008 — Preservação da geometria científica e simplificação visual

**Estado:** decisão conceitual aprovada; implementação e validação pendentes.

- Preservar geometrias originais válidas como referência científica, sem simplificação automática motivada somente pelo desempenho.
- Reparar geometrias inválidas quando necessário, mantendo os dados brutos imutáveis e registrando método, alterações de área, perímetro, topologia e eventuais perdas. Reparos que alterem substancialmente a geometria exigem investigação, não aceitação silenciosa.
- Permitir simplificação e generalização em cópias destinadas exclusivamente à visualização, inclusive por escala/zoom, sem alimentar cálculos científicos com essas cópias.
- Priorizar índices espaciais, processamento por data, streaming, reutilização de resultados e outras otimizações que preservem a definição matemática dos indicadores.
- Uma eventual simplificação para fins científicos exige estudo de sensibilidade e aprovação metodológica específica, considerando área, perímetro, conectividade, centroides, extremos e TR/IGT.

**Justificativa:** a geometria é o próprio objeto da análise. O ganho de velocidade não justifica alterações geométricas não avaliadas. A representação cartográfica pode ser mais leve sem comprometer a referência científica, desde que não induza interpretações erradas.

**Pendências:** tolerâncias numéricas, critérios quantitativos de reparo e investigação do issue #44 continuam em aberto; não aumentar tolerâncias indiscriminadamente para ocultar inconsistências. Validar a separação entre os produtos científicos e visuais.

## D-009 — Objeto de estudo: evolução geométrica da área queimada acumulada

**Estado:** decisão conceitual aprovada; implementação, revisão terminológica e validação pendentes.

O objeto observado é a área queimada acumulada (burned area) representada pelos perímetros do GlobFire, não o fogo físico, a frente ativa ou a dinâmica de combustão. Preservar os indicadores TR/IGT como descritores geométricos, adaptando sua interpretação ao fenômeno acumulativo.

Deslocamentos de centroides e extremos representam mudanças de posição de elementos geométricos; taxas de deslocamento representam essas mudanças por unidade de tempo, não velocidade de propagação do fogo. Direções descrevem tendências da evolução geométrica, não necessariamente a direção física de propagação. Fusões e representatividade devem contextualizar a interpretação conforme D-005 e D-006.

**Justificativa:** uma região queimada acumulada cresce por incorporação de áreas e não se desloca materialmente como um furacão. O valor científico dos indicadores para caracterizar e comparar padrões espaço-temporais de queimadas é questão a investigar, e não conclusão já demonstrada. Não inferir causalidade, velocidade de frente ativa ou condições ambientais apenas a partir das geometrias.

**Pendências:** justificar a utilidade e selecionar os indicadores, testar padrões em eventos distintos, verificar robustez e avaliar eventual relação com variáveis externas em etapa futura. Revisar nomes, unidades, legendas e textos da interface para evitar interpretação física indevida.

## D-010 — Avaliação exploratória da aplicabilidade dos indicadores TR/IGT

**Estado:** decisão conceitual aprovada; avaliação científica pendente.

Avaliar inicialmente o conjunto de indicadores originais TR/IGT documentados nas respectivas metodologias, sem seleção prévia baseada apenas em intuição. Verificar definições, hipóteses, unidades e compatibilidade com a geometria do P2; registrar indicadores inaplicáveis ou indefinidos em vez de inventar resultados. Aplicar a eventos com características distintas e investigar utilidade, redundância, sensibilidade e limitações.

**Objetivo:** determinar se, como e em quais condições os indicadores fornecem informação cientificamente relevante sobre a evolução espaço-temporal da área queimada acumulada. A análise do P1 serve de contexto e referência para avaliar a contribuição adicional do P2.

**Resultados admissíveis:** a metodologia pode revelar-se pouco útil ou inadequada para áreas queimadas; pode ser parcialmente aplicável; ou pode permitir consolidar um conjunto de indicadores, requisitos de dados, condições de validade e regras de interpretação capaz de sustentar afirmações verificáveis sobre a evolução geométrica observada. Não pressupor resultado positivo, nem confundir caracterização geométrica com inferência sobre dinâmica física do fogo (D-009).

**Pendências:** estabelecer critérios verificáveis de utilidade, robustez e informação adicional; distinguir análise exploratória de validação em outros eventos; documentar resultados negativos e justificar qualquer seleção final de indicadores.

## D-011 — Critérios de avaliação científica dos indicadores

**Estado:** cinco critérios conceituais aprovados; operacionalização e validação pendentes.

Avaliar os indicadores TR/IGT segundo:
1. Interpretabilidade: significado geométrico claro, unidades e limites de interpretação.
2. Redundância: informação adicional em relação às métricas básicas do P1 e aos demais indicadores; correlação é evidência exploratória, não prova isolada de redundância.
3. Sensibilidade: resposta a mudanças geométricas relevantes, verificável em casos controlados.
4. Robustez: estabilidade frente a perturbações plausíveis, precisão dos dados, reparos e escolhas metodológicas.
5. Capacidade de diferenciação: distinguir padrões de evolução geométrica em eventos distintos, sem confundir efeito do tamanho, duração ou representatividade com diferenças de comportamento.

**Justificativa:** a seleção final deve decorrer da avaliação científica, não da aparência dos gráficos nem da expectativa de resultado positivo (D-010). Registrar resultados negativos, limitações e situações de aplicabilidade parcial.

**Pendências:** definir procedimentos quantitativos, casos sintéticos e reais, critérios de comparação, controles e evidências mínimas para cada dimensão. Não estabelecer limiares arbitrários nem tratar os cinco critérios como testes já executados.

## D-012 — Segmentação temporal de referência pelo P1 e BIC

**Estado:** decisão conceitual aprovada; especificação estatística, implementação e validação pendentes.

Utilizar inicialmente a série temporal da área queimada acumulada total do P1 para construir modelos candidatos de segmentação temporal. Selecionar entre modelos comparáveis pelo menor BIC (k ln(n) − 2 ln(verossimilhança máxima)), equilibrando ajuste e complexidade. Investigar posteriormente o comportamento dos indicadores TR/IGT do P2 nas fases identificadas, evitando usar esses mesmos indicadores para definir as fases de referência e depois alegar capacidade de distingui-las.

**Justificativa:** o P1 caracteriza o evento completo; a segmentação constitui referência construída sem utilizar diretamente os indicadores TR/IGT, não uma validação externa ou independência estatística garantida. O BIC seleciona modelos candidatos, não identifica causas físicas nem garante a existência de múltiplas fases.

**Pendências:** especificar família de modelos, verossimilhança, tratamento de datas irregulares e autocorrelação, contagem de parâmetros incluindo pontos de mudança quando aplicável, duração mínima dos segmentos e comparação com modelo sem mudanças. Verificar sensibilidade e não forçar segmentação quando os dados não a sustentarem. Interpretar fases como padrões da evolução observada da área queimada, não fases físicas da combustão.

## D-013 — Tolerância numérica não equivale a tolerância espacial

**Estado:** princípio conceitual aprovado; calibração e validação pendentes.

Distinguir erros numéricos comprovadamente introduzidos por operações computacionais (reprojeção, precisão finita, interseção e união) de separações e diferenças espaciais presentes nos dados de origem. Admitir correção controlada e rastreável dos primeiros, sem conectar polígonos originalmente separados por mera proximidade e sem criar área queimada artificialmente (D-002, D-008).

Não adotar limiar fixo arbitrário nem usar a resolução nominal de 500 m como tolerância topológica. Investigar a magnitude e a origem dos erros em casos sintéticos e reais, comparar geometrias antes e depois das operações e justificar tolerâncias de distância e área separadamente, incluindo o tratamento de empates da D-004. Registrar valores, unidades, método, efeitos sobre conectividade e indicadores, e testes de sensibilidade. Um empate residual deve ser resolvido de forma reprodutível, com critério explícito ainda a especificar.

**Limite:** discrepâncias cuja origem não possa ser demonstrada devem ser sinalizadas para investigação; tolerâncias não podem mascarar inconsistências reais ou substituir a auditoria do P1 (issue #44).

## Próximas decisões

Discutir individualmente, sem antecipar consenso:
- Calibração das tolerâncias e especificação do desempate residual (D-013).
- Tolerâncias, critérios quantitativos de reparo e auditoria topológica (issue #44).
- Operacionalização quantitativa e validação dos cinco critérios da D-011.
- Especificação estatística da segmentação D-012; validação e generalização.
