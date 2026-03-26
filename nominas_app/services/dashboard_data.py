from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from kpi_builder import format_eur


def parse_spanish_amount_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0.0)


@dataclass
class FilteredViews:
    monthly_view: pd.DataFrame
    annual_view: pd.DataFrame
    monthly_year_scope: pd.DataFrame
    period_options: list[str]


def filter_kpi_views(
    monthly: pd.DataFrame,
    annual: pd.DataFrame,
    year_option: int | str,
    period_option: str,
) -> FilteredViews:
    if year_option == "Todos":
        monthly_view = monthly.copy()
        annual_view = annual.copy()
    else:
        selected_year = int(year_option)
        monthly_view = monthly[monthly["Año"] == selected_year].copy()
        annual_view = annual[annual["Año"] == selected_year].copy()

    monthly_year_scope = monthly_view.copy()
    period_options = ["Todos"] + monthly_view["Periodo"].drop_duplicates().sort_values().tolist()
    if period_option != "Todos":
        monthly_view = monthly_view[monthly_view["Periodo"] == period_option].copy()

    monthly_view = monthly_view.sort_values(["Año", "Mes"]).reset_index(drop=True)
    annual_view = annual_view.sort_values(["Año"]).reset_index(drop=True)
    return FilteredViews(
        monthly_view=monthly_view,
        annual_view=annual_view,
        monthly_year_scope=monthly_year_scope,
        period_options=period_options,
    )


def build_quality_alerts(
    monthly_view: pd.DataFrame,
    monthly_year_scope: pd.DataFrame,
    year_option: int | str,
    period_option: str,
) -> tuple[list[str], list[dict[str, str]]]:
    alertas: list[str] = []
    if (monthly_view["neto"] < 0).any():
        bad_periods = monthly_view.loc[monthly_view["neto"] < 0, "Periodo_natural"].tolist()
        alertas.append(f"Neto mensual negativo en: {', '.join(bad_periods)}")
    if (monthly_view["pct_irpf"] > 0.60).any():
        high_periods = monthly_view.loc[monthly_view["pct_irpf"] > 0.60, "Periodo_natural"].tolist()
        alertas.append(f"% IRPF mensual > 60% en: {', '.join(high_periods)}")
    if year_option != "Todos" and period_option == "Todos":
        months_present = set(monthly_year_scope["Mes"].astype(int).tolist())
        expected = set(range(1, 13))
        missing = sorted(expected - months_present)
        if missing:
            alertas.append(f"Faltan meses en el año seleccionado: {', '.join(str(m) for m in missing)}")

    quality_rows: list[dict[str, str]] = []
    for _, row in monthly_view.iterrows():
        periodo = str(row["Periodo_natural"])
        if float(row["neto"]) < 0:
            quality_rows.append(
                {"Periodo": periodo, "Alerta": "Neto mensual negativo", "Detalle": format_eur(float(row["neto"]))}
            )
        if float(row["pct_irpf"]) > 0.60:
            quality_rows.append(
                {"Periodo": periodo, "Alerta": "% IRPF mensual > 60%", "Detalle": f"{float(row['pct_irpf']) * 100:.2f}%"}
            )
    return alertas, quality_rows


def build_nominas_view(df_nominas: pd.DataFrame, year_option: int | str, period_option: str) -> pd.DataFrame:
    nominas_view = df_nominas.copy()
    nominas_view["Año"] = pd.to_numeric(nominas_view["Año"], errors="coerce")
    nominas_view["Mes"] = pd.to_numeric(nominas_view["Mes"], errors="coerce")
    nominas_view = nominas_view.dropna(subset=["Año", "Mes"]).copy()
    nominas_view["Año"] = nominas_view["Año"].astype(int)
    nominas_view["Mes"] = nominas_view["Mes"].astype(int)
    if year_option != "Todos":
        nominas_view = nominas_view[nominas_view["Año"] == int(year_option)].copy()
    if period_option != "Todos":
        p_year, p_month = period_option.split("-")
        nominas_view = nominas_view[
            (nominas_view["Año"] == int(p_year)) & (nominas_view["Mes"] == int(p_month))
        ].copy()
    return nominas_view.sort_values(["Año", "Mes", "Concepto"]).reset_index(drop=True)

