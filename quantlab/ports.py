"""Local-only ports for Phase 1.

Future real market-data/broker adapters belong behind explicit interfaces and must not be
imported or called by Phase 1 runtime paths.
"""

from __future__ import annotations

from typing import Protocol


class StorageRepository(Protocol):
    def initialize(self) -> None: ...
    def seed_demo(self) -> str: ...


class SampleDataProvider(Protocol):
    def seed(self, repository: StorageRepository) -> str: ...


class DisabledMarketDataProvider:
    """Documentary seam for future adapters; intentionally unusable in Phase 1."""

    def __getattr__(self, name: str):  # pragma: no cover - defensive boundary
        raise RuntimeError(
            "Live market-data/broker adapters are disabled for Phase 1 local MVP. "
            "Use sample/offline data only."
        )
