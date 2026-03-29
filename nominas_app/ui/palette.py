from __future__ import annotations

import altair as alt

# Global ordered palette (source of truth)
COLOR_1 = "#3b82f6"
COLOR_2 = "#14b8a6"
COLOR_3 = "#f59e0b"
COLOR_4 = "#a855f7"
COLOR_5 = "#94a3b8"

GLOBAL_PALETTE = [COLOR_1, COLOR_2, COLOR_3, COLOR_4, COLOR_5]


def ordered_scale(domain: list[str], start_index: int = 0) -> alt.Scale:
    """Return an Altair scale with global palette in fixed order and offset."""
    palette_len = len(GLOBAL_PALETTE)
    colors = [GLOBAL_PALETTE[(start_index + idx) % palette_len] for idx in range(len(domain))]
    return alt.Scale(domain=domain, range=colors)


def legend_circle(title: str) -> alt.Legend:
    """Consistent circle legends for all charts."""
    return alt.Legend(title=title, symbolType="circle")

