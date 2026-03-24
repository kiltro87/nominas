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


def test_irpf_pct_is_read_from_dotted_concept_format() -> None:
    df = pd.DataFrame(
        [
            {"Año": 2025, "Mes": 12, "Concepto": "SALARIO BASE", "Importe": "9.765,62", "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": 2025, "Mes": 12, "Concepto": "TRIBUTACION I.R.P.F.33,17", "Importe": "-1.779,24", "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
        ]
    )
    monthly, _, _ = build_all_kpis(df)
    m = monthly.iloc[0]
    assert round(float(m["pct_irpf"]) * 100, 2) == 33.17


def test_negative_ingreso_reduces_devengado_not_deducciones() -> None:
    df = pd.DataFrame(
        [
            {"Año": 2025, "Mes": 1, "Concepto": "SALARIO BASE", "Importe": 1000, "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": 2025, "Mes": 1, "Concepto": "TAX REFUND", "Importe": -100, "Categoría": "Ingreso", "Subcategoría": "Impuestos (Ajustes)"},
            {"Año": 2025, "Mes": 1, "Concepto": "TRIBUTACION I.R.P.F.", "Importe": -200, "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
        ]
    )
    monthly, _, _ = build_all_kpis(df)
    m = monthly.iloc[0]
    assert m["total_devengado"] == 900
    assert m["total_deducir"] == 200
    assert m["neto"] == 700


def test_retrib_flexible_negative_goes_to_devengado() -> None:
    df = pd.DataFrame(
        [
            {"Año": 2025, "Mes": 1, "Concepto": "SALARIO BASE", "Importe": 1000, "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": 2025, "Mes": 1, "Concepto": "RETRIB. FLEXIBLE", "Importe": -100, "Categoría": "Devengo", "Subcategoría": "Beneficio en Especie"},
            {"Año": 2025, "Mes": 1, "Concepto": "TRIBUTACION I.R.P.F.", "Importe": -200, "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
        ]
    )
    monthly, _, _ = build_all_kpis(df)
    m = monthly.iloc[0]
    assert m["total_devengado"] == 900
    assert m["total_deducir"] == 200
    assert m["neto"] == 700


def test_refunds_in_deducciones_reduce_total_deducir() -> None:
    df = pd.DataFrame(
        [
            {"Año": 2025, "Mes": 1, "Concepto": "SALARIO BASE", "Importe": 1000, "Categoría": "Ingreso", "Subcategoría": "Ingreso Fijo"},
            {"Año": 2025, "Mes": 1, "Concepto": "TRIBUTACION I.R.P.F.", "Importe": -300, "Categoría": "Devengo", "Subcategoría": "Impuestos (IRPF)"},
            {"Año": 2025, "Mes": 1, "Concepto": "TAX REFUND", "Importe": -50, "Categoría": "Devengo", "Subcategoría": "Impuestos (Ajustes)"},
            {"Año": 2025, "Mes": 1, "Concepto": "ESPP REFUND", "Importe": -20, "Categoría": "Devengo", "Subcategoría": "Inversión Acciones (ESPP)"},
        ]
    )
    monthly, _, _ = build_all_kpis(df)
    m = monthly.iloc[0]
    assert m["total_devengado"] == 1000
    assert m["total_deducir"] == 230
    assert m["neto"] == 770


def test_missing_categoria_column_falls_back_to_sign_logic() -> None:
    df = pd.DataFrame(
        [
            {"Año": 2025, "Mes": 1, "Concepto": "SALARIO BASE", "Importe": 1000, "Subcategoría": "Ingreso Fijo"},
            {"Año": 2025, "Mes": 1, "Concepto": "TRIBUTACION I.R.P.F.", "Importe": -300, "Subcategoría": "Impuestos (IRPF)"},
        ]
    )
    monthly, _, _ = build_all_kpis(df)
    m = monthly.iloc[0]
    assert m["total_devengado"] == 1000
    assert m["total_deducir"] == 300
    assert m["neto"] == 700
