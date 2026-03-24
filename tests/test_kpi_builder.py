import pandas as pd

from kpi_builder import build_all_kpis


def _sample_nominas_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # 2025-12
            {"Año": 2025, "Mes": 12, "Concepto": "SALARIO BASE", "Importe": 3000, "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": 2025, "Mes": 12, "Concepto": "TRIBUTACION I.R.P.F.", "Importe": -600, "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
            {"Año": 2025, "Mes": 12, "Concepto": "COTIZACION CONT.COMU", "Importe": -150, "Categoría": "Devengo", "Subcategoría": "Seguridad Social"},
            {"Año": 2025, "Mes": 12, "Concepto": "PLAN PENSIONES - APORT EMPRESA", "Importe": 100, "Categoría": "Ingreso", "Subcategoría": "Ahorro Jubilación"},
            {"Año": 2025, "Mes": 12, "Concepto": "APORT. EMPLEADO P. PENS.", "Importe": -50, "Categoría": "Devengo", "Subcategoría": "Ahorro Jubilación"},
            {"Año": 2025, "Mes": 12, "Concepto": "TICKET RESTAURANT - NO IRPF", "Importe": 100, "Categoría": "Ingreso", "Subcategoría": "Beneficio en Especie"},
            # 2026-01
            {"Año": 2026, "Mes": 1, "Concepto": "SALARIO BASE", "Importe": 3200, "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": 2026, "Mes": 1, "Concepto": "TRIBUTACION I.R.P.F.", "Importe": -700, "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
            {"Año": 2026, "Mes": 1, "Concepto": "ESPP GAIN", "Importe": 500, "Categoría": "Ingreso", "Subcategoría": "Ingreso Variable (ESPP)"},
        ]
    )


def test_build_all_kpis_shapes() -> None:
    monthly, annual, espp = build_all_kpis(_sample_nominas_df())
    assert len(monthly) == 2
    assert len(annual) == 2
    assert len(espp) == 1


def test_monthly_core_values() -> None:
    monthly, _, _ = build_all_kpis(_sample_nominas_df())
    m_2025 = monthly[(monthly["Año"] == 2025) & (monthly["Mes"] == 12)].iloc[0]
    assert m_2025["neto"] == 2400
    assert m_2025["total_devengado"] == 3200
    assert m_2025["total_deducir"] == 800
    assert m_2025["irpf_importe"] == 600
    assert m_2025["ahorro_jub_total"] == 150


def test_annual_yoy_delta() -> None:
    _, annual, _ = build_all_kpis(_sample_nominas_df())
    a_2025 = annual[annual["Año"] == 2025].iloc[0]
    a_2026 = annual[annual["Año"] == 2026].iloc[0]
    assert a_2025["delta_neto_vs_anterior"] == 0
    assert a_2026["delta_neto_vs_anterior"] == a_2026["neto"] - a_2025["neto"]


def test_importe_spanish_decimal_parsing_regression() -> None:
    df = pd.DataFrame(
        [
            {"Año": "2025", "Mes": "12", "Concepto": "SALARIO BASE", "Importe": "1.797,37", "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": "2025", "Mes": "12", "Concepto": "TRIBUTACION I.R.P.F.", "Importe": "-1.779,24", "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
        ]
    )
    monthly, _, _ = build_all_kpis(df)
    m = monthly.iloc[0]
    assert m["total_devengado"] == 1797.37
    assert m["total_deducir"] == 1779.24
    assert round(m["neto"], 2) == 18.13
