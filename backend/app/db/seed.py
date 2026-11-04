import json
import logging
from datetime import datetime, date
from sqlmodel import Session, select
from app.db.session import sync_engine
from app.db.models import User, Wedding, WeddingMember, Venue, Supplier, BudgetLine, Booking
from app.db.seed_data_real import venues, suppliers
from app.utils.constants import extract_eircode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_database():
    with Session(sync_engine) as session:
        try:
            # Check if database is already seeded
            existing_venues = session.exec(select(Venue)).first()
            if existing_venues:
                logger.info("Database already seeded. Skipping.")
                return

            logger.info("Seeding database...")

            # 1. Seed Users
            users_to_seed = [
                User(id="couple_1", role="couple", name="Clara & Sean", email="clara.sean@wedding.ie", phone="+353871234567"),
                User(id="couple_2", role="couple", name="Priya & David", email="priya.david@gmail.com", phone="+353869876543"),
                User(id="planner_1", role="planner", name="Mary-Aoife (Wedding Wonders)", email="maryaoife@weddingwonders.ie", phone="+353855551234"),
            ]
            for u in users_to_seed:
                session.add(u)
            logger.info(f"Added {len(users_to_seed)} users.")

            # 2. Seed Venues
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

            # 3. Seed Suppliers
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

            # 4. Seed pre-made weddings
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
                                      email="clara.sean@wedding.ie", level="owner",
                                      user_id="couple_1"))
            session.add(WeddingMember(id="wm_planning_test", wedding_id="wedding_planning_test",
                                      email="priya.david@gmail.com", level="owner",
                                      user_id="couple_2"))

            # Seed budget lines for the planning wedding
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
                session.add(BudgetLine(id=bl_id, wedding_id=w_id, category=cat, allocated_amount=alloc, spent_amount=0.0))

            # Add a mock booking
            booking = Booking(
                id="booking_photo_test",
                wedding_id="wedding_planning_test",
                supplier_id="sup_dasha_caffrey",
                status="inquired",
                sourced_by_agent_id="supplier_matcher"
            )
            session.add(booking)

            session.commit()
            logger.info("Database seeding completed successfully.")

        except Exception as e:
            session.rollback()
            logger.error(f"Error seeding database: {e}")
            raise e


if __name__ == "__main__":
    seed_database()

