# Ensaio não destrutivo: partição de faces do P1 (D-013/D-014)

**Situação:** módulo experimental em `burngeoflow/validacao/particao_faces_experimental.py`. Não participa de P1/P2 oficial, de `linhagens`, de TR/IGT nem da aquisição. Testes sintéticos em `tests/test_particao_faces_experimental.py`.

## Problema documentado

No ID **24194371**, observação de 10/09/2020 rank 97 e sucessores de 11/09 ranks **3 e 83**, foi medida sobreposição de aproximadamente **1,190236657 m²** nos polígonos exportados, antes das transformações e reparos locais. A soma das áreas de interseção supera a área do antecessor. O P1 bruto do GEE já incorpora operações de geração de componentes; essa evidência NÃO determina se a sobreposição surgiu em DailyPerimeters ou durante a agregação remota. Ver `docs/ESTADO_EXECUCAO.md` e PR #51.

Uma segunda classe de problema, distinta, é a **autointerseção induzida pela reprojeção de vértices para LAEA e união por cordas retas**. A densificação adaptativa foi testada em cópias, mas não existe um orçamento de erro nem teste global de preservação da rede de nós e arestas compartilhadas.

## O que o ensaio calcula

Dado um **pequeno subconjunto focal** de polígonos válidos no MESMO CRS métrico:

1. Forma a rede de contornos e seus nós de cruzamento (`unary_union` das bordas), sem buffer, snap ou arredondamento.
2. Polygoniza as faces planas.
3. Para cada face de área positiva, registra todos os ranks cujas geometrias a cobrem. `ranks_cobertura` NÃO significa escolha de um único dono.
4. Mede:
   - soma das áreas originais `S = Σ A_i`;
   - área da união geométrica `U = A(∪ G_i)`;
   - área de faces exclusivas ou com cobertura múltipla;
   - área contada repetidamente `D = Σ_faces (multiplicidade − 1) × área`;
   - resíduos `R1 = Σ_faces área − U` e `R2 = (Σ_faces área + D) − S`.
5. Opcionalmente devolve geometrias das faces em GeoJSON (modo diagnóstico), sem gravar ou sobrescrever dados científicos.

**Relação esperada:** `S ≈ U + D`, com resíduos numéricos reportados tal como medidos, sem aceitar automaticamente uma tolerância.

Uma face coberta por ranks 3 e 83 entra **uma vez** em `U`, **duas vezes** em `S` e **uma vez** em `D`. Nenhuma política de atribuição exclusiva está implementada.

## Exemplo sintético e escopo dos testes

Dois quadrados 4 × 4 m deslocados 2 m têm áreas de 16 + 16 = 32 m², união de 24 m² e face compartilhada de 8 m². São reportadas três faces e duplicação de 8 m². Outros testes cobrem tripla sobreposição, contato apenas por vértice, contato por aresta, um polígono com buraco, imutabilidade de WKB e rejeição de insumos inválidos.

**Esses números são apenas testes sintéticos**, não medem ou substituem o dado real de 1,190237 m². Um ensaio de faces baseado em polígonos LAEA exige geometrias válidas; não aplica `make_valid` implicitamente.

## Riscos técnicos ainda não resolvidos

- A planarização por GEOS pode criar muitos nós/faces; avaliar memória e tempo no recorte mínimo antes de tentar o evento completo. Este módulo não é pipeline de processamento em massa.
- Contatos por vértice/aresta não são faces compartilhadas de área positiva. A conectividade D-002 permanece como contrato separado.
- `polygonize` e `unary_union` operam em coordenadas já projetadas. Não corrigem erros ou autointerseções que surgiram **antes** da partição.
- Uma tolerância numérica aferida para fechamento de área não pode ser reaproveitada como tolerância espacial de distância ou como regra para conectar polígonos.
- Nós correspondentes e segmentos parcialmente coincidentes precisam ser discretizados de maneira conjunta se houver densificação, para não produzir fissuras ou contatos fictícios.
- Não há limite analítico demonstrado para o erro máximo entre curva transformada e corda aproximante; amostras de 1/4, 1/2 e 3/4 são observações, não prova de um limite global.

## Proposta de ensaios antes de escolher parâmetros

1. Examinar WGS84 bruto, LAEA por cordas, densificação com nós compartilhados e partição final para **a mesma amostra**, sem misturar métodos.
2. Medir para cada feição `ΔA` e `ΔP`, áreas de diferença simétrica, número de vértices, validade e a dimensão das interseções para os mesmos pares. Quantificar criação/perda de contatos por vértice, aresta e área.
3. Medir resíduos de conservação `R1/R2`, estabilidade desses resíduos ao refinar a representação e orçamento de memória/tempo.
4. Verificar se a sequência de ranking P1, grupo por contato, arestas temporais, ancestralidade P2 e área nova/incorporada D-005 permanece estável sob os refinamentos. Não apenas a área total.
5. Definir **antes de validar** limiares quantitativos de erro por origem demonstrada (geometria, precisão numérica e interpretação científica), separando distância, área, topologia e desempates. Não usar a resolução nominal MODIS de ~500 m como tolerância GIS.

## Escolhas que exigem aprovação científica

- **Face de cobertura múltipla:** (A) manter cobertura união como geometria derivada de P1 e rastrear ranks de origem sem atribuição exclusiva; (B) impor um particionamento atributivo exclusivo após justificar critério de propriedade; (C) outra política justificada. Nenhuma escolhida no código.
- **Referência de contorno:** interpretar cada segmento original como linha em longitude/latitude a transformar ou como arco geodésico; escolher conforme proveniência GlobFire. Densificar sem estabelecer o significado do segmento muda o objeto observado.
- **Critérios numéricos de D-013/D-014:** orçamento de erro de área e deslocamento, estabilidade de contatos/nós, limites de alteração aceitável por reparo, política de rejeição e critérios para empate residual de P2.

O experimento NÃO modifica a metodologia nem torna o reprocessamento dos dois IDs cientificamente liberado.

## Uso mínimo como biblioteca de diagnóstico

```python
from shapely.geometry import box
from burngeoflow.validacao.particao_faces_experimental import auditar_faces

a = box(0, 0, 4, 4)  # CRS métrico de teste
b = box(2, 0, 6, 4)
auditoria = auditar_faces([(3, a), (83, b)], com_geometrias=False)
assert auditoria["area_uniao_m2"] == 24
assert auditoria["area_contada_repetidamente_m2"] == 8
```

**Observação:** o arquivo GeoJSON P1 real não é carregado automaticamente; é necessário preparar as geometrias válidas e o CRS métrico de referência, e confirmar hashes/proveniência antes de comparar áreas. Não publicar um diagnóstico real sem os insumos efetivamente examinados.
