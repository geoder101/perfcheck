"""Native numeric controls with persistent, editable laboratory readouts."""

import marimo as mo


def lab_slider(
    bounds: tuple[float, float, float], initial: float, label: str
) -> mo.ui.slider:
    """Use the same visible value contract for every inference slider."""
    start, stop, step = bounds
    return mo.ui.slider(
        start,
        stop,
        step=step,
        value=initial,
        label=label,
        show_value=True,
        include_input=True,
        full_width=True,
    )
