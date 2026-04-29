"""
Tenant Determination Service

Determines which tenant an incoming call belongs to using the in-memory tenant
registry.  Falls back to the ``CRM_TENANT_CODE`` environment variable when the
registry is unavailable or empty, so existing single-tenant deployments continue
to work without any changes.

Usage::

    from services.tenant_determination import get_tenant_for_call

    tenant_code = get_tenant_for_call()
    conversation.call_data.tenant_code = tenant_code
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def _get_registry_manager():
    """
    Return the current ``registry_manager`` from the CRM module.

    The CRM module may be loaded under either ``backend.services.crm`` (when
    imported from the project root, e.g. in tests or main.py) or
    ``services.crm`` (when imported from within the ``backend/`` directory).
    Both names point to the same file but Python caches them separately, so we
    check both entries in ``sys.modules`` before falling back to a direct
    import.
    """
    for mod_name in ("backend.services.crm", "services.crm"):
        mod = sys.modules.get(mod_name)
        if mod is not None:
            return getattr(mod, "registry_manager", None)
    # Neither variant is loaded yet — import directly.
    import services.crm as _crm  # noqa: PLC0415
    return _crm.registry_manager


def get_tenant_for_call() -> str:
    """
    Determine the tenant code for an incoming call.

    Selection strategy (in priority order):

    1. **Registry available with one or more active tenants**: use the first
       active tenant.  The ``TENANT_SELECTION_STRATEGY`` config variable
       controls how the tenant is chosen (default: ``"first_available"``).
    2. **Registry unavailable or empty**: fall back to ``CRM_TENANT_CODE``
       from the environment / config.

    Returns:
        The tenant code string to assign to this call.
    """
    from config import CRM_TENANT_CODE, TENANT_SELECTION_STRATEGY

    registry = _get_registry_manager()

    if registry is not None:
        all_tenants = registry.get_all_tenants()
        if all_tenants:
            if TENANT_SELECTION_STRATEGY == "first_available":
                tenant_code = next(iter(all_tenants))
                logger.info(
                    "Tenant determined from registry (strategy=%s): %s "
                    "— %d active tenant(s) available",
                    TENANT_SELECTION_STRATEGY,
                    tenant_code,
                    len(all_tenants),
                )
                return tenant_code

            # Unknown strategy — default to first_available behaviour.
            tenant_code = next(iter(all_tenants))
            logger.warning(
                "Unknown TENANT_SELECTION_STRATEGY '%s'; "
                "defaulting to first active tenant: %s",
                TENANT_SELECTION_STRATEGY,
                tenant_code,
            )
            return tenant_code

        logger.warning(
            "Tenant registry is available but contains no active tenants; "
            "falling back to CRM_TENANT_CODE"
        )
    else:
        logger.info(
            "Tenant registry unavailable; using CRM_TENANT_CODE fallback"
        )

    fallback = CRM_TENANT_CODE
    logger.info("Using fallback tenant code: %s", fallback)
    return fallback
