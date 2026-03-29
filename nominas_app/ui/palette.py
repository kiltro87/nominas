from __future__ import annotations

import altair as alt

# Global ordered palette (source of truth)
COLOR_1 = "#3b82f6"
COLOR_2 = "#14b8a6"
COLOR_3 = "#f59e0b"
COLOR_4 = "#a855f7"
COLOR_5 = "#94a3b8"

GLOBAL_PALETTE = [COLOR_1, COLOR_2, COLOR_3, COLOR_4, COLOR_5]

# Semantic mapping to keep a concept color stable across charts.
COLOR_BY_CONCEPT: dict[str, str] = {
    "Neto": COLOR_1,
    "Bruto": COLOR_2,
    "Ahorro jub. empresa": COLOR_2,
    "Ahorro jubilación": COLOR_2,
    "Ahorro fiscal": COLOR_1,
    "ESPP": COLOR_3,
    "ESPP neto estimado": COLOR_3,
    "IRPF": COLOR_3,
    "Consumo en especie": COLOR_3,
    "RSU": COLOR_4,
    "RSU neto estimado": COLOR_4,
    "Seg. Social": COLOR_4,
    "Otras deducciones": COLOR_5,
    "Deducciones": COLOR_5,
    "Bonus/Acciones": COLOR_3,
}


def ordered_scale(domain: list[str]) -> alt.Scale:
    """Return an Altair scale with global palette in fixed order."""
    return alt.Scale(domain=domain, range=GLOBAL_PALETTE[: len(domain)])


def semantic_scale(domain: list[str]) -> alt.Scale:
    """Return an Altair scale using concept->color mapping."""
    colors = [COLOR_BY_CONCEPT.get(name, GLOBAL_PALETTE[idx % len(GLOBAL_PALETTE)]) for idx, name in enumerate(domain)]
    return alt.Scale(domain=domain, range=colors)

