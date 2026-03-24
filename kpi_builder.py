from __future__ import annotations

import re
from typing import Dict, Tuple

import pandas as pd

MONTH_NAMES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def _norm(s: str) -> str:
    return (s or "").strip().upper()


def _as_float(series: pd.Series) -> pd.Series:
    def parse_value(v: object) -> float:
        if v is None:
            return 0.0
        s = str(v).strip()
        if not s:
            return 0.0
        # Normaliza formato español/europeo: 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    return series.map(parse_value).astype(float)


def _build_base(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Año"] = pd.to_numeric(out["Año"], errors="coerce").astype("Int64")
    out["Mes"] = pd.to_numeric(out["Mes"], errors="coerce").astype("Int64")
    out["Importe"] = _as_float(out["Importe"])
    out["Categoria_norm"] = out.get("Categoría", "").astype(str).map(_norm)
    out["Concepto_norm"] = out["Concepto"].astype(str).map(_norm)
    out["Subcat_norm"] = out["Subcategoría"].astype(str).map(_norm)
    # Compatibilidad con históricos: algunos refund se guardaron con signo invertido.
    # En deducciones, Tax/ESPP refund deben reducir deducciones (importe positivo final).
    refund_mask = (
        (out["Categoria_norm"] == "DEVENGO")
        & (out["Importe"] < 0)
        & out["Concepto_norm"].str.contains("TAX REFUND|ESPP REFUND", regex=True)
    )
    out.loc[refund_mask, "Importe"] = out.loc[refund_mask, "Importe"].abs()
    out = out.dropna(subset=["Año", "Mes"])
    out["Año"] = out["Año"].astype(int)
    out["Mes"] = out["Mes"].astype(int)
    out["Periodo"] = out["Año"].astype(str) + "-" + out["Mes"].astype(str).str.zfill(2)
    out["Periodo_natural"] = out["Mes"].map(MONTH_NAMES_ES) + " " + out["Año"].astype(str)
    return out


def _extract_irpf_pct_from_concept(series: pd.Series) -> float | None:
    # Caso típico: "TRIBUTACION I.R.P.F.33,17"
    pattern = re.compile(r"IRPF\.?\s*([0-9]{1,2},[0-9]{2})", flags=re.IGNORECASE)
    for value in series.astype(str):
        m = pattern.search(value)
        if m:
            return float(m.group(1).replace(",", ".")) / 100.0
    return None


def build_monthly_kpis(df_nominas: pd.DataFrame) -> pd.DataFrame:
    df = _build_base(df_nominas)
    if df.empty:
        return pd.DataFrame()
    rows = []
    for (year, month), g in df.groupby(["Año", "Mes"], sort=True):
        # Regla contable de nómina:
        # - Retrib. Flexible se muestra en DEVENGOS con signo negativo y debe
        #   restar del total devengado.
        # - Tax Refund / ESPP Refund (o deducción) se tratan como deducciones.
        is_retrib_flexible = g["Concepto_norm"].str.contains("RETRIB. FLEXIBLE", regex=False)
        is_ingreso = (g["Categoria_norm"] == "INGRESO") | is_retrib_flexible
        is_devengo = (g["Categoria_norm"] == "DEVENGO") & (~is_retrib_flexible)
        if not is_ingreso.any() and not is_devengo.any():
            # Fallback para históricos sin columna Categoría normalizada.
            is_ingreso = g["Importe"] > 0
            is_devengo = g["Importe"] < 0

        total_devengado = g.loc[is_ingreso, "Importe"].sum()
        total_deducir = -g.loc[is_devengo, "Importe"].sum()
        irpf_importe = -g.loc[g["Subcat_norm"] == "IMPUESTOS (IRPF)", "Importe"].sum()
        ss_importe = -g.loc[g["Subcat_norm"] == "SEGURIDAD SOCIAL", "Importe"].sum()
        fijo_ingreso = g.loc[g["Subcat_norm"] == "INGRESO FIJO", "Importe"].sum()
        variable_ingreso = g.loc[g["Subcat_norm"].str.startswith("INGRESO VARIABLE"), "Importe"].sum()
        beneficio_especie = g.loc[g["Subcat_norm"] == "BENEFICIO EN ESPECIE", "Importe"].sum()
        ahorro_jub_empresa = g.loc[g["Concepto_norm"].str.contains("PLAN PENSIONES - APORT EMPRESA"), "Importe"].sum()
        ahorro_jub_empleado = -g.loc[g["Concepto_norm"].str.contains("APORT. EMPLEADO P. PENS."), "Importe"].sum()
        consumo_especie = g.loc[
            g["Concepto_norm"].str.contains(
                "TICKET RESTAURANT|SEGURO MEDICO|SEGURO VIDA|FITNESS|TICKET TRANSPORTE|RETRIB. FLEXIBLE"
            ),
            "Importe",
        ].abs().sum()
        ingresos_libres_impuestos = g.loc[g["Concepto_norm"].str.contains("NO IRPF"), "Importe"].sum()
        espp_gain = g.loc[g["Subcat_norm"] == "INGRESO VARIABLE (ESPP)", "Importe"].sum()
        rsu_gain = g.loc[g["Subcat_norm"] == "INGRESO VARIABLE (RSU)", "Importe"].sum()

        rows.append(
            {
                "Año": year,
                "Mes": month,
                "neto": total_devengado - total_deducir,
                "total_devengado": total_devengado,
                "total_deducir": total_deducir,
                "irpf_importe": irpf_importe,
                "ss_importe": ss_importe,
                "fijo_ingreso": fijo_ingreso,
                "variable_ingreso": variable_ingreso,
                "beneficio_especie": beneficio_especie,
                "ahorro_jub_empresa": ahorro_jub_empresa,
                "ahorro_jub_empleado": ahorro_jub_empleado,
                "consumo_especie": consumo_especie,
                "ingresos_libres_impuestos": ingresos_libres_impuestos,
                "espp_gain": espp_gain,
                "rsu_gain": rsu_gain,
                "Periodo_natural": f"{MONTH_NAMES_ES.get(int(month), str(month))} {year}",
                "irpf_pct_nomina": _extract_irpf_pct_from_concept(
                    g.loc[g["Subcat_norm"] == "IMPUESTOS (IRPF)", "Concepto"]
                ),
            }
        )

    monthly = pd.DataFrame(rows)
    monthly["ahorro_jub_total"] = monthly["ahorro_jub_empresa"] + monthly["ahorro_jub_empleado"]
    monthly["tipo_marginal_estimado"] = (monthly["irpf_importe"] / monthly["total_devengado"]).fillna(0.0)
    monthly["tipo_marginal_estimado"] = monthly["tipo_marginal_estimado"].clip(lower=0.0, upper=0.60)
    monthly["rsu_neto_estimado"] = monthly["rsu_gain"] * (1 - monthly["tipo_marginal_estimado"])
    monthly["espp_neto_estimado"] = monthly["espp_gain"] * (1 - monthly["tipo_marginal_estimado"])
    monthly["ahorro_fiscal"] = (
        monthly["ingresos_libres_impuestos"] * monthly["tipo_marginal_estimado"] + monthly["ahorro_jub_empresa"]
    )
    monthly["riqueza_real_mensual"] = (
        monthly["neto"] + monthly["ahorro_jub_empresa"] + monthly["rsu_neto_estimado"] + monthly["espp_neto_estimado"]
    )
    monthly["pct_irpf"] = (monthly["irpf_importe"] / monthly["total_devengado"]).fillna(0.0)
    # Si la nómina informa el % explícitamente, priorizarlo sobre la aproximación.
    monthly["pct_irpf"] = monthly["irpf_pct_nomina"].where(
        monthly["irpf_pct_nomina"].notna(), monthly["pct_irpf"]
    )
    monthly["pct_ss"] = (monthly["ss_importe"] / monthly["total_devengado"]).fillna(0.0)
    monthly["pct_variable"] = (monthly["variable_ingreso"] / monthly["total_devengado"]).fillna(0.0)
    monthly["Periodo"] = monthly["Año"].astype(str) + "-" + monthly["Mes"].astype(str).str.zfill(2)
    return monthly.sort_values(["Año", "Mes"]).reset_index(drop=True)


def build_annual_kpis(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()
    grp = monthly.groupby("Año", as_index=False)
    annual = grp[
        [
            "total_devengado",
            "total_deducir",
            "neto",
            "irpf_importe",
            "ss_importe",
            "fijo_ingreso",
            "variable_ingreso",
            "beneficio_especie",
            "ahorro_jub_empresa",
            "ahorro_jub_empleado",
            "ahorro_jub_total",
            "consumo_especie",
            "ingresos_libres_impuestos",
            "espp_gain",
            "rsu_gain",
            "rsu_neto_estimado",
            "espp_neto_estimado",
            "ahorro_fiscal",
            "riqueza_real_mensual",
        ]
    ].sum()
    annual = annual.rename(columns={"riqueza_real_mensual": "riqueza_real_anual"})
    annual["media_neto_mensual"] = grp["neto"].mean()["neto"].values
    annual["pct_irpf_efectivo_anual"] = (annual["irpf_importe"] / annual["total_devengado"]).fillna(0.0)
    annual["pct_ss_efectivo_anual"] = (annual["ss_importe"] / annual["total_devengado"]).fillna(0.0)
    annual = annual.sort_values("Año").reset_index(drop=True)
    annual["delta_neto_vs_anterior"] = annual["neto"].diff().fillna(0.0)
    annual["pct_crecimiento_neto_yoy"] = annual["neto"].pct_change().fillna(0.0)
    annual["delta_irpf_yoy"] = annual["pct_irpf_efectivo_anual"].diff().fillna(0.0)
    return annual


def build_espp_months(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame(columns=["Año", "Mes", "Periodo", "Periodo_natural", "espp_gain"])
    out = monthly.loc[monthly["espp_gain"] > 0, ["Año", "Mes", "Periodo", "Periodo_natural", "espp_gain"]].copy()
    return out.sort_values(["Año", "Mes"]).reset_index(drop=True)


def build_all_kpis(df_nominas: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly = build_monthly_kpis(df_nominas)
    annual = build_annual_kpis(monthly)
    espp_months = build_espp_months(monthly)
    return monthly, annual, espp_months


def format_eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def summarize_latest(monthly: pd.DataFrame, annual: pd.DataFrame) -> Dict[str, float]:
    latest_m = monthly.sort_values(["Año", "Mes"]).iloc[-1]
    latest_y = annual.sort_values("Año").iloc[-1]
    return {
        "neto_mes": float(latest_m["neto"]),
        "irpf_pct_mes": float(latest_m["pct_irpf"]),
        "riqueza_real_mes": float(latest_m["riqueza_real_mensual"]),
        "neto_anual": float(latest_y["neto"]),
        "irpf_pct_anual": float(latest_y["pct_irpf_efectivo_anual"]),
        "ahorro_jub_anual": float(latest_y["ahorro_jub_total"]),
    }
