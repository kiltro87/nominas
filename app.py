import json
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

import altair as alt
import pandas as pd
import streamlit as st

from kpi_builder import build_all_kpis, format_eur
from sheets_client import SheetsClient


st.set_page_config(page_title="Análisis de Nóminas", layout="wide")
st.title("Análisis de Nóminas")
st.caption("Dashboard de nóminas alimentado automáticamente desde Drive -> Google Sheets")

hide_amounts = st.toggle("Modo privacidad: ocultar importes", value=False)


def show_eur(value: float) -> str:
    return "••••••" if hide_amounts else format_eur(float(value))


def apply_privacy_to_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: "••••••" if hide_amounts else format_eur(float(x)))
    return out


def draw_monthly_chart(df: pd.DataFrame, y_columns: list[str], title: str, percent_scale: bool = False) -> None:
    chart_df = df.copy()
    for c in y_columns:
        chart_df[c] = pd.to_numeric(chart_df[c], errors="coerce").fillna(0.0)
        if percent_scale:
            chart_df[c] = chart_df[c] * 100
    long_df = chart_df.melt(
        id_vars=["Periodo_natural"],
        value_vars=y_columns,
        var_name="Métrica",
        value_name="Valor",
    )
    order = chart_df["Periodo_natural"].tolist()
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Valor:Q", title="%" if percent_scale else "€"),
            color="Métrica:N",
            tooltip=["Periodo_natural:N", "Métrica:N", "Valor:Q"],
        )
        .properties(title=title)
    )
    st.altair_chart(chart, use_container_width=True)

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

        nominas_view = df_nominas.copy()
        nominas_view["Año"] = pd.to_numeric(nominas_view["Año"], errors="coerce")
        nominas_view["Mes"] = pd.to_numeric(nominas_view["Mes"], errors="coerce")
        nominas_view = nominas_view.dropna(subset=["Año", "Mes"]).copy()
        nominas_view["Año"] = nominas_view["Año"].astype(int)
        nominas_view["Mes"] = nominas_view["Mes"].astype(int)
        if year_option != "Todos":
            nominas_view = nominas_view[nominas_view["Año"] == int(year_option)].copy()
        if period_option != "Todos":
            p_year, p_month = period_option.split("-")
            nominas_view = nominas_view[
                (nominas_view["Año"] == int(p_year)) & (nominas_view["Mes"] == int(p_month))
            ].copy()
        nominas_view = nominas_view.sort_values(["Año", "Mes", "Concepto"]).reset_index(drop=True)

        monthly_title = "KPIs mensuales"
        if year_option == "Todos" and period_option == "Todos":
            monthly_title += " (último mes disponible)"
        st.subheader(monthly_title)
        m = monthly_view.sort_values(["Año", "Mes"]).iloc[-1]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Bruto mes", show_eur(float(m["total_devengado"])))
        c2.metric("% IRPF mes", f"{float(m['pct_irpf']) * 100:.2f}%")
        c3.metric("Neto mes", show_eur(float(m["neto"])))
        c4.metric("Consumo en especie", show_eur(float(m["consumo_especie"])))
        c5.metric("Riqueza real mensual", show_eur(float(m["riqueza_real_mensual"])))

        c6, c7, c8, c9 = st.columns(4)
        c6.metric("Ahorro fiscal mes", show_eur(float(m["ahorro_fiscal"])))
        c7.metric("Ahorro jub. empresa mes", show_eur(float(m["ahorro_jub_empresa"])))
        c8.metric("Ahorro jub. empleado mes", show_eur(float(m["ahorro_jub_empleado"])))
        c9.metric("Ingresos libres imp. mes", show_eur(float(m["ingresos_libres_impuestos"])))

        annual_title = "KPIs anuales"
        if year_option == "Todos":
            annual_title += " (último año disponible)"
        st.subheader(annual_title)
        y = annual_view.sort_values("Año").iloc[-1]
        a1, a2, a3, a4, a5 = st.columns(5)
        a1.metric("Bruto anual", show_eur(float(y["total_devengado"])))
        a2.metric("% IRPF efectivo anual", f"{float(y['pct_irpf_efectivo_anual']) * 100:.2f}%")
        a3.metric("Neto anual", show_eur(float(y["neto"])))
        a4.metric("ESPP Gain anual", show_eur(float(y["espp_gain"])))
        a5.metric("Riqueza real anual", show_eur(float(y["riqueza_real_anual"])))

        a6, a7, a8, a9, a10 = st.columns(5)
        a6.metric("Ahorro jubilación anual", show_eur(float(y["ahorro_jub_total"])))
        a7.metric("Ahorro fiscal anual", show_eur(float(y["ahorro_fiscal"])))
        a8.metric("Consumo en especie anual", show_eur(float(y["consumo_especie"])))
        a9.metric("Ingresos libres imp. anual", show_eur(float(y["ingresos_libres_impuestos"])))
        a10.metric("Bruto variable anual", show_eur(float(y["variable_ingreso"])))

        st.markdown("##### Jubilación, ESPP y RSU")
        grp1, grp2, grp3 = st.columns(3)
        with grp1:
            st.caption("Jubilación")
            st.metric("Aportación empresa", show_eur(float(y["ahorro_jub_empresa"])))
            st.metric("Aportación empleado", show_eur(float(y["ahorro_jub_empleado"])))
        with grp2:
            st.caption("ESPP")
            st.metric("ESPP bruto", show_eur(float(y["espp_gain"])))
            st.metric("ESPP neto estimado", show_eur(float(y["espp_neto_estimado"])))
        with grp3:
            st.caption("RSU")
            st.metric("RSU bruto", show_eur(float(y["rsu_gain"])))
            st.metric("RSU neto estimado", show_eur(float(y["rsu_neto_estimado"])))

        st.subheader("Comparativa y evolución")
        if year_option == "Todos" and period_option == "Todos":
            annual_amount_chart = annual_view[["Año", "total_devengado", "neto"]].copy()
            annual_amount_chart["ingresos_recibidos"] = (
                annual_view["neto"]
                + annual_view["consumo_especie"]
                + annual_view["ahorro_jub_total"]
                + annual_view["espp_neto_estimado"]
                + annual_view["rsu_neto_estimado"]
            )
            annual_amount_chart = annual_amount_chart.rename(
                columns={
                    "total_devengado": "Salario Bruto",
                    "neto": "Salario Neto",
                    "ingresos_recibidos": "Ingresos recibidos (incluyendo Tickets, pensión y acciones)",
                }
            )
            if hide_amounts:
                annual_amount_chart[
                    [
                        "Salario Bruto",
                        "Salario Neto",
                        "Ingresos recibidos (incluyendo Tickets, pensión y acciones)",
                    ]
                ] = 0.0
            st.line_chart(
                annual_amount_chart.set_index("Año")[
                    [
                        "Salario Bruto",
                        "Salario Neto",
                        "Ingresos recibidos (incluyendo Tickets, pensión y acciones)",
                    ]
                ]
            )
            annual_pct_chart = annual_view[["Año", "pct_irpf_efectivo_anual", "pct_ss_efectivo_anual"]].copy()
            annual_pct_chart["% IRPF efectivo anual"] = annual_pct_chart["pct_irpf_efectivo_anual"] * 100
            annual_pct_chart["% Seguridad Social anual"] = annual_pct_chart["pct_ss_efectivo_anual"] * 100
            st.line_chart(annual_pct_chart.set_index("Año")[["% IRPF efectivo anual", "% Seguridad Social anual"]])
        else:
            monthly_amount_chart = monthly_view[["Periodo_natural", "total_devengado", "neto"]].copy()
            monthly_amount_chart["ingresos_recibidos"] = (
                monthly_view["neto"]
                + monthly_view["consumo_especie"]
                + monthly_view["ahorro_jub_total"]
                + monthly_view["espp_neto_estimado"]
                + monthly_view["rsu_neto_estimado"]
            )
            monthly_amount_chart = monthly_amount_chart.rename(
                columns={
                    "total_devengado": "Salario Bruto",
                    "neto": "Salario Neto",
                    "ingresos_recibidos": "Ingresos recibidos (incluyendo Tickets, pensión y acciones)",
                }
            )
            if hide_amounts:
                monthly_amount_chart[
                    [
                        "Salario Bruto",
                        "Salario Neto",
                        "Ingresos recibidos (incluyendo Tickets, pensión y acciones)",
                    ]
                ] = 0.0
            draw_monthly_chart(
                monthly_amount_chart,
                ["Salario Bruto", "Salario Neto", "Ingresos recibidos (incluyendo Tickets, pensión y acciones)"],
                "Evolución salarial e ingresos recibidos",
            )
            draw_monthly_chart(monthly_view, ["pct_irpf", "pct_ss"], "Evolución mensual (% IRPF y % SS)", percent_scale=True)
        annual_table = annual_view[
            ["Año", "neto", "delta_neto_vs_anterior", "pct_crecimiento_neto_yoy", "pct_irpf_efectivo_anual", "delta_irpf_yoy"]
        ].copy()
        for col in ["pct_crecimiento_neto_yoy", "pct_irpf_efectivo_anual", "delta_irpf_yoy"]:
            annual_table[col] = (annual_table[col].astype(float) * 100).round(2)
        annual_table = apply_privacy_to_columns(annual_table, ["neto", "delta_neto_vs_anterior"])
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
            espp_table = espp_view[["Periodo_natural", "espp_gain"]].rename(
                columns={"Periodo_natural": "Periodo", "espp_gain": "ESPP Gain"}
            )
            espp_table = apply_privacy_to_columns(espp_table, ["ESPP Gain"])
            st.dataframe(espp_table, width="stretch")
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
                    }
                )
            for col in ["% IRPF", "% SS", "% variable"]:
                if col in detail_df.columns:
                    detail_df[col] = (detail_df[col].astype(float) * 100).round(2)
            detail_df = apply_privacy_to_columns(
                detail_df,
                [
                    "Neto",
                    "Total devengado",
                    "Total a deducir",
                    "IRPF (€)",
                    "Seguridad Social (€)",
                    "Ahorro fiscal (€)",
                    "Riqueza real mensual (€)",
                    "Ahorro jub. empresa (€)",
                    "Ahorro jub. empleado (€)",
                    "Ahorro jubilación total (€)",
                    "Ingresos libres impuestos (€)",
                    "ESPP Gain bruto (€)",
                    "ESPP neto estimado (€)",
                    "RSU Gain bruto (€)",
                    "RSU neto estimado (€)",
                    "Ingreso fijo (€)",
                    "Ingreso variable (€)",
                    "Beneficio en especie (€)",
                ],
            )
            st.dataframe(
                detail_df,
                width="stretch",
            )

        with st.expander("Desglose mensual"):
            breakdown = nominas_view.copy()
            breakdown["Concepto_agrupado"] = breakdown["Concepto"].astype(str)
            irpf_mask = breakdown["Concepto_agrupado"].str.upper().str.contains(r"^TRIBUTACION\\s+I\\.?R\\.?P\\.?F\\.?", regex=True)
            breakdown.loc[irpf_mask, "Concepto_agrupado"] = "TRIBUTACION I.R.P.F."
            breakdown["Importe_num"] = pd.to_numeric(
                breakdown["Importe"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                errors="coerce",
            ).fillna(0.0)
            breakdown["Periodo"] = (
                breakdown["Año"].astype(int).astype(str) + "-" + breakdown["Mes"].astype(int).astype(str).str.zfill(2)
            )

            if period_option == "Todos":
                month_order = monthly_view["Periodo"].drop_duplicates().tolist()
            else:
                month_order = [period_option]

            pivot = (
                breakdown.pivot_table(
                    index="Concepto_agrupado",
                    columns="Periodo",
                    values="Importe_num",
                    aggfunc="sum",
                    fill_value=0.0,
                )
                .reindex(columns=month_order, fill_value=0.0)
                .reset_index()
            )
            pivot = pivot.rename(columns={"Concepto_agrupado": "Concepto"})

            if hide_amounts:
                for col in [c for c in pivot.columns if c != "Concepto"]:
                    pivot[col] = "••••••"
            else:
                for col in [c for c in pivot.columns if c != "Concepto"]:
                    pivot[col] = pivot[col].apply(lambda x: format_eur(float(x)))

            st.dataframe(pivot, width="stretch")

        with st.expander("Definiciones de métricas"):
            st.markdown(
                """
- `Riqueza real mensual = neto + ahorro_jub_empresa + rsu_neto_estimado + espp_neto_estimado`
- `% IRPF mensual = porcentaje informado en nómina (ej. 33,17%) si está disponible; si no, aproximación por ratio`
- `Ahorro fiscal = ingresos_libres_impuestos * tipo marginal estimado (interno) + ahorro_jub_empresa`
- `Ingresos recibidos = neto + consumo_especie + ahorro_jub_total + espp_neto_estimado + rsu_neto_estimado`
- `IRPF efectivo anual = irpf_importe_anual / total_devengado_anual`
                """
            )
else:
    st.info("No hay datos en la pestaña 'Nominas' o falta configuración de acceso a Google Sheets.")
