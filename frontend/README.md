# Frontend BurnGeoFlow

Aplicação responsiva em React + TypeScript + Vite, independente da
renderização Python. Mapa MapLibre GL JS, gráficos leves em SVG e API FastAPI
por data/camada.

## Pré-requisitos

- Node.js 24 (ou versão compatível com Vite 8).
- API FastAPI em `http://127.0.0.1:8000`. Consulte [docs/API.md](../docs/API.md).
- P1/P2 de pelo menos um evento na pasta `execucoes/<ID>/`.

## Iniciar

Terminal 1, raiz do repositório:

```powershell
python -m pip install -r requirements-api.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, pasta frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Abra <http://127.0.0.1:5173>. O frontend não faz cálculos GEE
diretamente: a API inicia a CLI existente em um processo separado.

Para processar outro ID, expanda **Processar e acompanhar eventos**, informe
ID, origem e, quando útil, ano. Clique em **Executar**. Acompanhe o estado
em SQLite e as mensagens no painel de logs. Quando terminar com sucesso, a
interface atualiza a lista e reabre os resultados. A autenticação GEE deve
estar previamente configurada no computador.

A CLI manual permanece disponível:

```powershell
python executar_pipeline.py --id 24340828 --origem gee --ano 2020
```

Uma única execução ativa por vez evita concorrência excessiva no sistema.

Configuração: copie .env.example para .env.local se precisar alterar a
origem da API; a variável `VITE_API_BASE_URL` é pública e contém somente
o endereço local, nunca credenciais.

## Recursos

- Seleção de evento e ID manual.
- Processamento por ID/origem com estado e logs via API, sem duplicar CLI.
- Slider temporal com anterior/próxima data e reprodução.
- Mapa com P1/P2, camadas independentes e opção de mapa-base OSM.
- Indicadores da observação e da transição, gráficos sem re-renderização
  da página pelo servidor, tabela dos primeiros 100 patches.
- Exportação GeoJSON do dia e série CSV, alertas de qualidade.
- Cache de até 12 combinações (data,camada) no browser e cancelamento
  de solicitações antigas para evitar exibir a data errada.
- Navegação móvel: menu recolhível e cards responsivos.

Os GeoJSONs não são simplificados nem alterados. A primeira indexação
da API pode demorar mais; as próximas consultas leem somente a data
selecionada. Ainda é necessário testar a fluidez no computador Windows do
usuário, com seus dados reais e placas gráficas reais.

O OpenStreetMap é somente mapa-base. As geometrias/indicadores locais
continuam disponíveis sem conexão externa; tiles podem faltar offline.

## Desenvolvimento e qualidade

```powershell
npm ci
npm run test
npm run build
```

O CI executa testes de utilitários, verificação TypeScript e build Vite.
A paridade visual no navegador requer teste manual nesta entrega;
smoke tests Playwright podem ser acrescentados se o uso justificar.
