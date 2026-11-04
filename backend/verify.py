import os
import sys

# Override configuration variables to use local SQLite for verification
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./verify_test.db"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///./verify_test.db"
os.environ["DEVELOPMENT_MODE"] = "True"
os.environ["ALLOW_MOCK_AUTH"] = "True"

# Add current folder to path
sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from sqlmodel import SQLModel, Session, select
from app.db.session import sync_engine
from app.db.models import Venue, Supplier, User, Wedding, Booking, WeddingMember, BudgetLine
from app.db.seed import seed_database

def run_verification():
    print("--- STARTING BACKEND SCHEMA & SEED VERIFICATION ---")
    
    # 1. Initialize schemas
    print("1. Creating database tables in SQLite...")
    SQLModel.metadata.create_all(sync_engine)
    print("   Schemas created successfully (no SQL syntax/constraint errors).")
    
    # 2. Run seed logic
    print("2. Running database seed parser...")
    seed_database()
    
    # 3. Query seeded tables to verify integrity
    print("3. Querying database tables...")
    with Session(sync_engine) as session:
        # Check users
        users = session.exec(select(User)).all()
        print(f"   * Users seeded: {len(users)}")
        assert len(users) == 2, f"Expected 2 users, got {len(users)}"  # demo planner removed (PD-003)
        
        # Check venues
        venues = session.exec(select(Venue)).all()
        print(f"   * Venues seeded: {len(venues)}")
        assert len(venues) > 0, "No venues seeded"
        
        # Check suppliers
        suppliers = session.exec(select(Supplier)).all()
        print(f"   * Suppliers seeded: {len(suppliers)}")
        assert len(suppliers) > 0, "No suppliers seeded"
        
        # Check weddings
        weddings = session.exec(select(Wedding)).all()
        print(f"   * Weddings seeded: {len(weddings)}")
        assert len(weddings) == 2, f"Expected 2 weddings, got {len(weddings)}"
        
        # Check bookings
        bookings = session.exec(select(Booking)).all()
        print(f"   * Bookings seeded: {len(bookings)}")
        assert len(bookings) == 1, f"Expected 1 booking, got {len(bookings)}"

    # 4. Outside dev mode, an empty database gets the catalogue but no demo data (B26)
    print("4. Seeding an empty database outside development mode...")
    from app.config import settings
    SQLModel.metadata.drop_all(sync_engine)
    SQLModel.metadata.create_all(sync_engine)
    settings.DEVELOPMENT_MODE = False
    try:
        seed_database()
    finally:
        settings.DEVELOPMENT_MODE = True
    with Session(sync_engine) as session:
        assert session.exec(select(Venue)).first() is not None, "Catalogue venues not seeded"
        assert session.exec(select(Supplier)).first() is not None, "Catalogue suppliers not seeded"
        assert session.exec(select(User)).all() == [], "Demo users seeded outside dev mode"
        assert session.exec(select(Wedding)).all() == [], "Demo weddings seeded outside dev mode"
        assert session.exec(select(Booking)).all() == [], "Demo bookings seeded outside dev mode"
        assert session.exec(select(WeddingMember)).all() == [], "Demo access rows seeded"
        assert session.exec(select(BudgetLine)).all() == [], "Demo budget lines seeded"
        print("   * Catalogue seeded; no demo users, weddings, access rows, budgets or bookings")

    print("\n--- VERIFICATION SUCCESS: ALL SCHEMA AND DATA TESTS PASSED ---")

    # Clean up database file after run
    if os.path.exists("./verify_test.db"):
        os.remove("./verify_test.db")
        print("   Temporary database file cleaned up.")

if __name__ == "__main__":
    run_verification()
