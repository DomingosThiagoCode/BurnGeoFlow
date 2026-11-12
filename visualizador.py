"""Interface local para navegar nos incêndios processados pelo BurnGeoFlow.

Iniciar: streamlit run visualizador.py

A interface é de leitura: NÃO executa o GEE, NÃO altera P1/P2 e não
apresenta métricas como validação externa.
"""
from __future__ import annotations

import json
from math import log2
from pathlib import Path

from burngeoflow.visualizacao.dados import (
    ROOT, ErroVisualizador, assinatura_arquivos, camada_dia,
    carregar_evento, caminhos, descobrir_eventos, limites_dia,
    linha_dia, transicao_para,
)


def main():
    try:
        import pandas as pd
        import pydeck as pdk
        import streamlit as st
    except ImportError as exc:
        raise SystemExit(
            "Instale as dependências opcionais: "
            "python -m pip install -r requirements-viewer.txt"
        ) from exc

    st.set_page_config(
        page_title="BurnGeoFlow | Visualizador",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("🔥 BurnGeoFlow")
    st.caption(
        "Visualizador espaço-temporal de áreas queimadas | "
        "P1, P2 e indicadores integrados"
    )

    base = ROOT / "execucoes"
    ids = descobrir_eventos(base)
    with st.sidebar:
        st.header("Explorar incêndio")
        if ids:
            opcoes = ["Escolher um ID..."] + [str(i) for i in ids]
            escolha = st.selectbox(
                "Eventos locais disponíveis", opcoes,
                index=1 if ids else 0,
            )
            evento_id = int(escolha) if escolha != opcoes[0] else None
            st.caption(f"{len(ids)} evento(s) com P1/P2 armazenados.")
        else:
            evento_id = None
            st.info("Nenhum evento processado encontrado na pasta execucoes/.")

        if st.checkbox("Informar ID manualmente", value=not ids):
            informado = st.number_input(
                "ID GlobFire", min_value=1,
                value=ids[0] if ids else 24340828, step=1,
                format="%d",
            )
            evento_id = int(informado)

        st.divider()
        st.markdown("**Fluxo para outros eventos**")
        st.caption(
            "O processamento inicial é feito pela CLI. Depois, "
            "os resultados aparecem automaticamente aqui."
        )
        if evento_id is not None:
            st.code(
                f"python executar_pipeline.py --id {evento_id} --origem gee",
                language="powershell",
            )
            st.caption("Se souber o ano, adicione --ano AAAA para acelerar a busca.")

    if evento_id is None:
        st.info("Selecione um ID disponível no menu lateral.")
        return
    arquivos = caminhos(base, evento_id)
    if not arquivos["p1"].is_file() or not arquivos["p2"].is_file():
        st.warning(
            f"Não existem GeoJSONs P1/P2 locais para o ID {evento_id}. "
            "Execute a aquisição/processamento primeiro."
        )
        return

    @st.cache_data(show_spinner="Carregando mapas e indicadores...", max_entries=4)
    def obter_evento(i: int, assinatura: tuple) -> dict:
        # A assinatura informa ao cache quando arquivos foram alterados.
        return carregar_evento(base, i)

    try:
        evento = obter_evento(evento_id, assinatura_arquivos(arquivos))
    except (ErroVisualizador, OSError, KeyError, TypeError, ValueError) as exc:
        st.error(f"Não foi possível abrir o evento: {exc}")
        st.stop()
    datas = evento["datas"]
    # O seletor e os botões compartilham a mesma chave por evento.
    # on_click executa antes do rerun, evitando modificar widget
    # já instanciado no mesmo ciclo Streamlit.
    chave_data = f"data_selecionada_{evento_id}"
    if st.session_state.get(chave_data) not in datas:
        st.session_state[chave_data] = datas[-1]

    def mover_data(deslocamento: int):
        indice_atual = datas.index(st.session_state[chave_data])
        novo = max(0, min(len(datas)-1, indice_atual + deslocamento))
        st.session_state[chave_data] = datas[novo]

    with st.sidebar:
        st.divider()
        st.subheader("Linha do tempo")
        dia = st.select_slider(
            "Data de observação", options=datas, key=chave_data,
        )
        indice = datas.index(dia)
        antes, depois = st.columns(2)
        with antes:
            st.button(
                "◀ Anterior", disabled=indice == 0, use_container_width=True,
                on_click=mover_data, args=(-1,),
            )
        with depois:
            st.button(
                "Próxima ▶", disabled=indice == len(datas)-1,
                use_container_width=True, on_click=mover_data, args=(1,),
            )
        st.divider()
        mostrar_p1 = st.checkbox("P1: todos os componentes", value=True)
        mostrar_p2 = st.checkbox("P2: região rastreada", value=True)
        if not mostrar_p1 and not mostrar_p2:
            st.warning("Habilite ao menos uma camada.")
        st.divider()
        if evento["completo"]:
            st.success("Etapas de análise disponíveis")
        else:
            st.warning(
                "P1/P2 disponíveis, mas nem todos os resultados das "
                "Etapas 5 e 6 foram encontrados."
            )
        resumo6 = evento["resumo6"]
        if resumo6:
            st.caption(f"Auditoria: {resumo6.get('status_cientifico', 'sem status')}")
            if not resumo6.get("validacao_externa_concluida"):
                st.caption("Validação externa: não realizada")

    registro = linha_dia(evento, dia)
    st.markdown(f"#### Evento {evento_id} | {dia}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Componentes P1", str(len(evento["p1_por_data"][dia])))
    if registro:
        def fnum(nome):
            valor = registro.get(nome)
            return float(valor) if valor not in (None, "") else None
        a1 = fnum("area_total_laea_km2")
        a2 = fnum("p2_area_laea_km2")
        dominancia = fnum("dominancia_cobertura_p2_pct")
        col2.metric("Área coberta P1", f"{a1:,.2f} km²" if a1 is not None else "N/D")
        col3.metric("Área P2", f"{a2:,.2f} km²" if a2 is not None else "N/D")
        col4.metric(
            "P2 / P1", f"{dominancia:.1f}%" if dominancia is not None else "N/D"
        )
    else:
        col2.metric("Área coberta P1", "Sem integração")
        col3.metric("Área P2", "Sem integração")
        col4.metric("P2 / P1", "Sem integração")

    aba_mapa, aba_graficos, aba_dados = st.tabs([
        "🗺️ Mapa temporal", "📈 Indicadores", "📄 Dados e exportação",
    ])
    with aba_mapa:
        if mostrar_p1 or mostrar_p2:
            feats = evento["p1_por_data"][dia]
            bbox = limites_dia(feats)
            span = max(bbox[2]-bbox[0], bbox[3]-bbox[1], 0.001)
            zoom = max(3.0, min(13.0, log2(360.0/span)-1.4))
            camadas = []
            if mostrar_p1:
                camadas.append(
                    pdk.Layer(
                        "GeoJsonLayer",
                        camada_dia(evento, dia, incluir_p1=True, incluir_p2=False),
                        pickable=True, auto_highlight=True,
                        filled=True, stroked=True,
                        get_fill_color=[234, 126, 54, 90],
                        get_line_color=[185, 84, 39, 210],
                        get_line_width=90, line_width_min_pixels=1,
                    )
                )
            if mostrar_p2:
                camadas.append(
                    pdk.Layer(
                        "GeoJsonLayer",
                        camada_dia(evento, dia, incluir_p1=False, incluir_p2=True),
                        pickable=True, auto_highlight=True,
                        filled=True, stroked=True,
                        get_fill_color=[24, 148, 143, 75],
                        get_line_color=[7, 111, 124, 245],
                        get_line_width=180, line_width_min_pixels=3,
                    )
                )
            vis = pdk.Deck(
                layers=camadas,
                initial_view_state=pdk.ViewState(
                    longitude=(bbox[0]+bbox[2])/2,
                    latitude=(bbox[1]+bbox[3])/2,
                    zoom=zoom, pitch=0,
                ),
                tooltip={"html": "<b>Componente</b><br>Data: {data}<br>"
                         "Rank: {rank}<br>Rank P2: {rank_global}",
                         "style": {"backgroundColor": "#24313A",
                                   "color": "#FFFFFF"}},
                map_style="light",
            )
            st.pydeck_chart(vis, use_container_width=True)
            st.caption(
                "Laranja: componentes P1 · Verde: região móvel P2. "
                "Geometrias originais EPSG:4326, sem simplificação."
            )
        atual = transicao_para(evento, dia)
        if atual:
            m1, m2, m3 = st.columns(3)
            m1.metric("Convergências na transição", atual.get(
                "eventos_convergencia", "N/D"
            ))
            valor = atual.get("p2_incremento_ja_queimado_km2")
            m2.metric(
                "P2: incorporação já queimada",
                f"{float(valor):,.3f} km²" if valor not in ("", None) else "N/D",
            )
            valor = atual.get("area_nova_evento_km2")
            m3.metric(
                "Área nova no evento",
                f"{float(valor):,.3f} km²" if valor not in ("", None) else "N/D",
            )
            if int(atual["dias_intervalo"]) > 1:
                st.warning(
                    f"Lacuna de {atual['dias_intervalo']} dias "
                    "entre as observações."
                )

    with aba_graficos:
        if not evento["serie"]:
            st.info("Métricas integradas ainda indisponíveis para este evento.")
        else:
            df = pd.DataFrame(evento["serie"])
            df["data"] = pd.to_datetime(df["data"])
            for campo in [
                "area_total_laea_km2", "p2_area_laea_km2", "numero_patches",
                "dominancia_maior_patch_pct",
            ]:
                df[campo] = pd.to_numeric(df[campo], errors="coerce")
            st.subheader("Área queimada acumulada e região móvel")
            serie = df.set_index("data")[[
                "area_total_laea_km2", "p2_area_laea_km2",
            ]].rename(columns={
                "area_total_laea_km2": "Cobertura P1 (km²)",
                "p2_area_laea_km2": "Região P2 (km²)",
            })
            st.line_chart(serie, height=270)
            st.subheader("Fragmentação: componentes e dominância")
            a, b = st.columns(2)
            with a:
                st.line_chart(df.set_index("data")[["numero_patches"]].rename(
                    columns={"numero_patches": "Nº de patches P1"}
                ), height=230)
            with b:
                st.line_chart(df.set_index("data")[[
                    "dominancia_maior_patch_pct"
                ]].rename(columns={
                    "dominancia_maior_patch_pct": "Maior patch (%)"
                }), height=230)
            if evento["transicoes"]:
                t = pd.DataFrame(evento["transicoes"])
                t["data_atual"] = pd.to_datetime(t["data_atual"])
                for coluna in [
                    "area_nova_evento_km2",
                    "p2_incremento_ja_queimado_km2",
                    "p2_incremento_nova_area_evento_km2",
                ]:
                    t[coluna] = pd.to_numeric(t[coluna], errors="coerce")
                st.subheader("Crescimento do evento × incorporação do P2")
                st.line_chart(t.set_index("data_atual")[[
                    "area_nova_evento_km2",
                    "p2_incremento_ja_queimado_km2",
                    "p2_incremento_nova_area_evento_km2",
                ]].rename(columns={
                    "area_nova_evento_km2": "Área nova no evento (km²)",
                    "p2_incremento_ja_queimado_km2": "P2 incorpora já queimada (km²)",
                    "p2_incremento_nova_area_evento_km2": "P2 incorpora nova área (km²)",
                }), height=280)
        st.caption(
            "Indicadores espaciais e temporais, não velocidades físicas do fogo. "
            "Fases BIC e convergências exigem interpretação científica."
        )

    with aba_dados:
        dados_p1 = [
            {
                "rank": f["properties"].get("rank"),
                "data": f["properties"].get("data"),
                "area_gee_km2": f["properties"].get("area_km2"),
            }
            for f in evento["p1_por_data"][dia]
        ]
        st.subheader("Componentes P1 da data")
        st.dataframe(
            pd.DataFrame(dados_p1).sort_values("rank"),
            use_container_width=True, hide_index=True,
        )
        st.subheader("Baixar camadas da data")
        pac = camada_dia(evento, dia, incluir_p1=True, incluir_p2=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Baixar P1 + P2 (GeoJSON)",
                json.dumps(pac, ensure_ascii=False).encode("utf-8"),
                file_name=f"BurnGeoFlow_{evento_id}_{dia}_P1_P2.geojson",
                mime="application/geo+json",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Baixar indicadores (CSV)",
                (pd.DataFrame(evento["serie"]).to_csv(index=False).encode("utf-8")
                 if evento["serie"] else b""),
                file_name=f"BurnGeoFlow_{evento_id}_serie.csv",
                mime="text/csv", disabled=not bool(evento["serie"]),
                use_container_width=True,
            )
        st.caption(
            "Exportação para consulta. Os P1/P2 originais permanecem intactos."
        )
    st.divider()
    st.caption(
        "BurnGeoFlow | Exploração de dados. "
        "O sucesso do pipeline não constitui validação externa."
    )


if __name__ == "__main__":
    main()
