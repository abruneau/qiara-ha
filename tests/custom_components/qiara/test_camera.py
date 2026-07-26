"""Tests for Qiara camera helpers."""
from __future__ import annotations

from custom_components.qiara.camera import build_srt_url


def test_build_srt_url_basic():
    """SRT URL carries streamid, passphrase, and caller-mode live params."""
    url = build_srt_url("192.168.0.146", 9000, "HLS_TEST", "secret")
    assert url == (
        "srt://192.168.0.146:9000?streamid=HLS_TEST&passphrase=secret"
        "&mode=caller&transtype=live&latency=500000"
    )


def test_build_srt_url_custom_latency():
    """Latency override is reflected in the URL."""
    url = build_srt_url("192.168.0.146", "9000", "cam1", "pw", latency=1000000)
    assert url.endswith("&mode=caller&transtype=live&latency=1000000")
    assert url.startswith("srt://192.168.0.146:9000?streamid=cam1&passphrase=pw")
