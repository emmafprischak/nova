"""
Agent Authentication - validates that inbound requests come from an allowed voice agent
and that the agent is permitted to post to the requested tenant.

Each voice agent instance is identified by a pre-shared API key sent in the
``Authorization`` request header (``Bearer <key>`` or bare ``<key>``).

The allowlist is loaded from the ``ALLOWED_AGENTS`` config variable (a JSON array).
When the list is empty (e.g. in development), validation is bypassed with a warning.
"""
from fastapi import HTTPException, Request

from backend.config import ALLOWED_AGENTS


def get_agent_from_request(request: Request) -> dict | None:
    """Return the agent record matching the API key in the Authorization header.

    Accepts both ``Bearer <key>`` and bare ``<key>`` formats.

    Returns the matching agent dict, or ``None`` if the key is absent / unknown.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return None

    # Strip optional "Bearer " prefix
    api_key = auth_header.removeprefix("Bearer ").strip()
    if not api_key:
        return None

    for agent in ALLOWED_AGENTS:
        if agent.get("api_key") == api_key:
            return agent

    return None


def require_agent_for_tenant(request: Request, tenant_code: str) -> dict:
    """Validate that the request carries a known API key allowed for *tenant_code*.

    When ``ALLOWED_AGENTS`` is empty, validation is skipped (development mode).

    Returns the matched agent record on success.
    Raises ``HTTPException(403)`` on any auth failure.
    """
    if not ALLOWED_AGENTS:
        print("WARNING: ALLOWED_AGENTS is empty – skipping agent auth (development mode)")
        return {}

    agent = get_agent_from_request(request)

    if agent is None:
        raise HTTPException(
            status_code=403,
            detail="Missing or unrecognised agent API key",
        )

    allowed_tenants = agent.get("allowed_tenants", [])
    if tenant_code not in allowed_tenants:
        raise HTTPException(
            status_code=403,
            detail=f"Agent '{agent.get('agent_id')}' is not permitted to post to tenant '{tenant_code}'",
        )

    return agent
