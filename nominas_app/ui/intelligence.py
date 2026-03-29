from __future__ import annotations

import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas_app.ui.formatting import show_eur


def _safe_float(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _kpi_card(title: str, value: str, subtitle: str, delta: str | None = None) -> None:
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.caption(title)
        with c2:
            if delta:
                st.caption(delta)
        st.markdown(f"### {value}")
        st.caption(subtitle)


def _render_overview(
    annual_view: pd.DataFrame,
    monthly_view: pd.DataFrame,
    year_option: int | str,
    hide_amounts: bool,
) -> None:
    y = annual_view.sort_values("Año").iloc[-1]
    m = monthly_view.sort_values(["Año", "Mes"]).iloc[-1]
    prev = annual_view[annual_view["Año"] == int(y["Año"]) - 1]
    prev_row = prev.iloc[-1] if not prev.empty else None

    neto_mensual = _safe_float(m["neto"])
    irpf_efectivo = _safe_float(y["pct_irpf_efectivo_anual"]) * 100.0
    ahorro_capital = _safe_float(y["ahorro_jub_total"]) + _safe_float(y["espp_gain"]) + _safe_float(y["rsu_gain"])
    coste_empresa = _safe_float(y["total_devengado"]) + _safe_float(y["ss_importe"])

    ahorro_delta = None
    irpf_delta = None
    if prev_row is not None:
        prev_ahorro = _safe_float(prev_row["ahorro_jub_total"]) + _safe_float(prev_row["espp_gain"]) + _safe_float(prev_row["rsu_gain"])
        if prev_ahorro != 0:
            ahorro_delta = f"↗ {(ahorro_capital - prev_ahorro) / abs(prev_ahorro) * 100:.2f}%"
        prev_irpf = _safe_float(prev_row["pct_irpf_efectivo_anual"]) * 100.0
        irpf_delta = f"↘ {irpf_efectivo - prev_irpf:.2f} pp"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi_card("Sueldo Neto Mensual", show_eur(neto_mensual, hide_amounts), "Base sobre jornada completa")
    with k2:
        _kpi_card("Eficiencia Fiscal (IRPF)", f"{irpf_efectivo:.2f}%", "Promedio anual acumulado", irpf_delta)
    with k3:
        _kpi_card("Ahorro & Capital", show_eur(ahorro_capital, hide_amounts), "Incluye ESPP, RSU y Jubilacion", ahorro_delta)
    with k4:
        _kpi_card("Coste Empresa Total", show_eur(coste_empresa, hide_amounts), "Estimacion incluyendo SS")

    left, right = st.columns([2.1, 1.0])
    with left:
        with st.container(border=True):
            st.subheader("Flujo de Compensación")
            st.caption("Visualización del Bruto vs Neto Real")
            st.markdown(f"**SALARIO BRUTO ANUAL**: {show_eur(_safe_float(y['total_devengado']), hide_amounts)}")
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**Retenciones & Gastos**")
                irpf = _safe_float(y["irpf_importe"])
                ss = _safe_float(y["ss_importe"])
                total_deducido = _safe_float(y["total_deducir"])
                base = max(_safe_float(y["total_devengado"]), 1.0)
                st.progress(min(max(irpf / base, 0.0), 1.0), text=f"IRPF {irpf / base * 100:.1f}%")
                st.progress(min(max(ss / base, 0.0), 1.0), text=f"Seguridad Social {ss / base * 100:.1f}%")
                st.metric("TOTAL DEDUCIDO", show_eur(total_deducido, hide_amounts))
            with d2:
                st.markdown("**Patrimonio Generado**")
                neto = _safe_float(y["neto"])
                ahorro_diferido = _safe_float(y["ahorro_jub_total"])
                st.progress(min(max(neto / base, 0.0), 1.0), text=f"Neto Efectivo {neto / base * 100:.1f}%")
                st.progress(min(max(ahorro_diferido / base, 0.0), 1.0), text=f"Ahorro Diferido {ahorro_diferido / base * 100:.1f}%")
                st.metric("NETO + AHORRO", show_eur(neto + ahorro_diferido, hide_amounts))
            st.info(
                "Análisis de Eficiencia: al optimizar retribución flexible en especie "
                "puedes reducir la base imponible en determinados escenarios."
            )

    with right:
        with st.container(border=True):
            st.subheader("Stocks & Inversión")
            st.caption("YTD actual")
            espp = _safe_float(y["espp_gain"])
            rsu = _safe_float(y["rsu_gain"])
            st.metric("ESPP (Stock Purchase)", show_eur(espp, hide_amounts), "Aportación con descuento")
            st.metric("RSUs (Vesting)", show_eur(rsu, hide_amounts))
            st.button("Ver Plan de Acciones", use_container_width=True, key="pi_plan_acciones_btn")
        with st.container(border=True):
            st.subheader("Simulador de Variable")
            st.caption("Calcula cuánto recibirás neto de tu bonus anual tras impuestos.")
            bruto_bonus = st.number_input("Bonus bruto estimado (€)", min_value=0.0, value=5000.0, step=500.0, key="pi_bonus_input")
            tipo = irpf_efectivo / 100.0
            neto_bonus = bruto_bonus * (1 - tipo)
            st.metric("Bonus neto estimado", show_eur(neto_bonus, hide_amounts))

    if year_option == "Todos":
        st.caption("Vista consolidada para todos los años (usando el último disponible para KPIs principales).")
    else:
        st.caption(f"Vista enfocada al año {year_option}.")


def render_payroll_intelligence(
    annual_view: pd.DataFrame,
    monthly_view: pd.DataFrame,
    year_option: int | str,
    hide_amounts: bool,
) -> None:
    if annual_view.empty or monthly_view.empty:
        st.info("Sin datos suficientes para construir Payroll Intelligence.")
        return

    st.title("Payroll Intelligence")
    st.caption("Análisis detallado de compensación y eficiencia fiscal")
    tabs = st.tabs(["OVERVIEW", "TAX", "INVESTMENTS", "EVOLUTION"])

    with tabs[0]:
        _render_overview(
            annual_view=annual_view,
            monthly_view=monthly_view,
            year_option=year_option,
            hide_amounts=hide_amounts,
        )
    with tabs[1]:
        st.info("Bloque TAX en preparación sobre la misma base de métricas.")
    with tabs[2]:
        st.info("Bloque INVESTMENTS en preparación (ESPP/RSU detallado).")
    with tabs[3]:
        st.info("Bloque EVOLUTION en preparación (timeline y comparativa anual).")
