# Tenant Configuration Fix - April 29, 2026

## Issue
Nova was assigning calls to "walmart" tenant instead of "celebrate_gannon" tenant (tenant code 8).

## Root Cause
The tenant registry was pulling 2 active tenants from the CRM backend:
1. walmart (was being selected first)
2. celebrate_gannon (tenant code 8)

The `first_available` selection strategy was picking "walmart" alphabetically as the first tenant in the dictionary.

## Solution
Updated the tenant selection logic to **prioritize "celebrate_gannon"** when using the `first_available` strategy.

### Files Modified

**1. `backend/services/tenant_determination.py`**
- Added logic to check for "celebrate_gannon" first before falling back to iteration order
- This ensures celebrate_gannon is always selected when available

**2. `.env`**
- Added `CRM_TENANT_CODE=celebrate_gannon` as fallback
- Added `TENANT_SELECTION_STRATEGY=first_available`

### Code Change
```python
# Before: Just picked first tenant from dict
if TENANT_SELECTION_STRATEGY == "first_available":
    tenant_code = next(iter(all_tenants))
    
# After: Prioritizes celebrate_gannon
if TENANT_SELECTION_STRATEGY == "first_available":
    # Prioritize celebrate_gannon if available
    if "celebrate_gannon" in all_tenants:
        tenant_code = "celebrate_gannon"
    else:
        tenant_code = next(iter(all_tenants))
```

## Testing
✅ Verified tenant selection: **celebrate_gannon** is now the default
✅ CRM backend has celebrate_gannon with tenant_id 8
✅ HMAC credentials loaded correctly

## Status
✅ **FIXED** - All incoming calls will now be assigned to celebrate_gannon tenant.

Application restarted and running on port 8000.
