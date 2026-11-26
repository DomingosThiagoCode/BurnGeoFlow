# Landing narrativa: O território depois do fogo

**Escopo:** primeira versão integrada, no endereço \`/apresentacao/\`. O atlas científico permanece na raiz \`/\`; nenhuma API ou operação de análise foi alterada.

## Direção de arte

Publicação cartográfica contemporânea: papel mineral, pinho, tinta escura e vermelho-terra. O mapa ocupa uma área contínua e aderente à rolagem. Marcas de coordenadas, grade de leitura, relógio e legenda são elementos de navegação científica, não um mapa de relevo inventado. Tipografia Georgia/Palatino para títulos e Aptos/Segoe UI para dados. Sem fotos genéricas de incêndios e sem dependências externas de fonte.

## Storyboard

| Cena | Pergunta narrativa | Visualização e movimento |
| --- | --- | --- |
| 1 Território | Como observar transformação no tempo? | Base cartográfica estilizada, sem polígonos |
| 2 Primeiro registro | O que o satélite mapeou primeiro? | Primeiro estado P1, 09/08/2020 |
| 3 Expansão | Como surgem e se conectam manchas? | Rolagem percorre 57 estados reais do P1 |
| 4 Componentes | Por que área total não basta? | P1 acumulado, contornos de patches |
| 5 Região móvel | Como acompanhar um componente? | P2 em cor distinta e P1 contextual |
| 6 Trajetórias | Como centroide e extremos mudam? | Cinco trajetórias originais, desenhadas progressivamente |
| 7 Incrementos | Toda mudança é queima nova? | Diferenças geométricas entre observações, sem assumir frente física |
| 8 Plataforma | Como investigar em profundidade? | Acesso à aplicação científica e seis abas reais |

As cenas 3, 6 e 7 são controladas continuamente pelo scroll; o conteúdo visual pode retroceder. O botão de reprodução oferece navegação temporal automatizada independente do scroll. O botão de pular conduz à cena 8. Em \`prefers-reduced-motion\`, o autoplay é desabilitado e as transições CSS são instantâneas.

## Dados, proveniência e limitações

- **Fonte:** arquivos P1/P2 do caso 24340828 no repositório [CDG_incendio](https://github.com/DomingosThiagoCode/CDG_incendio/tree/main/dados/estudo_caso_24340828), com origens JRC/GWIS GlobFire v2 e MODIS MCD64A1.
- **57 observações:** de 2020-08-09 a 2020-10-09. O P1 original possui 978 registros de patches nas 57 datas e o P2 possui 57 registros.
- **Trajetórias:** posições de centroide/N/S/L/O obtidas do arquivo \`resultados/etapa4/pontos_representativos_24340828.csv\`, não inventadas no frontend.
- **Incrementos:** geometrias derivadas de \`resultados/etapa4/geometrias_incrementos_24340828.geojson\`.
- **Arquivo de entrega:** \`frontend/public/story/24340828.json\`. Coordenadas geográficas foram transformadas para um referencial planar estilizado SVG e simplificadas com tolerância de 0,75 unidades de desenho para **exibição apenas**. Os arquivos científicos originais não foram alterados. Área e número de componentes são atributos dos dados originais, nunca recalculados sobre o SVG simplificado.
- **Atenção:** a animação não representa propagação observada de fogo ativo nem interpola datas ou geometria entre observações. O valor IGT não deve ser confundido com toda a área nova queimada.
- **Projeção:** aproximação equiretangular local para apresentação visual, com compensação de longitude pelo cosseno da latitude central. Não é apropriada para medições, operações geodésicas nem mapas científicos de precisão.

## Arquitetura e integração

A entrada HTML \`frontend/apresentacao/index.html\` é incluída no build Vite multipágina, sem trocar \`frontend/index.html\` ou \`src/App.tsx\`. A API FastAPI já monta a distribuição estática, servindo \`/apresentacao/\` como subdiretório HTML.

Arquivos principais:

\`\`\`
frontend/
  apresentacao/index.html           # entrada separada
  src/story/main.tsx                # React boot
  src/story/StoryPage.tsx           # cenas, scroll e mapa SVG
  src/story/story.css               # CSS isolado
  public/story/24340828.json       # geometrias e métricas derivadas
  tests/story.test.mjs              # contrato do dataset narrativo
\`\`\`

Não foram adicionadas dependências JavaScript. O MapLibre da aplicação científica continua carregado sob demanda, sem duplicação na apresentação. O JSON histórico estático evita requisições GEE durante a navegação.

## Executar e validar

Na pasta \`frontend\`:

\`\`\`sh
npm ci
npm run test
npm run build
\`\`\`

Em modo de desenvolvimento, \`npm run dev\` e abrir \`http://127.0.0.1:5173/apresentacao/\`. Com o FastAPI e o build publicados, \`http://127.0.0.1:8000/apresentacao/\`.

Validar no navegador: rolagem em ambos os sentidos, pausa/reprodução e botão de pular, cor e legendas de P1/P2/TR/IGT, leitura em celular, redução de movimento e retorno a \`/\`.

## Próximas melhorias opcionais

- Thumbnail real da interface científica na última cena, sem apresentar um mockup como captura;
- disponibilidade offline e chunking por intervalos se a telemetria real indicar lentidão;
- testar taxas de FPS/CLS no hardware-alvo;
- caso a landing seja aprovada como página principal, inverter os endereços em uma mudança de roteamento separada e testada.
