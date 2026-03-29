from __future__ import annotations

import altair as alt

# Global ordered palette (source of truth)
COLOR_1 = "#3b82f6"
COLOR_2 = "#14b8a6"
COLOR_3 = "#f59e0b"
COLOR_4 = "#a855f7"
COLOR_5 = "#94a3b8"

GLOBAL_PALETTE = [COLOR_1, COLOR_2, COLOR_3, COLOR_4, COLOR_5]


def ordered_scale(domain: list[str]) -> alt.Scale:
    """Return an Altair scale with global palette in fixed order."""
    return alt.Scale(domain=domain, range=GLOBAL_PALETTE[: len(domain)])

