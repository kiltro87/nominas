from __future__ import annotations

from typing import Any

import pandas as pd

from kpi_builder import format_eur


METRIC_HELP: dict[str, str] = {
    "Bruto": "Suma de devengos netos del periodo mostrado.",
    "% IRPF": "Porcentaje de IRPF informado en nómina (si existe) o ratio IRPF/Bruto del periodo.",
    "Neto": "Bruto menos total a deducir del periodo.",
    "Ahorro fiscal": "Ingresos libres de impuestos multiplicados por tipo marginal estimado + aportación empresa a jubilación.",
    "Ahorro jub. empresa": "Aportación de empresa al plan de pensiones en el periodo.",
    "Ahorro jub. empleado": "Aportación del empleado al plan de pensiones en el periodo.",
    "Ingresos libres imp.": "Importes del periodo marcados como exentos o no sujetos a IRPF.",
    "% IRPF efectivo": "IRPF anual / Bruto anual para el año seleccionado.",
    "IRPF medio": "Promedio mensual del % IRPF en el año mostrado.",
    "Ingresos totales": "Neto + aportacion empresa a jubilacion + netos estimados de RSU y ESPP.",
    "Ahorro jubilación": "Aportación total (empresa + empleado) a jubilación.",
    "Consumo en especie": "Consumo asociado a conceptos en especie (tickets, seguros, fitness, etc.).",
    "Aportación empresa": "Aportación anual de la empresa al plan de pensiones.",
    "Aportación empleado": "Aportación anual del empleado al plan de pensiones.",
    "ESPP": "Ganancia anual identificada como ESPP.",
    "RSU": "Ganancia anual identificada como RSU/stock options.",
}


def show_eur(value: float, hide_amounts: bool) -> str:
    return "••••••" if hide_amounts else format_eur(float(value))


def show_compact_eur(value: float) -> str:
    v = float(value)
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av < 1000:
        return format_eur(v)
    if av < 1_000_000:
        return f"{sign}{str(f'{av / 1000:.1f}').replace('.', ',')}k €"
    return f"{sign}{str(f'{av / 1_000_000:.1f}').replace('.', ',')}M €"


def zebra_styler(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    display_df = df.copy()
    display_df.index = pd.RangeIndex(start=1, stop=len(display_df) + 1, step=1)
    bg = pd.DataFrame("", index=display_df.index, columns=display_df.columns)
    bg.iloc[1::2, :] = "background-color: #f7f7f7"
    return display_df.style.apply(lambda _: bg, axis=None)


def apply_privacy_to_columns(df: pd.DataFrame, columns: list[str], hide_amounts: bool) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: "••••••" if hide_amounts else format_eur(float(x)))
    return out


def metric_with_help(container: Any, label: str, value: str, delta: str | None = None) -> None:
    help_text = METRIC_HELP.get(label)
    try:
        if delta is None:
            container.metric(label, value, help=help_text)
        else:
            container.metric(label, value, delta=delta, help=help_text)
    except TypeError:
        if delta is None:
            container.metric(label, value)
        else:
            container.metric(label, value, delta=delta)

