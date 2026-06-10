"""P5: Entity Vault API - Single source of truth for business data."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.routers.deps import get_current_account
from app.models.account import Account
from app.services.entity_vault_service import get_entity_vault_service
from app.services.oauth_service import get_oauth_service
from app.schemas.entity_vault import (
    EntityVaultCreate,
    EntityVaultUpdate,
    SyncRequest,
    SyncResponse,
    NAPConsistencyReport,
    Address,
    ContactInfo,
    BusinessHours,
)

router = APIRouter(prefix="/entity-vault", tags=["Entity Vault"])


# ====================
# CRUD Operations
# ====================

@router.get("/{location_id}")
async def get_entity_vault(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Get entity vault for a location."""
    service = get_entity_vault_service(db)
    vault = await service.get(location_id)
    
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity vault not found for this location",
        )
    
    # Return vault data as dict
    return {
        "id": str(vault.id),
        "location_id": str(vault.location_id),
        "business_name": vault.business_name,
        "tagline": vault.tagline,
        "description": vault.description,
        "primary_category": vault.primary_category,
        "secondary_categories": vault.secondary_categories,
        "address": vault.address,
        "full_address": vault.full_address,
        "city": vault.city,
        "state": vault.state,
        "zip_code": vault.zip_code,
        "coordinates": vault.coordinates,
        "phone": vault.phone,
        "website": vault.website,
        "contact_info": vault.contact_info,
        "business_hours": vault.business_hours,
        "special_hours": vault.special_hours,
        "hours_timezone": vault.hours_timezone,
        "payment_methods": vault.payment_methods,
        "amenities": vault.amenities,
        "service_area": vault.service_area,
        "logo_url": vault.logo_url,
        "cover_photo_url": vault.cover_photo_url,
        "photo_urls": vault.photo_urls,
        "services": vault.services,
        "tone": vault.tone,
        "forbidden_phrases": vault.forbidden_phrases,
        "required_phrases": vault.required_phrases,
        "faq": vault.faq,
        "primary_keywords": vault.primary_keywords,
        "secondary_keywords": vault.secondary_keywords,
        "local_keywords": vault.local_keywords,
        "gbp_sync_status": vault.gbp_sync_status,
        "gbp_last_synced_at": vault.gbp_last_synced_at.isoformat() if vault.gbp_last_synced_at else None,
        "created_at": vault.created_at.isoformat() if vault.created_at else None,
        "updated_at": vault.updated_at.isoformat() if vault.updated_at else None,
    }


@router.post("/{location_id}", status_code=status.HTTP_201_CREATED)
async def create_entity_vault(
    location_id: UUID,
    data: EntityVaultCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Create entity vault for a location."""
    # Verify location ownership
    from app.models.location import Location
    from sqlalchemy import select
    
    result = await db.execute(
        select(Location).where(
            Location.id == location_id,
            Location.account_id == current_user.id,
        )
    )
    location = result.scalar_one_or_none()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    
    service = get_entity_vault_service(db)
    
    try:
        # Override location_id from path
        data.location_id = location_id
        vault = await service.create(data)
        return {"success": True, "vault_id": str(vault.id)}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{location_id}")
async def update_entity_vault(
    location_id: UUID,
    data: EntityVaultUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Update entity vault."""
    service = get_entity_vault_service(db)
    
    try:
        vault = await service.update(location_id, data)
        return {"success": True, "vault_id": str(vault.id)}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{location_id}")
async def delete_entity_vault(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Delete entity vault."""
    service = get_entity_vault_service(db)
    success = await service.delete(location_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity vault not found",
        )
    
    return {"success": True, "message": "Entity vault deleted"}


# ====================
# Individual Field Updates
# ====================

@router.put("/{location_id}/address")
async def update_address(
    location_id: UUID,
    address: Address,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Update business address."""
    service = get_entity_vault_service(db)
    
    try:
        update = EntityVaultUpdate(address=address)
        vault = await service.update(location_id, update)
        return {"success": True, "address": vault.address}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{location_id}/contact")
async def update_contact(
    location_id: UUID,
    contact: ContactInfo,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Update contact information."""
    service = get_entity_vault_service(db)
    
    try:
        update = EntityVaultUpdate(contact=contact)
        vault = await service.update(location_id, update)
        return {"success": True, "contact": vault.contact}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{location_id}/hours")
async def update_hours(
    location_id: UUID,
    hours: BusinessHours,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Update business hours."""
    service = get_entity_vault_service(db)
    
    try:
        update = EntityVaultUpdate(hours=hours)
        vault = await service.update(location_id, update)
        return {"success": True, "hours": vault.hours}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================
# Platform Sync
# ====================

@router.post("/{location_id}/sync", response_model=SyncResponse)
async def sync_to_platforms(
    location_id: UUID,
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Sync entity vault to external platforms."""
    # Get access token for Google
    oauth_service = get_oauth_service(db)
    access_token = await oauth_service.get_valid_access_token(current_user.id, "google")
    
    service = get_entity_vault_service(db)
    
    try:
        results = await service.sync_to_platforms(location_id, request, access_token)
        all_success = all(r.success for r in results)
        
        return SyncResponse(
            location_id=location_id,
            results=results,
            all_success=all_success,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{location_id}/sync/google")
async def sync_to_google(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Quick sync to Google Business Profile."""
    oauth_service = get_oauth_service(db)
    access_token = await oauth_service.get_valid_access_token(current_user.id, "google")
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account not connected. Please connect first.",
        )
    
    service = get_entity_vault_service(db)
    request = SyncRequest(platforms=["google"])
    
    try:
        results = await service.sync_to_platforms(location_id, request, access_token)
        return results[0] if results else {"success": False, "error": "No result"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================
# NAP Consistency
# ====================

@router.get("/{location_id}/nap-check", response_model=NAPConsistencyReport)
async def check_nap_consistency(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Check NAP (Name, Address, Phone) consistency across platforms."""
    service = get_entity_vault_service(db)
    
    try:
        report = await service.check_nap_consistency(location_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================
# Import from External
# ====================

@router.post("/{location_id}/import/google")
async def import_from_google(
    location_id: UUID,
    gbp_location_name: str = Query(..., description="GBP location name, e.g., accounts/123/locations/456"),
    db: AsyncSession = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Import entity data from Google Business Profile."""
    oauth_service = get_oauth_service(db)
    access_token = await oauth_service.get_valid_access_token(current_user.id, "google")
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account not connected. Please connect first.",
        )
    
    service = get_entity_vault_service(db)
    
    try:
        vault = await service.import_from_gbp(location_id, access_token, gbp_location_name)
        return {
            "success": True,
            "message": "Imported from Google Business Profile",
            "vault_id": str(vault.id),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ====================
# Business Hours Status
# ====================

@router.get("/{location_id}/is-open")
async def check_is_open(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check if business is currently open."""
    service = get_entity_vault_service(db)
    vault = await service.get(location_id)
    
    if not vault or not vault.business_hours:
        raise HTTPException(status_code=404, detail="Entity vault or hours not found")
    
    from app.schemas.entity_vault import BusinessHours
    hours = BusinessHours(**vault.business_hours)
    is_open = hours.is_currently_open()
    
    return {
        "is_open": is_open,
        "timezone": vault.hours_timezone or hours.timezone,
    }
