from __future__ import annotations

import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas_app.services.dashboard_data import (
    COMPARE_MODE_NONE,
    COMPARE_MODE_PREVIOUS,
    build_monthly_concept_delta,
    get_comparison_row,
)
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
    cmp_row = get_comparison_row(monthly_all=monthly_all, current_row=m, compare_mode=compare_mode)

    delta_label = f"vs {cmp_row['Periodo_natural']}" if cmp_row is not None else None
    monthly_title = "KPIs mensuales"
    if year_option == "Todos" and period_option == "Todos":
        monthly_title += " (último mes disponible)"

    compare_chip = ""
    if compare_mode != COMPARE_MODE_NONE:
        compare_chip_text = (
            delta_label
            if delta_label is not None
            else ("vs mes anterior" if compare_mode == COMPARE_MODE_PREVIOUS else "vs mismo mes año anterior")
        )
        compare_chip = (
            f"<span style='margin-left:8px;padding:2px 8px;border-radius:999px;"
            f"background:#eef2ff;border:1px solid #c7d2fe;font-size:12px;color:#3730a3;'>{compare_chip_text}</span>"
        )

    with st.container(border=True):
        st.markdown(f"### {monthly_title}{compare_chip}", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        if cmp_row is not None:
            metric_with_help(c1, "Bruto", show_eur(float(m["total_devengado"]), hide_amounts), delta=format_eur(float(m["total_devengado"] - cmp_row["total_devengado"])))
            metric_with_help(c2, "Neto", show_eur(float(m["neto"]), hide_amounts), delta=format_eur(float(m["neto"] - cmp_row["neto"])))
            metric_with_help(c3, "% IRPF", f"{float(m['pct_irpf']) * 100:.2f}%", delta=f"{(float(m['pct_irpf']) - float(cmp_row['pct_irpf'])) * 100:.2f} pp")
            metric_with_help(
                c4,
                "Ingresos totales",
                show_eur(float(m["riqueza_real_mensual"]), hide_amounts),
                delta=format_eur(float(m["riqueza_real_mensual"] - cmp_row["riqueza_real_mensual"])),
            )
        else:
            metric_with_help(c1, "Bruto", show_eur(float(m["total_devengado"]), hide_amounts))
            metric_with_help(c2, "Neto", show_eur(float(m["neto"]), hide_amounts))
            metric_with_help(c3, "% IRPF", f"{float(m['pct_irpf']) * 100:.2f}%")
            metric_with_help(c4, "Ingresos totales", show_eur(float(m["riqueza_real_mensual"]), hide_amounts))

        ahorro_jub_mensual = float(m["ahorro_jub_empresa"]) + float(m["ahorro_jub_empleado"])
        d1, d2, d3 = st.columns(3)
        metric_with_help(d1, "Ahorro fiscal", show_eur(float(m["ahorro_fiscal"]), hide_amounts))
        metric_with_help(d2, "Ahorro jubilación", show_eur(ahorro_jub_mensual, hide_amounts))
        metric_with_help(d3, "Consumo en especie", show_eur(float(m["consumo_especie"]), hide_amounts))

        if cmp_row is not None:
            with st.expander("Explicar delta (Top 5 conceptos)"):
                explain = build_monthly_concept_delta(
                    raw_nominas=raw_nominas,
                    cur_year=cur_year,
                    cur_month=cur_month,
                    cmp_year=int(cmp_row["Año"]),
                    cmp_month=int(cmp_row["Mes"]),
                    limit=5,
                )
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
        latest_available_year = int(monthly["Año"].max())
        selected_year = int(y["Año"])
        show_yoy = selected_year < latest_available_year
        prev_year_agg = None
        if show_yoy:
            annual_from_monthly = (
                monthly.groupby("Año", as_index=False)[
                    [
                        "total_devengado",
                        "total_deducir",
                        "neto",
                        "irpf_importe",
                        "consumo_especie",
                        "ingresos_libres_impuestos",
                        "ahorro_fiscal",
                        "ahorro_jub_total",
                        "espp_gain",
                        "rsu_gain",
                        "riqueza_real_mensual",
                    ]
                ]
                .sum()
                .sort_values("Año")
            )
            prev = annual_from_monthly[annual_from_monthly["Año"] == selected_year - 1]
            if not prev.empty:
                prev_year_agg = prev.iloc[-1]

        def yoy_pct_delta(current: float, previous: float | None) -> str | None:
            if previous is None or float(previous) == 0.0:
                return None
            return f"{((float(current) - float(previous)) / float(previous)) * 100:.2f}% YoY"

        def yoy_pp_delta(current: float, previous: float | None) -> str | None:
            if previous is None:
                return None
            return f"{(float(current) - float(previous)) * 100:.2f} pp YoY"

        irpf_medio = monthly[monthly["Año"] == int(y["Año"])]["pct_irpf"].mean()
        a1, a2, a3, a4 = st.columns(4)
        bruto_delta = yoy_pct_delta(
            float(y["total_devengado"]),
            float(prev_year_agg["total_devengado"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        neto_delta = yoy_pct_delta(
            float(y["neto"]),
            float(prev_year_agg["neto"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        prev_irpf_efectivo = (
            float(prev_year_agg["irpf_importe"]) / float(prev_year_agg["total_devengado"])
            if (prev_year_agg is not None and float(prev_year_agg["total_devengado"]) != 0.0)
            else None
        )
        irpf_efectivo_delta = yoy_pp_delta(float(y["pct_irpf_efectivo_anual"]), prev_irpf_efectivo) if show_yoy else None
        prev_irpf_medio = (
            monthly[monthly["Año"] == selected_year - 1]["pct_irpf"].mean()
            if show_yoy and (selected_year - 1) in set(monthly["Año"].astype(int).tolist())
            else None
        )
        irpf_medio_delta = yoy_pp_delta(float(irpf_medio), float(prev_irpf_medio)) if (show_yoy and prev_irpf_medio is not None) else None
        ingresos_totales_delta = yoy_pct_delta(
            float(y["riqueza_real_anual"]),
            float(prev_year_agg["riqueza_real_mensual"]) if prev_year_agg is not None else None,
        ) if show_yoy else None

        metric_with_help(a1, "Bruto", show_eur(float(y["total_devengado"]), hide_amounts), delta=bruto_delta)
        metric_with_help(a2, "Neto", show_eur(float(y["neto"]), hide_amounts), delta=neto_delta)
        metric_with_help(a3, "% IRPF efectivo", f"{float(y['pct_irpf_efectivo_anual']) * 100:.2f}%", delta=irpf_efectivo_delta)
        metric_with_help(a4, "Ingresos totales", show_eur(float(y["riqueza_real_anual"]), hide_amounts), delta=ingresos_totales_delta)

        ahorro_fiscal_delta = yoy_pct_delta(
            float(y["ahorro_fiscal"]),
            float(prev_year_agg["ahorro_fiscal"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        ahorro_jub_delta = yoy_pct_delta(
            float(y["ahorro_jub_total"]),
            float(prev_year_agg["ahorro_jub_total"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        consumo_especie_delta = yoy_pct_delta(
            float(y["consumo_especie"]),
            float(prev_year_agg["consumo_especie"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        deducciones_delta = yoy_pct_delta(
            float(y["total_deducir"]),
            float(prev_year_agg["total_deducir"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        media_neto_delta = yoy_pct_delta(
            float(y["media_neto_mensual"]),
            float(prev_year_agg["neto"] / 12.0) if prev_year_agg is not None else None,
        ) if show_yoy else None
        bonus_acciones = float(y["espp_gain"] + y["rsu_gain"])
        bonus_acciones_delta = yoy_pct_delta(
            bonus_acciones,
            float(prev_year_agg["espp_gain"] + prev_year_agg["rsu_gain"]) if prev_year_agg is not None else None,
        ) if show_yoy else None
        b1, b2, b3, b4 = st.columns(4)
        metric_with_help(b1, "IRPF medio", f"{float(irpf_medio) * 100:.2f}%", delta=irpf_medio_delta)
        metric_with_help(b2, "Ahorro fiscal", show_eur(float(y["ahorro_fiscal"]), hide_amounts), delta=ahorro_fiscal_delta)
        metric_with_help(b3, "Ahorro jubilación", show_eur(float(y["ahorro_jub_total"]), hide_amounts), delta=ahorro_jub_delta)
        metric_with_help(b4, "Consumo en especie", show_eur(float(y["consumo_especie"]), hide_amounts), delta=consumo_especie_delta)
        c1, c2, c3 = st.columns(3)
        metric_with_help(c1, "Nomina neta media mensual", show_eur(float(y["media_neto_mensual"]), hide_amounts), delta=media_neto_delta)
        metric_with_help(c2, "Deducciones YTD", show_eur(float(y["total_deducir"]), hide_amounts), delta=deducciones_delta)
        metric_with_help(c3, "Bonus + acciones (YTD)", show_eur(bonus_acciones, hide_amounts), delta=bonus_acciones_delta)

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

