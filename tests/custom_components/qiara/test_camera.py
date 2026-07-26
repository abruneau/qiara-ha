"""Tests for Qiara camera helpers."""
from __future__ import annotations

from custom_components.qiara.camera import build_srt_url


def test_build_srt_url_basic():
    """SRT URL includes streamid and passphrase query params."""
    url = build_srt_url("lwip.localdomain", 9000, "HLS_TEST", "secret")
    assert url == "srt://lwip.localdomain:9000?streamid=HLS_TEST&passphrase=secret"


def test_build_srt_url_with_latency():
    """Latency is appended only when provided."""
    url = build_srt_url("192.168.0.146", "9000", "cam1", "pw", latency=120)
    assert url == "srt://192.168.0.146:9000?streamid=cam1&passphrase=pw&latency=120"
