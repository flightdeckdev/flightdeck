"""Experimental adoption helpers: map runtime telemetry to v1 ``RunEvent`` models.

These modules are **optional** and may require ``pip install 'flightdeck-ai[…]'`` extras; see
**``docs/sdk-integrations.md``**. They do not change core CLI behavior. The normative wire
contract remains **``schemas/v1/run_event.schema.json``** and **``POST /v1/events``**.

Import specific helpers from submodules (for example ``flightdeck.integrations.common``) so
optional third-party packages are only loaded when you use that integration.
"""

from flightdeck.integrations.common import make_run_end_event, temporal_labels

__all__ = ["make_run_end_event", "temporal_labels"]
