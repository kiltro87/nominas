from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from kpi_builder import format_eur

COMPARE_MODE_NONE = "Sin comparación"
COMPARE_MODE_PREVIOUS = "Mes anterior"
COMPARE_MODE_PREVIOUS_YEAR = "Mismo mes año anterior"


def parse_spanish_amount_series(series: pd.Series) -> pd.Series:
    def parse_value(v: object) -> float:
        s = str(v).strip()
        if not s:
            return 0.0
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    return series.map(parse_value).astype(float).fillna(0.0)


@dataclass
class FilteredViews:
    monthly_view: pd.DataFrame
    annual_view: pd.DataFrame
    monthly_year_scope: pd.DataFrame
    period_options: list[str]


def build_period_options(monthly: pd.DataFrame, year_option: int | str) -> list[str]:
    if year_option == "Todos":
        scope = monthly
    else:
        scope = monthly[monthly["Año"] == int(year_option)]
    return ["Todos"] + scope["Periodo"].drop_duplicates().sort_values().tolist()


def get_comparison_row(monthly_all: pd.DataFrame, current_row: pd.Series, compare_mode: str) -> pd.Series | None:
    """Return the comparison row for the selected mode, if available."""
    if compare_mode == COMPARE_MODE_NONE:
        return None
    monthly_sorted = monthly_all.sort_values(["Año", "Mes"]).reset_index(drop=True)
    cur_year, cur_month = int(current_row["Año"]), int(current_row["Mes"])
    if compare_mode == COMPARE_MODE_PREVIOUS:
        prev = monthly_sorted[
            (monthly_sorted["Año"] < cur_year)
            | ((monthly_sorted["Año"] == cur_year) & (monthly_sorted["Mes"] < cur_month))
        ]
        return prev.iloc[-1] if not prev.empty else None
    if compare_mode == COMPARE_MODE_PREVIOUS_YEAR:
        prev = monthly_sorted[(monthly_sorted["Año"] == cur_year - 1) & (monthly_sorted["Mes"] == cur_month)]
        return prev.iloc[-1] if not prev.empty else None
    return None


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


def normalize_irpf_concept(df: pd.DataFrame, concept_col: str = "Concepto", out_col: str = "Concepto_agrupado") -> pd.DataFrame:
    out = df.copy()
    out[out_col] = out[concept_col].astype(str)
    irpf_mask = out[out_col].str.upper().str.contains(r"^TRIBUTACION\s+I\.?R\.?P\.?F\.?", regex=True)
    out.loc[irpf_mask, out_col] = "TRIBUTACION I.R.P.F."
    return out


def build_monthly_concept_delta(
    raw_nominas: pd.DataFrame,
    cur_year: int,
    cur_month: int,
    cmp_year: int,
    cmp_month: int,
    limit: int = 5,
) -> pd.DataFrame:
    raw_comp = raw_nominas.copy()
    raw_comp["Año"] = pd.to_numeric(raw_comp["Año"], errors="coerce")
    raw_comp["Mes"] = pd.to_numeric(raw_comp["Mes"], errors="coerce")
    raw_comp["Importe_num"] = parse_spanish_amount_series(raw_comp["Importe"])

    cur_rows = raw_comp[(raw_comp["Año"] == cur_year) & (raw_comp["Mes"] == cur_month)].copy()
    prev_rows = raw_comp[(raw_comp["Año"] == cmp_year) & (raw_comp["Mes"] == cmp_month)].copy()
    cur_rows = normalize_irpf_concept(cur_rows)
    prev_rows = normalize_irpf_concept(prev_rows)

    cur_agg = cur_rows.groupby("Concepto_agrupado", as_index=False)["Importe_num"].sum().rename(columns={"Importe_num": "Actual"})
    prev_agg = prev_rows.groupby("Concepto_agrupado", as_index=False)["Importe_num"].sum().rename(columns={"Importe_num": "Comparado"})
    explain = cur_agg.merge(prev_agg, on="Concepto_agrupado", how="outer").fillna(0.0)
    explain["Delta"] = explain["Actual"] - explain["Comparado"]
    explain = explain.sort_values("Delta", ascending=False, key=lambda s: s.abs()).head(limit)
    return explain.rename(columns={"Concepto_agrupado": "Concepto"}).reset_index(drop=True)


def build_top_concepts(nominas_view: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    base = nominas_view.copy()
    base["Importe_num"] = parse_spanish_amount_series(base["Importe"])
    return (
        base.groupby("Concepto", as_index=False)["Importe_num"]
        .sum()
        .rename(columns={"Importe_num": "Importe"})
        .sort_values("Importe", ascending=False, key=lambda s: s.abs())
        .head(limit)
        .reset_index(drop=True)
    )


def build_salary_base_outliers(nominas_view: pd.DataFrame, deviation_threshold: float = 0.20) -> list[dict[str, str]]:
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
    if salario_base.empty:
        return quality_adv
    med = float(salario_base["Importe_num"].median())
    if med == 0:
        return quality_adv
    salario_base["desv_pct"] = (salario_base["Importe_num"] - med).abs() / abs(med)
    outliers = salario_base[salario_base["desv_pct"] > deviation_threshold]
    for _, r in outliers.iterrows():
        quality_adv.append(
            {
                "Periodo": f"{int(r['Año'])}-{int(r['Mes']):02d}",
                "Regla": "SALARIO BASE fuera de rango (>20% de mediana)",
                "Valor": format_eur(float(r["Importe_num"])),
            }
        )
    return quality_adv


def build_coverage_pivot(monthly: pd.DataFrame) -> pd.DataFrame:
    coverage = monthly[["Año", "Mes"]].copy()
    coverage["present"] = "OK"
    return (
        coverage.pivot_table(index="Año", columns="Mes", values="present", aggfunc="first", fill_value="")
        .reindex(columns=list(range(1, 13)), fill_value="")
        .rename(columns={i: f"{i:02d}" for i in range(1, 13)})
        .reset_index()
    )

