"""Public Scenario Engine abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ScenarioValidationError(ValueError):
    """Raised when a structured scenario request is unsafe or invalid."""


class ScenarioEngine(ABC):
    """Backend-neutral interface usable by a future PlanningEngine or agent."""

    @abstractmethod
    def run(self, request: dict) -> dict:
        """Run a deterministic scenario and return its calculation artifacts."""

    @abstractmethod
    def validate(self, request: dict) -> None:
        """Validate request structure and supported business semantics."""

    @abstractmethod
    def get_metadata(self) -> dict:
        """Describe supported baselines, scopes, and levers."""
