from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas.services.dashboard_data import parse_spanish_amount_series
from nominas.ui.formatting import apply_privacy_to_columns, show_compact_eur, zebra_styler


def render_monthly_detail(monthly_view: pd.DataFrame, hide_amounts: bool) -> None:
    with st.expander("Información mensual explicada"):
        detail_cols = [
            "Año",
            "Mes",
            "Periodo_natural",
            "neto",
            "total_devengado",
            "total_deducir",
            "irpf_importe",
            "ss_importe",
            "ahorro_fiscal",
            "riqueza_real_mensual",
            "ahorro_jub_empresa",
            "ahorro_jub_empleado",
            "ahorro_jub_total",
            "ingresos_libres_impuestos",
            "espp_gain",
            "espp_neto_estimado",
            "rsu_gain",
            "rsu_neto_estimado",
            "fijo_ingreso",
            "variable_ingreso",
            "beneficio_especie",
            "pct_irpf",
            "pct_ss",
            "pct_variable",
        ]
        detail_df = monthly_view[detail_cols].rename(
            columns={
                "Periodo_natural": "Periodo",
                "neto": "Neto",
                "total_devengado": "Total devengado",
                "total_deducir": "Total a deducir",
                "irpf_importe": "IRPF (€)",
                "ss_importe": "Seguridad Social (€)",
                "ahorro_fiscal": "Ahorro fiscal (€)",
                "riqueza_real_mensual": "Ingresos totales (€)",
                "ahorro_jub_empresa": "Ahorro jub. empresa (€)",
                "ahorro_jub_empleado": "Ahorro jub. empleado (€)",
                "ahorro_jub_total": "Ahorro jubilación total (€)",
                "ingresos_libres_impuestos": "Ingresos libres impuestos (€)",
                "espp_gain": "ESPP Gain bruto (€)",
                "espp_neto_estimado": "ESPP neto estimado (€)",
                "rsu_gain": "RSU Gain bruto (€)",
                "rsu_neto_estimado": "RSU neto estimado (€)",
                "fijo_ingreso": "Ingreso fijo (€)",
                "variable_ingreso": "Ingreso variable (€)",
                "beneficio_especie": "Beneficio en especie (€)",
                "pct_irpf": "% IRPF",
                "pct_ss": "% SS",
                "pct_variable": "% variable",
            }
        )
        for col in ["% IRPF", "% SS", "% variable"]:
            if col in detail_df.columns:
                detail_df[col] = (detail_df[col].astype(float) * 100).round(2)
        detail_df = apply_privacy_to_columns(
            detail_df,
            [
                "Neto",
                "Total devengado",
                "Total a deducir",
                "IRPF (€)",
                "Seguridad Social (€)",
                "Ahorro fiscal (€)",
                "Ingresos totales (€)",
                "Ahorro jub. empresa (€)",
                "Ahorro jub. empleado (€)",
                "Ahorro jubilación total (€)",
                "Ingresos libres impuestos (€)",
                "ESPP Gain bruto (€)",
                "ESPP neto estimado (€)",
                "RSU Gain bruto (€)",
                "RSU neto estimado (€)",
                "Ingreso fijo (€)",
                "Ingreso variable (€)",
                "Beneficio en especie (€)",
            ],
            hide_amounts,
        )
        st.dataframe(zebra_styler(detail_df), width="stretch")
        detail_csv = detail_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Descargar detalle mensual (CSV)",
            data=detail_csv,
            file_name="detalle_mensual.csv",
            mime="text/csv",
        )


def render_breakdown(
    nominas_view: pd.DataFrame,
    monthly_view: pd.DataFrame,
    period_option: str,
    hide_amounts: bool,
) -> None:
    with st.expander("Desglose mensual"):
        breakdown = nominas_view.copy()
        breakdown["Concepto_agrupado"] = breakdown["Concepto"].astype(str)
        irpf_mask = breakdown["Concepto_agrupado"].str.upper().str.contains(r"^TRIBUTACION\s+I\.?R\.?P\.?F\.?", regex=True)
        breakdown.loc[irpf_mask, "Concepto_agrupado"] = "TRIBUTACION I.R.P.F."
        ctrl1, ctrl2, ctrl3, ctrl4, ctrl5, ctrl6 = st.columns(6)
        with ctrl1:
            grouping_mode = st.selectbox(
                "Agrupar por",
                options=["Concepto", "Subcategoría"],
                index=0,
                key="breakdown_grouping_mode",
            )
        with ctrl2:
            concept_filter = st.text_input(
                "Buscar texto",
                value="",
                key="breakdown_text_filter",
                placeholder="Ej. IRPF, ESPP, SALARIO...",
            ).strip()
        with ctrl3:
            only_changes = st.checkbox("Solo con cambios (Δ abs != 0)", value=False, key="breakdown_only_changes")
        with ctrl4:
            hide_zero_rows = st.checkbox("Ocultar filas en cero", value=True, key="breakdown_hide_zeros")
        with ctrl5:
            top_n = st.number_input("Top filas", min_value=10, max_value=5000, value=200, step=10, key="breakdown_top_n")
        with ctrl6:
            expand_amounts = st.checkbox("Expandir importes", value=True, key="breakdown_expand_amounts")
        breakdown["Importe_num"] = parse_spanish_amount_series(breakdown["Importe"])
        breakdown["Periodo"] = (
            breakdown["Año"].astype(int).astype(str) + "-" + breakdown["Mes"].astype(int).astype(str).str.zfill(2)
        )
        if grouping_mode == "Subcategoría":
            breakdown["Clave_desglose"] = breakdown["Subcategoría"].astype(str)
            index_col_name = "Subcategoría"
        else:
            breakdown["Clave_desglose"] = breakdown["Concepto_agrupado"]
            index_col_name = "Concepto"

        if period_option == "Todos":
            month_order = monthly_view["Periodo"].drop_duplicates().tolist()
        else:
            month_order = [period_option]

        pivot = (
            breakdown.pivot_table(
                index="Clave_desglose",
                columns="Periodo",
                values="Importe_num",
                aggfunc="sum",
                fill_value=0.0,
            )
            .reindex(columns=month_order, fill_value=0.0)
            .reset_index()
        )
        pivot = pivot.rename(columns={"Clave_desglose": index_col_name})

        if period_option == "Todos" and len(month_order) >= 2:
            latest = month_order[-1]
            prev = month_order[-2]
            pivot["Δ abs"] = pivot[latest] - pivot[prev]
            pivot["Δ %"] = pivot.apply(
                lambda r: ((r[latest] - r[prev]) / r[prev] * 100.0) if float(r[prev]) != 0 else 0.0, axis=1
            )
            if only_changes:
                pivot = pivot[pivot["Δ abs"] != 0].copy()
            pivot = pivot.sort_values(by="Δ abs", ascending=False, key=lambda s: s.abs()).reset_index(drop=True)
        else:
            value_cols = [c for c in pivot.columns if c != index_col_name]
            if value_cols:
                pivot["_sort_abs"] = pivot[value_cols].abs().sum(axis=1)
                pivot = pivot.sort_values("_sort_abs", ascending=False).drop(columns=["_sort_abs"]).reset_index(drop=True)

        if concept_filter:
            pivot = pivot[
                pivot[index_col_name].astype(str).str.contains(re.escape(concept_filter), case=False, na=False)
            ].copy()
        if hide_zero_rows:
            numeric_cols = [c for c in pivot.columns if c not in {index_col_name, "Δ %"}]
            if numeric_cols:
                non_zero_mask = pivot[numeric_cols].fillna(0.0).abs().sum(axis=1) != 0
                pivot = pivot[non_zero_mask].copy()
        pivot = pivot.head(int(top_n))

        if pivot.empty:
            st.info(
                "No hay filas para el desglose con los filtros actuales. "
                "Prueba a quitar 'Solo con cambios', ampliar el Top, o limpiar la búsqueda."
            )
        else:
            if hide_amounts:
                for col in [c for c in pivot.columns if c != index_col_name]:
                    pivot[col] = "••••••"
            else:
                eur_cols = [c for c in pivot.columns if c not in {index_col_name, "Δ %"}]
                for col in eur_cols:
                    if expand_amounts:
                        pivot[col] = pivot[col].apply(lambda x: format_eur(float(x)))
                    else:
                        pivot[col] = pivot[col].apply(lambda x: show_compact_eur(float(x)))
                if "Δ %" in pivot.columns:
                    pivot["Δ %"] = pivot["Δ %"].apply(lambda x: f"{float(x):.2f}%")

            st.dataframe(zebra_styler(pivot), width="stretch")
        csv_payload = pivot.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Descargar desglose mensual (CSV)",
            data=csv_payload,
            file_name="desglose_mensual.csv",
            mime="text/csv",
        )

