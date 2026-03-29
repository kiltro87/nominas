from __future__ import annotations

import pandas as pd
import streamlit as st

from nominas_app.services.dashboard_data import build_coverage_pivot, build_salary_base_outliers
from nominas_app.ui.formatting import zebra_styler


def render_quality_sections(
    quality_rows: list[dict[str, str]],
    nominas_view: pd.DataFrame,
    monthly: pd.DataFrame,
) -> None:
    if quality_rows:
        with st.expander("Alertas de calidad detalladas"):
            quality_df = pd.DataFrame(quality_rows, columns=["Periodo", "Alerta", "Detalle"])
            st.dataframe(zebra_styler(quality_df), width="stretch")

    with st.expander("Calidad de datos avanzada"):
        quality_adv = build_salary_base_outliers(nominas_view=nominas_view, deviation_threshold=0.20)
        if quality_adv:
            st.dataframe(zebra_styler(pd.DataFrame(quality_adv)), width="stretch")
        else:
            st.info("Sin outliers detectados en SALARIO BASE con regla actual.")

    with st.expander("Calendario de cobertura"):
        coverage_pivot = build_coverage_pivot(monthly=monthly)
        st.dataframe(zebra_styler(coverage_pivot), width="stretch")


def render_metric_definitions() -> None:
    with st.expander("Definiciones de métricas"):
        st.markdown(
            """
- `Ingresos totales = neto + ahorro_jub_empresa + rsu_neto_estimado + espp_neto_estimado`
- `% IRPF mensual = porcentaje informado en nómina (ej. 33,17%) si está disponible; si no, aproximación por ratio`
- `Ahorro fiscal = ingresos_libres_impuestos * tipo marginal estimado (interno) + ahorro_jub_empresa`
- `Ingresos recibidos = neto + consumo_especie + ahorro_jub_total + espp_neto_estimado + rsu_neto_estimado`
- `IRPF efectivo anual = irpf_importe_anual / total_devengado_anual`
            """
        )

