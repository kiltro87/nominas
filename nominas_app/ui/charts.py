from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from nominas_app.ui.palette import COLOR_2, COLOR_5, ordered_scale, semantic_scale


def _build_multiyear_bruto_neto_bonus_chart(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    chart_df = annual_view[["Año", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    if hide_amounts:
        chart_df[["total_devengado", "neto", "espp_gain", "rsu_gain"]] = 0.0

    long_df = chart_df.melt(
        id_vars=["Año"],
        value_vars=["total_devengado", "neto"],
        var_name="Salario",
        value_name="Importe",
    )
    long_df["Salario"] = long_df["Salario"].map({"total_devengado": "Bruto", "neto": "Neto"})

    line = (
        alt.Chart(long_df)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Año:O", title="Año"),
            y=alt.Y("Importe:Q", title="€"),
            color=alt.Color(
                "Salario:N",
                title="Salario",
                scale=ordered_scale(["Neto", "Bruto"]),
            ),
            tooltip=["Año:O", "Salario:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    bonus_df = chart_df.melt(
        id_vars=["Año"],
        value_vars=["espp_gain", "rsu_gain"],
        var_name="Bonus",
        value_name="Importe",
    )
    bonus_df["Bonus"] = bonus_df["Bonus"].map({"espp_gain": "ESPP", "rsu_gain": "RSU"})
    bars = (
        alt.Chart(bonus_df)
        .mark_bar(opacity=0.35)
        .encode(
            x=alt.X("Año:O"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Bonus:N",
                title="Bonus",
                scale=ordered_scale(["ESPP", "RSU"]),
            ),
            tooltip=["Año:O", "Bonus:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    return (bars + line).resolve_scale(color="independent").properties(
        height=300, title="Evolución multianual: Bruto, Neto y Bonus/Acciones"
    )


def _build_monthly_bruto_neto_bonus_chart(monthly_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    chart_df = monthly_view[["Periodo_natural", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    if hide_amounts:
        chart_df[["total_devengado", "neto", "espp_gain", "rsu_gain"]] = 0.0

    long_df = chart_df.melt(
        id_vars=["Periodo_natural"],
        value_vars=["total_devengado", "neto"],
        var_name="Salario",
        value_name="Importe",
    )
    long_df["Salario"] = long_df["Salario"].map({"total_devengado": "Bruto", "neto": "Neto"})
    order = chart_df["Periodo_natural"].tolist()
    line = (
        alt.Chart(long_df)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€"),
            color=alt.Color(
                "Salario:N",
                title="Salario",
                scale=ordered_scale(["Neto", "Bruto"]),
            ),
            tooltip=["Periodo_natural:N", "Salario:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    bonus_df = chart_df.melt(
        id_vars=["Periodo_natural"],
        value_vars=["espp_gain", "rsu_gain"],
        var_name="Bonus",
        value_name="Importe",
    )
    bonus_df["Bonus"] = bonus_df["Bonus"].map({"espp_gain": "ESPP", "rsu_gain": "RSU"})
    bars = (
        alt.Chart(bonus_df)
        .mark_bar(opacity=0.35)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Bonus:N",
                title="Bonus",
                scale=ordered_scale(["ESPP", "RSU"]),
            ),
            tooltip=["Periodo_natural:N", "Bonus:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    return (bars + line).resolve_scale(color="independent").properties(
        height=300, title="Evolución mensual: Bruto, Neto y Bonus/Acciones"
    )


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


def _build_deductions_waterfall(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    y = annual_view.sort_values("Año").iloc[-1]
    bruto = float(y["total_devengado"])
    irpf = float(y["irpf_importe"])
    ss = float(y["ss_importe"])
    total_deducir = float(y["total_deducir"])
    neto = float(y["neto"])
    otras_deducciones = max(total_deducir - irpf - ss, 0.0)
    if hide_amounts:
        bruto, irpf, ss, neto, otras_deducciones = 0.0, 0.0, 0.0, 0.0, 0.0
    breakdown = pd.DataFrame(
        [
            {"periodo": "YTD", "componente": "Neto", "importe": neto},
            {"periodo": "YTD", "componente": "IRPF", "importe": irpf},
            {"periodo": "YTD", "componente": "Seg. Social", "importe": ss},
            {"periodo": "YTD", "componente": "Otras deducciones", "importe": otras_deducciones},
        ]
    )
    return (
        alt.Chart(breakdown)
        .mark_bar()
        .encode(
            x=alt.X("periodo:N", title=""),
            y=alt.Y("importe:Q", title="€", stack=True),
            color=alt.Color(
                "componente:N",
                title="Componente",
                scale=semantic_scale(["Neto", "IRPF", "Seg. Social", "Otras deducciones"]),
            ),
            tooltip=["componente:N", alt.Tooltip("importe:Q", format=",.2f")],
        )
        .properties(height=280, title=f"Desglose de Bruto YTD (total {bruto:,.2f} €)")
    )


def _build_savings_mix_chart(monthly_year_scope: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    df = monthly_year_scope[["Periodo_natural", "ahorro_fiscal", "ahorro_jub_total", "consumo_especie"]].copy()
    if hide_amounts:
        df[["ahorro_fiscal", "ahorro_jub_total", "consumo_especie"]] = 0.0
    long_df = df.melt(
        id_vars=["Periodo_natural"],
        value_vars=["ahorro_fiscal", "ahorro_jub_total", "consumo_especie"],
        var_name="Tipo",
        value_name="Importe",
    )
    long_df["Tipo"] = long_df["Tipo"].map(
        {
            "ahorro_fiscal": "Ahorro fiscal",
            "ahorro_jub_total": "Ahorro jubilación",
            "consumo_especie": "Consumo en especie",
        }
    )
    order = df["Periodo_natural"].tolist()
    return (
        alt.Chart(long_df)
        .mark_bar(opacity=0.75)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Tipo:N",
                scale=semantic_scale(["Ahorro fiscal", "Ahorro jubilación", "Consumo en especie"]),
            ),
            tooltip=["Periodo_natural:N", "Tipo:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
        .properties(height=280, title="Composición mensual: ahorro y consumo")
    )


def _build_income_mix_area_chart(monthly_year_scope: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    df = monthly_year_scope[
        ["Periodo_natural", "neto", "ahorro_jub_empresa", "espp_neto_estimado", "rsu_neto_estimado"]
    ].copy()
    plot_df = df.rename(
        columns={
            "neto": "Neto",
            "ahorro_jub_empresa": "Ahorro jub. empresa",
            "espp_neto_estimado": "ESPP neto estimado",
            "rsu_neto_estimado": "RSU neto estimado",
        }
    )[
        [
            "Periodo_natural",
            "Neto",
            "Ahorro jub. empresa",
            "ESPP neto estimado",
            "RSU neto estimado",
        ]
    ]
    if hide_amounts:
        plot_df[
            ["Neto", "Ahorro jub. empresa", "ESPP neto estimado", "RSU neto estimado"]
        ] = 0.0
    long_df = plot_df.melt(
        id_vars=["Periodo_natural"],
        value_vars=["Neto", "Ahorro jub. empresa", "ESPP neto estimado", "RSU neto estimado"],
        var_name="Fuente",
        value_name="Importe",
    )
    order = plot_df["Periodo_natural"].tolist()
    return (
        alt.Chart(long_df)
        .mark_area(opacity=0.55)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Fuente:N",
                scale=semantic_scale(["Neto", "Ahorro jub. empresa", "ESPP neto estimado", "RSU neto estimado"]),
            ),
            tooltip=["Periodo_natural:N", "Fuente:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
        .properties(height=280, title="Ingresos totales: desglose por componente")
    )


def render_comparison_charts(
    annual_view: pd.DataFrame,
    monthly_view: pd.DataFrame,
    monthly_year_scope: pd.DataFrame,
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

    st.markdown("#### Dashboards visuales complementarios")
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.altair_chart(_build_deductions_waterfall(annual_view=annual_view, hide_amounts=hide_amounts), use_container_width=True)
    with r1c2:
        st.altair_chart(_build_savings_mix_chart(monthly_year_scope=monthly_year_scope, hide_amounts=hide_amounts), use_container_width=True)

    st.altair_chart(
        _build_income_mix_area_chart(monthly_year_scope=monthly_year_scope, hide_amounts=hide_amounts),
        use_container_width=True,
    )

