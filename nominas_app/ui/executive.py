from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas_app.ui.formatting import show_eur, zebra_styler


def _apply_executive_styles() -> None:
    st.markdown(
        """
<style>
.exec-title {
  font-weight: 800;
  font-size: 1.1rem;
  letter-spacing: 0.01em;
  color: #0f2a52;
}
.exec-hero {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 45%, #eef2ff 100%);
  border: 1px solid #dbeafe;
  border-radius: 16px;
  padding: 0.8rem 1rem;
  margin-bottom: 0.45rem;
}
.exec-hero-title {
  font-size: 1.15rem;
  font-weight: 800;
  color: #0b2447;
}
.exec-subtle {
  color: #4b5563;
  font-size: 0.86rem;
}
.exec-card {
  background: linear-gradient(180deg, #f9fbff 0%, #f2f7ff 100%);
  border: 1px solid #dbeafe;
  border-radius: 14px;
  padding: 0.75rem 0.85rem;
}
.exec-card-value {
  font-size: 1.6rem;
  font-weight: 800;
  color: #0b2447;
  line-height: 1.1;
}
.exec-card-delta-up { color: #15803d; font-weight: 700; font-size: 0.9rem; }
.exec-card-delta-down { color: #b91c1c; font-weight: 700; font-size: 0.9rem; }
.exec-block-title {
  font-size: 1rem;
  font-weight: 750;
  color: #0f2a52;
  margin-bottom: 0.35rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_exec_card(title: str, value: str, subtitle: str, delta: float | None = None) -> None:
    delta_html = ""
    if delta is not None:
        delta_class = "exec-card-delta-up" if delta >= 0 else "exec-card-delta-down"
        delta_html = f"<div class='{delta_class}'>vs año anterior: {format_eur(float(delta))}</div>"
    st.markdown(
        (
            "<div class='exec-card'>"
            f"<div class='exec-title'>{title}</div>"
            f"<div class='exec-card-value'>{value}</div>"
            f"<div class='exec-subtle'>{subtitle}</div>"
            f"{delta_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _build_multiyear_chart(annual_view: pd.DataFrame, hide_amounts: bool) -> alt.Chart:
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
    bars = (
        alt.Chart(chart_df)
        .mark_bar(opacity=0.30, color="#f59e0b")
        .encode(
            x=alt.X("Año:O"),
            y=alt.Y("bonus_acciones:Q", title="€"),
            tooltip=["Año:O", alt.Tooltip("bonus_acciones:Q", format=",.2f")],
        )
    )
    return (bars + line).properties(height=285, title="Evolución multianual: Bruto, Neto y Bonus/Acciones")


def _build_irpf_chart(monthly_year_scope: pd.DataFrame) -> alt.Chart:
    month_df = monthly_year_scope[["Periodo_natural", "pct_irpf"]].copy()
    month_df["IRPF_real"] = pd.to_numeric(month_df["pct_irpf"], errors="coerce").fillna(0.0) * 100
    mean_value = float(month_df["IRPF_real"].mean()) if not month_df.empty else 0.0
    target_df = pd.DataFrame({"Objetivo": [mean_value], "k": [0]})

    line = (
        alt.Chart(month_df)
        .mark_line(point=True, color="#14b8a6", strokeWidth=2.5)
        .encode(
            x=alt.X("Periodo_natural:N", sort=month_df["Periodo_natural"].tolist(), title="Periodo"),
            y=alt.Y("IRPF_real:Q", title="% IRPF"),
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
    st.markdown("<div class='exec-block-title'>Estado de acciones y bonus</div>", unsafe_allow_html=True)
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
    st.markdown("<div class='exec-block-title'>Alertas y proximos hitos</div>", unsafe_allow_html=True)
    rows = quality_rows[:4]
    if not rows:
        st.success("Sin alertas de calidad activas para el filtro.")
    else:
        for row in rows:
            st.warning(f"{row['Periodo']}: {row['Alerta']}")
    st.info("Hitos sugeridos: revisión salarial (mar), bonus semestral (jun), bonus anual (sep-dic).")


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


def render_executive_dashboard(
    monthly_view: pd.DataFrame,
    annual_view: pd.DataFrame,
    monthly_year_scope: pd.DataFrame,
    year_option: int | str,
    hide_amounts: bool,
    quality_rows: list[dict[str, str]],
) -> None:
    _apply_executive_styles()
    st.markdown(
        (
            "<div class='exec-hero'>"
            "<div class='exec-hero-title'>Analisis estrategico y de evolucion anual</div>"
            "<div class='exec-subtle'>Vista ejecutiva Hybrid Premium (sin reemplazar el dashboard actual).</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    latest_year = annual_view.sort_values("Año").iloc[-1]
    prev_year = annual_view.sort_values("Año").iloc[-2] if len(annual_view) > 1 else None

    bruto_delta = (
        float(latest_year["total_devengado"] - prev_year["total_devengado"]) if prev_year is not None else None
    )
    bonus_total = float(latest_year["espp_gain"] + latest_year["rsu_gain"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _render_exec_card(
            "Costo total empresa (YTD)",
            show_eur(float(latest_year["total_devengado"]), hide_amounts),
            f"Año {int(latest_year['Año'])}",
            bruto_delta,
        )
    with c2:
        _render_exec_card(
            "Nomina neta media mensual",
            show_eur(float(latest_year["media_neto_mensual"]), hide_amounts),
            "Promedio del año filtrado",
        )
    with c3:
        _render_exec_card(
            "Deducciones YTD",
            show_eur(float(latest_year["total_deducir"]), hide_amounts),
            "Total anual acumulado",
        )
    with c4:
        _render_exec_card(
            "Bonus + acciones (YTD)",
            show_eur(bonus_total, hide_amounts),
            "ESPP + RSU",
        )

    left, mid, right = st.columns([2.2, 1.1, 1.3])
    with left:
        st.altair_chart(_build_multiyear_chart(annual_view=annual_view, hide_amounts=hide_amounts), use_container_width=True)
    with mid:
        _render_bonus_progress(bonus_value=bonus_total, hide_amounts=hide_amounts)
    with right:
        st.altair_chart(_build_irpf_chart(monthly_year_scope=monthly_year_scope), use_container_width=True)

    t1, t2, t3 = st.columns([1.5, 1.1, 1.2])
    with t1:
        st.markdown("<div class='exec-block-title'>Resumen de totales anuales</div>", unsafe_allow_html=True)
        summary = _build_annual_summary_table(annual_view=annual_view, hide_amounts=hide_amounts)
        st.dataframe(zebra_styler(summary), width="stretch")
    with t2:
        _render_alerts_and_hitos(quality_rows=quality_rows)
    with t3:
        st.markdown("<div class='exec-block-title'>Distribucion de gastos YTD</div>", unsafe_allow_html=True)
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

    if year_option == "Todos":
        st.caption("Mostrando evolucion completa (todos los años).")
    else:
        st.caption(f"Mostrando enfoque ejecutivo para el año {year_option}.")
