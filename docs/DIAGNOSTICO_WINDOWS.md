# Diagnóstico e mitigação de travamentos no Windows

## Sintomas investigados

No primeiro teste local em 12/11/2026:

- Visual Studio Code informou `oom` e fechou uma janela.
- Edge/Chrome registrou `ERR_INSUFFICIENT_RESOURCES` e erros
  secundários de JavaScript e extensões.
- O Uvicorn respondeu `200` ao HTML, bundle JS e CSS.
- O `404` para favicon não explica o travamento.
- A exceção `ConnectionResetError [WinError 10054]` pode ocorrer
  quando o cliente aborta uma conexão; isoladamente, não prova falha do servidor.

**Diagnóstico limitado:** não temos heap snapshots, quantidade de RAM
disponível, tamanho do arquivo real por data ou perfil da GPU. Não concluir
que somente MapLibre, Python ou extensões são culpados.

## Mitigação nesta versão

1. React não importa MapLibre/WebGL no carregamento inicial.
2. O mapa e os GeoJSONs são buscados **somente** após clicar em
   **Abrir mapa do evento**. Métricas e séries são carregadas à parte.
3. Ao sair do mapa, o componente MapLibre é desmontado e a interface
   descarta as geometrias correntes.
4. O cache no navegador foi reduzido de 12 para 4 pares data/camada.
5. MapLibre v6 agora recebe a URL de seu worker **explicitamente** via Vite,
   conforme documentação do projeto.
6. O build valida um orçamento para o bundle de entrada e a existência de
   um chunk cartográfico separado.

A geometria de cada data **não foi reduzida ou simplificada** nesta correção.
Os produtos geoespaciais e as análises científicas não sofrem alterações.

## Procedimento de homologação

Com o programa e seus resultados já instalados:

```powershell
git pull origin main
cd frontend
npm ci
npm run build
npm run check:bundle
cd ..
python iniciar_burngeoflow.py
```

Abra primeiro <http://127.0.0.1:8000/api/health> e depois
<http://127.0.0.1:8000>. A página deve mostrar o painel de indicadores
sem criar um mapa WebGL antes do clique. Se funcionar, teste
**Abrir mapa do evento** e a navegação temporal.

Em caso de falha:

- Feche abas e apps pesados e monitore RAM pelo Gerenciador de Tarefas.
- Teste numa janela InPrivate sem extensões ativadas, para distinguir
  interferências de complementos.
- Registre qual das duas etapas falhou: página inicial **sem mapa** ou
  mapa após ativação.
- Abra DevTools > Rede e verifique o primeiro recurso com erro, seu URL,
  status e tamanho. Se for uma consulta geográfica, anote data e camada.
- Não apague `execucoes/` nem os arquivos P1/P2. Não execute
  novamente o GEE só para tentar corrigir um problema de interface.

Em versão futura, se o mapa por data ainda exceder a memória do browser,
usar visualização derivada em tiles ou simplificação **exclusivamente para
exibição**, preservando o GeoJSON original para download e análise.

Referência oficial: https://maplibre.org/maplibre-gl-js/docs/guides/large-data/
