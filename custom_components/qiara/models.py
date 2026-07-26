"""Pydantic models for Qiara data validation."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QiaraSensorData(BaseModel):
    """Model for Qiara sensor data."""

    id: str
    name: str
    type: str
    state: Optional[str] = None
    battery_level: Optional[int] = None
    temperature: Optional[float] = None
    last_updated: Optional[datetime] = None
    available: bool = True
