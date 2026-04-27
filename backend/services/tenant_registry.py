"""
Tenant Registry Manager

Bootstraps on startup by pulling all active voice-agent integrations from the
CRM backend.  The credentials are cached in-memory and refreshed periodically
so that new tenants added to the CRM are picked up without restarting Nova.

Usage:
    # During app startup (see backend/main.py):
    registry = TenantRegistryManager(crm_url=..., master_api_key=..., refresh_interval=3600)
    await registry.bootstrap()
    asyncio.create_task(registry.start_periodic_sync())

    # During call processing:
    creds = registry.get_tenant_credentials("walmart")
    # creds -> {"api_key": "vai_...", "signing_secret": "...", "is_active": True}
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class TenantRegistryManager:
    """Manages per-tenant credentials fetched from the CRM tenant-registry endpoint."""

    def __init__(self, crm_url: str, master_api_key: str, refresh_interval: int = 3600) -> None:
        """
        Args:
            crm_url: Base URL of the CRM backend
                     (e.g. "https://crm-backend-8b97.onrender.com").
            master_api_key: API key used to authenticate against
                            GET /public/tenant-registry/.
            refresh_interval: Seconds between background registry syncs.
                               Defaults to 3600 (1 hour).
        """
        self.crm_url = crm_url.rstrip("/")
        self.master_api_key = master_api_key
        self.refresh_interval = refresh_interval

        # In-memory cache: tenant_code → {"api_key": ..., "signing_secret": ..., "is_active": ...}
        self._registry: Dict[str, Dict] = {}
        self.last_refresh: Optional[datetime] = None
        self._is_syncing: bool = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def bootstrap(self) -> bool:
        """
        Perform an initial blocking sync at startup.

        Returns:
            True if the registry was loaded successfully, False otherwise.
        """
        logger.info("TenantRegistryManager: bootstrapping registry …")
        try:
            await self._fetch_and_update()
            logger.info(
                "TenantRegistryManager: bootstrap complete — %d active tenant(s) loaded",
                len(self._registry),
            )
            return True
        except Exception as exc:
            logger.error("TenantRegistryManager: bootstrap failed: %s", exc)
            return False

    async def start_periodic_sync(self) -> None:
        """
        Background coroutine that refreshes the registry every
        ``refresh_interval`` seconds.  Schedule this with asyncio.create_task()
        after a successful bootstrap.
        """
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self._fetch_and_update()
            except asyncio.CancelledError:
                logger.info("TenantRegistryManager: periodic sync cancelled")
                raise
            except Exception as exc:
                logger.error("TenantRegistryManager: periodic sync error: %s", exc)

    def get_tenant_credentials(self, tenant_code: str) -> Optional[Dict]:
        """
        Return the credential dict for *tenant_code*, or None if not found.

        The returned dict contains at minimum::

            {
                "api_key": "vai_…",
                "signing_secret": "…",
                "is_active": True,
            }
        """
        return self._registry.get(tenant_code)

    def is_tenant_active(self, tenant_code: str) -> bool:
        """Return True if *tenant_code* is present in the active registry."""
        return tenant_code in self._registry

    def get_all_tenants(self) -> Dict[str, Dict]:
        """Return a copy of the full in-memory registry."""
        return dict(self._registry)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_and_update(self) -> None:
        """
        Fetch the registry from the CRM backend and update the in-memory cache.
        Raises on network / authentication errors so callers can handle them.
        If the fetch fails the existing cache is preserved (stale fallback).
        """
        if self._is_syncing:
            logger.debug("TenantRegistryManager: sync already in progress, skipping")
            return

        self._is_syncing = True
        try:
            url = f"{self.crm_url}/public/tenant-registry/"
            headers = {
                "X-Master-API-Key": self.master_api_key,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            data = response.json()
            tenants = data.get("tenants", [])

            new_registry: Dict[str, Dict] = {}
            for tenant in tenants:
                if tenant.get("is_active"):
                    code = tenant.get("tenant_code")
                    if code:
                        new_registry[code] = {
                            "api_key": tenant.get("api_key", ""),
                            "signing_secret": tenant.get("signing_secret", ""),
                            "is_active": True,
                        }

            self._registry = new_registry
            self.last_refresh = datetime.now(timezone.utc)
            logger.info(
                "TenantRegistryManager: registry synced — %d active tenant(s)",
                len(self._registry),
            )

        except Exception:
            # Keep using the stale cache so Nova can continue serving calls
            logger.warning(
                "TenantRegistryManager: sync failed — continuing with stale cache "
                "(%d tenant(s))",
                len(self._registry),
            )
            raise
        finally:
            self._is_syncing = False
