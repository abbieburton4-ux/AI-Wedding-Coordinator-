import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "venueflow_mock.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys and WAL mode
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(force=False):
    """Initializes the SQLite database with schemas and seeds mock data if forced or empty."""
    db_exists = os.path.exists(DB_PATH)
    if db_exists and not force:
        return True

    conn = get_connection()
    cursor = conn.cursor()

    # Drop tables in reverse order of dependencies
    cursor.execute("DROP TABLE IF EXISTS agent_decision_logs;")
    cursor.execute("DROP TABLE IF EXISTS timeline_items;")
    cursor.execute("DROP TABLE IF EXISTS budget_lines;")
    cursor.execute("DROP TABLE IF EXISTS supplier_payments;")
    cursor.execute("DROP TABLE IF EXISTS contracts;")
    cursor.execute("DROP TABLE IF EXISTS quotes;")
    cursor.execute("DROP TABLE IF EXISTS bookings;")
    cursor.execute("DROP TABLE IF EXISTS supplier_availability;")
    cursor.execute("DROP TABLE IF EXISTS venue_availability;")
    cursor.execute("DROP TABLE IF EXISTS payments;")
    cursor.execute("DROP TABLE IF EXISTS subscriptions;")
    cursor.execute("DROP TABLE IF EXISTS suppliers;")
    cursor.execute("DROP TABLE IF EXISTS venues;")
    cursor.execute("DROP TABLE IF EXISTS weddings;")
    cursor.execute("DROP TABLE IF EXISTS users;")

    # 1. USERS
    cursor.execute("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. WEDDINGS
    cursor.execute("""
        CREATE TABLE weddings (
            id TEXT PRIMARY KEY,
            couple_user_id TEXT NOT NULL,
            planner_user_id TEXT,
            venue_id TEXT,
            wedding_date TEXT,
            wedding_date_start TEXT,
            wedding_date_end TEXT,
            region TEXT,
            ceremony_type TEXT,
            guest_count_estimate INTEGER,
            budget_total REAL NOT NULL,
            currency TEXT DEFAULT 'EUR',
            style_notes TEXT,
            status TEXT NOT NULL, -- 'intake', 'planning', 'booked', 'completed', 'cancelled'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            idempotency_key TEXT UNIQUE,
            FOREIGN KEY (couple_user_id) REFERENCES users(id),
            FOREIGN KEY (planner_user_id) REFERENCES users(id),
            FOREIGN KEY (venue_id) REFERENCES venues(id)
        );
    """)

    # 2A. PAYMENTS (VenueFlow revenue)
    cursor.execute("""
        CREATE TABLE payments (
            id TEXT PRIMARY KEY,
            payer_user_id TEXT NOT NULL,
            wedding_id TEXT,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'EUR',
            stripe_payment_id TEXT,
            status TEXT NOT NULL,
            payment_type TEXT NOT NULL, -- 'coordinator_fee', 'planner_setup', 'other'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (payer_user_id) REFERENCES users(id),
            FOREIGN KEY (wedding_id) REFERENCES weddings(id)
        );
    """)

    # 2B. SUBSCRIPTIONS (B2B planners)
    cursor.execute("""
        CREATE TABLE subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan TEXT NOT NULL, -- 'starter', 'growth', 'enterprise'
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'EUR',
            stripe_subscription_id TEXT,
            status TEXT NOT NULL,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    # 3. VENUES
    cursor.execute("""
        CREATE TABLE venues (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            region TEXT NOT NULL, -- e.g. 'Dublin', 'Galway', 'Sligo', 'Kerry'
            venue_type TEXT NOT NULL, -- 'country_house', 'hotel', 'community_hall', 'gaa_clubhouse', 'church', 'farm', 'restaurant', 'other'
            capacity_min INTEGER,
            capacity_max INTEGER,
            indoor_outdoor INTEGER DEFAULT 1, -- 1=both, 2=indoor-only, 3=outdoor-only
            on_site_accommodation INTEGER DEFAULT 0, -- 0=No, 1=Yes
            contact_info TEXT, -- JSON
            pricing_summary TEXT, -- JSON
            eircode TEXT, -- derived from address; geocoding key for Google Maps (null for NI/unknown)
            source TEXT DEFAULT 'scraped',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3A. VENUE_AVAILABILITY
    cursor.execute("""
        CREATE TABLE venue_availability (
            id TEXT PRIMARY KEY,
            venue_id TEXT NOT NULL,
            date TEXT NOT NULL, -- YYYY-MM-DD
            start_time TEXT,
            end_time TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (venue_id) REFERENCES venues(id)
        );
    """)

    # 4. SUPPLIERS
    cursor.execute("""
        CREATE TABLE suppliers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL, -- 'catering', 'florals', 'photography', 'videography', 'music', 'dj', 'officiant', 'stationery', 'hair_makeup', 'transport', 'cake', 'other'
            location TEXT NOT NULL,
            contact_info TEXT, -- JSON
            pricing_summary TEXT, -- JSON
            attributes TEXT, -- JSON (styles, tags)
            source TEXT DEFAULT 'scraped',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 4A. SUPPLIER_AVAILABILITY
    cursor.execute("""
        CREATE TABLE supplier_availability (
            id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            date TEXT NOT NULL, -- YYYY-MM-DD
            start_time TEXT,
            end_time TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
    """)

    # 5. BOOKINGS (Polymorphic: either venue_id or supplier_id)
    cursor.execute("""
        CREATE TABLE bookings (
            id TEXT PRIMARY KEY,
            wedding_id TEXT NOT NULL,
            venue_id TEXT,
            supplier_id TEXT,
            status TEXT NOT NULL, -- 'shortlisted', 'inquired', 'quoted', 'booked', 'declined', 'cancelled', 'unresponsive'
            sourced_by_agent_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (wedding_id) REFERENCES weddings(id),
            FOREIGN KEY (venue_id) REFERENCES venues(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            CHECK (
                (venue_id IS NOT NULL AND supplier_id IS NULL) OR
                (venue_id IS NULL AND supplier_id IS NOT NULL)
            )
        );
    """)

    # 6. QUOTES
    cursor.execute("""
        CREATE TABLE quotes (
            id TEXT PRIMARY KEY,
            booking_id TEXT NOT NULL,
            line_items TEXT, -- JSON list of items
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'EUR',
            status TEXT NOT NULL, -- 'pending', 'accepted', 'declined', 'expired'
            generated_by_agent_id TEXT,
            rationale_text TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        );
    """)

    # 7. CONTRACTS
    cursor.execute("""
        CREATE TABLE contracts (
            id TEXT PRIMARY KEY,
            booking_id TEXT NOT NULL,
            contract_pdf_url TEXT,
            signed_by TEXT, -- JSON array of signatures
            terms_snapshot TEXT,
            risk_flags TEXT, -- JSON list of risk items [{clause, severity, note, suggested_action}]
            reviewed_by_agent_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        );
    """)

    # 8. SUPPLIER PAYMENTS (Direct tracking only)
    cursor.execute("""
        CREATE TABLE supplier_payments (
            id TEXT PRIMARY KEY,
            booking_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'EUR',
            kind TEXT NOT NULL, -- 'deposit', 'balance', 'additional'
            external_reference TEXT, -- Receipt ID / bank ref
            paid_on TEXT, -- YYYY-MM-DD
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        );
    """)

    # 9. BUDGET LINES
    cursor.execute("""
        CREATE TABLE budget_lines (
            id TEXT PRIMARY KEY,
            wedding_id TEXT NOT NULL,
            category TEXT NOT NULL, -- 'venue', 'catering', 'florals', 'photography', 'videography', 'music', 'dj', 'officiant', 'stationery', 'hair_makeup', 'transport', 'cake', 'other'
            allocated_amount REAL NOT NULL,
            spent_amount REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (wedding_id) REFERENCES weddings(id)
        );
    """)

    # 10. TIMELINE ITEMS
    cursor.execute("""
        CREATE TABLE timeline_items (
            id TEXT PRIMARY KEY,
            wedding_id TEXT NOT NULL,
            kind TEXT NOT NULL, -- 'planning', 'day_of'
            title TEXT NOT NULL,
            description TEXT,
            due_at TEXT, -- ISO Date/DateTime
            status TEXT NOT NULL, -- 'todo', 'in_progress', 'completed'
            generated_by_agent_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (wedding_id) REFERENCES weddings(id)
        );
    """)

    # 11. AGENT DECISION LOGS (Submission Critical)
    cursor.execute("""
        CREATE TABLE agent_decision_logs (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            model_id TEXT,
            prompt_version TEXT,
            wedding_id TEXT,
            user_id TEXT,
            booking_id TEXT,
            parent_decision_id TEXT,
            trigger TEXT NOT NULL, -- 'couple_action', 'planner_action', 'supplier_response', 'scheduled', 'parent_decision', 'agent_initiated'
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            decision_type TEXT NOT NULL, -- 'intake_validation', 'timeline_generate', 'venue_match', 'supplier_match', 'inquiry_draft', 'quote_draft', 'budget_alert' etc.
            status TEXT NOT NULL, -- 'success', 'error', 'blocked_by_guardrail', 'overridden'
            error_kind TEXT,
            error_message TEXT,
            rationale_summary TEXT,
            input_payload TEXT, -- JSON
            output_payload TEXT, -- JSON
            confidence_score REAL,
            latency_ms INTEGER,
            tokens_input INTEGER,
            tokens_output INTEGER,
            external_api_calls TEXT, -- JSON array
            follow_up_actions TEXT, -- JSON array
            overridden_by_user_id TEXT,
            FOREIGN KEY (wedding_id) REFERENCES weddings(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        );
    """)

    # Seed initial data
    seed_data(cursor)

    conn.commit()
    conn.close()
    return True

def seed_data(cursor):
    # 1. Users
    users = [
        ("couple_1", "couple", "Clara & Sean", "clara.sean@wedding.ie", "+353871234567"),
        ("couple_2", "couple", "Priya & David", "priya.david@gmail.com", "+353869876543"),
        ("planner_1", "planner", "Mary-Aoife (Wedding Wonders)", "maryaoife@weddingwonders.ie", "+353855551234"),
    ]
    cursor.executemany("INSERT INTO users (id, role, name, email, phone) VALUES (?, ?, ?, ?, ?)", users)

    # 2 & 3. Venues + Suppliers — real Irish seed data (25 venues, 22 suppliers).
    # Drop-in lists from seed_data_real.py; same tuple arity as the schema.
    # Contacts ship verified-or-null (see seed_data_real docstring) and the pilot
    # contactability guard (agents.resolve_inquiry_recipient) ensures no real
    # venue is emailed by the system before opting in.
    from seed_data_real import venues, suppliers
    from constants import extract_eircode
    # Derive the eircode geocoding key from each venue's address (col index 2).
    # Address stays the single source of truth; eircode is appended as the
    # final column so the seed tuples don't need an extra field maintained.
    venues_with_eircode = [tuple(v) + (extract_eircode(v[2]),) for v in venues]
    cursor.executemany("INSERT INTO venues (id, name, address, region, venue_type, capacity_min, capacity_max, indoor_outdoor, on_site_accommodation, contact_info, pricing_summary, eircode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", venues_with_eircode)
    cursor.executemany("INSERT INTO suppliers (id, name, category, location, contact_info, pricing_summary, attributes) VALUES (?, ?, ?, ?, ?, ?, ?)", suppliers)

    # 4. A Pre-made Wedding in intake stage
    cursor.execute("""
        INSERT INTO weddings (id, couple_user_id, status, budget_total, currency, region, ceremony_type, guest_count_estimate)
        VALUES ('wedding_intake_test', 'couple_1', 'intake', 30000.0, 'EUR', 'Sligo', 'Civil/Humanist', 100);
    """)

    # 5. A Pre-made Wedding in planning stage
    cursor.execute("""
        INSERT INTO weddings (id, couple_user_id, status, budget_total, currency, region, ceremony_type, guest_count_estimate, wedding_date)
        VALUES ('wedding_planning_test', 'couple_2', 'planning', 45000.0, 'EUR', 'Dublin', 'Irish Catholic', 150, '2026-08-15');
    """)
    # Seed budget lines for the pre-made planning wedding
    premade_budget = [
        ("bl_venue", "wedding_planning_test", "venue", 15000.0),
        ("bl_catering", "wedding_planning_test", "catering", 12000.0),
        ("bl_photo", "wedding_planning_test", "photography", 4000.0),
        ("bl_florist", "wedding_planning_test", "florals", 3000.0),
        ("bl_music", "wedding_planning_test", "music", 2500.0),
        ("bl_officiant", "wedding_planning_test", "officiant", 600.0),
        ("bl_other", "wedding_planning_test", "other", 7900.0)
    ]
    cursor.executemany("INSERT INTO budget_lines (id, wedding_id, category, allocated_amount, spent_amount) VALUES (?, ?, ?, ?, 0.0)", premade_budget)

    # Add a mock booking for planning wedding to show quote extraction.
    # References a real photographer from the seed (sup_dasha_caffrey, Dublin).
    cursor.execute("""
        INSERT INTO bookings (id, wedding_id, supplier_id, status, sourced_by_agent_id)
        VALUES ('booking_photo_test', 'wedding_planning_test', 'sup_dasha_caffrey', 'inquired', 'supplier_matcher');
    """)

# HELPER FUNCTIONS FOR APP AND AGENTS

def get_weddings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT w.*, u.name as couple_name 
        FROM weddings w 
        JOIN users u ON w.couple_user_id = u.id
        ORDER BY w.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_wedding_details(wedding_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT w.*, u.name as couple_name, u.email as couple_email, u.phone as couple_phone,
               v.name as venue_name
        FROM weddings w
        JOIN users u ON w.couple_user_id = u.id
        LEFT JOIN venues v ON w.venue_id = v.id
        WHERE w.id = ?
    """, (wedding_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_budget_lines(wedding_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM budget_lines WHERE wedding_id = ? ORDER BY allocated_amount DESC", (wedding_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_timeline_items(wedding_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM timeline_items WHERE wedding_id = ? ORDER BY due_at ASC", (wedding_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_bookings(wedding_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, 
               v.name as venue_name, v.venue_type, v.region as venue_region,
               s.name as supplier_name, s.category as supplier_category, s.location as supplier_region
        FROM bookings b
        LEFT JOIN venues v ON b.venue_id = v.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE b.wedding_id = ?
        ORDER BY b.created_at DESC
    """, (wedding_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_quotes(booking_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quotes WHERE booking_id = ?", (booking_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_agent_logs(wedding_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if wedding_id:
        cursor.execute("SELECT * FROM agent_decision_logs WHERE wedding_id = ? ORDER BY timestamp DESC", (wedding_id,))
    else:
        cursor.execute("SELECT * FROM agent_decision_logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_booking_status(booking_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
    conn.commit()
    conn.close()

def insert_quote(quote_id, booking_id, line_items, total_amount, currency, status, agent_id, rationale, expires_at=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO quotes (id, booking_id, line_items, total_amount, currency, status, generated_by_agent_id, rationale_text, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (quote_id, booking_id, json.dumps(line_items), total_amount, currency, status, agent_id, rationale, expires_at))
    conn.commit()
    conn.close()

def update_wedding_venue(wedding_id, venue_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE weddings SET venue_id = ?, status = 'booked' WHERE id = ?", (venue_id, wedding_id))
    conn.commit()
    conn.close()

def get_all_venues():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM venues ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_suppliers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers ORDER BY category, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
