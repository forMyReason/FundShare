from fundshare.ui_captions import show_nav_interval_no_buy_points_caption


def test_show_nav_interval_no_buy_points_caption_empty() -> None:
    assert show_nav_interval_no_buy_points_caption([]) is True


def test_show_nav_interval_no_buy_points_caption_nonempty() -> None:
    assert show_nav_interval_no_buy_points_caption([{"date": "2026-01-01"}]) is False
