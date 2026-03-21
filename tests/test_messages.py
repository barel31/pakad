import pytest
from backend.messages import render_alert, render

def test_render_alert_hebrew():
    msg = render_alert(
        language="he",
        title="ירי רקטות וטילים",
        areas=["תל אביב", "רמת גן"],
        time_str="14:32:07",
    )
    assert "ירי רקטות וטילים" in msg
    assert "תל אביב" in msg
    assert "14:32:07" in msg

def test_render_alert_english():
    msg = render_alert(
        language="en",
        title="ירי רקטות וטילים",
        areas=["תל אביב", "רמת גן"],
        time_str="14:32:07",
    )
    assert "Rocket" in msg
    assert "תל אביב" in msg   # areas always Hebrew
    assert "14:32:07" in msg

def test_render_command_response():
    msg = render("start_welcome", "he")
    assert isinstance(msg, str)
    assert len(msg) > 0

def test_render_unknown_key_raises():
    with pytest.raises(KeyError):
        render("nonexistent_key", "he")
