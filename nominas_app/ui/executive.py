from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas_app.services.dashboard_data import parse_spanish_amount_series
from nominas_app.ui.formatting import metric_with_help, show_eur, zebra_styler


def _build_multiyear_chart(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
    chart_df = annual_view[["Año", "total_devengado", "neto", "espp_gain", "rsu_gain"]].copy()
    if hide_amounts:
        chart_df[["total_devengado", "neto", "espp_gain", "rsu_gain"]] = 0.0

    long_df = chart_df.melt(
        id_vars=["Año"],
        value_vars=["total_devengado", "neto"],
        var_name="Métrica",
        value_name="Importe",
    )
    metric_labels = {"total_devengado": "Bruto", "neto": "Neto"}
    long_df["Métrica"] = long_df["Métrica"].map(metric_labels)

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
    bonus_df = chart_df.melt(
        id_vars=["Año"],
        value_vars=["espp_gain", "rsu_gain"],
        var_name="BonusTipo",
        value_name="Importe",
    )
    bonus_df["BonusTipo"] = bonus_df["BonusTipo"].map({"espp_gain": "ESPP", "rsu_gain": "RSU"})
    bars = (
        alt.Chart(bonus_df)
        .mark_bar(opacity=0.35)
        .encode(
            x=alt.X("Año:O"),
            y=alt.Y("Importe:Q", title="€", stack=True),
            color=alt.Color("BonusTipo:N", scale=alt.Scale(domain=["ESPP", "RSU"], range=["#f59e0b", "#a855f7"])),
            tooltip=["Año:O", "BonusTipo:N", alt.Tooltip("Importe:Q", format=",.2f")],
        )
    )
    return (bars + line).resolve_scale(color="independent").properties(
        height=285, title="Evolución multianual: Bruto, Neto y Bonus/Acciones"
    )


def _build_irpf_chart(monthly_year_scope: pd.DataFrame) -> alt.Chart:
    month_df = monthly_year_scope[["Periodo_natural", "pct_irpf"]].copy()
    month_df["IRPF_real"] = pd.to_numeric(month_df["pct_irpf"], errors="coerce").fillna(0.0) * 100
    values = pd.to_numeric(month_df["IRPF_real"], errors="coerce").dropna()
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
    mean_value = float(month_df["IRPF_real"].mean()) if not month_df.empty else 0.0
    target_df = pd.DataFrame({"Objetivo": [mean_value], "k": [0]})

    line = (
        alt.Chart(month_df)
        .mark_line(point=True, color="#14b8a6", strokeWidth=2.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=month_df["Periodo_natural"].tolist(), title="Periodo"),
            y=alt.Y("IRPF_real:Q", title="% IRPF", scale=y_scale),
            tooltip=["Periodo_natural:N", alt.Tooltip("IRPF_real:Q", format=".2f")],
        )
    )
    rule = (
        alt.Chart(target_df)
        .mark_rule(color="#475569", strokeDash=[6, 4])
        .encode(y="Objetivo:Q", tooltip=[alt.Tooltip("Objetivo:Q", format=".2f")])
    )
    return (line + rule).properties(height=240, title="Seguimiento de IRPF (anual)")


def _render_bonus_progress(bonus_value: float, hide_amounts: bool) -> None:
    with st.container(border=True):
        st.markdown("##### Estado de acciones y bonus")
        default_goal = float(max(round(bonus_value * 1.1, 2), 1.0))
        objective = st.number_input(
            "Objetivo anual bonus+acciones (€)",
            min_value=1.0,
            value=default_goal,
            step=100.0,
            key="exec_bonus_objective",
        )
        ratio = min(max(bonus_value / objective, 0.0), 1.0)
        st.progress(ratio)
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Logrado", show_eur(bonus_value, hide_amounts))
        with c2:
            st.metric("% logrado", f"{ratio * 100:.1f}%")


def _render_alerts_and_hitos(quality_rows: list[dict[str, str]]) -> None:
    with st.container(border=True):
        st.markdown("##### Alertas y proximos hitos")
        rows = quality_rows[:4]
        if not rows:
            st.success("Sin alertas de calidad activas para el filtro.")
        else:
            for row in rows:
                st.warning(f"{row['Periodo']}: {row['Alerta']}")
        st.info("Hitos sugeridos: revision salarial (mar), bonus semestral (jun), bonus anual (sep-dic).")


def _build_annual_summary_table(annual_view: pd.DataFrame, hide_amounts: bool) -> pd.DataFrame:
    table = annual_view[["Año", "total_devengado", "neto", "total_deducir", "espp_gain", "rsu_gain"]].copy()
    table["bonus_acciones"] = table["espp_gain"] + table["rsu_gain"]
    table = table.rename(
        columns={
            "total_devengado": "Bruto",
            "neto": "Neto",
            "total_deducir": "Deducciones",
            "bonus_acciones": "Bonus/Acciones",
        }
    )
    table = table[["Año", "Bruto", "Neto", "Deducciones", "Bonus/Acciones"]].sort_values("Año", ascending=False)
    if hide_amounts:
        for col in ["Bruto", "Neto", "Deducciones", "Bonus/Acciones"]:
            table[col] = "••••••"
    else:
        for col in ["Bruto", "Neto", "Deducciones", "Bonus/Acciones"]:
            table[col] = table[col].apply(lambda x: format_eur(float(x)))
    return table.reset_index(drop=True)


def _build_month_comparison(monthly_all: pd.DataFrame, monthly_view: pd.DataFrame, compare_mode: str) -> tuple[pd.Series | None, pd.Series | None]:
    if compare_mode == "Sin comparación" or monthly_view.empty:
        return None, None
    monthly_sorted = monthly_all.sort_values(["Año", "Mes"]).reset_index(drop=True)
    cur = monthly_view.sort_values(["Año", "Mes"]).iloc[-1]
    cur_year, cur_month = int(cur["Año"]), int(cur["Mes"])
    cmp_row = None
    if compare_mode == "Mes anterior":
        prev = monthly_sorted[
            (monthly_sorted["Año"] < cur_year) | ((monthly_sorted["Año"] == cur_year) & (monthly_sorted["Mes"] < cur_month))
        ]
        if not prev.empty:
            cmp_row = prev.iloc[-1]
    elif compare_mode == "Mismo mes año anterior":
        prev = monthly_sorted[(monthly_sorted["Año"] == cur_year - 1) & (monthly_sorted["Mes"] == cur_month)]
        if not prev.empty:
            cmp_row = prev.iloc[-1]
    return cur, cmp_row


def _render_period_comparison(monthly_all: pd.DataFrame, monthly_view: pd.DataFrame, compare_mode: str, hide_amounts: bool) -> None:
    with st.container(border=True):
        st.markdown("##### Comparativa del periodo")
        cur, cmp_row = _build_month_comparison(monthly_all=monthly_all, monthly_view=monthly_view, compare_mode=compare_mode)
        if compare_mode == "Sin comparación":
            st.info("Selecciona 'Comparar contra' para activar esta sección.")
            return
        if cur is None or cmp_row is None:
            st.info("No hay referencia suficiente para la comparación seleccionada.")
            return
        c1, c2, c3 = st.columns(3)
        c1.metric("Bruto", show_eur(float(cur["total_devengado"]), hide_amounts), delta=format_eur(float(cur["total_devengado"] - cmp_row["total_devengado"])))
        c2.metric("Neto", show_eur(float(cur["neto"]), hide_amounts), delta=format_eur(float(cur["neto"] - cmp_row["neto"])))
        c3.metric("% IRPF", f"{float(cur['pct_irpf']) * 100:.2f}%", delta=f"{(float(cur['pct_irpf']) - float(cmp_row['pct_irpf'])) * 100:.2f} pp")


def _render_equity_block(monthly_view: pd.DataFrame, annual_selected: pd.Series, hide_amounts: bool) -> None:
    with st.container(border=True):
        st.markdown("##### ESPP, RSU y plan de acciones")
        espp = float(annual_selected["espp_gain"])
        rsu = float(annual_selected["rsu_gain"])
        plan_neto = float(annual_selected["espp_neto_estimado"] + annual_selected["rsu_neto_estimado"])
        c1, c2, c3 = st.columns(3)
        c1.metric("ESPP (bruto anual)", show_eur(espp, hide_amounts))
        c2.metric("RSU (bruto anual)", show_eur(rsu, hide_amounts))
        c3.metric("Plan de acciones (neto estimado)", show_eur(plan_neto, hide_amounts))

        detail = monthly_view[["Periodo_natural", "espp_gain", "rsu_gain", "espp_neto_estimado", "rsu_neto_estimado"]].copy()
        detail = detail.rename(
            columns={
                "Periodo_natural": "Periodo",
                "espp_gain": "ESPP bruto",
                "rsu_gain": "RSU bruto",
                "espp_neto_estimado": "ESPP neto est.",
                "rsu_neto_estimado": "RSU neto est.",
            }
        )
        non_zero = (
            pd.to_numeric(detail["ESPP bruto"], errors="coerce").fillna(0.0) != 0.0
        ) | (
            pd.to_numeric(detail["RSU bruto"], errors="coerce").fillna(0.0) != 0.0
        )
        detail = detail[non_zero].reset_index(drop=True)
        if detail.empty:
            st.info("Sin movimientos de ESPP/RSU para el filtro actual.")
            return
        for col in ["ESPP bruto", "RSU bruto", "ESPP neto est.", "RSU neto est."]:
            detail[col] = detail[col].apply(lambda x: "••••••" if hide_amounts else format_eur(float(x)))
        st.dataframe(zebra_styler(detail), width="stretch")


def _render_supporting_tables(
    monthly_view: pd.DataFrame,
    nominas_view: pd.DataFrame,
    hide_amounts: bool,
) -> None:
    with st.container(border=True):
        st.markdown("##### Soporte analitico")
        left, right = st.columns(2)
        with left:
            st.caption("Detalle mensual clave")
            detail = monthly_view[
                ["Periodo_natural", "neto", "total_devengado", "total_deducir", "pct_irpf"]
            ].copy()
            detail = detail.rename(
                columns={
                    "Periodo_natural": "Periodo",
                    "neto": "Neto",
                    "total_devengado": "Bruto",
                    "total_deducir": "Deducciones",
                    "pct_irpf": "% IRPF",
                }
            )
            detail["% IRPF"] = (pd.to_numeric(detail["% IRPF"], errors="coerce").fillna(0.0) * 100).round(2).astype(str) + "%"
            for col in ["Neto", "Bruto", "Deducciones"]:
                detail[col] = detail[col].apply(lambda x: "••••••" if hide_amounts else format_eur(float(x)))
            st.dataframe(zebra_styler(detail.tail(6).reset_index(drop=True)), width="stretch")
        with right:
            st.caption("Top conceptos del filtro")
            base = nominas_view.copy()
            base["Importe_num"] = parse_spanish_amount_series(base["Importe"])
            top = (
                base.groupby("Concepto", as_index=False)["Importe_num"]
                .sum()
                .rename(columns={"Importe_num": "Importe"})
                .sort_values("Importe", ascending=False, key=lambda s: s.abs())
                .head(8)
                .reset_index(drop=True)
            )
            if top.empty:
                st.info("Sin conceptos para el filtro actual.")
            else:
                top["Importe"] = top["Importe"].apply(lambda x: "••••••" if hide_amounts else format_eur(float(x)))
                st.dataframe(zebra_styler(top), width="stretch")


def render_executive_dashboard(
    monthly_view: pd.DataFrame,
    monthly_all: pd.DataFrame,
    annual_view: pd.DataFrame,
    annual_all: pd.DataFrame,
    monthly_year_scope: pd.DataFrame,
    year_option: int | str,
    compare_mode: str,
    hide_amounts: bool,
    quality_rows: list[dict[str, str]],
    nominas_view: pd.DataFrame,
) -> None:
    with st.container(border=True):
        st.subheader("Analisis estrategico y evolucion anual")
        st.caption("Vista ejecutiva Hybrid Premium (sin reemplazar el dashboard actual).")

    latest_year = annual_view.sort_values("Año").iloc[-1]
    prev_year = annual_all[annual_all["Año"] == int(latest_year["Año"]) - 1]
    prev_year_row = prev_year.iloc[-1] if not prev_year.empty else None

    bruto_delta = (
        float(latest_year["total_devengado"] - prev_year_row["total_devengado"]) if prev_year_row is not None else None
    )
    neto_medio_delta = (
        float(latest_year["media_neto_mensual"] - prev_year_row["media_neto_mensual"]) if prev_year_row is not None else None
    )
    bonus_total = float(latest_year["espp_gain"] + latest_year["rsu_gain"])

    with st.container(border=True):
        st.markdown("##### KPIs estrategicos")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_with_help(
                c1,
                "Bruto",
                show_eur(float(latest_year["total_devengado"]), hide_amounts),
                delta=(format_eur(bruto_delta) if bruto_delta is not None else None),
            )
        with c2:
            c2.metric(
                "Nomina neta media mensual",
                show_eur(float(latest_year["media_neto_mensual"]), hide_amounts),
                delta=(format_eur(neto_medio_delta) if neto_medio_delta is not None else None),
            )
        with c3:
            c3.metric("Deducciones YTD", show_eur(float(latest_year["total_deducir"]), hide_amounts))
        with c4:
            c4.metric("Bonus + acciones (YTD)", show_eur(bonus_total, hide_amounts))

    left, mid, right = st.columns([2.2, 1.1, 1.3])
    with left:
        with st.container(border=True):
            st.altair_chart(
                _build_multiyear_chart(annual_view=annual_view, hide_amounts=hide_amounts),
                use_container_width=True,
            )
    with mid:
        _render_bonus_progress(bonus_value=bonus_total, hide_amounts=hide_amounts)
    with right:
        with st.container(border=True):
            st.altair_chart(_build_irpf_chart(monthly_year_scope=monthly_year_scope), use_container_width=True)

    t1, t2, t3 = st.columns([1.5, 1.1, 1.2])
    with t1:
        with st.container(border=True):
            st.markdown("##### Resumen de totales anuales")
            summary = _build_annual_summary_table(annual_view=annual_view, hide_amounts=hide_amounts)
            st.dataframe(zebra_styler(summary), width="stretch")
    with t2:
        _render_alerts_and_hitos(quality_rows=quality_rows)
    with t3:
        with st.container(border=True):
            st.markdown("##### Distribucion de gastos YTD")
            donut_df = pd.DataFrame(
                {
                    "Categoria": ["Neto", "Deducciones", "Bonus/Acciones"],
                    "Importe": [
                        float(latest_year["neto"]),
                        float(latest_year["total_deducir"]),
                        bonus_total,
                    ],
                }
            )
            if hide_amounts:
                donut_df["Importe"] = 1.0
            donut = (
                alt.Chart(donut_df)
                .mark_arc(innerRadius=65)
                .encode(
                    theta="Importe:Q",
                    color=alt.Color(
                        "Categoria:N",
                        scale=alt.Scale(range=["#14b8a6", "#f59e0b", "#3b82f6"]),
                    ),
                    tooltip=["Categoria:N", alt.Tooltip("Importe:Q", format=",.2f")],
                )
                .properties(height=270)
            )
            st.altair_chart(donut, use_container_width=True)

    _render_period_comparison(
        monthly_all=monthly_all,
        monthly_view=monthly_view,
        compare_mode=compare_mode,
        hide_amounts=hide_amounts,
    )
    _render_equity_block(
        monthly_view=monthly_view,
        annual_selected=latest_year,
        hide_amounts=hide_amounts,
    )
    _render_supporting_tables(
        monthly_view=monthly_view,
        nominas_view=nominas_view,
        hide_amounts=hide_amounts,
    )

    if year_option == "Todos":
        st.caption("Mostrando evolucion completa (todos los años).")
    else:
        st.caption(f"Mostrando enfoque ejecutivo para el año {year_option}.")
