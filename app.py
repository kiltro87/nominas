import pandas as pd
import streamlit as st

from kpi_builder import build_all_kpis
from nominas.services.config_loader import load_nominas_from_sheet
from nominas.services.dashboard_data import (
    build_nominas_view,
    build_quality_alerts,
    filter_kpi_views,
)
from nominas.ui.cards import render_annual_kpis_card, render_monthly_kpis_card
from nominas.ui.charts import render_comparison_charts
from nominas.ui.quality import render_metric_definitions, render_quality_sections
from nominas.ui.style import apply_app_styles
from nominas.ui.tables import render_breakdown, render_monthly_detail


@st.cache_data(ttl=300)
def build_kpis_cached(df: pd.DataFrame):
    return build_all_kpis(df)


@st.cache_data(ttl=300)
def load_nominas_cached() -> pd.DataFrame:
    return load_nominas_from_sheet()


st.set_page_config(page_title="Análisis de Nóminas", layout="wide")
st.title("Análisis de Nóminas")
apply_app_styles()
hide_amounts = st.toggle(
    "Modo privacidad",
    value=False,
    help="Oculta importes monetarios en KPIs, tablas y graficas para compartir la pantalla.",
)

df_nominas = load_nominas_cached()
if df_nominas.empty:
    st.info("No hay datos en la pestaña 'Nominas' o falta configuración de acceso a Google Sheets.")
    st.stop()

monthly, annual, _ = build_kpis_cached(df_nominas)
if monthly.empty or annual.empty:
    st.info("No hay suficientes datos para construir KPIs agregados todavía.")
    st.stop()

monthly = monthly.sort_values(["Año", "Mes"]).reset_index(drop=True)
annual = annual.sort_values(["Año"]).reset_index(drop=True)

available_years = sorted(int(y) for y in monthly["Año"].unique())
filter_col1, filter_col2, filter_col3 = st.columns(3)
with filter_col1:
    year_option = st.selectbox(
        "Filtro de año",
        options=["Todos"] + available_years,
        index=0,
        help="Selecciona un año para centrar KPIs y evolución mensual.",
    )

if year_option == "Todos":
    month_scope = monthly.copy()
else:
    month_scope = monthly[monthly["Año"] == int(year_option)].copy()
period_options = ["Todos"] + month_scope["Periodo"].drop_duplicates().sort_values().tolist()
with filter_col2:
    period_option = st.selectbox(
        "Filtro de mes",
        options=period_options,
        index=0,
        help="Opcional: filtra un mes concreto dentro del año seleccionado.",
    )
with filter_col3:
    compare_mode = st.selectbox(
        "Comparar contra",
        options=["Sin comparación", "Mes anterior", "Mismo mes año anterior"],
        index=0,
        help="Aplica al bloque de KPIs mensuales.",
    )

views = filter_kpi_views(monthly=monthly, annual=annual, year_option=year_option, period_option=period_option)
monthly_view = views.monthly_view
annual_view = views.annual_view
monthly_year_scope = views.monthly_year_scope
nominas_view = build_nominas_view(df_nominas, year_option=year_option, period_option=period_option)

alertas, quality_rows = build_quality_alerts(
    monthly_view=monthly_view,
    monthly_year_scope=monthly_year_scope,
    year_option=year_option,
    period_option=period_option,
)
if alertas:
    st.warning(" | ".join(alertas))

render_monthly_kpis_card(
    monthly_view=monthly_view,
    monthly=monthly,
    year_option=year_option,
    period_option=period_option,
    compare_mode=compare_mode,
    raw_nominas=df_nominas,
    hide_amounts=hide_amounts,
)
render_annual_kpis_card(
    annual_view=annual_view,
    monthly=monthly,
    monthly_view=monthly_view,
    year_option=year_option,
    hide_amounts=hide_amounts,
)
render_comparison_charts(
    annual_view=annual_view,
    monthly_view=monthly_view,
    year_option=year_option,
    period_option=period_option,
    hide_amounts=hide_amounts,
)
render_monthly_detail(monthly_view=monthly_view, hide_amounts=hide_amounts)
render_breakdown(
    nominas_view=nominas_view,
    monthly_view=monthly_view,
    period_option=period_option,
    hide_amounts=hide_amounts,
)
render_quality_sections(
    quality_rows=quality_rows,
    nominas_view=nominas_view,
    monthly=monthly,
)
render_metric_definitions()
