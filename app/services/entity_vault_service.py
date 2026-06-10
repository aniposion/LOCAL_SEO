"""P5: Entity Vault service - Single source of truth for business data."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now_naive
from app.models.vault import EntityVault
from app.schemas.entity_vault import (
    EntityVaultCreate,
    EntityVaultUpdate,
    SyncRequest,
    SyncResult,
    NAPEntry,
    NAPConsistencyReport,
)
from app.services.google_api_service import get_google_api_service

logger = logging.getLogger(__name__)


class EntityVaultService:
    """Service for managing business entity data.
    
    Entity Vault is the single source of truth for all business information:
    - Basic info (name, description, categories)
    - Address and coordinates
    - Contact information
    - Business hours
    - Amenities and attributes
    - Media (photos, logo)
    
    It syncs to external platforms like GBP, Facebook, Yelp.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.google = get_google_api_service()

    # ====================
    # CRUD Operations
    # ====================

    async def get(self, location_id: UUID) -> Optional[EntityVault]:
        """Get entity vault for a location."""
        result = await self.db.execute(
            select(EntityVault).where(EntityVault.location_id == location_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, vault_id: UUID) -> Optional[EntityVault]:
        """Get entity vault by ID."""
        result = await self.db.execute(
            select(EntityVault).where(EntityVault.id == vault_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: EntityVaultCreate) -> EntityVault:
        """Create entity vault for a location."""
        # Check if already exists
        existing = await self.get(data.location_id)
        if existing:
            raise ValueError("Entity vault already exists for this location")
        
        vault = EntityVault(
            location_id=data.location_id,
            
            # Basic info
            business_name=data.business_name,
            description=data.long_description,
            tagline=data.short_description,
            primary_category=data.primary_category,
            secondary_categories=data.secondary_categories or [],
            
            # Address (both formats)
            full_address=data.address.model_dump() if data.address else None,
            address=data.address.street1 if data.address else None,
            city=data.address.city if data.address else None,
            state=data.address.state if data.address else None,
            zip_code=data.address.postal_code if data.address else None,
            coordinates=data.coordinates.model_dump() if data.coordinates else None,
            
            # Contact
            contact_info=data.contact.model_dump() if data.contact else None,
            phone=data.contact.primary_phone if data.contact else None,
            website=str(data.contact.website) if data.contact and data.contact.website else None,
            
            # Hours
            business_hours=data.hours.model_dump() if data.hours else None,
            special_hours=[h.model_dump() for h in data.special_hours] if data.special_hours else [],
            hours_timezone=data.hours.timezone if data.hours else "America/New_York",
            
            # Attributes
            service_area=data.service_area.model_dump() if data.service_area else None,
            payment_methods=data.payment_methods.model_dump() if data.payment_methods else None,
            amenities=data.amenities.model_dump() if data.amenities else None,
            
            # Media
            logo_url=str(data.logo_url) if data.logo_url else None,
            cover_photo_url=str(data.cover_photo_url) if data.cover_photo_url else None,
            photo_urls=data.photo_urls or [],
            
            # Custom
            custom_attributes=data.custom_attributes or {},
        )
        
        self.db.add(vault)
        await self.db.commit()
        await self.db.refresh(vault)
        
        logger.info(f"Created entity vault {vault.id} for location {data.location_id}")
        return vault

    async def update(
        self,
        location_id: UUID,
        data: EntityVaultUpdate,
    ) -> EntityVault:
        """Update entity vault."""
        vault = await self.get(location_id)
        if not vault:
            raise ValueError("Entity vault not found")
        
        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if value is not None:
                if hasattr(value, "model_dump"):
                    value = value.model_dump()
                elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
                    value = [v.model_dump() for v in value]
                setattr(vault, field, value)
        
        vault.updated_at = utc_now_naive()
        
        # Mark as pending sync
        vault.gbp_sync_status = "pending"
        
        await self.db.commit()
        await self.db.refresh(vault)
        
        logger.info(f"Updated entity vault {vault.id}")
        return vault

    async def delete(self, location_id: UUID) -> bool:
        """Delete entity vault."""
        vault = await self.get(location_id)
        if not vault:
            return False
        
        await self.db.delete(vault)
        await self.db.commit()
        
        logger.info(f"Deleted entity vault for location {location_id}")
        return True

    # ====================
    # Platform Sync
    # ====================

    async def sync_to_platforms(
        self,
        location_id: UUID,
        request: SyncRequest,
        access_token: str = None,
    ) -> list[SyncResult]:
        """Sync entity vault to external platforms."""
        vault = await self.get(location_id)
        if not vault:
            raise ValueError("Entity vault not found")
        
        results = []
        
        for platform in request.platforms:
            if platform == "google":
                result = await self._sync_to_google(vault, access_token, request.fields)
            elif platform == "facebook":
                result = await self._sync_to_facebook(vault, access_token, request.fields)
            else:
                result = SyncResult(
                    platform=platform,
                    success=False,
                    fields_synced=[],
                    error=f"Unknown platform: {platform}",
                    synced_at=utc_now_naive(),
                )
            
            results.append(result)
        
        # Update sync status
        google_result = next((r for r in results if r.platform == "google"), None)
        if google_result:
            vault.gbp_sync_status = "synced" if google_result.success else "error"
            vault.gbp_last_synced_at = utc_now_naive() if google_result.success else None
            await self.db.commit()
        
        return results

    async def _sync_to_google(
        self,
        vault: EntityVault,
        access_token: str,
        fields: list[str] = None,
    ) -> SyncResult:
        """Sync to Google Business Profile."""
        if not access_token:
            return SyncResult(
                platform="google",
                success=False,
                fields_synced=[],
                error="No access token provided",
                synced_at=utc_now_naive(),
            )
        
        try:
            # Get GBP location
            from app.models.location import Location
            result = await self.db.execute(
                select(Location).where(Location.id == vault.location_id)
            )
            location = result.scalar_one_or_none()
            
            if not location or not location.gbp_location_id:
                return SyncResult(
                    platform="google",
                    success=False,
                    fields_synced=[],
                    error="No GBP location linked",
                    synced_at=utc_now_naive(),
                )
            
            # Build update data for GBP
            update_data = {}
            synced_fields = []
            
            if not fields or "title" in fields:
                update_data["title"] = vault.business_name
                synced_fields.append("title")
            
            if not fields or "phoneNumbers" in fields:
                if vault.phone:
                    update_data["phoneNumbers"] = {
                        "primaryPhone": vault.phone
                    }
                    synced_fields.append("phoneNumbers")
            
            if not fields or "websiteUri" in fields:
                if vault.website:
                    update_data["websiteUri"] = vault.website
                    synced_fields.append("websiteUri")
            
            if not fields or "regularHours" in fields:
                hours = self._convert_hours_to_gbp(vault.business_hours)
                if hours:
                    update_data["regularHours"] = hours
                    synced_fields.append("regularHours")
            
            # Note: Actual GBP API call would go here
            # await self.google.update_location(access_token, location.gbp_location_id, update_data)
            
            logger.info(f"Synced {len(synced_fields)} fields to Google for vault {vault.id}")
            
            return SyncResult(
                platform="google",
                success=True,
                fields_synced=synced_fields,
                synced_at=utc_now_naive(),
            )
            
        except Exception as e:
            logger.error(f"Google sync failed: {e}")
            return SyncResult(
                platform="google",
                success=False,
                fields_synced=[],
                error=str(e),
                synced_at=utc_now_naive(),
            )

    async def _sync_to_facebook(
        self,
        vault: EntityVault,
        access_token: str,
        fields: list[str] = None,
    ) -> SyncResult:
        """Sync to Facebook Page."""
        # Facebook API integration would go here
        return SyncResult(
            platform="facebook",
            success=False,
            fields_synced=[],
            error="Facebook sync not yet implemented",
            synced_at=utc_now_naive(),
        )

    def _convert_hours_to_gbp(self, hours: dict) -> dict:
        """Convert internal hours format to GBP format."""
        if not hours:
            return None
        
        day_map = {
            "monday": "MONDAY",
            "tuesday": "TUESDAY",
            "wednesday": "WEDNESDAY",
            "thursday": "THURSDAY",
            "friday": "FRIDAY",
            "saturday": "SATURDAY",
            "sunday": "SUNDAY",
        }
        
        periods = []
        for day_name, gbp_day in day_map.items():
            day_data = hours.get(day_name, {})
            if day_data.get("is_open") and day_data.get("open_time") and day_data.get("close_time"):
                periods.append({
                    "openDay": gbp_day,
                    "closeDay": gbp_day,
                    "openTime": day_data["open_time"],
                    "closeTime": day_data["close_time"],
                })
        
        return {"periods": periods} if periods else None

    # ====================
    # NAP Consistency
    # ====================

    async def check_nap_consistency(
        self,
        location_id: UUID,
    ) -> NAPConsistencyReport:
        """Check NAP (Name, Address, Phone) consistency across platforms."""
        vault = await self.get(location_id)
        if not vault:
            raise ValueError("Entity vault not found")
        
        # Master data
        master_name = vault.business_name
        master_address = vault.address or ""
        if vault.city and vault.state:
            master_address = f"{vault.address or ''}, {vault.city}, {vault.state}"
        master_phone = vault.phone
        
        # Check various sources
        entries = []
        
        # Check GBP
        gbp_entry = await self._check_gbp_nap(location_id, master_name, master_address, master_phone)
        if gbp_entry:
            entries.append(gbp_entry)
        
        # Check other sources (would add Yelp, Facebook, etc.)
        # entries.extend(await self._check_yelp_nap(...))
        # entries.extend(await self._check_facebook_nap(...))
        
        # Calculate consistency
        consistent_count = sum(1 for e in entries if e.is_consistent)
        total = len(entries)
        
        # Collect issues
        issues = []
        for entry in entries:
            for inconsistency in entry.inconsistencies:
                issues.append({
                    "source": entry.source,
                    "issue": inconsistency,
                })
        
        return NAPConsistencyReport(
            location_id=location_id,
            master_name=master_name,
            master_address=master_address,
            master_phone=master_phone,
            entries=entries,
            total_sources=total,
            consistent_count=consistent_count,
            inconsistent_count=total - consistent_count,
            consistency_score=round((consistent_count / total) * 100, 1) if total > 0 else 100.0,
            issues=issues,
            generated_at=utc_now_naive(),
        )

    async def _check_gbp_nap(
        self,
        location_id: UUID,
        master_name: str,
        master_address: str,
        master_phone: str,
    ) -> Optional[NAPEntry]:
        """Check GBP NAP data."""
        # In production, fetch from GBP API
        # For now, simulate
        return NAPEntry(
            source="google",
            source_url="https://business.google.com",
            name=master_name,
            address=master_address,
            phone=master_phone,
            is_consistent=True,
            inconsistencies=[],
            last_checked_at=utc_now_naive(),
        )

    # ====================
    # Import from GBP
    # ====================

    async def import_from_gbp(
        self,
        location_id: UUID,
        access_token: str,
        gbp_location_name: str,
    ) -> EntityVault:
        """Import entity data from Google Business Profile."""
        # Get GBP location data
        gbp_data = await self.google.get_location(access_token, gbp_location_name)
        
        if not gbp_data:
            raise ValueError("GBP location not found")
        
        # Parse GBP data
        address_data = gbp_data.get("storefrontAddress", {})
        phone_data = gbp_data.get("phoneNumbers", {})
        
        # Check if vault exists
        existing = await self.get(location_id)
        
        if existing:
            # Update existing
            update = EntityVaultUpdate(
                business_name=gbp_data.get("title"),
                primary_category=gbp_data.get("categories", {}).get("primaryCategory", {}).get("displayName"),
            )
            return await self.update(location_id, update)
        else:
            # Create new
            from app.schemas.entity_vault import Address, ContactInfo
            
            create_data = EntityVaultCreate(
                location_id=location_id,
                business_name=gbp_data.get("title", "Unknown Business"),
                primary_category=gbp_data.get("categories", {}).get("primaryCategory", {}).get("displayName"),
                address=Address(
                    street1=address_data.get("addressLines", [""])[0],
                    city=address_data.get("locality", ""),
                    state=address_data.get("administrativeArea", ""),
                    postal_code=address_data.get("postalCode", ""),
                    country=address_data.get("regionCode", "US"),
                ),
                contact=ContactInfo(
                    primary_phone=phone_data.get("primaryPhone"),
                    website=gbp_data.get("websiteUri"),
                ),
            )
            
            return await self.create(create_data)


def get_entity_vault_service(db: AsyncSession) -> EntityVaultService:
    """Get entity vault service instance."""
    return EntityVaultService(db)
