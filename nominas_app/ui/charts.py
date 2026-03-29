from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from nominas_app.ui.palette import COLOR_1, COLOR_5, legend_circle, ordered_scale


def _coerce_finite(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out[cols] = out[cols].replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    return out


def _empty_chart(title: str, height: int = 280) -> alt.Chart:
    return (
        alt.Chart(pd.DataFrame({"msg": ["Sin datos para el filtro actual"]}))
        .mark_text(size=13)
        .encode(text="msg:N")
        .properties(height=height, title=title)
    )


def _build_multiyear_bruto_neto_bonus_chart(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    if annual_view.empty:
        return _empty_chart("Evolución multianual: Bruto, Neto y Bonus/Acciones", height=300)
    chart_df = annual_view[["Año", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    chart_df = _coerce_finite(chart_df, ["total_devengado", "neto", "espp_gain", "rsu_gain"])
    if hide_amounts:
        chart_df[["total_devengado", "neto", "espp_gain", "rsu_gain"]] = 0.0

    salary_df = chart_df.melt(
        id_vars=["Año"], value_vars=["total_devengado", "neto"], var_name="Serie", value_name="Importe"
    )
    salary_df["Grupo"] = "Salario"
    salary_df["Serie"] = salary_df["Serie"].map({"total_devengado": "Bruto", "neto": "Neto"})
    bonus_df = chart_df.melt(
        id_vars=["Año"], value_vars=["espp_gain", "rsu_gain"], var_name="Serie", value_name="Importe"
    )
    bonus_df["Grupo"] = "Bonus"
    bonus_df["Serie"] = bonus_df["Serie"].map({"espp_gain": "ESPP", "rsu_gain": "RSU"})
    combined_df = pd.concat([salary_df, bonus_df], ignore_index=True)
    combined_df = _coerce_finite(combined_df, ["Importe"])

    line = (
        alt.Chart(combined_df)
        .transform_filter(alt.datum.Grupo == "Salario")
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Año:O", title="Año"),
            y=alt.Y("Importe:Q", title="€"),
            color=alt.Color(
                "Serie:N",
                scale=ordered_scale(["Bruto", "Neto"]),
                legend=legend_circle("Salario"),
            ),
            tooltip=["Año:O", "Serie:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    bars = (
        alt.Chart(combined_df)
        .transform_filter(alt.datum.Grupo == "Bonus")
        .mark_bar(opacity=0.5)
        .encode(
            x=alt.X("Año:O"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Serie:N",
                scale=ordered_scale(["ESPP", "RSU"], start_index=2),
                legend=legend_circle("Bonus"),
            ),
            tooltip=["Año:O", "Serie:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    return (bars + line).resolve_scale(color="independent").properties(
        height=300, title="Evolución multianual: Bruto, Neto y Bonus/Acciones"
    )


def _build_monthly_bruto_neto_bonus_chart(monthly_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    if monthly_view.empty:
        return _empty_chart("Evolución mensual: Bruto, Neto y Bonus/Acciones", height=300)
    chart_df = monthly_view[["Periodo_natural", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    chart_df = _coerce_finite(chart_df, ["total_devengado", "neto", "espp_gain", "rsu_gain"])
    if hide_amounts:
        chart_df[["total_devengado", "neto", "espp_gain", "rsu_gain"]] = 0.0

    salary_df = chart_df.melt(
        id_vars=["Periodo_natural"], value_vars=["total_devengado", "neto"], var_name="Serie", value_name="Importe"
    )
    salary_df["Grupo"] = "Salario"
    salary_df["Serie"] = salary_df["Serie"].map({"total_devengado": "Bruto", "neto": "Neto"})
    bonus_df = chart_df.melt(
        id_vars=["Periodo_natural"], value_vars=["espp_gain", "rsu_gain"], var_name="Serie", value_name="Importe"
    )
    bonus_df["Grupo"] = "Bonus"
    bonus_df["Serie"] = bonus_df["Serie"].map({"espp_gain": "ESPP", "rsu_gain": "RSU"})
    combined_df = pd.concat([salary_df, bonus_df], ignore_index=True)
    combined_df = _coerce_finite(combined_df, ["Importe"])
    order = chart_df["Periodo_natural"].tolist()
    line = (
        alt.Chart(combined_df)
        .transform_filter(alt.datum.Grupo == "Salario")
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€"),
            color=alt.Color(
                "Serie:N",
                scale=ordered_scale(["Bruto", "Neto"]),
                legend=legend_circle("Salario"),
            ),
            tooltip=["Periodo_natural:N", "Serie:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    bars = (
        alt.Chart(combined_df)
        .transform_filter(alt.datum.Grupo == "Bonus")
        .mark_bar(opacity=0.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Serie:N",
                scale=ordered_scale(["ESPP", "RSU"], start_index=2),
                legend=legend_circle("Bonus"),
            ),
            tooltip=["Periodo_natural:N", "Serie:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    return (bars + line).resolve_scale(color="independent").properties(
        height=300, title="Evolución mensual: Bruto, Neto y Bonus/Acciones"
    )


def _build_irpf_followup_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> alt.Chart:
    if df.empty:
        return _empty_chart(title, height=300)
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
        .mark_line(point=True, color=COLOR_1, strokeWidth=2.5)
        .encode(
            x=alt.X(f"{x_col}:N", sort=order, title="Periodo" if x_col == "Periodo_natural" else "Año"),
            y=alt.Y("IRPF:Q", title="% IRPF", scale=y_scale),
            tooltip=[f"{x_col}:N", alt.Tooltip("IRPF:Q", format=".2f")],
        )
    )
    rule = alt.Chart(target_df).mark_rule(color=COLOR_5, strokeDash=[6, 4]).encode(y="target:Q")
    return (line + rule).properties(height=300, title=title)


def _build_deductions_waterfall(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    if annual_view.empty:
        return _empty_chart("Desglose de Bruto YTD", height=280)
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
    breakdown = _coerce_finite(breakdown, ["importe"])
    return (
        alt.Chart(breakdown)
        .mark_bar(opacity=0.5)
        .encode(
            x=alt.X("periodo:N", title=""),
            y=alt.Y("importe:Q", title="€", stack=True),
            color=alt.Color(
                "componente:N",
                scale=ordered_scale(["Neto", "IRPF", "Seg. Social", "Otras deducciones"]),
                legend=legend_circle("Componente"),
            ),
            tooltip=["componente:N", alt.Tooltip("importe:Q", format=",.2f")],
        )
        .properties(height=280, title=f"Desglose de Bruto YTD (total {bruto:,.2f} €)")
    )


def _build_savings_mix_chart(monthly_year_scope: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    if monthly_year_scope.empty:
        return _empty_chart("Composición mensual: ahorro y consumo", height=280)
    df = monthly_year_scope[["Periodo_natural", "ahorro_fiscal", "ahorro_jub_total", "consumo_especie"]].copy()
    df = _coerce_finite(df, ["ahorro_fiscal", "ahorro_jub_total", "consumo_especie"])
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
    long_df = _coerce_finite(long_df, ["Importe"])
    order = df["Periodo_natural"].tolist()
    return (
        alt.Chart(long_df)
        .mark_bar(opacity=0.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Tipo:N",
                scale=ordered_scale(["Ahorro fiscal", "Ahorro jubilación", "Consumo en especie"]),
                legend=legend_circle("Tipo"),
            ),
            tooltip=["Periodo_natural:N", "Tipo:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
        .properties(height=280, title="Composición mensual: ahorro y consumo")
    )


def _build_income_mix_area_chart(monthly_year_scope: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    if monthly_year_scope.empty:
        return _empty_chart("Ingresos totales: desglose por componente", height=280)
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
    plot_df = _coerce_finite(plot_df, ["Neto", "Ahorro jub. empresa", "ESPP neto estimado", "RSU neto estimado"])
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
    long_df = _coerce_finite(long_df, ["Importe"])
    order = plot_df["Periodo_natural"].tolist()
    return (
        alt.Chart(long_df)
        .mark_area(opacity=0.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=order, title="Periodo"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color(
                "Fuente:N",
                scale=ordered_scale(["Neto", "Ahorro jub. empresa", "ESPP neto estimado", "RSU neto estimado"]),
                legend=legend_circle("Fuente"),
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
    if annual_view.empty and monthly_view.empty:
        st.info("Sin datos suficientes para renderizar la sección de comparativa y evolución.")
        return
    with st.container():
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
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.altair_chart(_build_deductions_waterfall(annual_view=annual_view, hide_amounts=hide_amounts), use_container_width=True)
        with r1c2:
            st.altair_chart(_build_savings_mix_chart(monthly_year_scope=monthly_year_scope, hide_amounts=hide_amounts), use_container_width=True)
        st.altair_chart(
            _build_income_mix_area_chart(monthly_year_scope=monthly_year_scope, hide_amounts=hide_amounts),
            use_container_width=True,
        )

