# Tenant-Specific Authentication Keys Update

## Changes Made

Renamed generic CRM authentication keys to tenant-specific keys to clarify that current keys only work for the **celebrate_gannon** tenant.

### Environment Variables (.env)

**Before:**
```
CRM_API_KEY=vai_DaLfrOsAeRU2LCPAxUIhzcC0FqkQ_FyP
CRM_SIGNING_SECRET=meXMVcjn-UkJEjkcRQ3UgSHBpBTfHeBs5QYFApg_peUoEmGXTPwlw6tkKanA6ydx
```

**After:**
```
# Celebrate Gannon Tenant Keys
# These keys provide access ONLY to the celebrate_gannon tenant
CELEBRATE_GANNON_API_KEY=vai_DaLfrOsAeRU2LCPAxUIhzcC0FqkQ_FyP
CELEBRATE_GANNON_SIGNING_SECRET=meXMVcjn-UkJEjkcRQ3UgSHBpBTfHeBs5QYFApg_peUoEmGXTPwlw6tkKanA6ydx

# Walmart Tenant Keys (TO BE ADDED)
# These keys will provide access ONLY to the walmart tenant
# WALMART_API_KEY=<to_be_added>
# WALMART_SIGNING_SECRET=<to_be_added>
```

### Code Changes

**1. backend/config.py**
- Added  and 
- Added placeholders for  and 
- Kept legacy  pointing to celebrate_gannon for backwards compatibility

**2. backend/services/crm.py**
- Updated fallback credentials to load from .env instead of hardcoded values
- Added walmart tenant fallback (will activate when keys are added to .env)

## How to Add Walmart Tenant Keys

When you receive the walmart tenant keys, simply:

1. Edit 
2. Uncomment and fill in:
   ```
   WALMART_API_KEY=vai_<your_walmart_key>
   WALMART_SIGNING_SECRET=<your_walmart_secret>
   ```
3. Restart Nova: 

## Current Status

✅ Celebrate Gannon tenant: Fully configured with dedicated keys  
⏳ Walmart tenant: Placeholder added, awaiting keys

Both tenants will use their respective keys when the registry is unavailable.
