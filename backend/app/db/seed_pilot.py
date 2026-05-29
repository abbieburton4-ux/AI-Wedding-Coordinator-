"""
VenueFlow — Pilot-state seed script
===================================
Brings a fresh database to the exact state we want for a local pilot demo:

  1. The 3 pilot planner accounts (idempotent upsert).
  2. A printed block of static + signed-JWT bearer tokens for each planner so we
     can paste them straight into the local frontend (localStorage key
     ``vf_planner_token`` — see frontend/src/app/api/useApi.ts).
  3. The baseline catalog of venues + suppliers (plus the demo couples and two
     example weddings) so the Matcher Agents have real rows to retrieve from
     without hitting any external web search.

Run it standalone after migrations:

    alembic upgrade head
    python -m app.db.seed_pilot

It is safe to run repeatedly — venues/suppliers are seeded by the idempotent
``seed_database()`` (skips if already populated) and the planners are upserted.

NOTE on planner identities: per the no-fabricated-PII policy in
``seed_data_real.py`` we do NOT invent real people. planner_1 mirrors the
existing demo planner; planner_2 / planner_3 are clearly-labelled placeholders
on the @venueflow.ie domain. Swap in real pilot contacts when they're confirmed.
"""

import datetime
import logging

import jwt
from sqlmodel import Session, select

from app.config import settings
from app.db.session import sync_engine
from app.db.models import User, Venue, Supplier, Wedding
from app.db.seed import seed_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The 3 pilot planners. Stable ids so their tokens stay valid across re-seeds.
PILOT_PLANNERS = [
    {
        "id": "planner_1",
        "name": "Mary-Aoife (Wedding Wonders)",
        "email": "maryaoife@weddingwonders.ie",
        "phone": "+353855551234",
    },
    {
        "id": "planner_2",
        "name": "Pilot Planner Two",
        "email": "planner2@venueflow.ie",
        "phone": "+353870000002",
    },
    {
        "id": "planner_3",
        "name": "Pilot Planner Three",
        "email": "planner3@venueflow.ie",
        "phone": "+353870000003",
    },
]


def _make_jwt(user: User) -> str:
    """Mint a 30-day HS256 bearer token validated by app.api...auth.get_current_user."""
    secret = getattr(settings, "JWT_SECRET", None) or "dev-jwt-secret-key-change-me-in-production"
    return jwt.encode(
        {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "name": user.name,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30),
        },
        secret,
        algorithm="HS256",
    )


def upsert_pilot_planners(session: Session) -> list[User]:
    """Insert or refresh the 3 pilot planner accounts. Returns the User rows."""
    planners: list[User] = []
    for p in PILOT_PLANNERS:
        user = session.get(User, p["id"])
        if user:
            # Keep details in sync without disturbing created_at.
            user.role = "planner"
            user.name = p["name"]
            user.email = p["email"]
            user.phone = p["phone"]
        else:
            user = User(id=p["id"], role="planner", name=p["name"], email=p["email"], phone=p["phone"])
            session.add(user)
        planners.append(user)
    session.commit()
    for u in planners:
        session.refresh(u)
    return planners


def print_planner_tokens(planners: list[User]) -> None:
    """Print copy-paste-ready bearer tokens for each pilot planner."""
    bar = "=" * 78
    print("\n" + bar)
    print(" PILOT PLANNER ACCESS TOKENS")
    print(" Frontend stores the token at localStorage['vf_planner_token'].")
    print(" In the browser console on the running app, paste the snippet below.")
    print(bar)
    for u in planners:
        # Static token works because ALLOW_MOCK_AUTH validates the 'mock-' prefix
        # via direct DB lookup (app.api.v1.endpoints.auth.get_current_user, path 1).
        static_token = f"mock-{u.id}"
        # Signed JWT works via the HS256 path (path 2) — survives ALLOW_MOCK_AUTH=False.
        jwt_token = _make_jwt(u)
        print(f"\n# {u.name}  <{u.email}>  (id={u.id}, role={u.role})")
        print(f"  static : {static_token}")
        print(f"  jwt    : {jwt_token}")
        print(f"  paste  : localStorage.setItem('vf_planner_token', '{static_token}')")
    print("\n" + bar)
    print(" Authorization header for direct API calls:  Authorization: Bearer <token>")
    print(bar + "\n")


def seed_pilot() -> None:
    logger.info("Seeding pilot state (planners + catalog + demo weddings)...")

    # 1. Base catalog + demo couples/weddings (idempotent — skips if venues exist).
    seed_database()

    # 2. Pilot planners (upserted) + their tokens.
    with Session(sync_engine) as session:
        planners = upsert_pilot_planners(session)

        # Give planner_1 a managed wedding so the planner dashboard isn't empty —
        # planners only see weddings where planner_user_id == their id. The
        # 'planning' demo wedding already has budget lines + a booking, so it
        # renders a populated planner view. Idempotent: only sets if unassigned.
        demo_wedding = session.get(Wedding, "wedding_planning_test")
        if demo_wedding and not demo_wedding.planner_user_id:
            demo_wedding.planner_user_id = "planner_1"
            session.add(demo_wedding)
            session.commit()
            logger.info("Assigned wedding_planning_test to planner_1 for the planner demo.")

        venue_count = len(session.exec(select(Venue)).all())
        supplier_count = len(session.exec(select(Supplier)).all())

    logger.info(
        "Pilot seed complete: %d planners, %d venues, %d suppliers available to the Matcher Agents.",
        len(planners), venue_count, supplier_count,
    )
    print_planner_tokens(planners)


if __name__ == "__main__":
    seed_pilot()
