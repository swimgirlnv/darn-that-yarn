"""Logging helpers for Darn That Yarn."""

from __future__ import annotations

import logging


def get_logger(name: str = "darn_that_yarn") -> logging.Logger:
    return logging.getLogger(name)
