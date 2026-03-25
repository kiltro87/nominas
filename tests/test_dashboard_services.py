import pandas as pd

from nominas.services.dashboard_data import (
    build_nominas_view,
    build_quality_alerts,
    filter_kpi_views,
    parse_spanish_amount_series,
)


def _sample_monthly() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Año": 2025, "Mes": 1, "Periodo": "2025-01", "Periodo_natural": "Ene 2025", "neto": 1000, "pct_irpf": 0.2},
            {"Año": 2025, "Mes": 2, "Periodo": "2025-02", "Periodo_natural": "Feb 2025", "neto": -50, "pct_irpf": 0.7},
            {"Año": 2026, "Mes": 1, "Periodo": "2026-01", "Periodo_natural": "Ene 2026", "neto": 1100, "pct_irpf": 0.25},
        ]
    )


def _sample_annual() -> pd.DataFrame:
    return pd.DataFrame([{"Año": 2025}, {"Año": 2026}])


def test_parse_spanish_amount_series() -> None:
    s = pd.Series(["1.234,56", "-10,00", "foo"])
    out = parse_spanish_amount_series(s)
    assert list(out.round(2)) == [1234.56, -10.0, 0.0]


def test_filter_kpi_views_year_and_month() -> None:
    views = filter_kpi_views(_sample_monthly(), _sample_annual(), year_option=2025, period_option="2025-01")
    assert len(views.monthly_view) == 1
    assert int(views.monthly_view.iloc[0]["Mes"]) == 1
    assert len(views.annual_view) == 1
    assert views.period_options == ["Todos", "2025-01", "2025-02"]


def test_build_quality_alerts_emits_expected_messages() -> None:
    monthly = _sample_monthly()
    monthly_scope = monthly[monthly["Año"] == 2025].copy()
    alerts, rows = build_quality_alerts(
        monthly_view=monthly_scope,
        monthly_year_scope=monthly_scope,
        year_option=2025,
        period_option="Todos",
    )
    assert any("Neto mensual negativo" in x for x in alerts)
    assert any("% IRPF mensual > 60%" in x for x in alerts)
    assert any("Faltan meses en el año seleccionado" in x for x in alerts)
    assert len(rows) >= 2


def test_build_nominas_view_filters_and_sorts() -> None:
    df = pd.DataFrame(
        [
            {"Año": "2025", "Mes": "2", "Concepto": "B", "Importe": "10"},
            {"Año": "2025", "Mes": "1", "Concepto": "A", "Importe": "10"},
            {"Año": "2026", "Mes": "1", "Concepto": "A", "Importe": "10"},
        ]
    )
    out = build_nominas_view(df, year_option=2025, period_option="Todos")
    assert list(out["Mes"]) == [1, 2]

