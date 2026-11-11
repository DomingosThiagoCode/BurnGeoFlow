// ============================================================================
// ============================================================================
//
// PROJETO FOGO
// GLOBFIRE v2 - DAILY PERIMETERS
//
// ANÁLISE AUTOMÁTICA DE COMPONENTES + REGIÃO MÓVEL
//
// FUNCIONAMENTO:
//
// 1. Escolhe um incêndio apenas pelo ID.
// 2. Descobre automaticamente todas as datas.
// 3. Constrói a área queimada acumulada.
// 4. Separa TODOS os componentes desconectados em cada data.
// 5. Ordena os componentes por área.
// 6. Escolhe a região móvel uma única vez na primeira data.
// 7. Nas datas seguintes, rastreia a RM por continuidade espacial.
// 8. Permite qualquer número N de componentes.
// 9. Fusões são incorporadas automaticamente.
// 10. Detecta automaticamente o maior salto da RM.
// 11. Mostra antes / salto / depois.
// 12. Gera gráficos.
// 13. Prepara dois produtos:
//
//     P1 = todos os componentes em todas as datas
//     P2 = região móvel rastreada
//
// ============================================================================
// ============================================================================

// ============================================================================
// 0. CONFIGURAÇÃO
//
// >>>>> PARA TROCAR O INCÊNDIO, MEXA APENAS AQUI <<<<<
// ============================================================================

var anoDataset = 2020;

var idIncendio = 24340828;

// Precisão utilizada nas operações geométricas.
// 100 metros é a mesma ordem utilizada no código anterior.

var maxErro = 100;

// Zoom inicial do mapa.

var zoomMapa = 8;

// ============================================================================
// 1. CARREGAR GLOBFIRE
// ============================================================================

var datasetId = "JRC/GWIS/GlobFire/v2/DailyPerimeters/" + anoDataset;

var globfire = ee.FeatureCollection(datasetId);

print("Dataset:", datasetId);

// ============================================================================
// 2. FILTRAR O INCÊNDIO
// ============================================================================

var evento = globfire.filter(ee.Filter.eq("Id", idIncendio));

print("========================================");

print("ID DO INCÊNDIO:", idIncendio);

print("Quantidade de registros:", evento.size());

print("========================================");

// IMPORTANTE:
//
// Se "Quantidade de registros" aparecer como 0,
// confira:
//
// 1. o ID;
// 2. o anoDataset;

// ============================================================================
// 3. LISTA AUTOMÁTICA DE DATAS
// ============================================================================

var datas = ee.List(evento.aggregate_array("IDate")).distinct().sort();

print("Número de datas:", datas.size());

print(
  "Datas:",
  datas.map(function (d) {
    return ee.Date(ee.Number(d)).format("YYYY-MM-dd");
  }),
);

// ============================================================================
// 4. PRIMEIRA E ÚLTIMA DATA
// ============================================================================

var primeiraData = ee.Number(datas.get(0));

var ultimaData = ee.Number(datas.get(datas.size().subtract(1)));

print("Primeira data:", ee.Date(primeiraData).format("YYYY-MM-dd"));

print("Última data:", ee.Date(ultimaData).format("YYYY-MM-dd"));

// ============================================================================
// 5. FUNÇÃO: GEOMETRIA QUE SURGIU EM UMA DATA
// ============================================================================
//
// Pega somente os registros GlobFire associados àquela data.
//
// Isso NÃO é ainda a área acumulada.
//
// ============================================================================

function geometriaDaData(dataAtual) {
  dataAtual = ee.Number(dataAtual);

  var registrosDia = evento.filter(ee.Filter.eq("IDate", dataAtual));

  var geomDia = registrosDia.geometry().dissolve(maxErro);

  return geomDia;
}

// ============================================================================
// 6. FUNÇÃO: SEPARAR N COMPONENTES DE UMA GEOMETRIA ACUMULADA
// ============================================================================
//
// Entrada:
//
// geometria acumulada até uma determinada data.
//
// Saída:
//
// FeatureCollection contendo:
//
// - componente 1
// - componente 2
// - ...
// - componente N
//
// Cada componente recebe:
//
// data
// rank
// área
// área total
// número de componentes
// proporção da área total
//
// rank = 1 significa maior componente.
//
// ============================================================================

function componentesDaGeometria(geomAcumulada, dataAtual) {
  dataAtual = ee.Number(dataAtual);

  geomAcumulada = ee.Geometry(geomAcumulada);

  // ------------------------------------------------------------------------
  // Extrair os polígonos desconectados
  // ------------------------------------------------------------------------

  var listaGeometrias = geomAcumulada.geometries();

  // ------------------------------------------------------------------------
  // Transformar cada geometria em Feature
  // ------------------------------------------------------------------------

  var componentes = ee.FeatureCollection(
    listaGeometrias.map(function (g) {
      var geom = ee.Geometry(g);

      var areaKm2 = geom.area(maxErro).divide(1e6);

      return ee.Feature(
        geom,

        {
          id_incendio: idIncendio,

          ano_dataset: anoDataset,

          data_millis: dataAtual,

          data: ee.Date(dataAtual).format("YYYY-MM-dd"),

          area_km2: areaKm2,
        },
      );
    }),
  );

  // ------------------------------------------------------------------------
  // Ordenar do maior para o menor
  // ------------------------------------------------------------------------

  componentes = componentes.sort("area_km2", false);

  var numeroComponentes = componentes.size();

  var lista = componentes.toList(numeroComponentes);

  // ------------------------------------------------------------------------
  // Criar os ranks
  // ------------------------------------------------------------------------

  var indices = ee.List.sequence(0, numeroComponentes.subtract(1));

  var componentesRank = ee.FeatureCollection(
    indices.map(function (i) {
      i = ee.Number(i);

      var f = ee.Feature(lista.get(i));

      return f.set({
        rank: i.add(1),

        eh_maior: i.eq(0),
      });
    }),
  );

  // ------------------------------------------------------------------------
  // Área total acumulada
  // ------------------------------------------------------------------------

  var areaTotal = ee.Number(componentesRank.aggregate_sum("area_km2"));

  // ------------------------------------------------------------------------
  // Colocar metadados em todos os componentes
  // ------------------------------------------------------------------------

  componentesRank = componentesRank.map(function (f) {
    f = ee.Feature(f);

    var area = ee.Number(f.get("area_km2"));

    var proporcao = area.divide(areaTotal).multiply(100);

    return f.set({
      numero_componentes: numeroComponentes,

      area_total_km2: areaTotal,

      proporcao_area_pct: proporcao,
    });
  });

  return componentesRank;
}

// ============================================================================
// 7. CONSTRUIR PRIMEIRO ESTADO DO INCÊNDIO
// ============================================================================
//
// Na primeira data:
//
// acumulado = apenas o que existe na primeira data.
//
// ============================================================================

var geometriaAcumuladaInicial = geometriaDaData(primeiraData);

var componentesPrimeiraData = componentesDaGeometria(
  geometriaAcumuladaInicial,

  primeiraData,
);

print("Componentes iniciais:", componentesPrimeiraData);

print("Número de componentes iniciais:", componentesPrimeiraData.size());

// ============================================================================
// 8. ESCOLHER A REGIÃO MÓVEL INICIAL
// ============================================================================
//
// Esta é a ÚNICA VEZ em que usamos:
//
// "o maior componente é a RM"
//
// Depois disso, o rank NÃO define mais a identidade.
//
// ============================================================================

var rmInicialBase = ee.Feature(
  componentesPrimeiraData.filter(ee.Filter.eq("rank", 1)).first(),
);

var areaInicial = ee.Number(rmInicialBase.get("area_km2"));

var areaTotalInicial = ee.Number(rmInicialBase.get("area_total_km2"));

var numeroComponentesInicial = ee.Number(
  rmInicialBase.get("numero_componentes"),
);

var rmInicial = rmInicialBase.set({
  ordem_temporal: 1,

  rank_global: 1,

  metodo_continuidade: "inicial_maior_area",

  overlap_prev_km2: 0,

  overlap_prev_pct: 0,

  overlap_candidato_pct: 0,

  distancia_prev_m: 0,

  delta_area_km2: 0,

  delta_area_pct: 0,

  delta_area_total_km2: 0,

  delta_num_componentes: 0,

  rm_eh_maior: true,

  proporcao_rm_pct: areaInicial.divide(areaTotalInicial).multiply(100),
});

print("Área da RM inicial (km²):", areaInicial);

// ============================================================================
// 9. DATAS RESTANTES
// ============================================================================

var datasRestantes = datas.slice(1);

// ============================================================================
// 10. ESTADO INICIAL DO PROCESSAMENTO
// ============================================================================
//
// O iterate carregará:
//
// geom_acumulada
// geom_rm_anterior
// área da RM anterior
// área total anterior
// número de componentes anterior
// lista de todas as RMs
// lista de todos os componentes
//
// ============================================================================

var estadoInicial = ee.Dictionary({
  geom_acumulada: geometriaAcumuladaInicial,

  geom_rm_anterior: rmInicial.geometry(),

  area_rm_anterior: areaInicial,

  area_total_anterior: areaTotalInicial,

  numero_componentes_anterior: numeroComponentesInicial,

  lista_rm: ee.List([rmInicial]),

  lista_componentes: componentesPrimeiraData.toList(
    componentesPrimeiraData.size(),
  ),
});

// ============================================================================
// 11. PROCESSAMENTO TEMPORAL
// ============================================================================
//
// Para cada nova data:
//
// A. pega somente a área nova daquela data;
// B. une com o acumulado anterior;
// C. separa todos os N componentes;
// D. compara cada componente com a RM anterior;
// E. mede sobreposição;
// F. escolhe o componente de maior continuidade;
// G. guarda a nova RM;
// H. guarda todos os componentes.
//
// ============================================================================

var estadoFinal = ee.Dictionary(
  datasRestantes.iterate(
    function (dataAtual, estado) {
      dataAtual = ee.Number(dataAtual);

      estado = ee.Dictionary(estado);

      // ==================================================================
      // A. ESTADO ANTERIOR
      // ==================================================================

      var geomAcumuladaAnterior = ee.Geometry(estado.get("geom_acumulada"));

      var geomRMAnterior = ee.Geometry(estado.get("geom_rm_anterior"));

      var areaRMAnterior = ee.Number(estado.get("area_rm_anterior"));

      var areaTotalAnterior = ee.Number(estado.get("area_total_anterior"));

      var numeroComponentesAnterior = ee.Number(
        estado.get("numero_componentes_anterior"),
      );

      // ==================================================================
      // B. GEOMETRIA NOVA DA DATA
      // ==================================================================

      var geomNova = geometriaDaData(dataAtual);

      // ==================================================================
      // C. ATUALIZAR A ÁREA ACUMULADA
      // ==================================================================
      //
      // Em vez de recalcular tudo desde o primeiro dia:
      //
      // acumulado(t) =
      // acumulado(t-1) U novo(t)
      //
      // ==================================================================

      var geomAcumuladaAtual = geomAcumuladaAnterior.union(geomNova, maxErro);

      // ==================================================================
      // D. SEPARAR TODOS OS COMPONENTES
      // ==================================================================

      var componentes = componentesDaGeometria(
        geomAcumuladaAtual,

        dataAtual,
      );

      var numeroComponentes = componentes.size();

      var areaTotal = ee.Number(componentes.aggregate_sum("area_km2"));

      // ==================================================================
      // E. COMPARAR TODOS OS N COMPONENTES COM A RM ANTERIOR
      // ==================================================================

      var candidatos = componentes.map(function (f) {
        f = ee.Feature(f);

        // ------------------------------------------------------------
        // INTERSEÇÃO COM A RM ANTERIOR
        // ------------------------------------------------------------

        var geomIntersecao = f.geometry().intersection(
          geomRMAnterior,

          maxErro,
        );

        var areaOverlap = geomIntersecao.area(maxErro).divide(1e6);

        // ------------------------------------------------------------
        // % da RM anterior ainda contida neste candidato
        // ------------------------------------------------------------

        var overlapPrevPct = ee.Number(
          ee.Algorithms.If(
            areaRMAnterior.gt(0),

            areaOverlap.divide(areaRMAnterior).multiply(100),

            0,
          ),
        );

        // ------------------------------------------------------------
        // % do candidato explicado pela RM anterior
        // ------------------------------------------------------------

        var areaCandidato = ee.Number(f.get("area_km2"));

        var overlapCandidatoPct = ee.Number(
          ee.Algorithms.If(
            areaCandidato.gt(0),

            areaOverlap.divide(areaCandidato).multiply(100),

            0,
          ),
        );

        // ------------------------------------------------------------
        // Distância
        //
        // Só será usada como fallback.
        // ------------------------------------------------------------

        var distancia = f.geometry().distance(
          geomRMAnterior,

          maxErro,
        );

        return f.set({
          overlap_prev_km2: areaOverlap,

          overlap_prev_pct: overlapPrevPct,

          overlap_candidato_pct: overlapCandidatoPct,

          distancia_prev_m: distancia,
        });
      });

      // ==================================================================
      // F. DESCOBRIR O MELHOR CANDIDATO
      // ==================================================================

      var maxOverlap = ee.Number(candidatos.aggregate_max("overlap_prev_km2"));

      // Maior sobreposição espacial.

      var melhorOverlap = candidatos.sort("overlap_prev_km2", false).first();

      // Componente espacialmente mais próximo.

      var maisProximo = candidatos.sort("distancia_prev_m", true).first();

      // ==================================================================
      // G. ESCOLHA DA REGIÃO MÓVEL
      // ==================================================================
      //
      // Regra principal:
      //
      // maior sobreposição com RM(t-1)
      //
      // Se não existir sobreposição:
      //
      // componente mais próximo
      //
      // ==================================================================

      var escolhido = ee.Feature(
        ee.Algorithms.If(
          maxOverlap.gt(0),

          melhorOverlap,

          maisProximo,
        ),
      );

      var metodo = ee.String(
        ee.Algorithms.If(
          maxOverlap.gt(0),

          "sobreposicao",

          "distancia_fallback",
        ),
      );

      // ==================================================================
      // H. MÉTRICAS DA RM ATUAL
      // ==================================================================

      var areaAtual = ee.Number(escolhido.get("area_km2"));

      var rankAtual = ee.Number(escolhido.get("rank"));

      // Crescimento da RM.

      var deltaArea = areaAtual.subtract(areaRMAnterior);

      // Crescimento percentual.

      var deltaAreaPct = ee.Number(
        ee.Algorithms.If(
          areaRMAnterior.gt(0),

          deltaArea.divide(areaRMAnterior).multiply(100),

          0,
        ),
      );

      // Crescimento do incêndio inteiro.

      var deltaAreaTotal = areaTotal.subtract(areaTotalAnterior);

      // Mudança no número de componentes.

      var deltaNumeroComponentes = ee
        .Number(numeroComponentes)
        .subtract(numeroComponentesAnterior);

      var proporcaoRM = areaAtual.divide(areaTotal).multiply(100);

      var ordemTemporal = ee.Number(datas.indexOf(dataAtual)).add(1);

      // ==================================================================
      // I. FEATURE FINAL DA RM
      // ==================================================================

      var rmAtual = escolhido.set({
        ordem_temporal: ordemTemporal,

        rank_global: rankAtual,

        metodo_continuidade: metodo,

        delta_area_km2: deltaArea,

        delta_area_pct: deltaAreaPct,

        delta_area_total_km2: deltaAreaTotal,

        delta_num_componentes: deltaNumeroComponentes,

        rm_eh_maior: rankAtual.eq(1),

        proporcao_rm_pct: proporcaoRM,
      });

      // ==================================================================
      // J. ATUALIZAR LISTA DE RMS
      // ==================================================================

      var listaRMAnterior = ee.List(estado.get("lista_rm"));

      var listaRMNova = listaRMAnterior.add(rmAtual);

      // ==================================================================
      // K. ATUALIZAR LISTA DE TODOS OS COMPONENTES
      // ==================================================================

      var listaComponentesAnterior = ee.List(estado.get("lista_componentes"));

      var listaComponentesNova = listaComponentesAnterior.cat(
        componentes.toList(componentes.size()),
      );

      // ==================================================================
      // L. NOVO ESTADO
      // ==================================================================

      return ee.Dictionary({
        geom_acumulada: geomAcumuladaAtual,

        geom_rm_anterior: rmAtual.geometry(),

        area_rm_anterior: areaAtual,

        area_total_anterior: areaTotal,

        numero_componentes_anterior: numeroComponentes,

        lista_rm: listaRMNova,

        lista_componentes: listaComponentesNova,
      });
    },

    estadoInicial,
  ),
);

// ============================================================================
// ============================================================================
// 12. PRODUTOS FINAIS
// ============================================================================
// ============================================================================

// ============================================================================
// PRODUTO 1
//
// TODOS OS COMPONENTES
// EM TODAS AS DATAS
// ============================================================================

var produto1_componentes = ee
  .FeatureCollection(ee.List(estadoFinal.get("lista_componentes")))
  .sort("data_millis");

// ============================================================================
// PRODUTO 2
//
// SOMENTE A REGIÃO MÓVEL
// RASTREADA POR CONTINUIDADE ESPACIAL
// ============================================================================

var produto2_regiaoMovel = ee
  .FeatureCollection(ee.List(estadoFinal.get("lista_rm")))
  .sort("data_millis");

// ============================================================================
// 13. CRIAR TABELAS LEVES PARA O CONSOLE
// ============================================================================
//
// Não mandamos todas as geometrias gigantes para o Console.
//
// Isso ajuda bastante a evitar:
//
// Earth Engine memory capacity exceeded.
//
// ============================================================================

function removerGeometria(colecao, campos) {
  return colecao.map(function (f) {
    f = ee.Feature(f);

    return ee.Feature(
      null,

      f.toDictionary(campos),
    );
  });
}

// ============================================================================
// CAMPOS DO PRODUTO 1
// ============================================================================

var camposP1 = [
  "id_incendio",

  "data",

  "data_millis",

  "rank",

  "eh_maior",

  "area_km2",

  "numero_componentes",

  "area_total_km2",

  "proporcao_area_pct",
];

// ============================================================================
// CAMPOS DO PRODUTO 2
// ============================================================================

var camposP2 = [
  "id_incendio",

  "data",

  "data_millis",

  "ordem_temporal",

  "area_km2",

  "area_total_km2",

  "proporcao_rm_pct",

  "numero_componentes",

  "rank_global",

  "rm_eh_maior",

  "overlap_prev_km2",

  "overlap_prev_pct",

  "overlap_candidato_pct",

  "distancia_prev_m",

  "delta_area_km2",

  "delta_area_pct",

  "delta_area_total_km2",

  "delta_num_componentes",

  "metodo_continuidade",
];

// ============================================================================
// TABELAS SEM GEOMETRIA
// ============================================================================

var tabelaP1 = removerGeometria(
  produto1_componentes,

  camposP1,
);

var tabelaP2 = removerGeometria(
  produto2_regiaoMovel,

  camposP2,
);

// ============================================================================
// 14. INFORMAÇÕES DOS PRODUTOS
// ============================================================================

print("========================================");

print("PRODUTO 1 - TODOS OS COMPONENTES");

print("Número total de componentes-tempo:", produto1_componentes.size());

print("Primeiros 20 registros:", tabelaP1.limit(20));

print("========================================");

print("PRODUTO 2 - REGIÃO MÓVEL");

print("Número de posições da RM:", produto2_regiaoMovel.size());

print("Tabela da RM:", tabelaP2);

print("========================================");

// ============================================================================
// ============================================================================
// 15. DETECÇÃO AUTOMÁTICA DO MAIOR SALTO
// ============================================================================
// ============================================================================
//
// NÃO existe:
//
// var dataCentral = ...
//
// O código procura sozinho.
//
// Salto:
//
// ΔA(t) = Área_RM(t) - Área_RM(t-1)
//
// Selecionamos o maior ΔA.
//
// ============================================================================

// Excluir a primeira observação,
// pois ela não possui transição anterior.

var transicoesRM = produto2_regiaoMovel.filter(
  ee.Filter.gt("ordem_temporal", 1),
);

// ============================================================================
// MAIOR SALTO
// ============================================================================

var maiorSalto = ee.Feature(
  ee.Algorithms.If(
    transicoesRM.size().gt(0),

    transicoesRM.sort("delta_area_km2", false).first(),

    produto2_regiaoMovel.first(),
  ),
);

var dataMaiorSalto = ee.Number(maiorSalto.get("data_millis"));

print("========================================");

print("MAIOR SALTO DETECTADO AUTOMATICAMENTE");

print("Data:", maiorSalto.get("data"));

print("Aumento da RM (km²):", maiorSalto.get("delta_area_km2"));

print("Aumento percentual da RM:", maiorSalto.get("delta_area_pct"));

print("Área da RM após salto (km²):", maiorSalto.get("area_km2"));

print("Área total acumulada (km²):", maiorSalto.get("area_total_km2"));

print("Número de componentes:", maiorSalto.get("numero_componentes"));

print(
  "Mudança no número de componentes:",
  maiorSalto.get("delta_num_componentes"),
);

print("Rank global da RM:", maiorSalto.get("rank_global"));

print("Sobreposição com RM anterior (%):", maiorSalto.get("overlap_prev_pct"));

print("Método de continuidade:", maiorSalto.get("metodo_continuidade"));

print("========================================");

// ============================================================================
// 16. DESCOBRIR AUTOMATICAMENTE ANTES / SALTO / DEPOIS
// ============================================================================

var indiceSalto = ee.Number(datas.indexOf(dataMaiorSalto));

// --------------------------------------------------------------------------
// Índice anterior
// --------------------------------------------------------------------------

var indiceAntes = ee.Number(
  ee.Algorithms.If(
    indiceSalto.gt(0),

    indiceSalto.subtract(1),

    indiceSalto,
  ),
);

// --------------------------------------------------------------------------
// Índice posterior
// --------------------------------------------------------------------------

var indiceDepois = ee.Number(
  ee.Algorithms.If(
    indiceSalto.lt(datas.size().subtract(1)),

    indiceSalto.add(1),

    indiceSalto,
  ),
);

var dataAntes = ee.Number(datas.get(indiceAntes));

var dataDepois = ee.Number(datas.get(indiceDepois));

print("DATA ANTERIOR:", ee.Date(dataAntes).format("YYYY-MM-dd"));

print("DATA DO SALTO:", ee.Date(dataMaiorSalto).format("YYYY-MM-dd"));

print("DATA POSTERIOR:", ee.Date(dataDepois).format("YYYY-MM-dd"));

// ============================================================================
// 17. COMPONENTES ANTES / SALTO / DEPOIS
// ============================================================================

var componentesAntes = produto1_componentes.filter(
  ee.Filter.eq("data_millis", dataAntes),
);

var componentesSalto = produto1_componentes.filter(
  ee.Filter.eq("data_millis", dataMaiorSalto),
);

var componentesDepois = produto1_componentes.filter(
  ee.Filter.eq("data_millis", dataDepois),
);

// ============================================================================
// 18. RM ANTES / SALTO / DEPOIS
// ============================================================================

var rmAntes = produto2_regiaoMovel.filter(
  ee.Filter.eq("data_millis", dataAntes),
);

var rmSalto = produto2_regiaoMovel.filter(
  ee.Filter.eq("data_millis", dataMaiorSalto),
);

var rmDepois = produto2_regiaoMovel.filter(
  ee.Filter.eq("data_millis", dataDepois),
);

// ============================================================================
// 19. MOSTRAR TODOS OS N COMPONENTES NAS TRÊS DATAS
// ============================================================================

print("ANTES - componentes:", removerGeometria(componentesAntes, camposP1));

print("SALTO - componentes:", removerGeometria(componentesSalto, camposP1));

print("DEPOIS - componentes:", removerGeometria(componentesDepois, camposP1));

// ============================================================================
// 20. ÁREA QUE SURGIU EXATAMENTE NA DATA DO SALTO
// ============================================================================
//
// Serve para investigar:
// "o que apareceu espacialmente nessa data?"
//
// ============================================================================

var areaNovaSalto = evento.filter(ee.Filter.eq("IDate", dataMaiorSalto));

// ============================================================================
// 21. VERIFICAR SE A RM SEMPRE ERA O MAIOR COMPONENTE
// ============================================================================
//
// IMPORTANTE:
//
// Isso é apenas diagnóstico.
//
// NÃO usamos rank para rastrear a RM.
//
// ============================================================================

var rmNaoEraMaior = tabelaP2.filter(ee.Filter.gt("rank_global", 1));

print(
  "Número de datas em que RM não era o maior componente:",
  rmNaoEraMaior.size(),
);

print("Datas em que RM não era o maior componente:", rmNaoEraMaior);

// ============================================================================
// ============================================================================
// 22. GRÁFICOS
// ============================================================================
// ============================================================================

// ============================================================================
// GRÁFICO 1
//
// Área da RM x área total acumulada
// ============================================================================

var graficoArea = ui.Chart.feature
  .byFeature(
    tabelaP2,

    "data",

    ["area_km2", "area_total_km2"],
  )
  .setSeriesNames(["Região móvel", "Área total"])
  .setOptions({
    title: "Evolução da área acumulada",

    hAxis: {
      title: "Data",

      slantedText: true,

      slantedTextAngle: 45,
    },

    vAxis: {
      title: "Área (km²)",
    },

    lineWidth: 2,

    pointSize: 3,
  });

print(graficoArea);

// ============================================================================
// GRÁFICO 2
//
// Crescimento da RM entre observações
//
// O maior pico é o salto detectado automaticamente.
// ============================================================================

var graficoSalto = ui.Chart.feature
  .byFeature(
    tabelaP2,

    "data",

    ["delta_area_km2"],
  )
  .setSeriesNames(["Δ área RM"])
  .setOptions({
    title: "Crescimento da região móvel entre observações",

    hAxis: {
      title: "Data",

      slantedText: true,

      slantedTextAngle: 45,
    },

    vAxis: {
      title: "Δ área (km²)",
    },

    lineWidth: 2,

    pointSize: 4,
  });

print(graficoSalto);

// ============================================================================
// GRÁFICO 3
//
// Número de componentes desconectados
// ============================================================================

var graficoComponentes = ui.Chart.feature
  .byFeature(
    tabelaP2,

    "data",

    ["numero_componentes"],
  )
  .setSeriesNames(["Nº de componentes"])
  .setOptions({
    title: "Fragmentação da área acumulada",

    hAxis: {
      title: "Data",

      slantedText: true,

      slantedTextAngle: 45,
    },

    vAxis: {
      title: "Número de componentes",
    },

    lineWidth: 2,

    pointSize: 4,
  });

print(graficoComponentes);

// ============================================================================
// ============================================================================
// 23. MAPA
// ============================================================================
// ============================================================================

Map.setOptions("SATELLITE");

Map.centerObject(evento, zoomMapa);

// ============================================================================
// TODOS OS COMPONENTES NA DATA DO SALTO
// ============================================================================

Map.addLayer(
  componentesSalto.style({
    color: "FFFFFF",

    fillColor: "00000000",

    width: 2,
  }),

  {},

  "SALTO - todos os componentes",

  true,
);

// ============================================================================
// RM ANTES
// ============================================================================

Map.addLayer(
  rmAntes.style({
    color: "00BFFF",

    fillColor: "00BFFF44",

    width: 3,
  }),

  {},

  "RM - antes",

  true,
);

// ============================================================================
// RM NA DATA DO MAIOR SALTO
// ============================================================================

Map.addLayer(
  rmSalto.style({
    color: "FF0000",

    fillColor: "FF000055",

    width: 3,
  }),

  {},

  "RM - maior salto",

  true,
);

// ============================================================================
// RM DEPOIS
// ============================================================================

Map.addLayer(
  rmDepois.style({
    color: "FF8C00",

    fillColor: "FF8C0044",

    width: 3,
  }),

  {},

  "RM - depois",

  false,
);

// ============================================================================
// ÁREA NOVA NA DATA DO SALTO
// ============================================================================

Map.addLayer(
  areaNovaSalto.style({
    color: "FFFF00",

    fillColor: "FFFF0088",

    width: 2,
  }),

  {},

  "Área nova - data do salto",

  true,
);

// ============================================================================
// 24. ÚLTIMA DATA
// ============================================================================

var componentesUltimaData = produto1_componentes.filter(
  ee.Filter.eq("data_millis", ultimaData),
);

var rmFinal = produto2_regiaoMovel.filter(
  ee.Filter.eq("data_millis", ultimaData),
);

Map.addLayer(
  componentesUltimaData.style({
    color: "FFFFFF",

    fillColor: "00000000",

    width: 1,
  }),

  {},

  "FINAL - todos componentes",

  false,
);

Map.addLayer(
  rmFinal.style({
    color: "FF00FF",

    fillColor: "FF00FF33",

    width: 3,
  }),

  {},

  "FINAL - região móvel",

  false,
);

// ============================================================================
// ============================================================================
// 25. EXPORTAÇÕES
// ============================================================================
// ============================================================================
//
// Depois de executar:
//
// vá em:
//
// TASKS
//
// e clique em RUN.
//
// Serão criados exatamente os dois produtos espaciais principais.
//
// GeoJSON é utilizado porque preserva melhor os nomes dos atributos
// do que Shapefile.
//
// ============================================================================

// ============================================================================
// PRODUTO 1
//
// TODOS OS COMPONENTES
// ============================================================================

Export.table.toDrive({
  collection: produto1_componentes,

  description: "P1_componentes_" + idIncendio,

  fileNamePrefix: "P1_componentes_" + idIncendio,

  fileFormat: "GeoJSON",
});

// ============================================================================
// PRODUTO 2
//
// REGIÃO MÓVEL
// ============================================================================

Export.table.toDrive({
  collection: produto2_regiaoMovel,

  description: "P2_regiao_movel_" + idIncendio,

  fileNamePrefix: "P2_regiao_movel_" + idIncendio,

  fileFormat: "GeoJSON",
});

// ============================================================================
// ============================================================================
// 26. FIM
// ============================================================================
// ============================================================================

print("========================================");

print("PROCESSAMENTO CONFIGURADO");

print("P1 = todos os componentes");

print("P2 = região móvel rastreada");

print("Use a aba Tasks para executar os exports.");

print("========================================");
