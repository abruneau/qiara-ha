"""Pydantic models for Qiara data validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class QiaraSensorData(BaseModel):
    """Model for Qiara sensor data."""

    id: str
    name: str
    type: str
    # Raw sensor state from the device: None/False when inactive, or a truthy
    # value (True from a read, "dws_open"/"mvt_detected" from a push) when active.
    state: Any = None
    battery_level: Optional[int] = None
    temperature: Optional[float] = None
    last_updated: Optional[datetime] = None
    available: bool = True
