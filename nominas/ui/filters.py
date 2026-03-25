from __future__ import annotations

import streamlit as st


def render_filters(available_years: list[int], period_options: list[str]) -> tuple[int | str, str, str]:
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        year_option = st.selectbox(
            "Filtro de año",
            options=["Todos"] + available_years,
            index=0,
            help="Selecciona un año para centrar KPIs y evolución mensual.",
        )

    with filter_col2:
        period_option = st.selectbox(
            "Filtro de mes",
            options=period_options,
            index=0,
            help="Opcional: filtra un mes concreto dentro del año seleccionado.",
        )
    with filter_col3:
        compare_mode = st.selectbox(
            "Comparar contra",
            options=["Sin comparación", "Mes anterior", "Mismo mes año anterior"],
            index=0,
            help="Aplica al bloque de KPIs mensuales.",
        )
    return year_option, period_option, compare_mode

