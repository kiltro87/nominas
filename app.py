import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from kpi_builder import build_all_kpis, format_eur
from sheets_client import SheetsClient


st.set_page_config(page_title="Procesador de Nóminas", layout="wide")
st.title("Procesador de Nóminas")
st.caption("Dashboard de nóminas alimentado automáticamente desde Drive -> Google Sheets")
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
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                # Fallback: algunos secretos llegan con saltos reales en private_key.
                # Re-escapa solo ese campo para convertirlo en JSON válido.
                pattern = r'("private_key"\s*:\s*")(.*?)(")'
                match = re.search(pattern, raw_text, flags=re.DOTALL)
                if not match:
                    raise
                raw_key = match.group(2).replace("\\n", "\n")
                escaped_key = raw_key.replace("\\", "\\\\").replace("\n", "\\n")
                fixed = raw_text[: match.start(2)] + escaped_key + raw_text[match.end(2) :]
                payload = json.loads(fixed)

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
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
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
        with filter_col2:
            period_option = st.selectbox(
                "Filtro de mes",
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
            st.line_chart(monthly_view.set_index("Periodo_natural")[["neto", "riqueza_real_mensual"]])
            st.line_chart(monthly_view.set_index("Periodo_natural")[["pct_irpf", "pct_ss"]])
        st.dataframe(
            annual_view[
                ["Año", "neto", "delta_neto_vs_anterior", "pct_crecimiento_neto_yoy", "pct_irpf_efectivo_anual", "delta_irpf_yoy"]
            ].rename(
                columns={
                    "Año": "Año",
                    "neto": "Neto anual",
                    "delta_neto_vs_anterior": "Delta neto vs año anterior",
                    "pct_crecimiento_neto_yoy": "% crecimiento neto YoY",
                    "pct_irpf_efectivo_anual": "% IRPF efectivo anual",
                    "delta_irpf_yoy": "Delta IRPF YoY",
                }
            ),
            use_container_width=True,
        )

        st.subheader("ESPP Gain por mes")
        if not espp_view.empty:
            st.dataframe(
                espp_view[["Periodo_natural", "espp_gain"]].rename(
                    columns={"Periodo_natural": "Periodo", "espp_gain": "ESPP Gain"}
                ),
                use_container_width=True,
            )
        else:
            st.dataframe(pd.DataFrame([{"Info": "Sin ESPP Gain registrado"}]), use_container_width=True)

        with st.expander("Detalle mensual completo"):
            st.dataframe(
                monthly_view.rename(
                    columns={
                        "Periodo_natural": "Periodo",
                        "neto": "Neto",
                        "total_devengado": "Total devengado",
                        "total_deducir": "Total a deducir",
                        "irpf_importe": "IRPF (€)",
                        "ss_importe": "Seguridad Social (€)",
                        "ahorro_fiscal": "Ahorro fiscal (€)",
                        "riqueza_real_mensual": "Riqueza real mensual (€)",
                        "pct_irpf": "% IRPF",
                        "pct_ss": "% SS",
                    }
                ),
                use_container_width=True,
            )

        with st.expander("Definiciones de métricas"):
            st.markdown(
                """
- `Riqueza real mensual = neto + ahorro_jub_empresa + rsu_neto_estimado + espp_neto_estimado`
- `Tipo marginal estimado = irpf_importe / total_devengado` (capado entre 0% y 60%)
- `% IRPF mensual = porcentaje informado en nómina (ej. 33,17%) si está disponible; si no, aproximación por ratio`
- `Ahorro fiscal = ingresos_libres_impuestos * tipo_marginal_estimado + ahorro_jub_empresa`
- `IRPF efectivo anual = irpf_importe_anual / total_devengado_anual`
                """
            )
else:
    st.info("No hay datos en la pestaña 'Nominas' o falta configuración de acceso a Google Sheets.")
