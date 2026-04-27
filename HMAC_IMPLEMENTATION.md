# HMAC-Authenticated CRM Client Implementation

## Overview
Robust service-to-service client for posting call logs to CRM backend with HMAC-SHA256 authentication, retry logic, and comprehensive observability.

---

## 🔐 Authentication

### Credentials (in `.env`)
```bash
CRM_BACKEND_URL=https://crm-backend-8b97.onrender.com
CRM_TENANT_CODE=celebrate_gannon
CRM_API_KEY=vai_DaLfrOsAeRU2LCPAxUIhzcC0FqkQ_FyP
CRM_SIGNING_SECRET=meXMVcjn-UkJEjkcRQ3UgSHBpBTfHeBs5QYFApg_peUoEmGXTPwlw6tkKanA6ydx
```

### Request Headers
Every request includes:
```
X-Voice-Agent-Key: {api_key}
X-Voice-Agent-Timestamp: {unix_timestamp}
X-Voice-Agent-Signature: {hmac_sha256_hex}
Content-Type: application/json
X-Request-ID: {uuid}
```

### Signature Algorithm
```python
message = f"{timestamp}.{raw_json_body_bytes}"
signature = HMAC_SHA256(signing_secret, message).hexdigest()
```

**Critical:** Use the EXACT same JSON bytes for signature and HTTP body.

---

## 📁 Files Created

### 1. `backend/services/hmac_auth.py`
HMAC signing utilities:
- `sign_request(timestamp, raw_body_bytes, signing_secret)` → hex signature
- `create_auth_headers(api_key, signing_secret, raw_body_bytes)` → dict
- `get_current_timestamp()` → string
- `verify_timestamp_window(timestamp, max_age=300)` → (bool, error)

### 2. `backend/services/crm_client_hmac.py`
Resilient HTTP client:
- `CallLogClient` - Main client class
- `get_call_log_client()` - Singleton factory
- Exponential backoff retry logic
- Structured logging with trace IDs
- HTTPS enforcement

### 3. `backend/config.py` (updated)
Added environment variables:
- `CRM_API_KEY`
- `CRM_SIGNING_SECRET`

---

## 🔄 Retry Logic

### Configuration
```python
MAX_RETRIES = 3              # 4 total attempts
INITIAL_RETRY_DELAY = 1.0s   # First retry after 1s
MAX_RETRY_DELAY = 10.0s      # Cap at 10s
TIMEOUT_SECONDS = 30.0       # Per-request timeout
```

### Retry Strategy
| Error Type | Action |
|------------|--------|
| **5xx** server errors | ✅ Retry with exponential backoff |
| **Network** errors | ✅ Retry with exponential backoff |
| **Timeout** | ✅ Retry with exponential backoff |
| **401** auth failure | ❌ No retry - return error |
| **403** tenant mismatch | ❌ No retry - return error |
| **422** validation error | ❌ No retry - return error |

### Backoff Schedule
- Attempt 1: Immediate
- Attempt 2: Wait 1s
- Attempt 3: Wait 2s
- Attempt 4: Wait 4s

---

## 📊 Observability

### Structured Logging
All requests logged in JSON format:
```json
{
  "timestamp": "2024-04-25T14:30:00Z",
  "level": "INFO",
  "message": "CRM request completed",
  "trace_id": "uuid-request-id",
  "call_id": "CA123456",
  "request_id": "uuid",
  "status_code": 200,
  "latency_seconds": 0.342,
  "attempt": 1
}
```

### Metrics Tracked
- ✅ Request latency (per attempt)
- ✅ HTTP status codes
- ✅ Retry attempts
- ✅ Success/failure rates
- ✅ Auth failures (401)
- ✅ Validation errors (422)
- ✅ Tenant mismatches (403)

### Security
- **Secrets redacted** in logs (API keys shown as `prefix...`)
- **Signatures truncated** to first 16 chars
- **Full trace IDs** for correlation

---

## 📝 Payload Schema

### Endpoint
```
POST https://crm-backend-8b97.onrender.com/public/call-logs/
```

### Required Fields
```json
{
  "tenant_code": "celebrate_gannon",
  "full_transcript": "Full conversation text..."
}
```

### Optional Fields
```json
{
  "summary": "Brief call summary",
  "problem_statement": "Customer's issue",
  "outcome": "Result of call",
  "next_steps": "Follow-up actions",
  "caller_name": "John Doe",
  "caller_phone": "+12345678900",
  "call_duration": 180,
  "escalation_status": "none",
  "timestamp": "2024-04-25T14:30:00Z"
}
```

---

## 💻 Usage

### Basic Usage
```python
from backend.services.crm_client_hmac import get_call_log_client

# Get singleton client (auto-validates credentials)
client = get_call_log_client()

# Post call log
result = await client.post_call_log(
    call_id="CA123456789",
    full_transcript="Customer: Hello...\nAgent: How can I help?",
    summary="Customer inquiry about pricing",
    caller_name="John Doe",
    caller_phone="+12345678900",
    call_duration=180,
    escalation_status="none"
)

# Handle result
if result["success"]:
    print(f"✓ Success: {result['response']}")
else:
    print(f"✗ Failed: {result['error']}")
```

### Result Structure

**Success Response:**
```python
{
    "success": True,
    "response": {...},          # Server response body
    "status_code": 200,
    "attempts": 1,
    "latency_seconds": 0.342
}
```

**Failure Response:**
```python
{
    "success": False,
    "error": "Auth failure - invalid key/signature",
    "status_code": 401,
    "detail": "...",            # Server error detail
    "attempts": 1
}
```

---

## 🔒 Security Features

### 1. HTTPS Enforcement
```python
# Rejects HTTP URLs at initialization
client = CallLogClient(
    base_url="http://insecure.com",  # ❌ ValueError
    ...
)
```

### 2. Timestamp Validation
- Server validates timestamp within 5-minute window
- Prevents replay attacks
- Requires NTP-synced clocks

### 3. Canonical JSON Strategy
```python
# Serialize ONCE, use for both signing and sending
raw_body_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
headers = create_auth_headers(api_key, secret, raw_body_bytes)
# Send exact same bytes
await client.post(url, content=raw_body_bytes, headers=headers)
```

### 4. Request ID / Idempotency
- Each request gets unique UUID
- Server can deduplicate via `X-Request-ID` header
- Enables safe retries

---

## 🧪 Testing

### Run Signing Tests
```bash
cd /opt/nova/nova-voice-agent
python3 test_hmac_signing.py
```

Tests:
- ✅ Signature determinism
- ✅ Timestamp sensitivity
- ✅ Body sensitivity
- ✅ Canonical JSON
- ✅ Realistic payloads

### Run Integration Test (with real credentials)
```bash
cd /opt/nova/nova-voice-agent
python3 test_hmac_real.py
```

This will:
1. Load credentials from `.env`
2. Initialize HMAC client
3. Post a test call log
4. Display result with status code, latency, attempts

---

## 🚨 Error Handling

### Server Responses

| Status | Meaning | Client Action |
|--------|---------|---------------|
| **200** | Success | Return response |
| **401** | Invalid API key or signature | Log error, no retry |
| **403** | Tenant code mismatch | Log error, no retry |
| **422** | Missing/invalid required fields | Log error, no retry |
| **500** | Internal server error | Retry with backoff |
| **502** | Bad gateway | Retry with backoff |
| **503** | Service unavailable | Retry with backoff |
| **504** | Gateway timeout | Retry with backoff |

### Client Errors

**Timeout Example:**
```json
{
  "success": false,
  "error": "Failed after 4 attempts: Request timeout after 30s",
  "attempts": 4
}
```

**Auth Failure Example:**
```json
{
  "success": false,
  "error": "Authentication failed - invalid key/signature",
  "status_code": 401,
  "detail": "HMAC signature verification failed",
  "attempts": 1
}
```

**Validation Error Example:**
```json
{
  "success": false,
  "error": "Validation error - check required fields",
  "status_code": 422,
  "detail": "Missing required field: full_transcript",
  "attempts": 1
}
```

---

## 📋 Integration Checklist

- [x] HMAC signing function implemented
- [x] Resilient HTTP client with retry logic
- [x] Structured logging with trace IDs
- [x] HTTPS enforcement
- [x] Environment variables configured
- [x] Credentials added to `.env`
- [x] Test suite created and passing
- [ ] Integrate into webhook handlers
- [ ] Test with real CRM backend
- [ ] Monitor production logs
- [ ] Set up alerting for auth failures

---

## 🔧 Configuration

### Required Environment Variables
```bash
CRM_BACKEND_URL=https://crm-backend-8b97.onrender.com
CRM_TENANT_CODE=celebrate_gannon
CRM_API_KEY=vai_DaLfrOsAeRU2LCPAxUIhzcC0FqkQ_FyP
CRM_SIGNING_SECRET=meXMVcjn-UkJEjkcRQ3UgSHBpBTfHeBs5QYFApg_peUoEmGXTPwlw6tkKanA6ydx
```

### Optional Configuration
Modify in `backend/services/crm_client_hmac.py`:
```python
MAX_RETRIES = 3              # Number of retries
INITIAL_RETRY_DELAY = 1.0    # First retry delay (seconds)
MAX_RETRY_DELAY = 10.0       # Maximum retry delay (seconds)
TIMEOUT_SECONDS = 30.0       # Request timeout (seconds)
```

---

## 📚 References

### Server-Side Verification
The CRM backend will:
1. Extract `X-Voice-Agent-Timestamp` and `X-Voice-Agent-Signature` headers
2. Read raw request body bytes
3. Recompute: `HMAC_SHA256(signing_secret, "{timestamp}.{body}")`
4. Compare computed signature with received signature
5. Verify timestamp is within 5-minute window
6. Verify `tenant_code` in payload matches integration tenant

### HMAC-SHA256 Algorithm
- **Hash Function:** SHA-256
- **Message Format:** `"{timestamp}.{raw_body_bytes}"`
- **Output Format:** Hex string (64 characters)
- **Example:** `a10d73ef3f3f7b4f0115936336f5da4240ef3f9a2836beff2e63d15b79435f06`

---

## 🎯 Next Steps

1. **Test with real endpoint:**
   ```bash
   python3 test_hmac_real.py
   ```

2. **Integrate into webhooks:**
   Update `backend/routes/webhooks.py` to use HMAC client

3. **Monitor production:**
   Watch structured logs for auth failures and retries

4. **Secret rotation:**
   When credentials expire, update `.env` and restart service

---

## ✅ Implementation Complete!

All requirements met:
- ✅ Reusable signing function
- ✅ Canonical JSON strategy
- ✅ Resilient HTTP client with retry
- ✅ Structured logging and metrics
- ✅ HTTPS enforcement
- ✅ Credentials in environment
- ✅ Comprehensive testing
