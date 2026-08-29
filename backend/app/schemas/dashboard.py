"""Pydantic v2 schemas for the Dashboard & Settings module.

Response models for:

* ``GET /api/v1/dashboard/stats`` -> :class:`DashboardStats`
* ``GET /api/v1/usage`` -> :class:`UsageStats`
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    """Aggregate counters for the authenticated user's dashboard."""

    projects_total: int = Field(
        default=0, ge=0, description="All projects owned by the user."
    )
    projects_ready: int = Field(
        default=0, ge=0, description="Projects whose status is 'ready'."
    )
    shorts_total: int = Field(
        default=0, ge=0, description="All shorts across the user's projects."
    )
    renders_total: int = Field(
        default=0, ge=0, description="All render jobs started by the user."
    )
    renders_completed: int = Field(
        default=0, ge=0, description="Render jobs whose status is 'completed'."
    )
    storage_bytes: int = Field(
        default=0,
        ge=0,
        description="Sum of output file sizes for the user's completed renders.",
    )


class UsageStats(BaseModel):
    """Metered resource usage for the current calendar month."""

    period_start: datetime = Field(
        description="Inclusive UTC start of the current calendar month."
    )
    period_end: datetime = Field(
        description="Exclusive UTC start of the next calendar month."
    )
    # TODO wire metering: no per-request usage/metering table exists yet, so the
    # counters below are always 0 until one is added (see PRP Module 5).
    claude_input_tokens: int = Field(
        default=0, ge=0, description="Anthropic input tokens consumed this period."
    )
    claude_output_tokens: int = Field(
        default=0, ge=0, description="Anthropic output tokens produced this period."
    )
    stock_api_calls: int = Field(
        default=0, ge=0, description="Pexels/Pixabay stock API calls this period."
    )
