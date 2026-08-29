"""Shared slowapi rate limiter.

A single :class:`~slowapi.Limiter` instance must back every ``@limiter.limit``
decorator *and* ``app.state.limiter`` for slowapi to resolve limits, so all
routers import the limiter from here rather than constructing their own.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
