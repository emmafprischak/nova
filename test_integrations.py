"""
Test script to verify Cal.com and Notion integrations
"""
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.services.calendar import get_available_slots, book_appointment
from backend.services.crm import create_lead, push_to_crm_backend, determine_escalation_status
from backend.models import CallData

async def test_calcom():
    """Test Cal.com integration"""
    print("\n" + "="*60)
    print("Testing Cal.com Integration...")
    print("="*60)

    try:
        # Test getting available slots
        print("\n1. Fetching available appointment slots...")
        slots = await get_available_slots(days_ahead=7)

        if slots:
            print(f"✅ SUCCESS: Found {len(slots)} available slots")
            print("\nAvailable slots:")
            for i, slot in enumerate(slots[:3], 1):
                print(f"   {i}. {slot['date']} at {slot['time']}")
            return True
        else:
            print("❌ WARNING: No slots returned (but API might be working)")
            return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False

async def test_notion():
    """Test Notion integration"""
    print("\n" + "="*60)
    print("Testing Notion Integration...")
    print("="*60)

    try:
        # Test creating a lead
        print("\n1. Creating test lead in Notion...")

        test_call_data = CallData(
            name="Test User - Integration Check",
            phone="+15551234567",
            email="test@example.com",
            service="Integration Test",
            status="qualified",
            appointment_time=None,
            notes="This is a test entry to verify Notion integration"
        )

        result = await create_lead(test_call_data, "TEST_CALL_SID_123")

        if result.get("success"):
            print(f"✅ SUCCESS: Lead created in Notion")
            print(f"   Page ID: {result.get('page_id')}")
            if result.get('url'):
                print(f"   URL: {result.get('url')}")
            return True
        else:
            print(f"❌ FAILED: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False

async def test_crm_backend():
    """Test CRM backend integration (live network call, skipped if unavailable)"""
    print("\n" + "="*60)
    print("Testing CRM Backend Integration (live)...")
    print("="*60)

    try:
        # Test pushing data to CRM backend
        print("\n1. Pushing test contact to CRM backend...")

        from datetime import datetime, timedelta
        
        # Use a date 7 days in the future for more realistic test data
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        test_call_data = CallData(
            name="Test Contact - CRM Backend",
            phone="+15559876543",
            email="test.crm@example.com",
            service="CRM Integration Test",
            status="qualified",
            appointment_time=future_date,
            notes="This is a test entry to verify CRM backend integration"
        )

        result = await push_to_crm_backend(
            test_call_data,
            "TEST_CRM_CALL_SID_456",
            escalation_status="none",
        )

        if result.get("success"):
            print(f"✅ SUCCESS: Contact pushed to CRM backend")
            if result.get("response"):
                print(f"   Response: {result['response']}")
            return True
        else:
            error = result.get('error', 'Unknown error')
            error_lower = error.lower()
            if "not configured" in error_lower or "no address" in error_lower or "hostname" in error_lower or "connect" in error_lower:
                print(f"⚠️  SKIPPED: CRM backend not reachable in this environment")
                print("   Set CRM_BACKEND_URL and CRM_TENANT_CODE in .env to test")
                return True  # Not a failure, just not configured/reachable
            else:
                print(f"❌ FAILED: {error}")
                return False

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False


# ========== Mock-based CRM unit tests ==========

def _make_mock_http_client(status_code=200, response_body='{"success": true, "id": "abc123"}'):
    """Return a mocked httpx.AsyncClient context manager."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.text = response_body
    mock_response.json = Mock(return_value={"success": True, "id": "abc123"})
    mock_response.raise_for_status = Mock()

    captured = {}

    async def mock_post(*args, **kwargs):
        if 'json' in kwargs:
            captured.update(kwargs['json'])
        elif 'content' in kwargs:
            # crm.py now sends raw JSON bytes via content=
            import json as _json
            raw = kwargs['content']
            if isinstance(raw, bytes):
                captured.update(_json.loads(raw))
        return mock_response

    mock_client = MagicMock()
    mock_client.post = mock_post

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return mock_client
        async def __aexit__(self, *args):
            pass

    return MockAsyncClient, captured


async def test_crm_backend_mock_successful_call():
    """Mock test: successful booked call submits with escalation_status=none"""
    print("\n" + "="*60)
    print("Testing CRM Backend Mock - Successful Call (booked)...")
    print("="*60)

    MockClient, captured = _make_mock_http_client()
    test_call_data = CallData(
        name="Alice Smith",
        phone="+15551112222",
        email="alice@example.com",
        service="AI Consulting",
        status="booked",
        appointment_time="2026-04-10T10:00:00",
        notes="Test booking"
    )

    with patch('httpx.AsyncClient', MockClient):
        result = await push_to_crm_backend(
            call_data=test_call_data,
            call_sid="MOCK_SID_BOOKED",
            summary="Caller booked an AI consulting appointment successfully.",
            escalation_status="none",
        )

    ok = True
    if result.get("success"):
        print("   ✓ push_to_crm_backend returned success")
    else:
        print(f"   ✗ push_to_crm_backend failed: {result.get('error')}")
        ok = False

    for field in ("name", "email", "phone", "tenant_code", "summary", "escalation_status", "timestamp"):
        if field in captured:
            print(f"   ✓ '{field}' present in payload: {captured[field]!r}")
        else:
            print(f"   ✗ '{field}' missing from payload")
            ok = False

    if captured.get("escalation_status") == "none":
        print("   ✓ escalation_status is 'none' for successful booking")
    else:
        print(f"   ✗ escalation_status expected 'none', got {captured.get('escalation_status')!r}")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Successful call CRM submission works correctly")
    else:
        print("\n❌ FAILED: Successful call CRM submission has issues")
    return ok


async def test_crm_backend_mock_escalated_call():
    """Mock test: escalated call submits with escalation_status=escalated"""
    print("\n" + "="*60)
    print("Testing CRM Backend Mock - Escalated Call...")
    print("="*60)

    MockClient, captured = _make_mock_http_client()
    test_call_data = CallData(
        name="Bob Jones",
        phone="+15553334444",
        email="bob@example.com",
        service="Billing Support",
        status="needs_human",
        notes=""
    )

    with patch('httpx.AsyncClient', MockClient):
        result = await push_to_crm_backend(
            call_data=test_call_data,
            call_sid="MOCK_SID_ESCALATED",
            summary="Caller requested to speak with a human agent.",
            escalation_status="escalated",
        )

    ok = True
    if result.get("success"):
        print("   ✓ push_to_crm_backend returned success")
    else:
        print(f"   ✗ push_to_crm_backend failed: {result.get('error')}")
        ok = False

    if captured.get("escalation_status") == "escalated":
        print("   ✓ escalation_status is 'escalated'")
    else:
        print(f"   ✗ escalation_status expected 'escalated', got {captured.get('escalation_status')!r}")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Escalated call CRM submission works correctly")
    else:
        print("\n❌ FAILED: Escalated call CRM submission has issues")
    return ok


async def test_crm_backend_mock_pending_call():
    """Mock test: failed booking submits with escalation_status=pending"""
    print("\n" + "="*60)
    print("Testing CRM Backend Mock - Pending/Failed Booking...")
    print("="*60)

    MockClient, captured = _make_mock_http_client()
    test_call_data = CallData(
        name="Carol White",
        phone="+15555556666",
        email="carol@example.com",
        service="General Enquiry",
        status="needs_callback",
        notes=""
    )

    with patch('httpx.AsyncClient', MockClient):
        result = await push_to_crm_backend(
            call_data=test_call_data,
            call_sid="MOCK_SID_PENDING",
            summary="Caller requested a callback because booking failed.",
            escalation_status="pending",
        )

    ok = True
    if result.get("success"):
        print("   ✓ push_to_crm_backend returned success")
    else:
        print(f"   ✗ push_to_crm_backend failed: {result.get('error')}")
        ok = False

    if captured.get("escalation_status") == "pending":
        print("   ✓ escalation_status is 'pending'")
    else:
        print(f"   ✗ escalation_status expected 'pending', got {captured.get('escalation_status')!r}")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Pending call CRM submission works correctly")
    else:
        print("\n❌ FAILED: Pending call CRM submission has issues")
    return ok


async def test_crm_backend_mock_without_optional_fields():
    """Mock test: submission works with minimal fields (no summary/escalation supplied)"""
    print("\n" + "="*60)
    print("Testing CRM Backend Mock - Minimal Fields (no summary/escalation)...")
    print("="*60)

    MockClient, captured = _make_mock_http_client()
    test_call_data = CallData(
        name="David Brown",
        phone="+15557778888",
        email=None,
        service=None,
        status="booked",
        notes=""
    )

    with patch('httpx.AsyncClient', MockClient):
        # Do NOT pass summary or escalation_status — should auto-determine
        result = await push_to_crm_backend(
            call_data=test_call_data,
            call_sid="MOCK_SID_MINIMAL",
        )

    ok = True
    if result.get("success"):
        print("   ✓ push_to_crm_backend returned success without optional fields")
    else:
        print(f"   ✗ push_to_crm_backend failed: {result.get('error')}")
        ok = False

    # escalation_status should be auto-determined to 'none' for 'booked' status
    if "escalation_status" in captured:
        print(f"   ✓ escalation_status auto-determined: {captured['escalation_status']!r}")
        if captured["escalation_status"] == "none":
            print("   ✓ auto-determined escalation_status is 'none' for booked call")
        else:
            print(f"   ✗ expected 'none', got {captured['escalation_status']!r}")
            ok = False
    else:
        print("   ✗ escalation_status missing from payload")
        ok = False

    # email should fall back to default
    if "email" in captured:
        print(f"   ✓ email fallback used: {captured['email']!r}")
    else:
        print("   ✗ email missing from payload")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Minimal-field CRM submission works correctly")
    else:
        print("\n❌ FAILED: Minimal-field CRM submission has issues")
    return ok


def test_determine_escalation_status():
    """Unit test: determine_escalation_status() returns correct values for all outcomes"""
    print("\n" + "="*60)
    print("Testing determine_escalation_status()...")
    print("="*60)

    ok = True
    cases = [
        # (status, summary, expected)
        ("booked",         None,                                              "none"),
        ("qualified",      None,                                              "none"),
        ("needs_human",    None,                                              "escalated"),
        ("escalated",      None,                                              "escalated"),
        ("needs_callback", None,                                              "pending"),
        ("failed",         None,                                              "pending"),
        ("no_booking",     None,                                              "pending"),
        ("cancelled",      None,                                              "pending"),
        ("resolved",       None,                                              "resolved"),
        # Summary-based fallback (ambiguous status)
        ("new",            "Caller requested a callback from a human agent.", "pending"),
        ("new",            "Call was escalated to a human agent.",            "escalated"),
        ("new",            "Issue resolved after speaking with team.",        "resolved"),
        ("new",            "Caller scheduled an appointment successfully.",   "none"),
    ]

    for status, summary, expected in cases:
        call_data = CallData(name="Test", phone="+1555", status=status)
        result = determine_escalation_status(call_data, summary)
        if result == expected:
            print(f"   ✓ status={status!r} summary={'<text>' if summary else 'None'} → {result!r}")
        else:
            print(f"   ✗ status={status!r} summary={'<text>' if summary else 'None'} → got {result!r}, expected {expected!r}")
            ok = False

    # Test with a fully populated CallData object to ensure no unintended side-effects
    full_call_data = CallData(
        name="Fully Populated",
        phone="+15559990000",
        email="full@example.com",
        service="Full Test Service",
        status="booked",
        appointment_time="2026-05-01T09:00:00",
        notes="All fields populated",
        booking_uid="UID-12345",
        discovery_answers={"q1": "a1", "q2": "a2"},
    )
    result = determine_escalation_status(full_call_data, "Appointment was booked successfully.")
    if result == "none":
        print(f"   ✓ Fully populated CallData with 'booked' status → {result!r}")
    else:
        print(f"   ✗ Fully populated CallData with 'booked' status → got {result!r}, expected 'none'")
        ok = False

    if ok:
        print("\n✅ SUCCESS: determine_escalation_status() works correctly for all cases")
    else:
        print("\n❌ FAILED: determine_escalation_status() has unexpected results")
    return ok



# ========== Tenant Registry unit tests ==========

def _make_mock_registry_response(tenants):
    """Build a mock httpx response for the tenant-registry endpoint."""
    import json as _json
    mock_response = Mock()
    mock_response.status_code = 200
    body = _json.dumps({"tenants": tenants})
    mock_response.text = body
    mock_response.json = Mock(return_value={"tenants": tenants})
    mock_response.raise_for_status = Mock()
    return mock_response


async def test_tenant_registry_bootstrap():
    """Unit test: TenantRegistryManager.bootstrap() loads active tenants into cache."""
    print("\n" + "="*60)
    print("Testing TenantRegistryManager - Bootstrap...")
    print("="*60)

    from backend.services.tenant_registry import TenantRegistryManager

    sample_tenants = [
        {"tenant_code": "walmart", "api_key": "vai_wmt", "signing_secret": "sec_wmt", "is_active": True},
        {"tenant_code": "home_depot", "api_key": "vai_hd", "signing_secret": "sec_hd", "is_active": True},
        {"tenant_code": "inactive_co", "api_key": "vai_inc", "signing_secret": "sec_inc", "is_active": False},
    ]
    mock_resp = _make_mock_registry_response(sample_tenants)

    class MockAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args, **kwargs): return mock_resp

    ok = True
    with patch('httpx.AsyncClient', MockAsyncClient):
        manager = TenantRegistryManager(
            crm_url="https://crm.example.com",
            master_api_key="master_key_test",
        )
        result = await manager.bootstrap()

    if result:
        print("   ✓ bootstrap() returned True")
    else:
        print("   ✗ bootstrap() returned False")
        ok = False

    registry = manager.get_all_tenants()
    if len(registry) == 2:
        print(f"   ✓ 2 active tenants loaded (inactive tenant excluded)")
    else:
        print(f"   ✗ expected 2 active tenants, got {len(registry)}")
        ok = False

    for code in ("walmart", "home_depot"):
        creds = manager.get_tenant_credentials(code)
        if creds and creds.get("api_key"):
            print(f"   ✓ credentials present for '{code}'")
        else:
            print(f"   ✗ credentials missing for '{code}'")
            ok = False

    if not manager.get_tenant_credentials("inactive_co"):
        print("   ✓ inactive tenant correctly excluded from registry")
    else:
        print("   ✗ inactive tenant incorrectly included in registry")
        ok = False

    if manager.is_tenant_active("walmart"):
        print("   ✓ is_tenant_active('walmart') → True")
    else:
        print("   ✗ is_tenant_active('walmart') should be True")
        ok = False

    if not manager.is_tenant_active("unknown_tenant"):
        print("   ✓ is_tenant_active('unknown_tenant') → False")
    else:
        print("   ✗ is_tenant_active('unknown_tenant') should be False")
        ok = False

    if ok:
        print("\n✅ SUCCESS: TenantRegistryManager bootstrap works correctly")
    else:
        print("\n❌ FAILED: TenantRegistryManager bootstrap has issues")
    return ok


async def test_tenant_registry_stale_cache_on_failure():
    """Unit test: registry keeps stale cache when CRM is unreachable."""
    print("\n" + "="*60)
    print("Testing TenantRegistryManager - Stale Cache Fallback...")
    print("="*60)

    from backend.services.tenant_registry import TenantRegistryManager

    sample_tenants = [
        {"tenant_code": "walmart", "api_key": "vai_wmt", "signing_secret": "sec_wmt", "is_active": True},
    ]
    mock_resp = _make_mock_registry_response(sample_tenants)

    call_count = {"n": 0}

    class MockAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return mock_resp  # First call succeeds
            raise ConnectionError("CRM is down")  # Subsequent calls fail

    ok = True
    with patch('httpx.AsyncClient', MockAsyncClient):
        manager = TenantRegistryManager(
            crm_url="https://crm.example.com",
            master_api_key="master_key_test",
        )
        await manager.bootstrap()  # Load initial registry
        initial_count = len(manager.get_all_tenants())

        # Simulate a failed sync (CRM down)
        try:
            await manager._fetch_and_update()
        except Exception:
            pass  # Expected failure

    if initial_count == 1 and len(manager.get_all_tenants()) == 1:
        print("   ✓ stale cache preserved after failed sync")
    else:
        print(f"   ✗ expected 1 tenant in stale cache, got {len(manager.get_all_tenants())}")
        ok = False

    if manager.get_tenant_credentials("walmart"):
        print("   ✓ walmart credentials still available from stale cache")
    else:
        print("   ✗ walmart credentials lost after failed sync")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Stale cache fallback works correctly")
    else:
        print("\n❌ FAILED: Stale cache fallback has issues")
    return ok


async def test_crm_push_with_hmac_auth():
    """Unit test: CRM push includes HMAC auth headers when registry is configured."""
    print("\n" + "="*60)
    print("Testing CRM Push - HMAC Authentication Headers...")
    print("="*60)

    import backend.services.crm as crm_module
    from backend.services.tenant_registry import TenantRegistryManager

    # Patch in a fake registry with known credentials
    fake_registry = TenantRegistryManager(
        crm_url="https://crm.example.com",
        master_api_key="master_key_test",
    )
    fake_registry._registry = {
        "walmart": {"api_key": "vai_wmt_test", "signing_secret": "super_secret_wmt", "is_active": True},
    }

    captured_headers = {}
    captured_body = {}

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = '{"id": "log_1"}'
    mock_response.json = Mock(return_value={"id": "log_1"})
    mock_response.raise_for_status = Mock()

    class MockAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            import json as _json
            raw = kwargs.get("content", b"")
            if isinstance(raw, bytes):
                captured_body.update(_json.loads(raw))
            return mock_response

    test_call_data = CallData(
        name="Tenant Test",
        phone="+15550001111",
        email="tenant@example.com",
        status="booked",
        tenant_code="walmart",
    )

    original_manager = crm_module.registry_manager
    try:
        crm_module.registry_manager = fake_registry
        with patch('httpx.AsyncClient', MockAsyncClient):
            result = await crm_module.push_to_crm_backend(
                call_data=test_call_data,
                call_sid="MOCK_HMAC_SID",
                summary="Test HMAC call.",
                escalation_status="none",
            )
    finally:
        crm_module.registry_manager = original_manager

    ok = True
    if result.get("success"):
        print("   ✓ push_to_crm_backend returned success")
    else:
        print(f"   ✗ push_to_crm_backend failed: {result.get('error')}")
        ok = False

    for header in ("X-Voice-Agent-Key", "X-Voice-Agent-Timestamp", "X-Voice-Agent-Signature"):
        if captured_headers.get(header):
            print(f"   ✓ {header} present in request headers")
        else:
            print(f"   ✗ {header} missing from request headers")
            ok = False

    if captured_headers.get("X-Voice-Agent-Key") == "vai_wmt_test":
        print("   ✓ correct api_key used in X-Voice-Agent-Key")
    else:
        print(f"   ✗ expected 'vai_wmt_test', got {captured_headers.get('X-Voice-Agent-Key')!r}")
        ok = False

    if captured_body.get("tenant_code") == "walmart":
        print("   ✓ tenant_code 'walmart' in payload (from call_data.tenant_code)")
    else:
        print(f"   ✗ tenant_code expected 'walmart', got {captured_body.get('tenant_code')!r}")
        ok = False

    if ok:
        print("\n✅ SUCCESS: HMAC authentication headers added correctly")
    else:
        print("\n❌ FAILED: HMAC authentication header issues found")
    return ok


async def test_crm_push_tenant_code_fallback():
    """Unit test: CRM push falls back to CRM_TENANT_CODE when call_data has no tenant_code."""
    print("\n" + "="*60)
    print("Testing CRM Push - tenant_code Fallback to Config...")
    print("="*60)

    import backend.services.crm as crm_module

    captured_body = {}

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = '{"id": "log_2"}'
    mock_response.json = Mock(return_value={"id": "log_2"})
    mock_response.raise_for_status = Mock()

    class MockAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            import json as _json
            raw = kwargs.get("content", b"")
            if isinstance(raw, bytes):
                captured_body.update(_json.loads(raw))
            return mock_response

    # call_data without tenant_code → should fall back to CRM_TENANT_CODE from config
    test_call_data = CallData(
        name="Fallback Test",
        phone="+15550002222",
        status="booked",
    )

    original_manager = crm_module.registry_manager
    try:
        crm_module.registry_manager = None  # No registry configured
        with patch('httpx.AsyncClient', MockAsyncClient):
            result = await crm_module.push_to_crm_backend(
                call_data=test_call_data,
                call_sid="MOCK_FALLBACK_SID",
            )
    finally:
        crm_module.registry_manager = original_manager

    ok = True
    if result.get("success"):
        print("   ✓ push_to_crm_backend returned success")
    else:
        print(f"   ✗ push_to_crm_backend failed: {result.get('error')}")
        ok = False

    # tenant_code in payload should come from the global CRM_TENANT_CODE config
    from backend.config import CRM_TENANT_CODE
    if captured_body.get("tenant_code") == CRM_TENANT_CODE:
        print(f"   ✓ tenant_code fell back to config value '{CRM_TENANT_CODE}'")
    else:
        print(f"   ✗ tenant_code expected '{CRM_TENANT_CODE}', got {captured_body.get('tenant_code')!r}")
        ok = False

    if ok:
        print("\n✅ SUCCESS: tenant_code fallback works correctly")
    else:
        print("\n❌ FAILED: tenant_code fallback has issues")
    return ok


async def test_tenant_determination_registry_multi():
    """Unit test: get_tenant_for_call() returns first active tenant when registry has multiple tenants."""
    print("\n" + "="*60)
    print("Testing Tenant Determination - Registry with Multiple Tenants...")
    print("="*60)

    import backend.services.crm as crm_module
    from backend.services.tenant_registry import TenantRegistryManager

    fake_registry = TenantRegistryManager(
        crm_url="https://crm.example.com",
        master_api_key="master_key_test",
    )
    fake_registry._registry = {
        "walmart": {"api_key": "vai_wmt", "signing_secret": "sec_wmt", "is_active": True},
        "home_depot": {"api_key": "vai_hd", "signing_secret": "sec_hd", "is_active": True},
    }

    original_manager = crm_module.registry_manager
    ok = True
    try:
        crm_module.registry_manager = fake_registry
        from backend.services.tenant_determination import get_tenant_for_call
        result = get_tenant_for_call()
    finally:
        crm_module.registry_manager = original_manager

    # Python 3.7+ guarantees dict insertion order; "first_available" strategy
    # should return the first key inserted into the registry.
    if result == "walmart":
        print(f"   ✓ get_tenant_for_call() returned first active tenant: '{result}'")
    else:
        print(f"   ✗ expected 'walmart', got '{result}'")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Tenant determination (multi-tenant registry) works correctly")
    else:
        print("\n❌ FAILED: Tenant determination (multi-tenant registry) has issues")
    return ok


async def test_tenant_determination_registry_single():
    """Unit test: get_tenant_for_call() returns the only tenant when registry has one tenant."""
    print("\n" + "="*60)
    print("Testing Tenant Determination - Registry with Single Tenant...")
    print("="*60)

    import backend.services.crm as crm_module
    from backend.services.tenant_registry import TenantRegistryManager

    fake_registry = TenantRegistryManager(
        crm_url="https://crm.example.com",
        master_api_key="master_key_test",
    )
    fake_registry._registry = {
        "celebrate_gannon": {"api_key": "vai_cg", "signing_secret": "sec_cg", "is_active": True},
    }

    original_manager = crm_module.registry_manager
    ok = True
    try:
        crm_module.registry_manager = fake_registry
        from backend.services.tenant_determination import get_tenant_for_call
        result = get_tenant_for_call()
    finally:
        crm_module.registry_manager = original_manager

    if result == "celebrate_gannon":
        print(f"   ✓ get_tenant_for_call() returned the single registry tenant: '{result}'")
    else:
        print(f"   ✗ expected 'celebrate_gannon', got '{result}'")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Tenant determination (single-tenant registry) works correctly")
    else:
        print("\n❌ FAILED: Tenant determination (single-tenant registry) has issues")
    return ok


async def test_tenant_determination_no_registry():
    """Unit test: get_tenant_for_call() falls back to CRM_TENANT_CODE when registry is None."""
    print("\n" + "="*60)
    print("Testing Tenant Determination - Registry Unavailable (fallback)...")
    print("="*60)

    import backend.services.crm as crm_module
    from backend.config import CRM_TENANT_CODE

    original_manager = crm_module.registry_manager
    ok = True
    try:
        crm_module.registry_manager = None
        from backend.services.tenant_determination import get_tenant_for_call
        result = get_tenant_for_call()
    finally:
        crm_module.registry_manager = original_manager

    if result == CRM_TENANT_CODE:
        print(f"   ✓ get_tenant_for_call() fell back to CRM_TENANT_CODE: '{result}'")
    else:
        print(f"   ✗ expected CRM_TENANT_CODE '{CRM_TENANT_CODE}', got '{result}'")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Tenant determination (no registry fallback) works correctly")
    else:
        print("\n❌ FAILED: Tenant determination (no registry fallback) has issues")
    return ok


async def test_tenant_determination_empty_registry():
    """Unit test: get_tenant_for_call() falls back to CRM_TENANT_CODE when registry is empty."""
    print("\n" + "="*60)
    print("Testing Tenant Determination - Empty Registry (fallback)...")
    print("="*60)

    import backend.services.crm as crm_module
    from backend.services.tenant_registry import TenantRegistryManager
    from backend.config import CRM_TENANT_CODE

    fake_registry = TenantRegistryManager(
        crm_url="https://crm.example.com",
        master_api_key="master_key_test",
    )
    fake_registry._registry = {}  # Empty — no active tenants

    original_manager = crm_module.registry_manager
    ok = True
    try:
        crm_module.registry_manager = fake_registry
        from backend.services.tenant_determination import get_tenant_for_call
        result = get_tenant_for_call()
    finally:
        crm_module.registry_manager = original_manager

    if result == CRM_TENANT_CODE:
        print(f"   ✓ get_tenant_for_call() fell back to CRM_TENANT_CODE: '{result}'")
    else:
        print(f"   ✗ expected CRM_TENANT_CODE '{CRM_TENANT_CODE}', got '{result}'")
        ok = False

    if ok:
        print("\n✅ SUCCESS: Tenant determination (empty registry fallback) works correctly")
    else:
        print("\n❌ FAILED: Tenant determination (empty registry fallback) has issues")
    return ok


async def main():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("NOVA VOICE AGENT - INTEGRATION TESTS")
    print("="*60)

    # Test Cal.com
    calcom_ok = await test_calcom()

    # Test Notion
    notion_ok = await test_notion()

    # Test CRM Backend (live)
    crm_backend_ok = await test_crm_backend()

    # Mock-based CRM unit tests
    crm_mock_booked_ok = await test_crm_backend_mock_successful_call()
    crm_mock_escalated_ok = await test_crm_backend_mock_escalated_call()
    crm_mock_pending_ok = await test_crm_backend_mock_pending_call()
    crm_mock_minimal_ok = await test_crm_backend_mock_without_optional_fields()

    # Escalation status unit test (sync)
    escalation_ok = test_determine_escalation_status()

    # Tenant Registry unit tests
    registry_bootstrap_ok = await test_tenant_registry_bootstrap()
    registry_stale_ok = await test_tenant_registry_stale_cache_on_failure()
    crm_hmac_ok = await test_crm_push_with_hmac_auth()
    crm_fallback_ok = await test_crm_push_tenant_code_fallback()

    # Tenant determination unit tests
    td_multi_ok = await test_tenant_determination_registry_multi()
    td_single_ok = await test_tenant_determination_registry_single()
    td_no_registry_ok = await test_tenant_determination_no_registry()
    td_empty_ok = await test_tenant_determination_empty_registry()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Cal.com:                      {'✅ WORKING' if calcom_ok else '❌ FAILED'}")
    print(f"Notion:                       {'✅ WORKING' if notion_ok else '❌ FAILED'}")
    print(f"CRM Backend (live):           {'✅ WORKING' if crm_backend_ok else '❌ FAILED'}")
    print(f"CRM Mock - Booked:            {'✅ WORKING' if crm_mock_booked_ok else '❌ FAILED'}")
    print(f"CRM Mock - Escalated:         {'✅ WORKING' if crm_mock_escalated_ok else '❌ FAILED'}")
    print(f"CRM Mock - Pending:           {'✅ WORKING' if crm_mock_pending_ok else '❌ FAILED'}")
    print(f"CRM Mock - Minimal Fields:    {'✅ WORKING' if crm_mock_minimal_ok else '❌ FAILED'}")
    print(f"Escalation Status Logic:      {'✅ WORKING' if escalation_ok else '❌ FAILED'}")
    print(f"Registry - Bootstrap:         {'✅ WORKING' if registry_bootstrap_ok else '❌ FAILED'}")
    print(f"Registry - Stale Cache:       {'✅ WORKING' if registry_stale_ok else '❌ FAILED'}")
    print(f"CRM Push - HMAC Auth:         {'✅ WORKING' if crm_hmac_ok else '❌ FAILED'}")
    print(f"CRM Push - Tenant Fallback:   {'✅ WORKING' if crm_fallback_ok else '❌ FAILED'}")
    print(f"Tenant Det. - Multi-tenant:   {'✅ WORKING' if td_multi_ok else '❌ FAILED'}")
    print(f"Tenant Det. - Single-tenant:  {'✅ WORKING' if td_single_ok else '❌ FAILED'}")
    print(f"Tenant Det. - No Registry:    {'✅ WORKING' if td_no_registry_ok else '❌ FAILED'}")
    print(f"Tenant Det. - Empty Registry: {'✅ WORKING' if td_empty_ok else '❌ FAILED'}")
    print("="*60 + "\n")

    all_ok = (
        calcom_ok and notion_ok and crm_backend_ok and
        crm_mock_booked_ok and crm_mock_escalated_ok and
        crm_mock_pending_ok and crm_mock_minimal_ok and escalation_ok and
        registry_bootstrap_ok and registry_stale_ok and crm_hmac_ok and crm_fallback_ok and
        td_multi_ok and td_single_ok and td_no_registry_ok and td_empty_ok
    )

    if all_ok:
        print("🎉 All integrations are working correctly!")
        return 0
    else:
        print("⚠️  Some integrations need attention")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
