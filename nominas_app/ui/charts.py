from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st


def _build_multiyear_bruto_neto_bonus_chart(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    chart_df = annual_view[["Año", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    chart_df["bonus_acciones"] = chart_df["espp_gain"] + chart_df["rsu_gain"]
    if hide_amounts:
        chart_df[["total_devengado", "neto", "bonus_acciones"]] = 0.0

    long_df = chart_df.melt(
        id_vars=["Año", "bonus_acciones"],
        value_vars=["total_devengado", "neto"],
        var_name="Métrica",
        value_name="Importe",
    )
    long_df["Métrica"] = long_df["Métrica"].map({"total_devengado": "Bruto", "neto": "Neto"})

    line = (
        alt.Chart(long_df)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Año:O", title="Año"),
            y=alt.Y("Importe:Q", title="€"),
            color=alt.Color("Métrica:N", scale=alt.Scale(range=["#3b82f6", "#22c55e"])),
            tooltip=["Año:O", "Métrica:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    bars = (
        alt.Chart(chart_df)
        .mark_bar(opacity=0.30, color="#f59e0b")
        .encode(
            x=alt.X("Año:O"),
            y=alt.Y("bonus_acciones:Q", title="€"),
            tooltip=["Año:O", alt.Tooltip("bonus_acciones:Q", format=",.2f")],
        )
    )
    return (bars + line).properties(height=300, title="Evolución multianual: Bruto, Neto y Bonus/Acciones")


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
    if percent_scale:
        metric_name_map = {"pct_irpf": "% IRPF"}
        long_df["Métrica"] = long_df["Métrica"].map(lambda x: metric_name_map.get(x, x))
    values = pd.to_numeric(long_df["Valor"], errors="coerce").dropna()
    if values.empty:
        y_scale = alt.Scale(zero=True)
    else:
        vmin = float(values.min())
        vmax = float(values.max())
        if vmin == vmax:
            pad = max(abs(vmin) * 0.05, 1.0)
            domain = [vmin - pad, vmax + pad]
        else:
            pad = (vmax - vmin) * 0.08
            domain = [vmin - pad, vmax + pad]
        y_scale = alt.Scale(domain=domain, zero=False, nice=True)
    order = chart_df["Periodo_natural"].tolist()
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Valor:Q", title="%" if percent_scale else "€", scale=y_scale),
            color="Métrica:N",
            tooltip=["Periodo_natural:N", "Métrica:N", "Valor:Q"],
        )
        .properties(title=title)
    )
    st.altair_chart(chart, use_container_width=True)


def render_comparison_charts(
    annual_view: pd.DataFrame,
    monthly_view: pd.DataFrame,
    year_option: int | str,
    period_option: str,
    hide_amounts: bool,
) -> None:
    st.subheader("Comparativa y evolución")
    if year_option == "Todos" and period_option == "Todos":
        ch1, ch2 = st.columns(2)
        with ch1:
            st.altair_chart(
                _build_multiyear_bruto_neto_bonus_chart(annual_view=annual_view, hide_amounts=hide_amounts),
                use_container_width=True,
            )
        annual_pct_chart = annual_view[["Año", "pct_irpf_efectivo_anual"]].copy()
        annual_pct_chart["% IRPF efectivo anual"] = annual_pct_chart["pct_irpf_efectivo_anual"] * 100
        with ch2:
            st.line_chart(annual_pct_chart.set_index("Año")[["% IRPF efectivo anual"]])
    else:
        ch1, ch2 = st.columns(2)
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
        with ch1:
            draw_monthly_chart(
                monthly_amount_chart,
                ["Salario Bruto", "Salario Neto", "Ingresos recibidos (incluyendo Tickets, pensión y acciones)"],
                "Evolución salarial e ingresos recibidos",
            )
        with ch2:
            draw_monthly_chart(monthly_view, ["pct_irpf"], "Evolución mensual (% IRPF)", percent_scale=True)

