from __future__ import annotations

import pandas as pd
import streamlit as st

from nominas_app.services.dashboard_data import build_coverage_pivot
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

    with st.expander("Calendario de cobertura"):
        coverage_pivot = build_coverage_pivot(monthly=monthly)
        st.dataframe(zebra_styler(coverage_pivot), width="stretch")


def render_metric_definitions() -> None:
    return None

