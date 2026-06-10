"""Compatibility wrapper for the canonical dunning service.

This module remains importable so older code paths do not silently fork the
payment-failure workflow into a second implementation.
"""

from app.services.dunning_service import DUNNING_CONFIG, DunningService, get_dunning_service

__all__ = ["DUNNING_CONFIG", "DunningService", "get_dunning_service"]
