import json
import re
import tempfile
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
        monthly = monthly.sort_values(["Año", "Mes"]).reset_index(drop=True)
        annual = annual.sort_values(["Año"]).reset_index(drop=True)
        espp_months = espp_months.sort_values(["Año", "Mes"]).reset_index(drop=True)

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

        monthly_view = monthly_view.sort_values(["Año", "Mes"]).reset_index(drop=True)
        annual_view = annual_view.sort_values(["Año"]).reset_index(drop=True)
        espp_view = espp_view.sort_values(["Año", "Mes"]).reset_index(drop=True)

        st.subheader("KPIs mensuales (último mes)")
        m = monthly_view.sort_values(["Año", "Mes"]).iloc[-1]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Bruto mes", format_eur(float(m["total_devengado"])))
        c2.metric("% IRPF mes", f"{float(m['pct_irpf']) * 100:.2f}%")
        c3.metric("Neto mes", format_eur(float(m["neto"])))
        c4.metric("Consumo en especie", format_eur(float(m["consumo_especie"])))
        c5.metric("Riqueza real mensual", format_eur(float(m["riqueza_real_mensual"])))

        c6, c7, c8, c9, c10 = st.columns(5)
        c6.metric("Ahorro fiscal mes", format_eur(float(m["ahorro_fiscal"])))
        c7.metric("Ahorro jub. empresa mes", format_eur(float(m["ahorro_jub_empresa"])))
        c8.metric("Ahorro jub. empleado mes", format_eur(float(m["ahorro_jub_empleado"])))
        c9.metric("Ingresos libres imp. mes", format_eur(float(m["ingresos_libres_impuestos"])))
        c10.metric("Tipo marginal estimado", f"{float(m['tipo_marginal_estimado']) * 100:.2f}%")

        st.subheader("KPIs anuales (último año)")
        y = annual_view.sort_values("Año").iloc[-1]
        a1, a2, a3, a4, a5 = st.columns(5)
        a1.metric("Bruto anual", format_eur(float(y["total_devengado"])))
        a2.metric("% IRPF efectivo anual", f"{float(y['pct_irpf_efectivo_anual']) * 100:.2f}%")
        a3.metric("Neto anual", format_eur(float(y["neto"])))
        a4.metric("ESPP Gain anual", format_eur(float(y["espp_gain"])))
        a5.metric("Riqueza real anual", format_eur(float(y["riqueza_real_anual"])))

        a6, a7, a8, a9, a10 = st.columns(5)
        a6.metric("Ahorro jubilación anual", format_eur(float(y["ahorro_jub_total"])))
        a7.metric("Ahorro fiscal anual", format_eur(float(y["ahorro_fiscal"])))
        a8.metric("Consumo en especie anual", format_eur(float(y["consumo_especie"])))
        a9.metric("Ingresos libres imp. anual", format_eur(float(y["ingresos_libres_impuestos"])))
        a10.metric("Bruto variable anual", format_eur(float(y["variable_ingreso"])))

        st.subheader("Comparativa y evolución")
        if year_option == "Todos" and period_option == "Todos":
            st.line_chart(annual_view.set_index("Año")[["neto", "riqueza_real_anual"]])
            annual_pct_chart = annual_view[["Año", "pct_irpf_efectivo_anual", "pct_ss_efectivo_anual"]].copy()
            annual_pct_chart["% IRPF efectivo anual"] = annual_pct_chart["pct_irpf_efectivo_anual"] * 100
            annual_pct_chart["% Seguridad Social anual"] = annual_pct_chart["pct_ss_efectivo_anual"] * 100
            st.line_chart(annual_pct_chart.set_index("Año")[["% IRPF efectivo anual", "% Seguridad Social anual"]])
        else:
            st.line_chart(monthly_view.set_index("Periodo_natural")[["neto", "riqueza_real_mensual"]])
            monthly_pct_chart = monthly_view[["Periodo_natural", "pct_irpf", "pct_ss"]].copy()
            monthly_pct_chart["% IRPF mensual"] = monthly_pct_chart["pct_irpf"] * 100
            monthly_pct_chart["% Seguridad Social mensual"] = monthly_pct_chart["pct_ss"] * 100
            st.line_chart(monthly_pct_chart.set_index("Periodo_natural")[["% IRPF mensual", "% Seguridad Social mensual"]])
        annual_table = annual_view[
            ["Año", "neto", "delta_neto_vs_anterior", "pct_crecimiento_neto_yoy", "pct_irpf_efectivo_anual", "delta_irpf_yoy"]
        ].copy()
        for col in ["pct_crecimiento_neto_yoy", "pct_irpf_efectivo_anual", "delta_irpf_yoy"]:
            annual_table[col] = (annual_table[col].astype(float) * 100).round(2)
        st.dataframe(
            annual_table.rename(
                columns={
                    "Año": "Año",
                    "neto": "Neto anual",
                    "delta_neto_vs_anterior": "Delta neto vs año anterior",
                    "pct_crecimiento_neto_yoy": "% crecimiento neto YoY",
                    "pct_irpf_efectivo_anual": "% IRPF efectivo anual",
                    "delta_irpf_yoy": "Delta IRPF YoY (pp)",
                }
            ),
            width="stretch",
        )

        st.subheader("ESPP Gain por mes")
        if not espp_view.empty:
            st.dataframe(
                espp_view[["Periodo_natural", "espp_gain"]].rename(
                    columns={"Periodo_natural": "Periodo", "espp_gain": "ESPP Gain"}
                ),
                width="stretch",
            )
        else:
            st.dataframe(pd.DataFrame([{"Info": "Sin ESPP Gain registrado"}]), width="stretch")

        with st.expander("Detalle mensual completo"):
            detail_cols = [
                "Año",
                "Mes",
                "Periodo_natural",
                "neto",
                "total_devengado",
                "total_deducir",
                "irpf_importe",
                "ss_importe",
                "ahorro_fiscal",
                "riqueza_real_mensual",
                "ahorro_jub_empresa",
                "ahorro_jub_empleado",
                "ahorro_jub_total",
                "ingresos_libres_impuestos",
                "espp_gain",
                "espp_neto_estimado",
                "rsu_gain",
                "rsu_neto_estimado",
                "fijo_ingreso",
                "variable_ingreso",
                "beneficio_especie",
                "pct_irpf",
                "pct_ss",
                "pct_variable",
                "tipo_marginal_estimado",
            ]
            detail_df = monthly_view[detail_cols].rename(
                    columns={
                        "Periodo_natural": "Periodo",
                        "neto": "Neto",
                        "total_devengado": "Total devengado",
                        "total_deducir": "Total a deducir",
                        "irpf_importe": "IRPF (€)",
                        "ss_importe": "Seguridad Social (€)",
                        "ahorro_fiscal": "Ahorro fiscal (€)",
                        "riqueza_real_mensual": "Riqueza real mensual (€)",
                        "ahorro_jub_empresa": "Ahorro jub. empresa (€)",
                        "ahorro_jub_empleado": "Ahorro jub. empleado (€)",
                        "ahorro_jub_total": "Ahorro jubilación total (€)",
                        "ingresos_libres_impuestos": "Ingresos libres impuestos (€)",
                        "espp_gain": "ESPP Gain bruto (€)",
                        "espp_neto_estimado": "ESPP neto estimado (€)",
                        "rsu_gain": "RSU Gain bruto (€)",
                        "rsu_neto_estimado": "RSU neto estimado (€)",
                        "fijo_ingreso": "Ingreso fijo (€)",
                        "variable_ingreso": "Ingreso variable (€)",
                        "beneficio_especie": "Beneficio en especie (€)",
                        "pct_irpf": "% IRPF",
                        "pct_ss": "% SS",
                        "pct_variable": "% variable",
                        "tipo_marginal_estimado": "Tipo marginal estimado",
                    }
                )
            for col in ["% IRPF", "% SS", "% variable", "Tipo marginal estimado"]:
                if col in detail_df.columns:
                    detail_df[col] = (detail_df[col].astype(float) * 100).round(2)
            st.dataframe(
                detail_df,
                width="stretch",
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
