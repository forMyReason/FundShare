"""Pure helpers for Streamlit captions (unit-testable, no streamlit import)."""


def show_nav_interval_no_buy_points_caption(buy_points: list[object]) -> bool:
    """Whether to show the caption when the nav chart interval has no buy markers."""
    return len(buy_points) == 0
