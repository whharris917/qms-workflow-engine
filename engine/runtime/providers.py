"""External state provider framework.

Providers bridge external systems into the workflow engine's
state/affordance model. They are registered at the application
level and referenced declaratively from workflow YAML.
"""

from __future__ import annotations

from typing import Any, Protocol


class ExternalStateProvider(Protocol):
    """Contract for external state sources.

    A provider bridges one external system into the workflow engine's
    state/affordance model. Providers are registered at application startup
    and referenced by ID in workflow YAML definitions.
    """

    provider_id: str

    def query(self, bindings: dict[str, Any]) -> dict[str, Any]:
        """Fetch current state from the external system.

        Args:
            bindings: Resolved parameter values from the YAML declaration.

        Returns:
            Flat dict of key-value pairs representing current external state.

        Raises:
            ProviderUnavailableError: if the external system cannot be reached.
        """
        ...

    def get_affordances(self, bindings: dict[str, Any], state: dict[str, Any],
                        api_base: str) -> list[dict]:
        """Generate affordances in the engine's standard format.

        Returned affordances should NOT include 'id' — the node collector
        assigns sequential IDs after gathering from all sources.

        Args:
            bindings: Resolved parameter values.
            state: The state dict returned by the most recent query().
            api_base: URL prefix, e.g. "/agent/create-cr".

        Returns:
            List of affordance dicts (label, method, url, body, parameters).
        """
        ...

    def execute(self, bindings: dict[str, Any], action: str,
                params: dict[str, Any]) -> dict[str, Any]:
        """Execute a write action on the external system.

        Args:
            bindings: Resolved parameter values.
            action: Provider-specific action name (e.g. "route_review").
            params: Action parameters from the agent's POST body.

        Returns:
            {"ok": True, ...} on success or {"ok": False, "error": "reason"}.
        """
        ...

    def evaluate(self, bindings: dict[str, Any], state: dict[str, Any],
                 condition: dict) -> tuple[bool, str]:
        """Evaluate a provider-specific condition leaf.

        Args:
            bindings: Resolved parameter values.
            state: The state dict returned by query().
            condition: Provider-specific condition dict from YAML.

        Returns:
            (passed, reason) — same contract as evaluator.evaluate().
        """
        ...


class ProviderUnavailableError(Exception):
    """Raised when an external provider cannot be reached."""
    def __init__(self, provider_id: str, detail: str = ""):
        self.provider_id = provider_id
        self.detail = detail
        super().__init__(f"Provider '{provider_id}' unavailable: {detail}")


class ProviderRegistry:
    """Global registry of external state providers."""

    def __init__(self):
        self._providers: dict[str, ExternalStateProvider] = {}

    def register(self, provider: ExternalStateProvider):
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> ExternalStateProvider | None:
        return self._providers.get(provider_id)

    def __contains__(self, provider_id: str) -> bool:
        return provider_id in self._providers

    @property
    def ids(self) -> list[str]:
        return list(self._providers.keys())


# Module-level singleton
registry = ProviderRegistry()


def resolve_bindings(binding_defs: dict[str, str], data: dict) -> dict[str, Any]:
    """Resolve $field_ref bindings against workflow state.

    Values starting with $ are looked up in data.
    Literal values pass through unchanged.
    """
    resolved = {}
    for param, value in binding_defs.items():
        if isinstance(value, str) and value.startswith("$"):
            field_key = value[1:]
            resolved[param] = data.get(field_key)
        else:
            resolved[param] = value
    return resolved
