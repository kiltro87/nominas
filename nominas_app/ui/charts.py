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


def _build_monthly_bruto_neto_bonus_chart(monthly_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    chart_df = monthly_view[["Periodo_natural", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    chart_df["bonus_acciones"] = chart_df["espp_gain"] + chart_df["rsu_gain"]
    if hide_amounts:
        chart_df[["total_devengado", "neto", "bonus_acciones"]] = 0.0

    long_df = chart_df.melt(
        id_vars=["Periodo_natural", "bonus_acciones"],
        value_vars=["total_devengado", "neto"],
        var_name="Métrica",
        value_name="Importe",
    )
    long_df["Métrica"] = long_df["Métrica"].map({"total_devengado": "Bruto", "neto": "Neto"})
    order = chart_df["Periodo_natural"].tolist()
    line = (
        alt.Chart(long_df)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€"),
            color=alt.Color("Métrica:N", scale=alt.Scale(range=["#3b82f6", "#22c55e"])),
            tooltip=["Periodo_natural:N", "Métrica:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    bars = (
        alt.Chart(chart_df)
        .mark_bar(opacity=0.30, color="#f59e0b")
        .encode(
            x=alt.X("Periodo_natural:N", sort=order),
            y=alt.Y("bonus_acciones:Q", title="€"),
            tooltip=["Periodo_natural:N", alt.Tooltip("bonus_acciones:Q", format=",.2f")],
        )
    )
    return (bars + line).properties(height=300, title="Evolución mensual: Bruto, Neto y Bonus/Acciones")


def _build_irpf_followup_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> alt.Chart:
    chart_df = df[[x_col, y_col]].copy()
    chart_df["IRPF"] = pd.to_numeric(chart_df[y_col], errors="coerce").fillna(0.0) * 100.0
    values = pd.to_numeric(chart_df["IRPF"], errors="coerce").dropna()
    if values.empty:
        y_scale = alt.Scale(zero=True)
    else:
        vmin = float(values.min())
        vmax = float(values.max())
        if vmin == vmax:
            pad = max(abs(vmin) * 0.05, 0.5)
            domain = [vmin - pad, vmax + pad]
        else:
            pad = (vmax - vmin) * 0.10
            domain = [vmin - pad, vmax + pad]
        y_scale = alt.Scale(domain=domain, zero=False, nice=True)

    order = chart_df[x_col].tolist()
    mean_value = float(chart_df["IRPF"].mean()) if not chart_df.empty else 0.0
    target_df = pd.DataFrame({"target": [mean_value]})
    line = (
        alt.Chart(chart_df)
        .mark_line(point=True, color="#14b8a6", strokeWidth=2.5)
        .encode(
            x=alt.X(f"{x_col}:N", sort=order, title="Periodo" if x_col == "Periodo_natural" else "Año"),
            y=alt.Y("IRPF:Q", title="% IRPF", scale=y_scale),
            tooltip=[f"{x_col}:N", alt.Tooltip("IRPF:Q", format=".2f")],
        )
    )
    rule = alt.Chart(target_df).mark_rule(color="#475569", strokeDash=[6, 4]).encode(y="target:Q")
    return (line + rule).properties(height=300, title=title)


def render_comparison_charts(
    annual_view: pd.DataFrame,
    monthly_view: pd.DataFrame,
    year_option: int | str,
    period_option: str,
    hide_amounts: bool,
) -> None:
    st.subheader("Comparativa y evolución")
    ch1, ch2 = st.columns(2)
    with ch1:
        if year_option == "Todos" and period_option == "Todos":
            st.altair_chart(
                _build_multiyear_bruto_neto_bonus_chart(annual_view=annual_view, hide_amounts=hide_amounts),
                use_container_width=True,
            )
        else:
            st.altair_chart(
                _build_monthly_bruto_neto_bonus_chart(monthly_view=monthly_view, hide_amounts=hide_amounts),
                use_container_width=True,
            )
    with ch2:
        if year_option == "Todos" and period_option == "Todos":
            st.altair_chart(
                _build_irpf_followup_chart(
                    df=annual_view,
                    x_col="Año",
                    y_col="pct_irpf_efectivo_anual",
                    title="Seguimiento de IRPF (anual)",
                ),
                use_container_width=True,
            )
        else:
            st.altair_chart(
                _build_irpf_followup_chart(
                    df=monthly_view,
                    x_col="Periodo_natural",
                    y_col="pct_irpf",
                    title="Seguimiento de IRPF (anual)",
                ),
                use_container_width=True,
            )

