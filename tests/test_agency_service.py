from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.analytics import Analytics
from app.models.location import Location
from app.services.agency import AgencyService, TeamRole


def _second_location(db: Session, test_user: Account) -> Location:
    location = Location(
        id=uuid4(),
        account_id=test_user.id,
        name="Second Business",
        address="456 Test Ave",
        city="Test City",
        state="TS",
        country="US",
        phone="555-2222",
        services=["service"],
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


async def test_agency_dashboard_uses_column_analytics(
    db: Session,
    test_user: Account,
    test_location: Location,
) -> None:
    second_location = _second_location(db, test_user)
    today = date.today()
    db.add_all(
        [
            Analytics(
                location_id=test_location.id,
                platform="GBP",
                date=today,
                calls=7,
                direction_requests=3,
                impressions=100,
                source_raw={"new_reviews": 2},
            ),
            Analytics(
                location_id=second_location.id,
                platform="GBP",
                date=today,
                calls=4,
                direction_requests=1,
                impressions=50,
                source_raw={"new_reviews": 1},
            ),
        ]
    )
    db.commit()

    dashboard = await AgencyService(db).get_agency_dashboard(test_user.id)

    assert dashboard["total_locations"] == 2
    assert dashboard["aggregate_metrics"] == {
        "calls_7d": 11,
        "directions_7d": 4,
        "impressions_7d": 150,
        "new_reviews_7d": 3,
    }
    assert dashboard["locations"][0]["id"] == str(test_location.id)
    assert dashboard["locations"][0]["calls_7d"] == 7
    assert dashboard["locations"][1]["directions_7d"] == 1


async def test_agency_location_comparison_uses_column_analytics(
    db: Session,
    test_user: Account,
    test_location: Location,
) -> None:
    second_location = _second_location(db, test_user)
    today = date.today()
    db.add_all(
        [
            Analytics(
                location_id=test_location.id,
                platform="GBP",
                date=today,
                calls=3,
                direction_requests=9,
            ),
            Analytics(
                location_id=second_location.id,
                platform="GBP",
                date=today,
                calls=8,
                direction_requests=1,
            ),
        ]
    )
    db.commit()

    comparison = await AgencyService(db).get_location_comparison(
        test_user.id,
        metric="directions",
        days=30,
    )

    assert [item["rank"] for item in comparison] == [1, 2]
    assert comparison[0]["location_id"] == str(test_location.id)
    assert comparison[0]["value"] == 9
    assert comparison[1]["value"] == 1


async def test_agency_json_settings_updates_persist_after_refresh(
    db: Session,
    test_user: Account,
) -> None:
    test_user.settings = {
        "white_label": {"brand_name": "Old Brand"},
        "team_members": [{"email": "editor@example.com", "role": "viewer", "status": "active"}],
    }
    db.add(test_user)
    db.commit()

    service = AgencyService(db)
    await service.update_white_label_settings(
        test_user.id,
        {"brand_name": "New Brand", "primary_color": "#123456"},
    )
    await service.update_team_member_role(test_user.id, "editor@example.com", TeamRole.MANAGER)

    db.expire_all()
    reloaded = db.query(Account).filter(Account.id == test_user.id).one()

    assert reloaded.settings["white_label"]["brand_name"] == "New Brand"
    assert reloaded.settings["white_label"]["primary_color"] == "#123456"
    assert reloaded.settings["team_members"][0]["role"] == "manager"


async def test_remove_missing_team_member_reports_failure(
    db: Session,
    test_user: Account,
) -> None:
    test_user.settings = {"team_members": [{"email": "member@example.com", "role": "viewer"}]}
    db.add(test_user)
    db.commit()

    result = await AgencyService(db).remove_team_member(test_user.id, "missing@example.com")

    assert result == {"success": False, "error": "Team member not found"}
