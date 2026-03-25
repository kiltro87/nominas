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
compact_mode = st.toggle("Modo compacto", value=False)

METRIC_HELP: dict[str, str] = {
    "Bruto mes": "Suma de devengos netos del mes.",
    "% IRPF mes": "Porcentaje de IRPF informado en nómina (si existe) o ratio IRPF/Bruto del mes.",
    "Neto mes": "Bruto del mes menos total a deducir del mes.",
    "Consumo en especie": "Consumo asociado a conceptos en especie (tickets, seguros, fitness, etc.).",
    "Riqueza real mensual": "Neto + aportación empresa a jubilación + netos estimados de RSU y ESPP.",
    "Ahorro fiscal mes": "Ingresos libres de impuestos multiplicados por tipo marginal estimado + aportación empresa a jubilación.",
    "Ahorro jub. empresa mes": "Aportación de empresa al plan de pensiones en el mes.",
    "Ahorro jub. empleado mes": "Aportación del empleado al plan de pensiones en el mes.",
    "Ingresos libres imp. mes": "Importes del mes marcados como exentos o no sujetos a IRPF.",
    "Bruto anual": "Suma anual de devengos netos.",
    "% IRPF efectivo anual": "IRPF anual / Bruto anual.",
    "Neto anual": "Bruto anual menos total anual a deducir.",
    "ESPP Gain anual": "Ganancia bruta anual identificada como ESPP.",
    "Riqueza real anual": "Suma anual de riqueza real mensual.",
    "Ahorro jubilación anual": "Aportación anual total (empresa + empleado) a jubilación.",
    "Ahorro fiscal anual": "Suma anual del ahorro fiscal estimado.",
    "Consumo en especie anual": "Suma anual del consumo en especie.",
    "Ingresos libres imp. anual": "Suma anual de ingresos libres de impuestos.",
    "Bruto variable anual": "Suma anual de ingresos variables brutos.",
    "Aportación empresa": "Aportación anual de la empresa al plan de pensiones.",
    "Aportación empleado": "Aportación anual del empleado al plan de pensiones.",
    "ESPP bruto": "Ganancia bruta anual de ESPP.",
    "ESPP neto estimado": "ESPP bruto ajustado por tipo marginal estimado.",
    "RSU bruto": "Ganancia bruta anual de RSU/stock options.",
    "RSU neto estimado": "RSU bruto ajustado por tipo marginal estimado.",
}


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


def metric_with_help(container: Any, label: str, value: str, delta: str | None = None) -> None:
    help_text = METRIC_HELP.get(label)
    try:
        if delta is None:
            container.metric(label, value, help=help_text)
        else:
            container.metric(label, value, delta=delta, help=help_text)
    except TypeError:
        if delta is None:
            container.metric(label, value)
        else:
            container.metric(label, value, delta=delta)


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
    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)


df_nominas = load_nominas_from_sheet()

if not df_nominas.empty:
    @st.cache_data(ttl=300)
    def build_kpis_cached(df: pd.DataFrame):
        return build_all_kpis(df)

    monthly, annual, espp_months = build_kpis_cached(df_nominas)
    if monthly.empty or annual.empty:
        st.info("No hay suficientes datos para construir KPIs agregados todavía.")
    else:
        monthly = monthly.sort_values(["Año", "Mes"]).reset_index(drop=True)
        annual = annual.sort_values(["Año"]).reset_index(drop=True)
        espp_months = espp_months.sort_values(["Año", "Mes"]).reset_index(drop=True)

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
        with filter_col3:
            compare_mode = st.selectbox(
                "Comparar contra",
                options=["Sin comparación", "Mes anterior", "Mismo mes año anterior"],
                index=0,
                help="Aplica al bloque de KPIs mensuales.",
            )
        if period_option != "Todos":
            monthly_view = monthly_view[monthly_view["Periodo"] == period_option].copy()
            espp_view = espp_view[espp_view["Periodo"] == period_option].copy()

        monthly_view = monthly_view.sort_values(["Año", "Mes"]).reset_index(drop=True)
        annual_view = annual_view.sort_values(["Año"]).reset_index(drop=True)
        espp_view = espp_view.sort_values(["Año", "Mes"]).reset_index(drop=True)

        # Alertas rápidas de calidad (visibles arriba del dashboard)
        alertas: list[str] = []
        if (monthly_view["neto"] < 0).any():
            bad_periods = monthly_view.loc[monthly_view["neto"] < 0, "Periodo_natural"].tolist()
            alertas.append(f"Neto mensual negativo en: {', '.join(bad_periods)}")
        if (monthly_view["pct_irpf"] > 0.60).any():
            high_periods = monthly_view.loc[monthly_view["pct_irpf"] > 0.60, "Periodo_natural"].tolist()
            alertas.append(f"% IRPF mensual > 60% en: {', '.join(high_periods)}")
        if year_option != "Todos":
            months_present = set(monthly_view["Mes"].astype(int).tolist())
            expected = set(range(1, 13))
            missing = sorted(expected - months_present)
            if missing:
                alertas.append(f"Faltan meses en el año seleccionado: {', '.join(str(m) for m in missing)}")
        if alertas:
            st.warning(" | ".join(alertas))
        quality_rows: list[dict[str, str]] = []
        for _, row in monthly_view.iterrows():
            periodo = str(row["Periodo_natural"])
            if float(row["neto"]) < 0:
                quality_rows.append({"Periodo": periodo, "Alerta": "Neto mensual negativo", "Detalle": format_eur(float(row["neto"]))})
            if float(row["pct_irpf"]) > 0.60:
                quality_rows.append({"Periodo": periodo, "Alerta": "% IRPF mensual > 60%", "Detalle": f"{float(row['pct_irpf']) * 100:.2f}%"})

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
        # Comparador de periodos para tarjetas mensuales
        monthly_all = monthly.sort_values(["Año", "Mes"]).reset_index(drop=True)
        cur_year, cur_month = int(m["Año"]), int(m["Mes"])
        cmp_row = None
        if compare_mode == "Mes anterior":
            prev = monthly_all[(monthly_all["Año"] < cur_year) | ((monthly_all["Año"] == cur_year) & (monthly_all["Mes"] < cur_month))]
            if not prev.empty:
                cmp_row = prev.iloc[-1]
        elif compare_mode == "Mismo mes año anterior":
            prev = monthly_all[(monthly_all["Año"] == cur_year - 1) & (monthly_all["Mes"] == cur_month)]
            if not prev.empty:
                cmp_row = prev.iloc[-1]
        delta_label = None
        if cmp_row is not None:
            delta_label = f"vs {cmp_row['Periodo_natural']}"
            st.caption(delta_label)
        c1, c2, c3, c4, c5 = st.columns(5)
        if cmp_row is not None:
            metric_with_help(c1, "Bruto mes", show_eur(float(m["total_devengado"])), delta=format_eur(float(m["total_devengado"] - cmp_row["total_devengado"])))
            metric_with_help(c2, "% IRPF mes", f"{float(m['pct_irpf']) * 100:.2f}%", delta=f"{(float(m['pct_irpf']) - float(cmp_row['pct_irpf'])) * 100:.2f} pp")
            metric_with_help(c3, "Neto mes", show_eur(float(m["neto"])), delta=format_eur(float(m["neto"] - cmp_row["neto"])))
        else:
            metric_with_help(c1, "Bruto mes", show_eur(float(m["total_devengado"])))
            metric_with_help(c2, "% IRPF mes", f"{float(m['pct_irpf']) * 100:.2f}%")
            metric_with_help(c3, "Neto mes", show_eur(float(m["neto"])))
        metric_with_help(c4, "Consumo en especie", show_eur(float(m["consumo_especie"])))
        metric_with_help(c5, "Riqueza real mensual", show_eur(float(m["riqueza_real_mensual"])))

        c6, c7, c8, c9 = st.columns(4)
        metric_with_help(c6, "Ahorro fiscal mes", show_eur(float(m["ahorro_fiscal"])))
        metric_with_help(c7, "Ahorro jub. empresa mes", show_eur(float(m["ahorro_jub_empresa"])))
        metric_with_help(c8, "Ahorro jub. empleado mes", show_eur(float(m["ahorro_jub_empleado"])))
        metric_with_help(c9, "Ingresos libres imp. mes", show_eur(float(m["ingresos_libres_impuestos"])))

        if cmp_row is not None:
            with st.expander("Explicar delta (Top 5 conceptos)"):
                raw_comp = df_nominas.copy()
                raw_comp["Año"] = pd.to_numeric(raw_comp["Año"], errors="coerce")
                raw_comp["Mes"] = pd.to_numeric(raw_comp["Mes"], errors="coerce")
                raw_comp["Importe_num"] = pd.to_numeric(
                    raw_comp["Importe"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                    errors="coerce",
                ).fillna(0.0)
                cur_rows = raw_comp[(raw_comp["Año"] == cur_year) & (raw_comp["Mes"] == cur_month)].copy()
                prev_rows = raw_comp[
                    (raw_comp["Año"] == int(cmp_row["Año"])) & (raw_comp["Mes"] == int(cmp_row["Mes"]))
                ].copy()
                for frame in (cur_rows, prev_rows):
                    frame["Concepto_agrupado"] = frame["Concepto"].astype(str)
                    irpf_mask = frame["Concepto_agrupado"].str.upper().str.contains(
                        r"^TRIBUTACION\s+I\.?R\.?P\.?F\.?", regex=True
                    )
                    frame.loc[irpf_mask, "Concepto_agrupado"] = "TRIBUTACION I.R.P.F."
                cur_agg = cur_rows.groupby("Concepto_agrupado", as_index=False)["Importe_num"].sum().rename(
                    columns={"Importe_num": "Actual"}
                )
                prev_agg = prev_rows.groupby("Concepto_agrupado", as_index=False)["Importe_num"].sum().rename(
                    columns={"Importe_num": "Comparado"}
                )
                explain = cur_agg.merge(prev_agg, on="Concepto_agrupado", how="outer").fillna(0.0)
                explain["Delta"] = explain["Actual"] - explain["Comparado"]
                explain = explain.sort_values("Delta", ascending=False, key=lambda s: s.abs()).head(5)
                explain = explain.rename(columns={"Concepto_agrupado": "Concepto"})
                if hide_amounts:
                    for col in ["Actual", "Comparado", "Delta"]:
                        explain[col] = "••••••"
                else:
                    for col in ["Actual", "Comparado", "Delta"]:
                        explain[col] = explain[col].apply(lambda x: format_eur(float(x)))
                st.dataframe(explain, width="stretch")

        annual_title = "KPIs anuales"
        if year_option == "Todos":
            annual_title += " (último año disponible)"
        st.subheader(annual_title)
        y = annual_view.sort_values("Año").iloc[-1]
        a1, a2, a3, a4, a5 = st.columns(5)
        metric_with_help(a1, "Bruto anual", show_eur(float(y["total_devengado"])))
        metric_with_help(a2, "% IRPF efectivo anual", f"{float(y['pct_irpf_efectivo_anual']) * 100:.2f}%")
        metric_with_help(a3, "Neto anual", show_eur(float(y["neto"])))
        metric_with_help(a4, "ESPP Gain anual", show_eur(float(y["espp_gain"])))
        metric_with_help(a5, "Riqueza real anual", show_eur(float(y["riqueza_real_anual"])))

        a6, a7, a8, a9, a10 = st.columns(5)
        metric_with_help(a6, "Ahorro jubilación anual", show_eur(float(y["ahorro_jub_total"])))
        metric_with_help(a7, "Ahorro fiscal anual", show_eur(float(y["ahorro_fiscal"])))
        metric_with_help(a8, "Consumo en especie anual", show_eur(float(y["consumo_especie"])))
        metric_with_help(a9, "Ingresos libres imp. anual", show_eur(float(y["ingresos_libres_impuestos"])))
        metric_with_help(a10, "Bruto variable anual", show_eur(float(y["variable_ingreso"])))

        st.markdown("##### Jubilación, ESPP y RSU")
        grp1, grp2, grp3 = st.columns(3)
        with grp1:
            st.caption("Jubilación")
            metric_with_help(st, "Aportación empresa", show_eur(float(y["ahorro_jub_empresa"])))
            metric_with_help(st, "Aportación empleado", show_eur(float(y["ahorro_jub_empleado"])))
        with grp2:
            st.caption("ESPP")
            metric_with_help(st, "ESPP bruto", show_eur(float(y["espp_gain"])))
            metric_with_help(st, "ESPP neto estimado", show_eur(float(y["espp_neto_estimado"])))
        with grp3:
            st.caption("RSU")
            metric_with_help(st, "RSU bruto", show_eur(float(y["rsu_gain"])))
            metric_with_help(st, "RSU neto estimado", show_eur(float(y["rsu_neto_estimado"])))

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
        if not compact_mode:
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
            annual_csv = annual_table.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar KPIs anuales (CSV)",
                data=annual_csv,
                file_name="kpis_anuales.csv",
                mime="text/csv",
            )

        if not compact_mode:
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
            detail_csv = detail_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar detalle mensual (CSV)",
                data=detail_csv,
                file_name="detalle_mensual.csv",
                mime="text/csv",
            )

        with st.expander("Desglose mensual"):
            breakdown = nominas_view.copy()
            breakdown["Concepto_agrupado"] = breakdown["Concepto"].astype(str)
            irpf_mask = breakdown["Concepto_agrupado"].str.upper().str.contains(r"^TRIBUTACION\s+I\.?R\.?P\.?F\.?", regex=True)
            breakdown.loc[irpf_mask, "Concepto_agrupado"] = "TRIBUTACION I.R.P.F."
            ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns(5)
            with ctrl1:
                grouping_mode = st.selectbox(
                    "Agrupar por",
                    options=["Concepto", "Subcategoría"],
                    index=0,
                    key="breakdown_grouping_mode",
                )
            with ctrl2:
                concept_filter = st.text_input(
                    "Buscar texto",
                    value="",
                    key="breakdown_text_filter",
                    placeholder="Ej. IRPF, ESPP, SALARIO...",
                ).strip()
            with ctrl3:
                only_changes = st.checkbox("Solo con cambios (Δ abs != 0)", value=False, key="breakdown_only_changes")
            with ctrl4:
                hide_zero_rows = st.checkbox("Ocultar filas en cero", value=True, key="breakdown_hide_zeros")
            with ctrl5:
                top_n = st.number_input("Top filas", min_value=10, max_value=5000, value=200, step=10, key="breakdown_top_n")
            breakdown["Importe_num"] = pd.to_numeric(
                breakdown["Importe"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                errors="coerce",
            ).fillna(0.0)
            breakdown["Periodo"] = (
                breakdown["Año"].astype(int).astype(str) + "-" + breakdown["Mes"].astype(int).astype(str).str.zfill(2)
            )
            if grouping_mode == "Subcategoría":
                breakdown["Clave_desglose"] = breakdown["Subcategoría"].astype(str)
                index_col_name = "Subcategoría"
            else:
                breakdown["Clave_desglose"] = breakdown["Concepto_agrupado"]
                index_col_name = "Concepto"

            if period_option == "Todos":
                month_order = monthly_view["Periodo"].drop_duplicates().tolist()
            else:
                month_order = [period_option]

            pivot = (
                breakdown.pivot_table(
                    index="Clave_desglose",
                    columns="Periodo",
                    values="Importe_num",
                    aggfunc="sum",
                    fill_value=0.0,
                )
                .reindex(columns=month_order, fill_value=0.0)
                .reset_index()
            )
            pivot = pivot.rename(columns={"Clave_desglose": index_col_name})

            if period_option == "Todos" and len(month_order) >= 2:
                latest = month_order[-1]
                prev = month_order[-2]
                pivot["Δ abs"] = pivot[latest] - pivot[prev]
                pivot["Δ %"] = pivot.apply(
                    lambda r: ((r[latest] - r[prev]) / r[prev] * 100.0) if float(r[prev]) != 0 else 0.0, axis=1
                )
                if only_changes:
                    pivot = pivot[pivot["Δ abs"] != 0].copy()
                pivot = pivot.sort_values(by="Δ abs", ascending=False, key=lambda s: s.abs()).reset_index(drop=True)
            else:
                value_cols = [c for c in pivot.columns if c != index_col_name]
                if value_cols:
                    pivot["_sort_abs"] = pivot[value_cols].abs().sum(axis=1)
                    pivot = pivot.sort_values("_sort_abs", ascending=False).drop(columns=["_sort_abs"]).reset_index(drop=True)

            if concept_filter:
                pivot = pivot[
                    pivot[index_col_name].astype(str).str.contains(re.escape(concept_filter), case=False, na=False)
                ].copy()
            if hide_zero_rows:
                numeric_cols = [c for c in pivot.columns if c not in {index_col_name, "Δ %"}]
                if numeric_cols:
                    non_zero_mask = pivot[numeric_cols].fillna(0.0).abs().sum(axis=1) != 0
                    pivot = pivot[non_zero_mask].copy()
            pivot = pivot.head(int(top_n))

            if hide_amounts:
                for col in [c for c in pivot.columns if c != index_col_name]:
                    pivot[col] = "••••••"
            else:
                eur_cols = [c for c in pivot.columns if c not in {index_col_name, "Δ %"}]
                for col in eur_cols:
                    pivot[col] = pivot[col].apply(lambda x: format_eur(float(x)))
                if "Δ %" in pivot.columns:
                    pivot["Δ %"] = pivot["Δ %"].apply(lambda x: f"{float(x):.2f}%")

            st.dataframe(pivot, width="stretch")
            csv_payload = pivot.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar desglose mensual (CSV)",
                data=csv_payload,
                file_name="desglose_mensual.csv",
                mime="text/csv",
            )

        if quality_rows and not compact_mode:
            with st.expander("Alertas de calidad detalladas"):
                quality_df = pd.DataFrame(quality_rows, columns=["Periodo", "Alerta", "Detalle"])
                st.dataframe(quality_df, width="stretch")

        # Calidad avanzada: outliers en SALARIO BASE frente a mediana histórica
        if not compact_mode:
            with st.expander("Calidad de datos avanzada"):
                quality_adv: list[dict[str, str]] = []
                nom_base = nominas_view.copy()
                nom_base["Concepto_up"] = nom_base["Concepto"].astype(str).str.upper()
                nom_base["Importe_num"] = pd.to_numeric(
                    nom_base["Importe"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                    errors="coerce",
                ).fillna(0.0)
                salario_base = (
                    nom_base[nom_base["Concepto_up"].str.contains("SALARIO BASE", na=False)]
                    .groupby(["Año", "Mes"], as_index=False)["Importe_num"]
                    .sum()
                    .sort_values(["Año", "Mes"])
                )
                if not salario_base.empty:
                    med = float(salario_base["Importe_num"].median())
                    if med != 0:
                        salario_base["desv_pct"] = (salario_base["Importe_num"] - med).abs() / abs(med)
                        outliers = salario_base[salario_base["desv_pct"] > 0.20]
                        for _, r in outliers.iterrows():
                            quality_adv.append(
                                {
                                    "Periodo": f"{int(r['Año'])}-{int(r['Mes']):02d}",
                                    "Regla": "SALARIO BASE fuera de rango (>20% de mediana)",
                                    "Valor": format_eur(float(r["Importe_num"])),
                                }
                            )
                if quality_adv:
                    st.dataframe(pd.DataFrame(quality_adv), width="stretch")
                else:
                    st.info("Sin outliers detectados en SALARIO BASE con regla actual.")

        # Cobertura de meses disponibles por año
        if not compact_mode:
            with st.expander("Calendario de cobertura"):
                coverage = monthly[["Año", "Mes"]].copy()
                coverage["present"] = "OK"
                coverage_pivot = (
                    coverage.pivot_table(index="Año", columns="Mes", values="present", aggfunc="first", fill_value="")
                    .reindex(columns=list(range(1, 13)), fill_value="")
                    .rename(columns={i: f"{i:02d}" for i in range(1, 13)})
                    .reset_index()
                )
                st.dataframe(coverage_pivot, width="stretch")

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
