import json
import logging
from datetime import datetime, date
from sqlmodel import Session, select
from app.config import settings
from app.db.session import sync_engine
from app.db.models import User, Wedding, WeddingMember, Venue, Supplier, BudgetLine, Booking
from app.db.seed_data_real import venues, suppliers
from app.utils.constants import extract_eircode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_database():
    """Seed an empty database: the vendor catalogue always, demo data in dev mode only.

    The demo couples and weddings are made up. Anywhere real data lives
    (DEVELOPMENT_MODE off) they are never written, so the wedding's database
    holds only real people (AGENTS.md rule 3, PD-001).
    """
    with Session(sync_engine) as session:
        try:
            # Check if database is already seeded
            existing_venues = session.exec(select(Venue)).first()
            if existing_venues:
                logger.info("Database already seeded. Skipping.")
                return

            logger.info("Seeding vendor catalogue...")
            _seed_catalogue(session)

            if settings.DEVELOPMENT_MODE:
                logger.info("Development mode: seeding demo users and weddings...")
                _seed_demo_data(session)
            else:
                logger.info("Not in development mode: skipping demo users and weddings.")

            session.commit()
            logger.info("Database seeding completed successfully.")

        except Exception as e:
            session.rollback()
            logger.error(f"Error seeding database: {e}")
            raise e


def _seed_catalogue(session: Session):
    venues_seeded = 0
    for v in venues:
        contact = json.loads(v[9]) if isinstance(v[9], str) else v[9]
        pricing = json.loads(v[10]) if isinstance(v[10], str) else v[10]

        venue = Venue(
            id=v[0],
            name=v[1],
            address=v[2],
            region=v[3],
            venue_type=v[4],
            capacity_min=v[5],
            capacity_max=v[6],
            indoor_outdoor=v[7],
            on_site_accommodation=v[8],
            contact_info=contact,
            pricing_summary=pricing,
            eircode=extract_eircode(v[2])
        )
        session.add(venue)
        venues_seeded += 1
    logger.info(f"Added {venues_seeded} venues.")

    suppliers_seeded = 0
    for s in suppliers:
        contact = json.loads(s[4]) if isinstance(s[4], str) else s[4]
        pricing = json.loads(s[5]) if isinstance(s[5], str) else s[5]
        attrs = json.loads(s[6]) if isinstance(s[6], str) else s[6]

        supplier = Supplier(
            id=s[0],
            name=s[1],
            category=s[2],
            location=s[3],
            contact_info=contact,
            pricing_summary=pricing,
            attributes=attrs
        )
        session.add(supplier)
        suppliers_seeded += 1
    logger.info(f"Added {suppliers_seeded} suppliers.")


def _seed_demo_data(session: Session):
    # Fictional demo couples. Emails use the reserved example.com domain and phones
    # stay empty, so no demo row can point at a real person or business.
    users_to_seed = [
        User(id="couple_1", role="couple", name="Clara & Sean", email="clara.sean@example.com"),
        User(id="couple_2", role="couple", name="Priya & David", email="priya.david@example.com"),
    ]
    for u in users_to_seed:
        session.add(u)
    logger.info(f"Added {len(users_to_seed)} demo users.")

    wedding_intake = Wedding(
        id="wedding_intake_test",
        couple_user_id="couple_1",
        status="intake",
        budget_total=30000.0,
        currency="EUR",
        region="Sligo",
        ceremony_type="Civil/Humanist",
        guest_count_estimate=100
    )
    session.add(wedding_intake)

    wedding_planning = Wedding(
        id="wedding_planning_test",
        couple_user_id="couple_2",
        status="planning",
        budget_total=45000.0,
        currency="EUR",
        region="Dublin",
        ceremony_type="Irish Catholic",
        guest_count_estimate=150,
        wedding_date=date(2026, 8, 15)
    )
    session.add(wedding_planning)
    # Demo couples own their demo weddings on the access list (PD-002).
    session.add(WeddingMember(id="wm_intake_test", wedding_id="wedding_intake_test",
                              email="clara.sean@example.com", level="owner",
                              user_id="couple_1"))
    session.add(WeddingMember(id="wm_planning_test", wedding_id="wedding_planning_test",
                              email="priya.david@example.com", level="owner",
                              user_id="couple_2"))

    premade_budget = [
        ("bl_venue", "wedding_planning_test", "venue", 15000.0),
        ("bl_catering", "wedding_planning_test", "catering", 12000.0),
        ("bl_photo", "wedding_planning_test", "photography", 4000.0),
        ("bl_florist", "wedding_planning_test", "florals", 3000.0),
        ("bl_music", "wedding_planning_test", "music", 2500.0),
        ("bl_officiant", "wedding_planning_test", "officiant", 600.0),
        ("bl_other", "wedding_planning_test", "other", 7900.0)
    ]
    for bl_id, w_id, cat, alloc in premade_budget:
        session.add(BudgetLine(id=bl_id, wedding_id=w_id, category=cat,
                               allocated_amount=alloc, spent_amount=0.0))

    booking = Booking(
        id="booking_photo_test",
        wedding_id="wedding_planning_test",
        supplier_id="sup_dasha_caffrey",
        status="inquired",
        sourced_by_agent_id="supplier_matcher"
    )
    session.add(booking)


if __name__ == "__main__":
    seed_database()
