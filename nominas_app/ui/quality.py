from __future__ import annotations

import pandas as pd
import streamlit as st

from kpi_builder import format_eur
from nominas_app.services.dashboard_data import parse_spanish_amount_series
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
        quality_adv: list[dict[str, str]] = []
        nom_base = nominas_view.copy()
        nom_base["Concepto_up"] = nom_base["Concepto"].astype(str).str.upper()
        nom_base["Importe_num"] = parse_spanish_amount_series(nom_base["Importe"])
        salario_base = (
            nom_base[nom_base["Concepto_up"].str.contains("SALARIO BASE", na=False)]
            .groupby(["Año", "Mes"], as_index=False)["Importe_num"]
            .sum()
            .sort_values(["Año", "Mes"])
        )
        if not salario_base.empty:
            med = float(salario_base["Importe_num"].median())
            if med != 0:
                salario_base["desv_pct"] = (salario_base["Importe_num"] - med).abs() / abs(med)
                outliers = salario_base[salario_base["desv_pct"] > 0.20]
                for _, r in outliers.iterrows():
                    quality_adv.append(
                        {
                            "Periodo": f"{int(r['Año'])}-{int(r['Mes']):02d}",
                            "Regla": "SALARIO BASE fuera de rango (>20% de mediana)",
                            "Valor": format_eur(float(r["Importe_num"])),
                        }
                    )
        if quality_adv:
            st.dataframe(zebra_styler(pd.DataFrame(quality_adv)), width="stretch")
        else:
            st.info("Sin outliers detectados en SALARIO BASE con regla actual.")

    with st.expander("Calendario de cobertura"):
        coverage = monthly[["Año", "Mes"]].copy()
        coverage["present"] = "OK"
        coverage_pivot = (
            coverage.pivot_table(index="Año", columns="Mes", values="present", aggfunc="first", fill_value="")
            .reindex(columns=list(range(1, 13)), fill_value="")
            .rename(columns={i: f"{i:02d}" for i in range(1, 13)})
            .reset_index()
        )
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

