# Diagnóstico rastreável de excesso de interseções nas linhagens (#44)

## Contexto

O P1 legado de **24194371**, com 30.795 feições em 128 observações,
interrompeu `linhagens` na data **2020-09-10, rank 97**:

```
FALHA: Patch anterior 2020-09-10 rank 97: soma das intersecoes maior
que a propria area; revisar sobreposicoes em P1
```

**Este diagnóstico não é a correção da topologia.** É o primeiro passo
necessário para classificar a causa antes de determinar um tratamento
compatível com as decisões D-008/D-013/D-014 e a conectividade D-002.

## Invariante vigente (inalterada)

Para cada patch de uma das datas, `soma das áreas de interseção com os
patches da outra data <= área do próprio patch + max(1 m², 1e-8 × área)`.
A violação mantém o erro fatal, não gera arquivos CSV finais de linhagens
e não ignora patches, reduz áreas ou altera a geometria de entrada.

A nova exceção `ExcessoIntersecoes` inclui um dicionário com evidências;
o comando de etapa 3 as grava em JSON antes de parar.

## Evidências persistidas

Em `<pasta_saida>/diagnostico_topologia_<ID>_<data>_<lado>_r<rank>.json`:

- ID, data, rank e lado da transição (anterior/atual);
- data da observação oposta;
- área do patch na projeção LAEA e área de atributo GEE;
- SHA-256 do GeoJSON P1, definição LAEA e contagem de reparos;
- soma individual das interseções e área de sua **união geométrica**;
- diferença `soma - união` (área contada mais de uma vez);
- excesso `soma - área_patch` (área que viola a invariante);
- ranks, áreas, indicadores de reparo e até 30 exemplos de pares
  de interseções que se sobrepõem, além do número total de pares.

**Interpretação:** se `soma > união` acima do limiar, há área repetida
entre as interseções com os patches do outro dia. Isso fornece evidência
de dupla contagem geométrica no plano projetado, mas **não demonstra
automaticamente** a causa (fonte GEE, reparo após projeção, sobreposição
original ou outra discrepância).

## Como reproduzir sem baixar novamente do GEE

Usar o **P1 já existente** no computador, não executar nova aquisição.
A etapa 3 aceita diretamente um caminho do GeoJSON P1:

```powershell
python -m burngeoflow.processamento.linhagens "CAMINHO_DO_P1_COMPONENTES_24194371.geojson" --saida "diagnosticos/24194371"
```

Se a falha acontecer, o erro continuará aparecendo, mas o JSON será
gravado na pasta `diagnosticos/24194371/`. O comando pode exigir
processamento vetorial considerável para as 30.795 feições, mas **não
cria tasks remotas no Earth Engine**.

O arquivo serve para confrontar (i) interseções isoladas, (ii) união
sem dupla contagem, (iii) sobreposições de feições P1 da mesma data,
(iv) Geometrias WGS84 originais e (v) dados de regularização e reparos
já registrados. A correção definitiva só deve ocorrer após essa
classificação e testes de regressão para os dois IDs de desenvolvimento.

## Cobertura automatizada

`tests/test_diagnostico_linhagens.py` inclui:

- dois sucessores espacialmente sobrepostos;
- dois antecessores espacialmente sobrepostos;
- sucessores disjuntos, em que união = soma;
- diferença numérica pequena que não deve ser tratada como falha;
- persistência de JSON e preservação do SHA-256 P1 em erro.

Não usa rede, GEE, nem os 30.795 polígonos privados do evento real.

## Próximo passo ainda pendente

Executar o diagnóstico com os arquivos reais de 24194371 e registrar
as medidas de 10/09/2020 rank 97, a data sucessora, os patches e
a comparação com a auditoria espacial. Só então decidir a estratégia
de correção e repetir as análises, preservando os produtos antigos.
