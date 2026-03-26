from __future__ import annotations

import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas_app.services.dashboard_data import parse_spanish_amount_series
from nominas_app.ui.formatting import apply_privacy_to_columns, metric_with_help, show_eur, zebra_styler


def render_monthly_kpis_card(
    monthly_view: pd.DataFrame,
    monthly: pd.DataFrame,
    year_option: int | str,
    period_option: str,
    compare_mode: str,
    raw_nominas: pd.DataFrame,
    hide_amounts: bool,
) -> None:
    m = monthly_view.sort_values(["Año", "Mes"]).iloc[-1]
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

    delta_label = f"vs {cmp_row['Periodo_natural']}" if cmp_row is not None else None
    monthly_title = "KPIs mensuales"
    if year_option == "Todos" and period_option == "Todos":
        monthly_title += " (último mes disponible)"

    compare_chip = ""
    if compare_mode != "Sin comparación":
        compare_chip_text = (
            delta_label
            if delta_label is not None
            else ("vs mes anterior" if compare_mode == "Mes anterior" else "vs mismo mes año anterior")
        )
        compare_chip = (
            f"<span style='margin-left:8px;padding:2px 8px;border-radius:999px;"
            f"background:#eef2ff;border:1px solid #c7d2fe;font-size:12px;color:#3730a3;'>{compare_chip_text}</span>"
        )

    with st.container(border=True):
        st.markdown(f"### {monthly_title}{compare_chip}", unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        if cmp_row is not None:
            metric_with_help(c1, "Bruto", show_eur(float(m["total_devengado"]), hide_amounts), delta=format_eur(float(m["total_devengado"] - cmp_row["total_devengado"])))
            metric_with_help(c2, "Neto", show_eur(float(m["neto"]), hide_amounts), delta=format_eur(float(m["neto"] - cmp_row["neto"])))
            metric_with_help(c3, "% IRPF", f"{float(m['pct_irpf']) * 100:.2f}%", delta=f"{(float(m['pct_irpf']) - float(cmp_row['pct_irpf'])) * 100:.2f} pp")
        else:
            metric_with_help(c1, "Bruto", show_eur(float(m["total_devengado"]), hide_amounts))
            metric_with_help(c2, "Neto", show_eur(float(m["neto"]), hide_amounts))
            metric_with_help(c3, "% IRPF", f"{float(m['pct_irpf']) * 100:.2f}%")
        metric_with_help(c4, "Consumo en especie", show_eur(float(m["consumo_especie"]), hide_amounts))
        metric_with_help(c5, "Ingresos totales", show_eur(float(m["riqueza_real_mensual"]), hide_amounts))

        ahorro_jub_mensual = float(m["ahorro_jub_empresa"]) + float(m["ahorro_jub_empleado"])
        c6, c7, c8, c9, c10 = st.columns(5)
        metric_with_help(c6, "Ahorro fiscal", show_eur(float(m["ahorro_fiscal"]), hide_amounts))
        metric_with_help(c7, "Ahorro jubilación", show_eur(ahorro_jub_mensual, hide_amounts))
        metric_with_help(c8, "Ingresos libres imp.", show_eur(float(m["ingresos_libres_impuestos"]), hide_amounts))
        metric_with_help(c9, "Ahorro jub. empresa", show_eur(float(m["ahorro_jub_empresa"]), hide_amounts))
        metric_with_help(c10, "Ahorro jub. empleado", show_eur(float(m["ahorro_jub_empleado"]), hide_amounts))

        if cmp_row is not None:
            with st.expander("Explicar delta (Top 5 conceptos)"):
                raw_comp = raw_nominas.copy()
                raw_comp["Año"] = pd.to_numeric(raw_comp["Año"], errors="coerce")
                raw_comp["Mes"] = pd.to_numeric(raw_comp["Mes"], errors="coerce")
                raw_comp["Importe_num"] = parse_spanish_amount_series(raw_comp["Importe"])
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
                st.dataframe(zebra_styler(explain), width="stretch")


def render_annual_kpis_card(
    annual_view: pd.DataFrame,
    monthly: pd.DataFrame,
    monthly_view: pd.DataFrame,
    year_option: int | str,
    hide_amounts: bool,
) -> None:
    with st.container(border=True):
        annual_title = "KPIs anuales"
        if year_option == "Todos":
            annual_title += " (último año disponible)"
        st.subheader(annual_title)
        y = annual_view.sort_values("Año").iloc[-1]
        irpf_medio = monthly[monthly["Año"] == int(y["Año"])]["pct_irpf"].mean()
        a1, a2, a3, a4, a5 = st.columns(5)
        metric_with_help(a1, "Bruto", show_eur(float(y["total_devengado"]), hide_amounts))
        metric_with_help(a2, "Neto", show_eur(float(y["neto"]), hide_amounts))
        metric_with_help(a3, "% IRPF efectivo", f"{float(y['pct_irpf_efectivo_anual']) * 100:.2f}%")
        metric_with_help(a4, "IRPF medio", f"{float(irpf_medio) * 100:.2f}%")
        metric_with_help(a5, "Ingresos totales", show_eur(float(y["riqueza_real_anual"]), hide_amounts))

        b1, b2, b3, b4, b5 = st.columns(5)
        metric_with_help(b2, "Ahorro fiscal", show_eur(float(y["ahorro_fiscal"]), hide_amounts))
        metric_with_help(b3, "Ingresos libres imp.", show_eur(float(y["ingresos_libres_impuestos"]), hide_amounts))
        metric_with_help(b4, "Consumo en especie", show_eur(float(y["consumo_especie"]), hide_amounts))
        b5.metric("Delta neto vs año anterior", show_eur(float(y["delta_neto_vs_anterior"]), hide_amounts))
        b1.metric("% crecimiento neto YoY", f"{float(y['pct_crecimiento_neto_yoy']) * 100:.2f}%")

        block_left, block_right = st.columns([3, 2])
        with block_left:
            with st.container(border=True):
                st.markdown("##### Jubilación")
                jub_total = float(y["ahorro_jub_total"])
                jub_empresa = float(y["ahorro_jub_empresa"])
                jub_empleado = float(y["ahorro_jub_empleado"])
                j1, j2, j3 = st.columns(3)
                metric_with_help(j1, "Ahorro jubilación", show_eur(jub_total, hide_amounts))
                metric_with_help(j2, "Aportación empresa", show_eur(jub_empresa, hide_amounts))
                metric_with_help(j3, "Aportación empleado", show_eur(jub_empleado, hide_amounts))
        with block_right:
            with st.container(border=True):
                st.markdown("##### ESPP y RSU")
                rm1, rm2 = st.columns(2)
                metric_with_help(rm1, "ESPP", show_eur(float(y["espp_gain"]), hide_amounts))
                metric_with_help(rm2, "RSU", show_eur(float(y["rsu_gain"]), hide_amounts))
                gains_table = monthly_view[["Periodo_natural", "espp_gain", "rsu_gain"]].rename(
                    columns={"Periodo_natural": "Periodo", "espp_gain": "ESPP Gain", "rsu_gain": "RSU Gain"}
                )
                gains_table = gains_table[
                    (pd.to_numeric(gains_table["ESPP Gain"], errors="coerce").fillna(0.0) != 0.0)
                    | (pd.to_numeric(gains_table["RSU Gain"], errors="coerce").fillna(0.0) != 0.0)
                ].reset_index(drop=True)
                if gains_table.empty:
                    st.info(
                        "Sin datos de ESPP/RSU para el filtro actual. "
                        "Prueba con otro año o selecciona 'Todos' en mes."
                    )
                else:
                    with st.expander("Ver detalle mensual ESPP/RSU", expanded=False):
                        gains_recent = apply_privacy_to_columns(gains_table.copy(), ["ESPP Gain", "RSU Gain"], hide_amounts)
                        st.dataframe(zebra_styler(gains_recent), width="stretch")
                        csv_payload = gains_table.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Descargar ESPP/RSU mensual (CSV)",
                            data=csv_payload,
                            file_name="espp_rsu_mensual.csv",
                            mime="text/csv",
                        )

