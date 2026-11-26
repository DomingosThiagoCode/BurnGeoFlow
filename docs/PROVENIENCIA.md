# Proveniência científica

O código científico do BurnGeoFlow foi inicialmente desenvolvido no projeto
[CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio)
e migrado para um pacote Python com responsabilidades modulares.

- TR: trajetórias representativas do centroide e dos extremos N/S/L/O,
  adaptadas do método de Priscila Backes de Oliveira (IME, 2024).
- IGT: incrementos geométricos temporais por diferença de regiões;
  referência metodológica: Barbosa e Oliveira (2022).
- P1: análise das componentes de áreas queimadas acumuladas.
- P2: região principal selecionada por continuidade geométrica.
- Dados: JRC/GWIS GlobFire v2, derivados do MODIS MCD64A1.

O código original de experimentação (JavaScript GEE e SQLs PostGIS)
permanece disponível no CDG_incendio para rastreabilidade, mas não é
dependência do produto computacional.

A interpretação dos indicadores está restrita à evolução geométrica das
áreas queimadas; testes internos não equivalem à validação de campo.

## Portabilidade da aquisição

A geração Python aplica as decisões do JavaScript no CDG_incendio:
união acumulada por IDate, componentes classificados por área e P2
selecionado pela maior sobreposição com a observação anterior, com
fallback por distância. O processamento não representa movimento
físico da frente de fogo. A equivalência numérica e geométrica com
a exportação histórica requer teste autenticado, ainda não realizado.

O arquivo `aquisicao_<ID>.json` registra a assinatura da aquisição e o
caminho do diagnóstico. Em uma publicação ou revalidação local, o
`brutos_gee/diagnostico_geometrias.json` registra o SHA-256 de cada
GeoJSON bruto e, após a validação, dos produtos publicados. Esses hashes
permitem verificar os arquivos usados e comparar os produtos entre execuções.

Na aquisição GEE, o cache paginado registra a assinatura da consulta e o
token de entrada de cada página. Uma página só é gravada após a validação
da resposta, das feições, do token de saída e do limite de feições. Na
retomada, o cache é verificado novamente. Em caso de incompatibilidade
ou corrupção, a aquisição informa a página afetada e preserva o arquivo
para investigação.

## Revalidação offline de uma aquisição histórica

O manifesto legado `aquisicao_<ID>.json` registra a coleção e o ano,
a estratégia de exportação, a contagem de registros-fonte e o resumo
da validação estrutural. Ele pode ter sido gerado antes da assinatura
da aquisição e dos hashes por arquivo. Nesse caso, o manifesto permite
conferir os totais declarados, e a identidade dos arquivos históricos
depende de evidência adicional. O método
`acumulado_union__p2_overlap_e_distancia_fallback` identifica o P2
progressivo legado.

Para repetir a normalização, use os dois GeoJSON originais de
`brutos_gee/`. Guarde o manifesto, o diagnóstico histórico e os GeoJSON
publicados separadamente. A normalização extrai as partes poligonais
das coleções geométricas, audita as conversões e rejeita feições
sem partes poligonais cuja área declarada é positiva ou desconhecida.

No diretório do repositório, ajuste o ID e o caminho dos brutos:

```bash
evento=24340828
brutos_originais=/caminho/para/aquisicao/original/brutos_gee
saida=$(mktemp -d)
caso="$saida/dados/estudo_caso_$evento"
p1="P1_componentes_$evento.geojson"
p2="P2_regiao_movel_$evento.geojson"
mkdir -p "$caso/brutos_gee"
cp "$brutos_originais/$p1" "$brutos_originais/$p2" "$caso/brutos_gee/"
git rev-parse HEAD
python executar_pipeline.py --id "$evento" --origem brutos \
  --somente-aquisicao --saida "$saida"
```

O comando usa os brutos copiados e grava os GeoJSON revalidados e o
novo diagnóstico na pasta temporária. Ele se encerra após a validação
estrutural, sem autenticação GEE. Em uma execução bem-sucedida, confira
os hashes registrados de brutos e publicados com os hashes dos arquivos
da rodada:

```bash
python - "$caso" <<'PY'
from hashlib import file_digest
import json
from pathlib import Path
import sys

caso = Path(sys.argv[1])
brutos = caso / "brutos_gee"
diagnostico = json.loads((brutos / "diagnostico_geometrias.json").read_text())
for grupo, pasta in (("geojsons_brutos", brutos), ("geojsons_publicados", caso)):
    for item in diagnostico[grupo].values():
        with (pasta / item["arquivo"]).open("rb") as arquivo:
            atual = file_digest(arquivo, "sha256").hexdigest()
        if atual != item["sha256"]:
            raise SystemExit(f"SHA-256 divergente em {grupo}/{item['arquivo']}")
        print(f"{atual}  {grupo}/{item['arquivo']}")
PY
```

Compare os hashes dos publicados com os da entrega histórica. Se os
bytes divergirem, compare por data e rank as propriedades, a validade
geométrica e as diferenças espaciais. Use o diagnóstico histórico para
rastrear conversões e exclusões. A revalidação confirma o processamento
dos brutos disponíveis com o código atual. A equivalência com a
aquisição histórica exige conferir a origem dos brutos e as diferenças
observadas.
