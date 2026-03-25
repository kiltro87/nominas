import json
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from kpi_builder import build_all_kpis
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
from sheets_client import SheetsClient


def get_runtime_config() -> dict:
    cfg_path = Path("config.json")
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    if "GOOGLE_CREDENTIALS_JSON" in st.secrets and "SPREADSHEET_ID" in st.secrets:
        temp_creds = Path(tempfile.gettempdir()) / "streamlit_credentials.json"
        raw_secret: Any = st.secrets["GOOGLE_CREDENTIALS_JSON"]
        payload: Dict[str, Any]
        if isinstance(raw_secret, Mapping):
            payload = dict(raw_secret)
        else:
            raw_text = str(raw_secret).strip()
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                pattern = r'("private_key"\s*:\s*")(.*?)(")'
                match = re.search(pattern, raw_text, flags=re.DOTALL)
                if not match:
                    raise
                raw_key = match.group(2).replace("\\n", "\n")
                escaped_key = raw_key.replace("\\", "\\\\").replace("\n", "\\n")
                fixed = raw_text[: match.start(2)] + escaped_key + raw_text[match.end(2) :]
                payload = json.loads(fixed)

        if "private_key" in payload and isinstance(payload["private_key"], str):
            payload["private_key"] = payload["private_key"].replace("\r\n", "\n")

        temp_creds.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return {
            "credentials_path": str(temp_creds),
            "spreadsheet_id": str(st.secrets["SPREADSHEET_ID"]),
        }
    return {}


@st.cache_data(ttl=300)
def load_nominas_from_sheet() -> pd.DataFrame:
    cfg = get_runtime_config()
    if not cfg:
        return pd.DataFrame()
    try:
        client = SheetsClient(cfg["credentials_path"], cfg["spreadsheet_id"])
        values = client.get_all_values("Nominas")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo cargar 'Nominas' desde Google Sheets: {exc}")
        return pd.DataFrame()
    if len(values) < 2:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])


@st.cache_data(ttl=300)
def build_kpis_cached(df: pd.DataFrame):
    return build_all_kpis(df)


st.set_page_config(page_title="Análisis de Nóminas", layout="wide")
st.title("Análisis de Nóminas")
apply_app_styles()
hide_amounts = st.toggle(
    "Modo privacidad",
    value=False,
    help="Oculta importes monetarios en KPIs, tablas y graficas para compartir la pantalla.",
)

df_nominas = load_nominas_from_sheet()
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
