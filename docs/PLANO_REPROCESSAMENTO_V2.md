# Reprocessamento científico D-001/D-002: plano seguro para 24340828 e 24194371

**Estado de implementação:** a reconstrução P1/P2 v2 nesta PR é experimental e
**não está integrada às etapas finais**. O objetivo imediato é preservar o
trabalho feito, tornar as pendências observáveis e avançar apenas com
resultados cientificamente consistentes.

## Mudança metodológica

| Produto | Antes (legado) | Agora (decisão aprovada) | Implementação |
| --- | --- | --- | --- |
| P1 | Componentes exportados pelo GEE | Agrupamento transitivo de polígonos por vértice ou borda sem buffer, sem adicionar área (D-002) | Pré-processador v2, sujeito a bloqueio por sobreposição |
| P2 | Maior na data inicial, seguido para a frente por sobreposição/proximidade | Maior na data final, rastreado para trás pela maior interseção de área (D-001/D-007); sem saltos por proximidade (D-003) | Pré-processador v2 |
| Empate P2 | Heurística legada | Interseção, área, distância (D-004); empate residual não resolvido exige decisão | Empates estritamente iguais seguem os critérios; empate residual bloqueia |
| Datas | P2 forçado a ter todas as datas de P1 | P2 pode ter menos datas, e início posterior | Geração v2 implementada; validadores e métricas posteriores **pendentes** |
| TR/IGT e integração | Calculados com P2 progressivo | Devem ser recalculados somente com P2 retrospectivo após adaptar contratos | **Pendente (#46)** |

**Atenção:** dados acumulados do GlobFire não são observações diretas de
frente ativa de fogo. A separação entre área nova e incorporação na
região P2 permanece condicionada a testes científicos.

## 1. Inspecionar, não baixar de novo

No painel **Processar e acompanhar eventos**, digitar o ID e usar
**Inspecionar arquivos**. A nova API `GET /api/events/{ID}/pipeline-status`
retorna os quatro insumos (brutos GEE P1/P2; P1/P2 local), o estado da
preparação v2 e as oito etapas científicas do manifesto antigo.

As etapas são diferenciadas em:
- `concluido_legado`: produto anterior íntegro *naquela versão*, não
  homologado sob D-001/D-002;
- `desatualizado`: hash de código ou insumos não corresponde;
- `artefato_perdido`: manifesto previa um arquivo, mas ele está ausente ou vazio;
- `erro`: última tentativa da etapa falhou;
- `pendente`: não existe comprovação de conclusão;
- `dependencia_desatualizada`: estágio a jusante não pode ser confiável
  após mudança/falha anterior;
- `preprocessado_nao_integrado`: P1/P2 v2 gerados, mas não usados pelas
  análises antigas.

A consulta é **somente leitura**: não precisa de autenticação GEE, não
dispara job e não altera nem remove arquivos. O SHA-256 é calculado
quando o usuário clica em Inspecionar, não a cada polling da interface.

## 2. Pré-processar P1/P2 v2 somente após revisar bloqueios

Os arquivos originais esperados são:

```text
execucoes/
  24340828/
    dados/estudo_caso_24340828/
      P1_componentes_24340828.geojson
      P2_regiao_movel_24340828.geojson          # legado, preservado
      brutos_gee/                              # quando houve aquisição GEE
  24194371/
    dados/estudo_caso_24194371/
      P1_componentes_24194371.geojson
      P2_regiao_movel_24194371.geojson          # legado, preservado
      brutos_gee/
```

**Teste experimental e restrito** (não executa GEE nem TR/IGT):

```powershell
python executar_pipeline.py --id 24340828 --origem local --preparar-metodologia-v2
python executar_pipeline.py --id 24194371 --origem local --preparar-metodologia-v2
```

**Não rodar estes comandos como prova de validade científica** até a análise
das sobreposições (issue #44) e aprovação do método; o 24194371 pode bloquear
por inconsistência intradata, e esse bloqueio é intencional.

Os resultados experimentais são gravados em
`execucoes/<ID>/dados/estudo_caso_<ID>/derivados_v2/<versao>/`,
separados do legado. Um bloqueio salva `diagnostico_bloqueio.json` e
não cria manifesto de sucesso.

## 3. O que precisa ser concluído antes do reprocessamento integral

1. **#44 e #2:** diagnosticar e corrigir, com justificativa, inconsistências
   topológicas e equivalência dos insumos.
2. **#3 e #45:** validar conectividade P1, ancestralidade P2 e tratamento
   de empates, reparos, sobreposições e datas ausentes em P2.
3. **#46:** adequar validadores, auditoria, séries P1, TR/IGT, integração
   e visualização para P2 com início próprio.
4. **#34:** garantir checkpoints que invalide apenas produtos dependentes,
   não repita a aquisição e preserve diagnósticos de falhas.
5. Reprocessar os **dois IDs locais** uma vez, registrar SHA-256,
   estados por etapa, contagens, tempos e discrepâncias. Comparar com
   os produtos históricos sem sobrescrevê-los silenciosamente.

No estágio atual, **rodar o pipeline normalmente continua executando as
regras científicas legadas**. Um aviso explícito aparece no terminal e o
manifesto identifica `metodologia_aplicada=p1_legado_p2_progressivo`.
A interface não afirma que esses resultados cumprem a nova metodologia.

## 4. Política de reuso e perda de arquivos

- Brutos GEE e GeoJSONs de origem são intocados.
- Caches e resultados antigos são mantidos como histórico, identificados
  como legados.
- Não reutilizar um passo se SHA de código/entrada divergir, se a assinatura
  estiver ausente, se qualquer artefato obrigatório desaparecer ou se
  uma etapa anterior foi reexecutada.
- Falhas geométricas bloqueiam os produtos dependentes, sem atribuir causa
  a partir de um único número e sem descartes automáticos.
- O painel não apresenta porcentagens fictícias de progresso remoto GEE.

**Resumo operacional:** primeiro atualizar método e contratos científicos;
depois reprocessar *localmente* os dois IDs com checkpoints/proveniência;
somente após regressão é seguro tomar os novos indicadores como atuais.
