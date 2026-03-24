import json
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from extractor import extract_payroll
from kpi_builder import build_all_kpis, format_eur
from sheets_client import SheetsClient


st.set_page_config(page_title="Procesador de Nóminas", layout="wide")
st.title("Procesador de Nóminas")
st.caption("Extracción automática de conceptos y carga preparada para Google Sheets")

uploaded = st.file_uploader("Sube una o más nóminas PDF", type=["pdf"], accept_multiple_files=True)

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if st.button("Procesar Nóminas Nuevas", type="primary"):
    if not uploaded:
        st.warning("Primero sube al menos una nómina PDF.")
    else:
        latest = uploaded[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(latest.getbuffer())
            temp_path = Path(tmp.name)

        try:
            result = extract_payroll(str(temp_path))
            st.session_state.last_result = result
            st.success(f"Nómina procesada correctamente: {latest.name}")
        except Exception as exc:
            st.error(f"Error al procesar la nómina: {exc}")

result = st.session_state.last_result
def get_runtime_config() -> dict:
    # Prioridad 1: config local (desarrollo)
    cfg_path = Path("config.json")
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    # Prioridad 2: Streamlit Cloud secrets
    if "GOOGLE_CREDENTIALS_JSON" in st.secrets and "SPREADSHEET_ID" in st.secrets:
        temp_creds = Path(tempfile.gettempdir()) / "streamlit_credentials.json"
        raw_secret: Any = st.secrets["GOOGLE_CREDENTIALS_JSON"]
        payload: Dict[str, Any]

        # Soporta secret como objeto TOML o como string JSON.
        if isinstance(raw_secret, Mapping):
            payload = dict(raw_secret)
        else:
            raw_text = str(raw_secret).strip()
            payload = json.loads(raw_text)

        # Evita JSON inválido si private_key llega con saltos no escapados.
        if "private_key" in payload and isinstance(payload["private_key"], str):
            payload["private_key"] = payload["private_key"].replace("\r\n", "\n")

        temp_creds.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return {
            "credentials_path": str(temp_creds),
            "spreadsheet_id": str(st.secrets["SPREADSHEET_ID"]),
        }
    return {}


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
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


df_nominas = load_nominas_from_sheet()

if not df_nominas.empty:
    monthly, annual, espp_months = build_all_kpis(df_nominas)
    if monthly.empty or annual.empty:
        st.info("No hay suficientes datos para construir KPIs agregados todavía.")
    else:
        available_years = sorted(int(y) for y in monthly["Año"].unique())
        year_option = st.selectbox(
            "Filtro de año",
            options=["Todos"] + available_years,
            index=0,
            help="Selecciona un año para centrar KPIs y evolución mensual.",
        )
        if year_option == "Todos":
            monthly_view = monthly.copy()
            annual_view = annual.copy()
            espp_view = espp_months.copy()
        else:
            selected_year = int(year_option)
            monthly_view = monthly[monthly["Año"] == selected_year].copy()
            annual_view = annual[annual["Año"] == selected_year].copy()
            espp_view = espp_months[espp_months["Año"] == selected_year].copy()

        period_options = ["Todos"] + monthly_view["Periodo"].drop_duplicates().sort_values().tolist()
        period_option = st.selectbox(
            "Filtro de mes (Periodo)",
            options=period_options,
            index=0,
            help="Opcional: filtra un mes concreto dentro del año seleccionado.",
        )
        if period_option != "Todos":
            monthly_view = monthly_view[monthly_view["Periodo"] == period_option].copy()
            espp_view = espp_view[espp_view["Periodo"] == period_option].copy()

        st.subheader("KPIs mensuales (último mes)")
        m = monthly_view.sort_values(["Año", "Mes"]).iloc[-1]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Neto mes", format_eur(float(m["neto"])))
        c2.metric("% IRPF mes", f"{float(m['pct_irpf']) * 100:.2f}%")
        c3.metric("Ahorro fiscal mes", format_eur(float(m["ahorro_fiscal"])))
        c4.metric("Consumo en especie", format_eur(float(m["consumo_especie"])))
        c5.metric("Riqueza real mensual", format_eur(float(m["riqueza_real_mensual"])))

        st.subheader("KPIs anuales (último año)")
        y = annual_view.sort_values("Año").iloc[-1]
        a1, a2, a3, a4, a5 = st.columns(5)
        a1.metric("Neto anual", format_eur(float(y["neto"])))
        a2.metric("% IRPF efectivo anual", f"{float(y['pct_irpf_efectivo_anual']) * 100:.2f}%")
        a3.metric("Ahorro jubilación anual", format_eur(float(y["ahorro_jub_total"])))
        a4.metric("ESPP Gain anual", format_eur(float(y["espp_gain"])))
        a5.metric("Riqueza real anual", format_eur(float(y["riqueza_real_anual"])))

        st.subheader("Comparativa y evolución")
        if year_option == "Todos" and period_option == "Todos":
            st.line_chart(annual_view.set_index("Año")[["neto", "riqueza_real_anual"]])
            st.line_chart(annual_view.set_index("Año")[["pct_irpf_efectivo_anual", "pct_ss_efectivo_anual"]])
        else:
            st.line_chart(monthly_view.set_index("Periodo")[["neto", "riqueza_real_mensual"]])
            st.line_chart(monthly_view.set_index("Periodo")[["pct_irpf", "pct_ss"]])
        st.dataframe(
            annual_view[
                [
                    "Año",
                    "neto",
                    "delta_neto_vs_anterior",
                    "pct_crecimiento_neto_yoy",
                    "pct_irpf_efectivo_anual",
                    "delta_irpf_yoy",
                ]
            ],
            use_container_width=True,
        )

        st.subheader("ESPP Gain por mes")
        st.dataframe(espp_view if not espp_view.empty else pd.DataFrame([{"info": "Sin ESPP Gain registrado"}]))

        with st.expander("Detalle mensual completo"):
            st.dataframe(monthly_view, use_container_width=True)

        with st.expander("Definiciones de métricas"):
            st.markdown(
                """
- `Riqueza real mensual = neto + ahorro_jub_empresa + rsu_neto_estimado + espp_neto_estimado`
- `Tipo marginal estimado = irpf_importe / total_devengado` (capado entre 0% y 60%)
- `Ahorro fiscal = ingresos_libres_impuestos * tipo_marginal_estimado + ahorro_jub_empresa`
- `IRPF efectivo anual = irpf_importe_anual / total_devengado_anual`
                """
            )

if result:
    totals = result["totales"]
    sheet_rows = result["sheet_rows"]
    df = pd.DataFrame(sheet_rows)
    st.subheader("Última nómina procesada manualmente")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total devengado", format_eur(float(totals["total_devengado"])))
    c2.metric("Total a deducir", format_eur(float(totals["total_deducir"])))
    c3.metric("Neto calculado", format_eur(float(totals["neto_calculado"])))
    c4.metric("Validación neto", "OK" if totals["validacion_neto"] else "No cuadra")
    st.dataframe(df[["Año", "Mes", "Concepto", "Importe", "Categoría", "Subcategoría"]], use_container_width=True)
else:
    if df_nominas.empty:
        st.info("No hay datos en la pestaña 'Nominas' o falta config. Puedes subir una nómina y procesarla aquí.")
