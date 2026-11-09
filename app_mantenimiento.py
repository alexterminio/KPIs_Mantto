import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
import io

st.set_page_config(page_title="Indicadores de Mantenimiento Cartocor", layout="wide")

# ==========================================
# ENCABEZADO Y BOTONES FLOTANTES
# ==========================================
st.title("⚙️ Indicadores de Mantenimiento Cartocor")

col_btn1, col_btn2, _ = st.columns([2, 2, 6])

with col_btn1:
    with st.popover("📐 Ver Fórmulas de Indicadores"):
        st.markdown("### 📚 Glosario de Fórmulas")
        st.markdown("**1. Indisponibilidad (%)**")
        st.latex(r"\text{Indisponibilidad} = \left( \frac{\text{Horas de Parada (M + E)}}{\text{Horas Totales Programadas}} \right) \times 100")
        st.markdown("**2. MTTR (Tiempo Medio Para Reparar) - En Minutos**")
        st.latex(r"\text{MTTR} = \left( \frac{\text{Horas Total de Paradas}}{\text{Cantidad de Averías}} \right) \times 60")
        st.markdown("**3. MTBF (Tiempo Medio Entre Fallas) - En Horas**")
        st.latex(r"\text{MTBF} = \frac{\text{Horas Programadas} - \text{Horas Total de Paradas}}{\text{Cantidad de Averías}}")
        st.info("💡 **Nota:** Si en un mes hay 0 averías, el MTTR es 0 y el MTBF equivale al total de horas programadas del mes.")

with col_btn2:
    with st.popover("🚦 Ver Leyenda de Criticidad"):
        st.markdown("### 🚦 Leyenda de Criticidad")
        st.markdown("- **1:** Mayor a 1 hora")
        st.markdown("- **2:** Mayor a 30 min, menor a 1h")
        st.markdown("- **3:** Mayor a 5 min, menor a 30 min")
        st.markdown("- **4:** Menor a 5 min")

mapa_maquinas = {
    "CORRUGADORA": "CORRUG",
    "DONFANG": "DONFANG",
    "WARD15000": "WARD",
    "MARTIN 924": "MARTIN"
}

orden_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
               "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

def convertir_a_horas(valor):
    if isinstance(valor, datetime.time):
        return valor.hour + (valor.minute / 60) + (valor.second / 3600)
    elif pd.isna(valor):
        return 0
    else:
        return pd.to_numeric(valor, errors='coerce') / 60

archivo_subido = st.file_uploader("Cargar Base de Datos (.xlsx)", type=["xlsx"])

if archivo_subido is not None:
    try:
        # 1. Extracción y Limpieza
        df_general = pd.read_excel(archivo_subido, sheet_name="Tabla General")
        df_horas = pd.read_excel(archivo_subido, sheet_name="Horas Programadas")
        
        df_general.columns = df_general.columns.str.strip()
        df_horas.columns = df_horas.columns.str.strip()
        df_general["Horas_Parada"] = df_general["Durac"].apply(convertir_a_horas)
        
        if "Criticidad" not in df_general.columns: df_general["Criticidad"] = "Sin Clasificar"
        if "Nombre de Equipos" not in df_general.columns: df_general["Nombre de Equipos"] = df_general.get("MAQUINA", "Equipo Desconocido")
            
        mapa_meses_num = {i+1: orden_meses[i] for i in range(12)}
        df_general["Mes_Texto"] = df_general["Mes"].map(mapa_meses_num)
        
        if "Tipo" in df_general.columns:
            df_general["Tipo"] = df_general["Tipo"].fillna("").astype(str).str.strip().str.upper()
        
        df_mantenimiento = df_general[df_general["Tipo"].isin(["M", "E"])]
        meses_presentes = [m for m in orden_meses if m in df_horas["Mes"].dropna().unique().tolist()]

        st.markdown("---")
        
        col_sel1, _ = st.columns([1, 2])
        with col_sel1:
            maquina_seleccionada = st.selectbox("🔍 Selecciona el Equipo para el panel principal de Indisponibilidad:", list(mapa_maquinas.keys()))
            
        # ==========================================
        # PROCESAMIENTO MATRICIAL 
        # ==========================================
        datos_resumen_indisp, datos_resumen_mttr, datos_resumen_mtbf = [], [], []
        datos_graficos = {k: [] for k in ["TOTAL PLANTA"] + list(mapa_maquinas.keys())}
        acum_ytd = {k: {'hp': 0, 'p_m': 0, 'p_e': 0, 'f_m': 0, 'f_e': 0} for k in ["TOTAL PLANTA"] + list(mapa_maquinas.keys())}

        for mes in meses_presentes:
            df_mant_mes = df_mantenimiento[df_mantenimiento["Mes_Texto"] == mes]
            df_horas_mes = df_horas[df_horas["Mes"] == mes]
            
            hp_pl = df_horas_mes[list(mapa_maquinas.values())].sum().sum()
            df_pl_m, df_pl_e = df_mant_mes[df_mant_mes["Tipo"] == "M"], df_mant_mes[df_mant_mes["Tipo"] == "E"]
            
            p_pl_m, f_pl_m = df_pl_m["Horas_Parada"].sum(), df_pl_m.shape[0]
            p_pl_e, f_pl_e = df_pl_e["Horas_Parada"].sum(), df_pl_e.shape[0]
            p_pl_tot, f_pl_tot = p_pl_m + p_pl_e, f_pl_m + f_pl_e
            
            acum_ytd["TOTAL PLANTA"]['hp'] += hp_pl
            acum_ytd["TOTAL PLANTA"]['p_m'] += p_pl_m; acum_ytd["TOTAL PLANTA"]['p_e'] += p_pl_e
            acum_ytd["TOTAL PLANTA"]['f_m'] += f_pl_m; acum_ytd["TOTAL PLANTA"]['f_e'] += f_pl_e
            
            datos_graficos["TOTAL PLANTA"].append({
                "Mes": mes,
                "Indisp_E": (p_pl_e / hp_pl * 100) if hp_pl > 0 else 0,
                "Indisp_M": (p_pl_m / hp_pl * 100) if hp_pl > 0 else 0,
                "Indisp_T": (p_pl_tot / hp_pl * 100) if hp_pl > 0 else 0,
                "MTTR_E": (p_pl_e / f_pl_e * 60) if f_pl_e > 0 else 0,
                "MTTR_M": (p_pl_m / f_pl_m * 60) if f_pl_m > 0 else 0,
                "MTTR_T": (p_pl_tot / f_pl_tot * 60) if f_pl_tot > 0 else 0,
                "MTBF_E": ((hp_pl - p_pl_e) / f_pl_e) if f_pl_e > 0 else hp_pl,
                "MTBF_M": ((hp_pl - p_pl_m) / f_pl_m) if f_pl_m > 0 else hp_pl,
                "MTBF_T": ((hp_pl - p_pl_tot) / f_pl_tot) if f_pl_tot > 0 else hp_pl
            })
            
            fila_ind, fila_mttr, fila_mtbf = {("MES", ""): mes.upper()}, {("MES", ""): mes.upper()}, {("MES", ""): mes.upper()}
            
            fila_ind[("TOTAL PLANTA", "ELECTRICO")] = (p_pl_e / hp_pl * 100) if hp_pl > 0 else 0
            fila_ind[("TOTAL PLANTA", "MECANICO")] = (p_pl_m / hp_pl * 100) if hp_pl > 0 else 0
            fila_ind[("TOTAL PLANTA", "TOTAL")] = (p_pl_tot / hp_pl * 100) if hp_pl > 0 else 0
            fila_mttr[("TOTAL PLANTA", "ELECTRICO")] = (p_pl_e / f_pl_e * 60) if f_pl_e > 0 else 0
            fila_mttr[("TOTAL PLANTA", "MECANICO")] = (p_pl_m / f_pl_m * 60) if f_pl_m > 0 else 0
            fila_mttr[("TOTAL PLANTA", "TOTAL")] = (p_pl_tot / f_pl_tot * 60) if f_pl_tot > 0 else 0
            fila_mtbf[("TOTAL PLANTA", "ELECTRICO")] = ((hp_pl - p_pl_e) / f_pl_e) if f_pl_e > 0 else hp_pl
            fila_mtbf[("TOTAL PLANTA", "MECANICO")] = ((hp_pl - p_pl_m) / f_pl_m) if f_pl_m > 0 else hp_pl
            fila_mtbf[("TOTAL PLANTA", "TOTAL")] = ((hp_pl - p_pl_tot) / f_pl_tot) if f_pl_tot > 0 else hp_pl
            
            for maq_nombre, maq_col in mapa_maquinas.items():
                df_mq = df_mant_mes[df_mant_mes["MAQUINA"] == maq_nombre]
                hp_mq = df_horas_mes[maq_col].sum()
                
                p_mq_m, f_mq_m = df_mq[df_mq["Tipo"] == "M"]["Horas_Parada"].sum(), df_mq[df_mq["Tipo"] == "M"].shape[0]
                p_mq_e, f_mq_e = df_mq[df_mq["Tipo"] == "E"]["Horas_Parada"].sum(), df_mq[df_mq["Tipo"] == "E"].shape[0]
                p_mq_tot, f_mq_tot = p_mq_m + p_mq_e, f_mq_m + f_mq_e
                
                acum_ytd[maq_nombre]['hp'] += hp_mq
                acum_ytd[maq_nombre]['p_m'] += p_mq_m; acum_ytd[maq_nombre]['p_e'] += p_mq_e
                acum_ytd[maq_nombre]['f_m'] += f_mq_m; acum_ytd[maq_nombre]['f_e'] += f_mq_e
                
                datos_graficos[maq_nombre].append({
                    "Mes": mes,
                    "Indisp_E": (p_mq_e / hp_mq * 100) if hp_mq > 0 else 0,
                    "Indisp_M": (p_mq_m / hp_mq * 100) if hp_mq > 0 else 0,
                    "Indisp_T": (p_mq_tot / hp_mq * 100) if hp_mq > 0 else 0,
                    "MTTR_E": (p_mq_e / f_mq_e * 60) if f_mq_e > 0 else 0,
                    "MTTR_M": (p_mq_m / f_mq_m * 60) if f_mq_m > 0 else 0,
                    "MTTR_T": (p_mq_tot / f_mq_tot * 60) if f_mq_tot > 0 else 0,
                    "MTBF_E": ((hp_mq - p_mq_e) / f_mq_e) if f_mq_e > 0 else hp_mq,
                    "MTBF_M": ((hp_mq - p_mq_m) / f_mq_m) if f_mq_m > 0 else hp_mq,
                    "MTBF_T": ((hp_mq - p_mq_tot) / f_mq_tot) if f_mq_tot > 0 else hp_mq
                })
                
                fila_ind[(maq_nombre, "ELECTRICO")] = (p_mq_e / hp_mq * 100) if hp_mq > 0 else 0
                fila_ind[(maq_nombre, "MECANICO")] = (p_mq_m / hp_mq * 100) if hp_mq > 0 else 0
                fila_ind[(maq_nombre, "TOTAL")] = (p_mq_tot / hp_mq * 100) if hp_mq > 0 else 0
                fila_mttr[(maq_nombre, "ELECTRICO")] = (p_mq_e / f_mq_e * 60) if f_mq_e > 0 else 0
                fila_mttr[(maq_nombre, "MECANICO")] = (p_mq_m / f_mq_m * 60) if f_mq_m > 0 else 0
                fila_mttr[(maq_nombre, "TOTAL")] = (p_mq_tot / f_mq_tot * 60) if f_mq_tot > 0 else 0
                fila_mtbf[(maq_nombre, "ELECTRICO")] = ((hp_mq - p_mq_e) / f_mq_e) if f_mq_e > 0 else hp_mq
                fila_mtbf[(maq_nombre, "MECANICO")] = ((hp_mq - p_mq_m) / f_mq_m) if f_mq_m > 0 else hp_mq
                fila_mtbf[(maq_nombre, "TOTAL")] = ((hp_mq - p_mq_tot) / f_mq_tot) if f_mq_tot > 0 else hp_mq
                
            datos_resumen_indisp.append(fila_ind); datos_resumen_mttr.append(fila_mttr); datos_resumen_mtbf.append(fila_mtbf)

        fila_ytd_ind, fila_ytd_mttr, fila_ytd_mtbf = {("MES", ""): "PROMEDIO 2026"}, {("MES", ""): "PROMEDIO 2026"}, {("MES", ""): "PROMEDIO 2026"}
        for key in ["TOTAL PLANTA"] + list(mapa_maquinas.keys()):
            hp, p_m, p_e = acum_ytd[key]['hp'], acum_ytd[key]['p_m'], acum_ytd[key]['p_e']
            f_m, f_e = acum_ytd[key]['f_m'], acum_ytd[key]['f_e']
            p_tot, f_tot = p_m + p_e, f_m + f_e

            datos_graficos[key].append({
                "Mes": "Promedio 2026",
                "Indisp_E": (p_e / hp * 100) if hp > 0 else 0,
                "Indisp_M": (p_m / hp * 100) if hp > 0 else 0,
                "Indisp_T": (p_tot / hp * 100) if hp > 0 else 0,
                "MTTR_E": (p_e / f_e * 60) if f_e > 0 else 0,
                "MTTR_M": (p_m / f_m * 60) if f_m > 0 else 0,
                "MTTR_T": (p_tot / f_tot * 60) if f_tot > 0 else 0,
                "MTBF_E": ((hp - p_e) / f_e) if f_e > 0 else hp,
                "MTBF_M": ((hp - p_m) / f_m) if f_m > 0 else hp,
                "MTBF_T": ((hp - p_tot) / f_tot) if f_tot > 0 else hp
            })
            
            fila_ytd_ind[(key, "ELECTRICO")] = (p_e / hp * 100) if hp > 0 else 0
            fila_ytd_ind[(key, "MECANICO")] = (p_m / hp * 100) if hp > 0 else 0
            fila_ytd_ind[(key, "TOTAL")] = (p_tot / hp * 100) if hp > 0 else 0
            fila_ytd_mttr[(key, "ELECTRICO")] = (p_e / f_e * 60) if f_e > 0 else 0
            fila_ytd_mttr[(key, "MECANICO")] = (p_m / f_m * 60) if f_m > 0 else 0
            fila_ytd_mttr[(key, "TOTAL")] = (p_tot / f_tot * 60) if f_tot > 0 else 0
            fila_ytd_mtbf[(key, "ELECTRICO")] = ((hp - p_e) / f_e) if f_e > 0 else hp
            fila_ytd_mtbf[(key, "MECANICO")] = ((hp - p_m) / f_m) if f_m > 0 else hp
            fila_ytd_mtbf[(key, "TOTAL")] = ((hp - p_tot) / f_tot) if f_tot > 0 else hp

        datos_resumen_indisp.append(fila_ytd_ind); datos_resumen_mttr.append(fila_ytd_mttr); datos_resumen_mtbf.append(fila_ytd_mtbf)

        dfs_graficos = {k: pd.DataFrame(v) for k, v in datos_graficos.items()}
        
        def format_summary_df(datos):
            df = pd.DataFrame(datos)
            df.set_index(("MES", ""), inplace=True)
            df.columns = pd.MultiIndex.from_tuples(df.columns)
            df.index.name = "MES"
            return df
            
        df_r_indisp, df_r_mttr, df_r_mtbf = format_summary_df(datos_resumen_indisp), format_summary_df(datos_resumen_mttr), format_summary_df(datos_resumen_mtbf)

        # ==========================================
        # FUNCIONES DE GRÁFICOS ESCALADOS
        # ==========================================
        def crear_grafico_agrupado(df_datos, titulo_grafico, tipo_kpi):
            fig = go.Figure()
            if tipo_kpi == "Indisponibilidad (%)": pref, suf = "Indisp_", "%"
            elif tipo_kpi == "MTTR (Minutos)": pref, suf = "MTTR_", " min"
            else: pref, suf = "MTBF_", " hrs"

            fig.add_trace(go.Bar(x=df_datos['Mes'], y=df_datos[f'{pref}E'], name='<b>Eléctrico</b>', marker_color='#3DA9F2', text=df_datos[f'{pref}E'].apply(lambda x: f"<b>{x:.1f}{suf}</b>" if x > 0 else ""), textposition='outside', textfont=dict(size=15, color="black")))
            fig.add_trace(go.Bar(x=df_datos['Mes'], y=df_datos[f'{pref}M'], name='<b>Mecánico</b>', marker_color='#F28735', text=df_datos[f'{pref}M'].apply(lambda x: f"<b>{x:.1f}{suf}</b>" if x > 0 else ""), textposition='outside', textfont=dict(size=15, color="black")))
            fig.add_trace(go.Bar(x=df_datos['Mes'], y=df_datos[f'{pref}T'], name='<b>Total</b>', marker_color='#539A37', text=df_datos[f'{pref}T'].apply(lambda x: f"<b>{x:.1f}{suf}</b>" if x > 0 else ""), textposition='outside', textfont=dict(size=15, color="black")))
            fig.add_trace(go.Scatter(x=df_datos['Mes'], y=df_datos[f'{pref}T'], name='<b>Tendencia Total</b>', mode='lines+markers', line=dict(color='#2C3E50', width=3, shape='spline', smoothing=1), marker=dict(size=8, color='#2C3E50', symbol='circle')))
            
            max_val = max(df_datos[f'{pref}E'].max(), df_datos[f'{pref}M'].max(), df_datos[f'{pref}T'].max())
            max_y = max_val * 1.30 if pd.notna(max_val) and max_val > 0 else 10
            
            fig.update_layout(
                title=dict(text=f"<b>{titulo_grafico}</b>", x=0.5, font=dict(size=24, color="#333333")),
                barmode='group', bargap=0.3, bargroupgap=0.05, plot_bgcolor='white', height=500,
                font=dict(size=16, color="black", family="Arial"), 
                yaxis=dict(showgrid=True, gridcolor='#E5E5E5', range=[0, max_y], tickfont=dict(size=15, color="black")), xaxis=dict(showgrid=False, tickfont=dict(size=16, color="black")),
                margin=dict(t=60, b=50, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None, font=dict(size=16, color="black"))
            )
            return fig

        def crear_grafico_pareto(df_filtrado, kpi, titulo):
            if df_filtrado.empty:
                return go.Figure().update_layout(title="No hay datos para esta selección")
            
            if kpi == "Horas de Parada":
                df_agrupado = df_filtrado.groupby("Nombre de Equipos")["Horas_Parada"].sum().reset_index()
                df_agrupado.rename(columns={"Horas_Parada": "Valor"}, inplace=True)
                suf = " hrs"
            else:
                df_agrupado = df_filtrado.groupby("Nombre de Equipos").size().reset_index(name="Valor")
                suf = " averías"
                
            df_agrupado = df_agrupado[df_agrupado["Valor"] > 0]
            df_agrupado = df_agrupado.sort_values(by="Valor", ascending=False)
            df_agrupado["Porcentaje"] = (df_agrupado["Valor"] / df_agrupado["Valor"].sum()) * 100
            df_agrupado["Acumulado"] = df_agrupado["Porcentaje"].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_agrupado["Nombre de Equipos"], y=df_agrupado["Valor"], name="Métrica",
                marker_color='#3DA9F2', text=df_agrupado["Valor"].apply(lambda x: f"<b>{x:.1f}{suf}</b>" if kpi == "Horas de Parada" else f"<b>{int(x)}{suf}</b>"),
                textposition='auto', textfont=dict(size=15, color="black")
            ))
            fig.add_trace(go.Scatter(
                x=df_agrupado["Nombre de Equipos"], y=df_agrupado["Acumulado"], name="Acumulado %",
                mode='lines+markers+text', yaxis='y2', line=dict(color='#F28735', width=3),
                marker=dict(size=8, color='#F28735', symbol='circle'),
                text=df_agrupado["Acumulado"].apply(lambda x: f"{x:.1f}%"), textposition='top center', textfont=dict(size=15, color="gray")
            ))
            
            max_y = df_agrupado["Valor"].max() * 1.2 if not df_agrupado.empty else 10
            
            # --- CORRECCIÓN DE SINTAXIS (title=dict(text=..., font=dict(...))) ---
            fig.update_layout(
                title=dict(text=f"<b>{titulo}</b>", x=0.5, font=dict(size=24, color="#333333")),
                plot_bgcolor='white', height=500, font=dict(size=16, color="black"),
                yaxis=dict(title=dict(text=f"<b>{kpi}</b>", font=dict(size=18)), showgrid=True, gridcolor='#E5E5E5', range=[0, max_y], tickfont=dict(size=15)),
                yaxis2=dict(title=dict(text="<b>% Acumulado</b>", font=dict(size=18)), overlaying='y', side='right', range=[0, 110], showgrid=False, ticksuffix="%", tickfont=dict(size=15)),
                xaxis=dict(tickangle=-45, showgrid=False, tickfont=dict(size=15)),
                margin=dict(t=60, b=120, l=10, r=10),
                legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, font=dict(size=16))
            )
            return fig

        def crear_grafico_pie(df_filtrado):
            if df_filtrado.empty:
                return go.Figure().update_layout(title="No hay datos para esta selección")
            
            df_agrupado = df_filtrado.groupby("Criticidad").size().reset_index(name="Cantidad")
            fig = go.Figure(data=[go.Pie(
                labels=df_agrupado["Criticidad"], 
                values=df_agrupado["Cantidad"],
                hole=0.4,
                textinfo='label+percent+value',
                textfont=dict(size=18, color="white"),
                marker=dict(colors=['#E74C3C', '#F28735', '#F1C40F', '#539A37', '#9B59B6']) 
            )])
            
            fig.update_layout(
                title=dict(text="<b>Fallas por Nivel de Criticidad</b>", x=0.5, font=dict(size=26, color="#333333")),
                height=650, margin=dict(t=80, b=40, l=10, r=10),
                legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=18))
            )
            return fig

        # ==========================================
        # FUNCIÓN AUXILIAR: TABLAS DINÁMICAS Y FILTROS
        # ==========================================
        def generar_tabla_dinamica(df_filtrado):
            if df_filtrado.empty: return pd.DataFrame()
            pivot = pd.pivot_table(df_filtrado, values='Horas_Parada', index='Mes_Texto', columns='MAQUINA', aggfunc=['sum', 'count'], fill_value=0)
            meses_presentes_pivot = [m for m in orden_meses if m in pivot.index]
            pivot = pivot.reindex(meses_presentes_pivot)
            pivot.columns = [f"{maq} (Hrs)" if agg == 'sum' else f"{maq} (N° Fallas)" for agg, maq in pivot.columns]
            pivot = pivot.sort_index(axis=1)
            cols_hrs = [c for c in pivot.columns if "(Hrs)" in c]; cols_fallas = [c for c in pivot.columns if "(N° Fallas)" in c]
            pivot['TOTAL (Hrs)'], pivot['TOTAL (N° Fallas)'] = pivot[cols_hrs].sum(axis=1), pivot[cols_fallas].sum(axis=1)
            pivot.loc['TOTAL ANUAL'] = pivot.sum(axis=0)
            return pivot
            
        def aplicar_filtros_df(df_base, maq, mes, tip, crit):
            df_f = df_base.copy()
            if mes != "Resumen Total Anual": df_f = df_f[df_f["Mes_Texto"] == mes]
            if maq != "TOTAL PLANTA": df_f = df_f[df_f["MAQUINA"] == maq]
            if tip == "Mecánico (M)": df_f = df_f[df_f["Tipo"] == "M"]
            elif tip == "Eléctrico (E)": df_f = df_f[df_f["Tipo"] == "E"]
            if crit != "Todas": df_f = df_f[df_f["Criticidad"].astype(str) == crit]
            return df_f
            
        def renderizar_panel_y_grafico(kpi, prefix_key):
            st.markdown(f"##### ⚙️ Controles Panel {'Izquierdo' if 'izq' in prefix_key else 'Derecho'}")
            c1, c2 = st.columns(2)
            with c1: maq_sel = st.selectbox("Máquina:", ["TOTAL PLANTA"] + list(mapa_maquinas.keys()), key=f"maq_{prefix_key}")
            with c2: mes_sel = st.selectbox("Mes:", ["Resumen Total Anual"] + meses_presentes, key=f"mes_{prefix_key}")
            
            c3, c4 = st.columns(2)
            with c3: tip_sel = st.selectbox("Tipo de Falla:", ["Total (M+E)", "Mecánico (M)", "Eléctrico (E)"], key=f"tip_{prefix_key}")
            opciones_crit = ["Todas"] + sorted(list(df_mantenimiento["Criticidad"].astype(str).unique()))
            with c4: crit_sel = st.selectbox("Criticidad:", opciones_crit, key=f"crit_{prefix_key}")
            
            df_f = aplicar_filtros_df(df_mantenimiento, maq_sel, mes_sel, tip_sel, crit_sel)
            st.plotly_chart(crear_grafico_pareto(df_f, kpi, f"PARETO - {maq_sel}"), use_container_width=True, key=f"chart_{prefix_key}")

        td_total = generar_tabla_dinamica(df_mantenimiento)
        td_elec = generar_tabla_dinamica(df_mantenimiento[df_mantenimiento['Tipo'] == 'E'])
        td_meca = generar_tabla_dinamica(df_mantenimiento[df_mantenimiento['Tipo'] == 'M'])
        
        df_hp = df_horas.groupby('Mes')[list(mapa_maquinas.values())].sum()
        df_hp = df_hp.reindex([m for m in orden_meses if m in df_hp.index])
        df_hp['TOTAL PLANTA (Hrs)'] = df_hp.sum(axis=1)
        df_hp.loc['TOTAL ANUAL'] = df_hp.sum(axis=0)

        # ==========================================
        # SISTEMA DE NAVEGACIÓN POR PESTAÑAS
        # ==========================================
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard General", "📈 Análisis Pareto", "🗃️ Tablas de Cálculos", "⏱️ Historial (M y E)"])
        
        with tab1:
            st.markdown("### 1. Indisponibilidad de Equipos")
            col_ind_1, _, col_ind_2 = st.columns([1, 0.05, 1])
            with col_ind_1: st.plotly_chart(crear_grafico_agrupado(dfs_graficos["TOTAL PLANTA"], "INDISPONIBILIDAD - TOTAL PLANTA", "Indisponibilidad (%)"), use_container_width=True, key="chart_indisp_planta")
            with col_ind_2: st.plotly_chart(crear_grafico_agrupado(dfs_graficos[maquina_seleccionada], f"INDISPONIBILIDAD - {maquina_seleccionada}", "Indisponibilidad (%)"), use_container_width=True, key="chart_indisp_maq")
            st.markdown("---")
            st.markdown("### 2. Eficiencia de Mantenimiento y Confiabilidad (MTTR & MTBF)")
            col_m_1, _, col_m_2 = st.columns([1, 0.05, 1])
            with col_m_1:
                sel_mttr = st.selectbox("🎯 Filtro para gráfico de MTTR:", ["TOTAL PLANTA"] + list(mapa_maquinas.keys()), key="sel_mttr")
                st.plotly_chart(crear_grafico_agrupado(dfs_graficos[sel_mttr], f"MTTR - {sel_mttr}", "MTTR (Minutos)"), use_container_width=True, key="chart_mttr")
            with col_m_2:
                sel_mtbf = st.selectbox("🎯 Filtro para gráfico de MTBF:", ["TOTAL PLANTA"] + list(mapa_maquinas.keys()), key="sel_mtbf")
                st.plotly_chart(crear_grafico_agrupado(dfs_graficos[sel_mtbf], f"MTBF - {sel_mtbf}", "MTBF (Horas)"), use_container_width=True, key="chart_mtbf")

        with tab2:
            st.markdown("### 📈 Diagrama de Pareto por Sub-Equipos")
            st.markdown("---")
            
            st.markdown("#### ⏳ Pareto por Horas de Parada")
            col_p1, _, col_p2 = st.columns([1, 0.05, 1])
            with col_p1: renderizar_panel_y_grafico("Horas de Parada", "hrs_izq")
            with col_p2: renderizar_panel_y_grafico("Horas de Parada", "hrs_der")
            
            st.markdown("---")
            
            st.markdown("#### 🔧 Pareto por Cantidad de Averías")
            col_p3, _, col_p4 = st.columns([1, 0.05, 1])
            with col_p3: renderizar_panel_y_grafico("Cantidad de Averías", "ave_izq")
            with col_p4: renderizar_panel_y_grafico("Cantidad de Averías", "ave_der")
            
            st.markdown("---")
            
            st.markdown("### 🍩 Distribución de Fallas por Criticidad")
            c_pie1, c_pie2, c_pie3, _ = st.columns([1.5, 1.5, 1.5, 1.5])
            with c_pie1: pie_maq = st.selectbox("Filtro Máquina:", ["TOTAL PLANTA"] + list(mapa_maquinas.keys()), key="pie_maq")
            with c_pie2: pie_mes = st.selectbox("Filtro Mes:", ["Resumen Total Anual"] + meses_presentes, key="pie_mes")
            with c_pie3: pie_tip = st.selectbox("Filtro Tipo:", ["Total (M+E)", "Mecánico (M)", "Eléctrico (E)"], key="pie_tip")
            
            df_pie = aplicar_filtros_df(df_mantenimiento, pie_maq, pie_mes, pie_tip, "Todas")
            col_pie_l, col_pie_c, col_pie_r = st.columns([1, 3, 1])
            with col_pie_c:
                 st.plotly_chart(crear_grafico_pie(df_pie), use_container_width=True, key="pie_chart_crit")

        with tab3:
            st.markdown("### 📋 Matrices Resumen Gerencial")
            sel_matriz = st.radio("Selecciona la Matriz a visualizar:", ["Indisponibilidad (%)", "MTTR (Minutos)", "MTBF (Horas)"], horizontal=True)
            if sel_matriz == "Indisponibilidad (%)": st.dataframe(df_r_indisp.style.format("{:.2f}%"), use_container_width=True)
            elif sel_matriz == "MTTR (Minutos)": st.dataframe(df_r_mttr.style.format("{:.1f}"), use_container_width=True)
            else: st.dataframe(df_r_mtbf.style.format("{:.1f}"), use_container_width=True)
                
            st.markdown("---")
            st.markdown("### 🗃️ TD de detenciones de planta")
            st.markdown("#### 1. Total Planta (Mecánico + Eléctrico)")
            if not td_total.empty: st.dataframe(td_total.style.format("{:.2f}", subset=[c for c in td_total.columns if "(Hrs)" in c]), use_container_width=True)
            st.markdown("#### 2. Fallas Eléctricas (E)")
            if not td_elec.empty: st.dataframe(td_elec.style.format("{:.2f}", subset=[c for c in td_elec.columns if "(Hrs)" in c]), use_container_width=True)
            st.markdown("#### 3. Fallas Mecánicas (M)")
            if not td_meca.empty: st.dataframe(td_meca.style.format("{:.2f}", subset=[c for c in td_meca.columns if "(Hrs)" in c]), use_container_width=True)
            st.markdown("#### 4. Horas Programadas Utilizadas")
            st.dataframe(df_hp.style.format("{:.1f}"), use_container_width=True)

        with tab4:
            st.markdown("### ⏱️ Historial de Tiempos Filtrados")
            columnas_historial = [col for col in ["Fecha", "MAQUINA", "Nombre de Equipos", "Tipo", "Horas_Parada", "Criticidad", "Descripcion"] if col in df_mantenimiento.columns]
            st.dataframe(df_mantenimiento[columnas_historial], use_container_width=True)

        # ==========================================
        # BOTÓN DE DESCARGA EN LA BARRA LATERAL
        # ==========================================
        st.sidebar.markdown("### 📥 Exportación Completa")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_r_indisp.to_excel(writer, sheet_name='Resumen_Indisponibilidad')
            df_r_mttr.to_excel(writer, sheet_name='Resumen_MTTR')
            df_r_mtbf.to_excel(writer, sheet_name='Resumen_MTBF')
            dfs_graficos["TOTAL PLANTA"].to_excel(writer, sheet_name='Dashboard_Planta', index=False)
            dfs_graficos[maquina_seleccionada].to_excel(writer, sheet_name=f'Dashboard_{maquina_seleccionada}', index=False)
            td_total.to_excel(writer, sheet_name='TD_Total_Planta')
            td_elec.to_excel(writer, sheet_name='TD_Electrico')
            td_meca.to_excel(writer, sheet_name='TD_Mecanico')
            df_hp.to_excel(writer, sheet_name='Horas_Programadas')
            df_mantenimiento.to_excel(writer, sheet_name='Base_Filtrada_MyE', index=False)
            
        st.sidebar.download_button(
            label="📊 Descargar Excel",
            data=buffer.getvalue(),
            file_name=f"Calculos_Mantenimiento_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Error técnico: {e}")