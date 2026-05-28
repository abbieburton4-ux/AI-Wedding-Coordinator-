from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON, Text, Date, Time, CheckConstraint
from typing import Optional, List, Dict, Any
import datetime
import uuid

def generate_uuid_str() -> str:
    return str(uuid.uuid4())

def utcnow() -> datetime.datetime:
    """Naive UTC timestamp. Matches the naive DateTime columns and replaces the
    deprecated datetime.datetime.utcnow()."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: str = Field(primary_key=True, description="Firebase authentication UID")
    role: str = Field(description="Role: couple, planner, admin")
    name: str
    email: str = Field(index=True)
    phone: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    weddings_owned: List["Wedding"] = Relationship(
        back_populates="couple_user",
        sa_relationship_kwargs={"foreign_keys": "[Wedding.couple_user_id]"}
    )
    weddings_managed: List["Wedding"] = Relationship(
        back_populates="planner_user",
        sa_relationship_kwargs={"foreign_keys": "[Wedding.planner_user_id]"}
    )


class Wedding(SQLModel, table=True):
    __tablename__ = "weddings"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    couple_user_id: str = Field(foreign_key="users.id")
    planner_user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    venue_id: Optional[str] = Field(default=None, foreign_key="venues.id")
    
    wedding_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date))
    wedding_date_start: Optional[datetime.date] = Field(default=None, sa_column=Column(Date))
    wedding_date_end: Optional[datetime.date] = Field(default=None, sa_column=Column(Date))
    
    region: str
    ceremony_type: str
    guest_count_estimate: int
    budget_total: float
    currency: str = Field(default="EUR")
    style_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: str = Field(default="intake")  # intake, planning, booked, completed, cancelled
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    couple_user: User = Relationship(
        back_populates="weddings_owned",
        sa_relationship_kwargs={"foreign_keys": "[Wedding.couple_user_id]"}
    )
    planner_user: Optional[User] = Relationship(
        back_populates="weddings_managed",
        sa_relationship_kwargs={"foreign_keys": "[Wedding.planner_user_id]"}
    )
    venue: Optional["Venue"] = Relationship(back_populates="weddings")
    
    budget_lines: List["BudgetLine"] = Relationship(
        back_populates="wedding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    timeline_items: List["TimelineItem"] = Relationship(
        back_populates="wedding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    bookings: List["Booking"] = Relationship(
        back_populates="wedding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    guests: List["Guest"] = Relationship(
        back_populates="wedding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    payments: List["Payment"] = Relationship(
        back_populates="wedding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    decision_logs: List["AgentDecisionLog"] = Relationship(
        back_populates="wedding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Venue(SQLModel, table=True):
    __tablename__ = "venues"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    name: str
    address: str
    region: str
    venue_type: str
    capacity_min: Optional[int] = None
    capacity_max: Optional[int] = None
    indoor_outdoor: int = Field(default=1)  # 1=both, 2=indoor-only, 3=outdoor-only (matches seed data)
    on_site_accommodation: int = Field(default=0)  # 0=No, 1=Yes (matches seed data)
    contact_info: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    pricing_summary: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    eircode: Optional[str] = None
    source: str = Field(default="manual")
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    weddings: List[Wedding] = Relationship(back_populates="venue")
    availabilities: List["VenueAvailability"] = Relationship(
        back_populates="venue",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    bookings: List["Booking"] = Relationship(back_populates="venue")


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    name: str
    category: str
    location: str
    contact_info: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    pricing_summary: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    attributes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    source: str = Field(default="manual")
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    availabilities: List["SupplierAvailability"] = Relationship(
        back_populates="supplier",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    bookings: List["Booking"] = Relationship(back_populates="supplier")


class VenueAvailability(SQLModel, table=True):
    __tablename__ = "venue_availabilities"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    venue_id: str = Field(foreign_key="venues.id")
    date: datetime.date = Field(sa_column=Column(Date))
    start_time: Optional[datetime.time] = Field(default=None, sa_column=Column(Time))
    end_time: Optional[datetime.time] = Field(default=None, sa_column=Column(Time))
    source: str = Field(default="manual")
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    venue: Venue = Relationship(back_populates="availabilities")


class SupplierAvailability(SQLModel, table=True):
    __tablename__ = "supplier_availabilities"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    supplier_id: str = Field(foreign_key="suppliers.id")
    date: datetime.date = Field(sa_column=Column(Date))
    start_time: Optional[datetime.time] = Field(default=None, sa_column=Column(Time))
    end_time: Optional[datetime.time] = Field(default=None, sa_column=Column(Time))
    source: str = Field(default="manual")
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    supplier: Supplier = Relationship(back_populates="availabilities")


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "(venue_id IS NULL) <> (supplier_id IS NULL)",
            name="chk_booking_polymorphic"
        ),
    )

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    wedding_id: str = Field(foreign_key="weddings.id")
    venue_id: Optional[str] = Field(default=None, foreign_key="venues.id")
    supplier_id: Optional[str] = Field(default=None, foreign_key="suppliers.id")
    status: str = Field(default="shortlisted")  # shortlisted, inquired, quoted, booked, declined, cancelled
    sourced_by_agent_id: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    wedding: Wedding = Relationship(back_populates="bookings")
    venue: Optional[Venue] = Relationship(back_populates="bookings")
    supplier: Optional[Supplier] = Relationship(back_populates="bookings")
    
    quotes: List["Quote"] = Relationship(
        back_populates="booking",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    contract: Optional["Contract"] = Relationship(
        back_populates="booking",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False}
    )
    payments: List["SupplierPayment"] = Relationship(
        back_populates="booking",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    decision_logs: List["AgentDecisionLog"] = Relationship(back_populates="booking")


class Quote(SQLModel, table=True):
    __tablename__ = "quotes"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    booking_id: str = Field(foreign_key="bookings.id")
    line_items: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    total_amount: float
    currency: str = Field(default="EUR")
    status: str = Field(default="pending")  # pending, accepted, declined, expired
    generated_by_agent_id: Optional[str] = None
    rationale_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    expires_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    booking: Booking = Relationship(back_populates="quotes")


class Contract(SQLModel, table=True):
    __tablename__ = "contracts"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    booking_id: str = Field(foreign_key="bookings.id")
    contract_pdf_url: str
    signed_by: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    terms_snapshot: Optional[str] = Field(default=None, sa_column=Column(Text))
    risk_flags: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    reviewed_by_agent_id: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    booking: Booking = Relationship(back_populates="contract")


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    payer_user_id: str = Field(foreign_key="users.id")
    wedding_id: str = Field(foreign_key="weddings.id")
    amount: float
    currency: str = Field(default="EUR")
    stripe_payment_id: str
    status: str
    payment_type: str = Field(default="coordinator_fee")  # coordinator_fee, planner_setup
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    wedding: Wedding = Relationship(back_populates="payments")


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    user_id: str = Field(foreign_key="users.id")
    plan: str
    amount: float
    currency: str = Field(default="EUR")
    stripe_subscription_id: str
    status: str
    started_at: datetime.datetime
    created_at: datetime.datetime = Field(default_factory=utcnow)


class SupplierPayment(SQLModel, table=True):
    __tablename__ = "supplier_payments"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    booking_id: str = Field(foreign_key="bookings.id")
    amount: float
    currency: str = Field(default="EUR")
    kind: str  # deposit, balance, additional
    external_reference: Optional[str] = None
    paid_on: datetime.date = Field(sa_column=Column(Date))
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    booking: Booking = Relationship(back_populates="payments")


class BudgetLine(SQLModel, table=True):
    __tablename__ = "budget_lines"

    id: str = Field(primary_key=True, description="Prefix: bl_")
    wedding_id: str = Field(foreign_key="weddings.id")
    category: str
    allocated_amount: float
    spent_amount: float = Field(default=0.0)
    created_at: datetime.datetime = Field(default_factory=utcnow)
    updated_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    wedding: Wedding = Relationship(back_populates="budget_lines")


class TimelineItem(SQLModel, table=True):
    __tablename__ = "timeline_items"

    id: str = Field(primary_key=True, description="Prefix: ti_")
    wedding_id: str = Field(foreign_key="weddings.id")
    kind: str  # planning, day_of
    title: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    due_at: datetime.date = Field(sa_column=Column(Date))
    status: str = Field(default="todo")  # todo, in_progress, done
    generated_by_agent_id: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    wedding: Wedding = Relationship(back_populates="timeline_items")


class Guest(SQLModel, table=True):
    __tablename__ = "guests"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    wedding_id: str = Field(foreign_key="weddings.id")
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    rsvp_status: str = Field(default="invited")  # invited, attending, declined
    dietary: Optional[str] = Field(default=None, sa_column=Column(Text))
    plus_one: bool = Field(default=False)
    table_number: Optional[int] = None
    created_at: datetime.datetime = Field(default_factory=utcnow)

    # Relationships
    wedding: Wedding = Relationship(back_populates="guests")


class AgentDecisionLog(SQLModel, table=True):
    __tablename__ = "agent_decision_logs"

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    agent_id: str
    model_id: Optional[str] = None
    prompt_version: Optional[str] = None
    wedding_id: str = Field(foreign_key="weddings.id")
    user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    booking_id: Optional[str] = Field(default=None, foreign_key="bookings.id")
    parent_decision_id: Optional[str] = Field(default=None, foreign_key="agent_decision_logs.id")
    trigger: str
    timestamp: datetime.datetime = Field(default_factory=utcnow)
    decision_type: str
    status: str  # success, error, blocked_by_guardrail, overridden
    error_kind: Optional[str] = None
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    rationale_summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    input_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    confidence_score: Optional[float] = None
    latency_ms: Optional[int] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    external_api_calls: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    follow_up_actions: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    overridden_by_user_id: Optional[str] = None

    # Relationships
    wedding: Wedding = Relationship(back_populates="decision_logs")
    booking: Optional[Booking] = Relationship(back_populates="decision_logs")
    parent_decision: Optional["AgentDecisionLog"] = Relationship(
        sa_relationship_kwargs={"remote_side": "AgentDecisionLog.id"}
    )
