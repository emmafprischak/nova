"""
Unit tests for backend/services/agent_auth.py

Run with:  python test_agent_auth.py
"""
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(api_key: str | None) -> MagicMock:
    """Build a minimal mock FastAPI Request with the given Authorization header."""
    mock_request = MagicMock()
    if api_key is not None:
        mock_request.headers = {"Authorization": f"Bearer {api_key}"}
    else:
        mock_request.headers = {}
    return mock_request


def _make_allowlist(*agents) -> list[dict]:
    """Convenience helper to build an ALLOWED_AGENTS list."""
    return list(agents)


# ---------------------------------------------------------------------------
# get_agent_from_request
# ---------------------------------------------------------------------------

def test_get_agent_valid_key():
    """A known key returns the matching agent record."""
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import get_agent_from_request
        agent = get_agent_from_request(_make_request("key_abc"))
    assert agent is not None, "Expected a matching agent record"
    assert agent["agent_id"] == "nova-prod"
    print("   ✓ get_agent_from_request: valid key returns agent record")
    return True


def test_get_agent_unknown_key():
    """An unrecognised key returns None."""
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import get_agent_from_request
        agent = get_agent_from_request(_make_request("wrong_key"))
    assert agent is None, "Expected None for an unknown key"
    print("   ✓ get_agent_from_request: unknown key returns None")
    return True


def test_get_agent_missing_header():
    """A request without an Authorization header returns None."""
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import get_agent_from_request
        agent = get_agent_from_request(_make_request(None))
    assert agent is None, "Expected None when header is absent"
    print("   ✓ get_agent_from_request: missing header returns None")
    return True


def test_get_agent_bare_key_without_bearer_prefix():
    """A bare key (no 'Bearer ' prefix) is still matched."""
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    mock_request = MagicMock()
    mock_request.headers = {"Authorization": "key_abc"}  # no Bearer prefix
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import get_agent_from_request
        agent = get_agent_from_request(mock_request)
    assert agent is not None, "Expected match even without 'Bearer ' prefix"
    print("   ✓ get_agent_from_request: bare key (no Bearer prefix) is accepted")
    return True


# ---------------------------------------------------------------------------
# require_agent_for_tenant
# ---------------------------------------------------------------------------

def test_require_agent_valid_key_matching_tenant():
    """Valid key + matching tenant passes and returns the agent record."""
    from fastapi import HTTPException
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import require_agent_for_tenant
        result = require_agent_for_tenant(_make_request("key_abc"), "walmart")
    assert result["agent_id"] == "nova-prod"
    print("   ✓ require_agent_for_tenant: valid key + matching tenant → allowed")
    return True


def test_require_agent_valid_key_wrong_tenant():
    """Valid key but wrong tenant raises 403."""
    from fastapi import HTTPException
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import require_agent_for_tenant
        try:
            require_agent_for_tenant(_make_request("key_abc"), "acme")
            print("   ✗ require_agent_for_tenant: should have raised 403 for wrong tenant")
            return False
        except HTTPException as exc:
            assert exc.status_code == 403, f"Expected 403, got {exc.status_code}"
    print("   ✓ require_agent_for_tenant: valid key + wrong tenant → 403")
    return True


def test_require_agent_missing_key():
    """Missing Authorization header raises 403."""
    from fastapi import HTTPException
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import require_agent_for_tenant
        try:
            require_agent_for_tenant(_make_request(None), "walmart")
            print("   ✗ require_agent_for_tenant: should have raised 403 for missing key")
            return False
        except HTTPException as exc:
            assert exc.status_code == 403, f"Expected 403, got {exc.status_code}"
    print("   ✓ require_agent_for_tenant: missing key → 403")
    return True


def test_require_agent_unknown_key():
    """Unrecognised API key raises 403."""
    from fastapi import HTTPException
    allowlist = _make_allowlist(
        {"agent_id": "nova-prod", "api_key": "key_abc", "allowed_tenants": ["walmart"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import require_agent_for_tenant
        try:
            require_agent_for_tenant(_make_request("bad_key"), "walmart")
            print("   ✗ require_agent_for_tenant: should have raised 403 for unknown key")
            return False
        except HTTPException as exc:
            assert exc.status_code == 403, f"Expected 403, got {exc.status_code}"
    print("   ✓ require_agent_for_tenant: unknown key → 403")
    return True


def test_require_agent_empty_allowlist():
    """Empty ALLOWED_AGENTS bypasses enforcement (development mode)."""
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", []):
        from backend.services.agent_auth import require_agent_for_tenant
        # Should NOT raise – returns empty dict
        result = require_agent_for_tenant(_make_request(None), "walmart")
    assert result == {}, f"Expected empty dict in dev mode, got {result!r}"
    print("   ✓ require_agent_for_tenant: empty allowlist → bypassed (dev mode)")
    return True


def test_require_agent_multi_tenant_agent():
    """An agent with multiple allowed tenants is permitted for each of them."""
    from fastapi import HTTPException
    allowlist = _make_allowlist(
        {"agent_id": "nova-multi", "api_key": "key_multi", "allowed_tenants": ["walmart", "acme"]},
    )
    with patch("backend.services.agent_auth.ALLOWED_AGENTS", allowlist):
        from backend.services.agent_auth import require_agent_for_tenant
        r1 = require_agent_for_tenant(_make_request("key_multi"), "walmart")
        r2 = require_agent_for_tenant(_make_request("key_multi"), "acme")
        try:
            require_agent_for_tenant(_make_request("key_multi"), "other")
            print("   ✗ require_agent_for_tenant: should have raised 403 for unlisted tenant")
            return False
        except HTTPException as exc:
            assert exc.status_code == 403
    assert r1["agent_id"] == "nova-multi"
    assert r2["agent_id"] == "nova-multi"
    print("   ✓ require_agent_for_tenant: multi-tenant agent allowed for its tenants, rejected for others")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("NOVA VOICE AGENT - AGENT AUTH UNIT TESTS")
    print("=" * 60)

    tests = [
        ("get_agent: valid key", test_get_agent_valid_key),
        ("get_agent: unknown key", test_get_agent_unknown_key),
        ("get_agent: missing header", test_get_agent_missing_header),
        ("get_agent: bare key (no Bearer)", test_get_agent_bare_key_without_bearer_prefix),
        ("require_agent: valid key + matching tenant", test_require_agent_valid_key_matching_tenant),
        ("require_agent: valid key + wrong tenant → 403", test_require_agent_valid_key_wrong_tenant),
        ("require_agent: missing key → 403", test_require_agent_missing_key),
        ("require_agent: unknown key → 403", test_require_agent_unknown_key),
        ("require_agent: empty allowlist (dev mode)", test_require_agent_empty_allowlist),
        ("require_agent: multi-tenant agent", test_require_agent_multi_tenant_agent),
    ]

    results = []
    print()
    for name, fn in tests:
        print(f"Running: {name}")
        try:
            ok = fn()
        except Exception as exc:
            print(f"   ✗ EXCEPTION: {exc}")
            ok = False
        results.append((name, ok))

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    all_ok = True
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
        if not ok:
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("🎉 All agent auth tests passed!")
        return 0
    else:
        print("⚠️  Some agent auth tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
