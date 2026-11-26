# Roteiro do BurnGeoFlow

## Diretriz
A fonte de verdade científica é [METODOLOGIA.md](METODOLOGIA.md), decisões D-001 a D-016. Este roteiro organiza execução e dependências; não substitui decisões científicas. Estado: definições conceituais aprovadas, detalhamentos quantitativos e implementação ainda pendentes. Nenhum issue é fechado por mera documentação.

## Prioridades
- P0: bloqueadores científicos e de aquisição.
- P1: implementação científica, desempenho, testes e avaliação.
- P2: interface, catálogo e documentação operacional; refatoração visual depois da regressão básica.
- P3: ampliação, validação confirmatória e consolidação/distribuição.
Prioridades são ordem de trabalho, não severidade absoluta; testes e documentação devem acompanhar cada mudança. Não atrasar correções essenciais de segurança/operabilidade por causa da fila visual.

## Etapas e critérios de passagem

| Etapa | Objetivo | Issues | Critério para avançar |
|---|---|---|---|
| E1 | Definições metodológicas | D-001–D-016 | Registro conceitual concluído; parâmetros quantitativos ainda pendentes. |
| E2 | Adequar e estabilizar o núcleo | #2, #3, #44, #45, #34, #46 | Aquisição rastreável; P1 e P2 conformes; inconsistências investigadas; produtos e caches versionados; testes unitários e de integração. |
| E3 | Testes controlados e regressão | #47 | Casos sintéticos e ambos os eventos de desenvolvimento processados integralmente e auditados; desempenho medido; sem falhas fundamentais ou resultados ocultamente corrigidos. |
| E4 | Investigação exploratória | #47 | Protocolos dos cinco critérios executados; contribuição dos indicadores em relação ao P1, limitações e resultados negativos documentados. |
| E5 | Validação e generalização | #48 | Protocolo congelado; novos eventos de validação distintos dos de desenvolvimento; evidências e limites reportados. |
| E6 | Consolidação científica e distribuição | #48, #4, #41 | Conclusões sustentadas pelos testes; pacote metodológico quando aplicável, documentação e eventual artigo/release. |

## Ordem de execução imediata (E2/E3)

1. [#44](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/44): reproduzir a inconsistência de 10/09/2020 rank 97 no P1 antigo e identificar sua causa. Em paralelo, [#2](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/2): revisar aquisição GEE/local, proveniência e insumos. Não mascarar erros com tolerâncias.
2. [#3](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/3): implementar agrupamento transitivo por borda/vértice no P1, preservar bruto, recalcular métricas/rank; confirmar consistência topológica e linhagens no P1 revisado em conjunto com #44.
3. [#45](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/45): P2 retrospectivo sobre P1 revisado, sem salto artificial, com regras D-001/D-003/D-004/D-006/D-007. Não reutilizar P2 progressivo como se fosse atual. #2 deve validar equivalência da aquisição e dos produtos revisados.
4. [#34](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/34): otimizar gargalos sem alterar definições científicas; logs intermediários, memória, checkpoints e retomada. Pode ser trabalhado em paralelo desde o começo, especialmente quando bloquear testes.
5. [#46](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/46): adequar integração, área nova versus incorporação, representatividade, TR/IGT, nomes, geometrias visuais e segmentação P1/BIC.
6. [#47](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/47): testes sintéticos devem ser preparados desde o início e acompanhar cada mudança; executar regressão integral no final de E2. A avaliação de utilidade E4 é distinta da correção do software.

## Casos obrigatórios de desenvolvimento

| ID | Registros fonte | Datas | Histórico |
|---|---:|---:|---|
| 24340828 | 947 | 57 | Pipeline anterior concluído; nova metodologia ainda não validada. |
| 24194371 | 18.175 | 128 | P1 anterior com 30.795 feições; regularização e paisagem concluíram; linhagens falhou (#44); P2 progressivo inadequado ao objetivo. |

Preservar produtos antigos com sua versão; reprocessar localmente a partir de insumos válidos quando possível e validar GEE autenticado quando necessário. Registrar tempo, pico de memória, logs, proveniência, invariantes de área, seleção P2 e dependências. Não presumir que os números antigos de P1/P2 se mantenham após mudança de conectividade. Os dois casos não são validação independente. Não iniciar campanha de milhares de IDs antes de E3 e protocolo E5.

## Fila de produto (P2)

Após núcleo estável e regressão básica E3, sem bloquear a investigação científica:
- [#43](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/43): módulos do atlas, menu hover à esquerda, gerenciamento flutuante à direita.
- [#31](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/31): completar e validar catálogo leve.
- [#40](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/40): paginação, coordenada com #43; revisar branch preliminar existente.
- [#42](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/42): rosáceas interativas após confirmação das convenções científicas em #46.
- [#41](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/41): README incremental para operação e metodologia, revisão final de funcionalidades depois da interface.
- [#4](https://github.com/DomingosThiagoCode/BurnGeoFlow/issues/4): distribuição final em E6 (P3).

## Regras de conclusão
- Cada issue deve conter critérios de aceite, evidências e limitações. Não fechar por testes simulados quando exige validação real.
- Alterações metodológicas exigem atualização explícita de METODOLOGIA.md; não adaptar regras silenciosamente para fazer testes passarem.
- Preservar dados brutos, versionar produtos/caches e invalidar dependências afetadas.
- CI e testes científicos são complementares; interface funcional não implica validade científica.
- A etapa E5 depende de E4; a amostra deve crescer progressivamente, não por volume arbitrário de catálogo.
