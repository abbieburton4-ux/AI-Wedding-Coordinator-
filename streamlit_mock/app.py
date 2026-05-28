import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import uuid
import re
from datetime import datetime
import db
import agents

# Set Streamlit Page Config
st.set_page_config(
    page_title="VenueFlow — AI Coordinator Mockup",
    page_icon="💍",
    layout="wide"
)

# Custom premium styling matching CLAUDE.md branding (warm-ivory, muted-gold, serif headings)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,400&family=Montserrat:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Cormorant Garamond', serif;
        color: #B89047; /* Muted Gold */
        font-weight: 600;
    }
    
    .gold-header {
        font-family: 'Cormorant Garamond', serif;
        font-size: 3rem;
        color: #B89047;
        text-align: center;
        margin-bottom: 0.1rem;
    }
    
    .gold-sub {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1.5rem;
        font-style: italic;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .stButton>button {
        background-color: #B89047;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #9C7836;
        color: white;
        box-shadow: 0px 4px 10px rgba(184, 144, 71, 0.3);
    }
    
    .card {
        background-color: rgba(244, 240, 230, 0.4); /* Muted Warm Ivory */
        border: 1px solid rgba(184, 144, 71, 0.2);
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-box {
        text-align: center;
        padding: 1rem;
        background-color: #FAF8F5;
        border-radius: 6px;
        border-left: 4px solid #B89047;
    }
    
    .metric-value {
        font-family: 'Cormorant Garamond', serif;
        font-size: 2.2rem;
        font-weight: 600;
        color: #B89047;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize Database
db.init_db()

# PII Redaction Helper
def redact_pii(df_logs):
    """Redacts PII (emails, phone numbers) from a logs dataframe before CSV export."""
    df_redacted = df_logs.copy()
    
    email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    phone_pattern = re.compile(r'\+?[0-9]{3}-?[0-9]{3,4}-?[0-9]{4,6}')
    
    def redact_text(text):
        if not isinstance(text, str):
            return text
        text = re.sub(email_pattern, '[REDACTED_EMAIL]', text)
        text = re.sub(phone_pattern, '[REDACTED_PHONE]', text)
        return text

    columns_to_redact = ["input_payload", "output_payload", "rationale_summary", "error_message"]
    for col in columns_to_redact:
        if col in df_redacted.columns:
            df_redacted[col] = df_redacted[col].apply(redact_text)
            
    return df_redacted

# SIDEBAR CONFIGURATION
st.sidebar.markdown("<h2 style='text-align: center;'>VenueFlow settings</h2>", unsafe_allow_html=True)
st.sidebar.image("https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=300", use_container_width=True, caption="AI Wedding Coordinator")

# User Authentication Selector
st.sidebar.markdown("---")
st.sidebar.markdown("### User Authentication (Mock)")
user_roles = {
    "Clara & Sean (Couple)": ("couple_1", "couple"),
    "Mary-Aoife (Planner)": ("planner_1", "planner")
}
selected_user = st.sidebar.selectbox("Log in as:", list(user_roles.keys()))
current_user_id, current_user_role = user_roles[selected_user]
st.session_state.current_user_id = current_user_id
st.session_state.current_user_role = current_user_role

# Gemini API Key Setup
st.sidebar.markdown("---")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
if not api_key:
    st.sidebar.warning("🔑 Enter Gemini API Key to run agent workflows.")
else:
    st.sidebar.success("🔑 Gemini API Key configured!")

# DB Maintenance
st.sidebar.markdown("---")
st.sidebar.markdown("### Database Maintenance")
if st.sidebar.button("Reset & Re-Seed Database", use_container_width=True):
    db.init_db(force=True)
    st.sidebar.success("Database re-initialized successfully!")
    st.rerun()

# Active Wedding Selector
st.sidebar.markdown("---")
st.sidebar.markdown("### Active Wedding Context")
weddings = db.get_weddings()

# Role-based filtering of weddings
if st.session_state.current_user_role == "couple":
    weddings = [w for w in weddings if w["couple_user_id"] == st.session_state.current_user_id]

if weddings:
    wedding_options = {f"{w['couple_name']} - {w['region']} ({w['status']})": w['id'] for w in weddings}
    selected_wedding_label = st.sidebar.selectbox("Select Active Wedding", list(wedding_options.keys()))
    active_wedding_id = wedding_options[selected_wedding_label]
else:
    if st.session_state.current_user_role == "couple":
        st.sidebar.info("No weddings found for this couple. Submit Onboarding form first.")
    else:
        st.sidebar.info("No weddings in database. Go to Onboarding tab.")
    active_wedding_id = None

# MAIN PANEL
st.markdown("<div class='gold-header'>VenueFlow</div>", unsafe_allow_html=True)
st.markdown("<div class='gold-sub'>Autonomous AI Wedding Coordinator (Day-90 MVP Harness)</div>", unsafe_allow_html=True)

# Render Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💍 Wedding Onboarding (intake_planner)", 
    "🗺️ Sourcing & Schedulers (venue_matcher)", 
    "✉️ Inbound Quotes (quote_extractor)", 
    "📊 Metrics Dashboard",
    "📜 Audit Logs & DB Explorer"
])

# ==========================================
# TAB 1: WEDDING ONBOARDING
# ==========================================
with tab1:
    st.markdown("<h2>Wedding Profile Intake & Plan Seeding</h2>", unsafe_allow_html=True)
    st.markdown(
        "This workflow collects the couple's desires and budget constraints, runs the **Intake Planner Agent**, "
        "validates if the budget is realistic for the region/guest count, and seeds the planning budget & timeline."
    )
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>Intake Form</h4>", unsafe_allow_html=True)
        with st.form("onboarding_form"):
            couple_name = st.text_input("Couple Name(s)", placeholder="e.g. Clara & Sean", value="Clara & Sean")
            email = st.text_input("Primary Email", value="clara.sean@wedding.ie")
            phone = st.text_input("Primary Phone", value="+353871234567")
            
            budget_total = st.number_input("Total Wedding Budget (€)", min_value=1000, value=30000, step=1000)
            guest_count = st.number_input("Estimated Guest Count", min_value=10, value=100, step=10)
            
            region = st.selectbox("Preferred Region in Ireland", ["Sligo", "Dublin", "Galway", "Kerry", "Clare", "Monaghan", "Meath", "Leinster"])
            ceremony_type = st.selectbox("Ceremony/Tradition Type", [
                "Civil/Humanist", "Irish Catholic", "Hindu", "Muslim", "Multi-cultural"
            ])
            
            date_pref = st.radio("Wedding Date Option", ["Fixed Date", "Flexible Range (TBD)"])
            
            if date_pref == "Fixed Date":
                wedding_date = st.date_input("Wedding Date", min_value=datetime.today())
                wedding_date_start = None
                wedding_date_end = None
            else:
                wedding_date = None
                wedding_date_start = st.date_input("Range Start Date", min_value=datetime.today())
                wedding_date_end = st.date_input("Range End Date", min_value=datetime.today() + pd.Timedelta(days=180))
            
            style_notes = st.text_area("Style, Aesthetic & Theme Notes", value="Modern classic, elegant florals, cozy castle vibe.")
            
            submit_btn = st.form_submit_button("Submit & Simulate Stripe Payment")
        st.markdown("</div>", unsafe_allow_html=True)
        
        if submit_btn:
            if not api_key:
                st.error("Please enter a Gemini API Key in the sidebar first.")
            else:
                captured_steps = []
                wedding_id_for_state = None
                result = {"status": "init"}
                try:
                    with st.status("Setting up your wedding plan...", expanded=True) as status:
                        import hashlib
                        # 1. Compute Idempotency Key to prevent double-click duplicates
                        raw_key = f"{couple_name}_{email}_{budget_total}_{guest_count}_{region}_{ceremony_type}_{wedding_date}_{wedding_date_start}_{wedding_date_end}_{style_notes}"
                        idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

                        conn = db.get_connection()
                        cursor = conn.cursor()

                        # Check if wedding with this key already exists
                        cursor.execute("SELECT id, status, couple_user_id FROM weddings WHERE idempotency_key = ?", (idempotency_key,))
                        existing_wedding = cursor.fetchone()

                        if existing_wedding:
                            wedding_id = existing_wedding[0]
                            wedding_status = existing_wedding[1]
                            user_id = existing_wedding[2]
                            line = "Wedding plan already exists for this profile — retrieving existing plan"
                            captured_steps.append(line); st.write(line)
                        else:
                            user_id = f"usr_{uuid.uuid4().hex[:8]}"
                            wedding_id = f"wed_{uuid.uuid4().hex[:8]}"

                            cursor.execute("INSERT INTO users (id, role, name, email, phone) VALUES (?, 'couple', ?, ?, ?)", (user_id, couple_name, email, phone))

                            w_date_str = wedding_date.strftime("%Y-%m-%d") if wedding_date else None
                            w_start_str = wedding_date_start.strftime("%Y-%m-%d") if wedding_date_start else None
                            w_end_str = wedding_date_end.strftime("%Y-%m-%d") if wedding_date_end else None

                            cursor.execute("""
                                INSERT INTO weddings (id, couple_user_id, wedding_date, wedding_date_start, wedding_date_end, region, ceremony_type, guest_count_estimate, budget_total, status, style_notes, idempotency_key)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'intake', ?, ?)
                            """, (wedding_id, user_id, w_date_str, w_start_str, w_end_str, region, ceremony_type, guest_count, budget_total, style_notes, idempotency_key))
                            conn.commit()
                            wedding_status = 'intake'
                            line = f"Created account and wedding profile · `{wedding_id}`"
                            captured_steps.append(line); st.write(line)

                        conn.close()
                        wedding_id_for_state = wedding_id

                        line = "Payment of €299.00 coordinator fee simulated successfully"
                        captured_steps.append(line); st.write(line)

                        # Only run agent if not already planned (status = 'intake')
                        if wedding_status == 'intake':
                            def on_step(msg):
                                captured_steps.append(msg)
                                st.write(msg)

                            result = agents.run_intake_planner(
                                wedding_id,
                                user_id=st.session_state.current_user_id,
                                api_key=api_key,
                                on_step=on_step,
                            )

                            if result["status"] == "blocked":
                                status.update(
                                    label=f"Plan blocked: {result['warning'][:70]}",
                                    state="error",
                                )
                            else:
                                status.update(label="Wedding plan ready", state="complete")
                        else:
                            status.update(label="Plan retrieved", state="complete")
                            result = {"status": "exists", "summary": "Existing plan reused — no new agent run"}

                    # Status block closed. Persist trail for the col2 expander.
                    if wedding_id_for_state:
                        st.session_state[f"intake_steps_{wedding_id_for_state}"] = captured_steps

                    if result["status"] == "blocked":
                        st.info("Adjust your inputs and resubmit, or open Audit Logs to inspect the rationale.")
                    elif result["status"] == "success":
                        st.success(f"Agent rationale: {result.get('summary', '')}")
                        st.rerun()
                    else:
                        st.rerun()

                except Exception as e:
                    st.error(f"Error executing agent: {e}")
                        
    with col2:
        if active_wedding_id:
            w_details = db.get_wedding_details(active_wedding_id)
            st.markdown(f"<h3>Active Wedding: {w_details['couple_name']}</h3>", unsafe_allow_html=True)

            # Reasoning trail from the most recent intake_planner run for this
            # wedding — preserved across the st.rerun() that follows a successful
            # plan generation, so the couple can re-read what the AI did.
            intake_steps_key = f"intake_steps_{active_wedding_id}"
            if intake_steps_key in st.session_state and st.session_state[intake_steps_key]:
                with st.expander("How the AI built this plan", expanded=False):
                    for step in st.session_state[intake_steps_key]:
                        st.markdown(f"- {step}")

            c_date = w_details['wedding_date'] or f"TBD ({w_details['wedding_date_start']} to {w_details['wedding_date_end']})"
            
            # Show summary stats
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='metric-box'><div class='metric-value'>€{w_details['budget_total']:,.0f}</div><div class='metric-label'>Total Budget</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-box'><div class='metric-value'>{w_details['guest_count_estimate']}</div><div class='metric-label'>Guest Count</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-box'><div class='metric-value'>{w_details['region']}</div><div class='metric-label'>Region</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-box'><div class='metric-value'>{w_details['status'].upper()}</div><div class='metric-label'>Status</div></div>", unsafe_allow_html=True)
                
            st.markdown(f"**Ceremony Type**: {w_details['ceremony_type']} | **Date**: {c_date}")
            st.markdown(f"**Style Notes**: *{w_details['style_notes']}*")
            
            # Budget Splits and Timeline
            b_col, t_col = st.columns([1, 1.2])
            
            with b_col:
                st.markdown("<h4>Allocated Budget Splits</h4>", unsafe_allow_html=True)
                lines = db.get_budget_lines(active_wedding_id)
                if lines:
                    df_lines = pd.DataFrame(lines)
                    fig = px.pie(df_lines, values="allocated_amount", names="category", hole=0.4,
                                 color_discrete_sequence=px.colors.sequential.YlOrBr)
                    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df_lines[["category", "allocated_amount"]], hide_index=True)
                else:
                    st.info("No budget splits generated yet. Run onboarding.")
                    
            with t_col:
                st.markdown("<h4>Pre-Wedding Planning Timeline</h4>", unsafe_allow_html=True)
                items = db.get_timeline_items(active_wedding_id)
                if items:
                    df_items = pd.DataFrame(items)
                    st.dataframe(
                        df_items[["due_at", "title", "description", "status"]],
                        hide_index=True,
                        column_config={
                            "due_at": "Due Date",
                            "title": "Milestone",
                            "description": "What to do",
                            "status": "Status"
                        }
                    )
                else:
                    st.info("No timeline items generated yet. Run onboarding.")
        else:
            st.info("Select a wedding or create one to view the seeded budget and timeline.")

# ==========================================
# TAB 2: SOURCING & MATCHING
# ==========================================
with tab2:
    st.markdown("<h2>AI Sourcing & Recommendation Feeds</h2>", unsafe_allow_html=True)
    st.markdown(
        "Run the **Matcher Agents** (`venue_matcher` / `supplier_matcher`) to query available locations/vendors. "
        "The agent ranks options, writes rationale, and drafts outbound inquiry emails."
    )
    
    if not active_wedding_id:
        st.info("Select a wedding context in the sidebar first.")
    else:
        w_details = db.get_wedding_details(active_wedding_id)
        if w_details["status"] == "intake":
            st.warning("This wedding is in 'intake' status. You must submit the onboarding plan first to simulate payments and activate planning.")
        else:
            st.markdown(f"**Target Requirements**: Sourcing for **{w_details['guest_count_estimate']} guests** in **{w_details['region']}** (Style: *{w_details['style_notes']}*).")
            
            s_col1, s_col2 = st.columns([1, 1.5])
            
            with s_col1:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown("<h4>Trigger Sourcing Agents</h4>", unsafe_allow_html=True)
                
                # Match Venue
                if st.button("Run Venue Matcher Agent", use_container_width=True):
                    if not api_key:
                        st.error("Configure Gemini API Key first.")
                    else:
                        # Live-stream the agent's reasoning instead of hiding 10–20s
                        # of work behind a spinner. Each on_step callback writes a
                        # line into the open st.status block; st.status flushes
                        # the UI between writes so the user watches the AI work.
                        captured_steps = []
                        with st.status(
                            "AI coordinator working on your shortlist...",
                            expanded=True,
                        ) as status:
                            def on_step(msg):
                                captured_steps.append(msg)
                                st.write(msg)

                            res = agents.run_venue_matcher(
                                active_wedding_id,
                                user_id=st.session_state.current_user_id,
                                api_key=api_key,
                                on_step=on_step,
                            )

                            if res["status"] == "blocked":
                                status.update(
                                    label=f"Blocked: {res['warning'][:70]}",
                                    state="error",
                                )
                            else:
                                status.update(
                                    label=f"Matched {len(res['shortlist'])} venues for you",
                                    state="complete",
                                )

                        # Persist the reasoning trail so it's visible after the
                        # rerun that refreshes the shortlist below.
                        st.session_state[f"matcher_steps_{active_wedding_id}"] = captured_steps
                        if res["status"] == "success":
                            st.rerun()
                            
                st.markdown("<br/>", unsafe_allow_html=True)
                
                # Match Supplier
                supplier_cat = st.selectbox("Select Supplier Category", list(agents.SUPPLIER_CATEGORIES))
                if st.button(f"Run {supplier_cat.capitalize()} Matcher Agent", use_container_width=True):
                    if not api_key:
                        st.error("Configure Gemini API Key first.")
                    else:
                        with st.spinner(f"Matching {supplier_cat} options..."):
                            res = agents.run_supplier_matcher(active_wedding_id, supplier_cat, user_id=st.session_state.current_user_id, api_key=api_key)
                            if res["status"] == "blocked":
                                st.warning(f"⚠️ Supplier Matcher Blocked: {res['warning']}")
                            else:
                                st.success(f"Matched {supplier_cat} suppliers successfully!")
                                st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                
            with s_col2:
                st.markdown("<h4>Shortlisted & Sourced Recommendations</h4>", unsafe_allow_html=True)

                # Reasoning trail from the most recent matcher run — preserved
                # across the st.rerun() that follows a successful match, so the
                # couple can re-read what the AI did to produce their shortlist.
                steps_key = f"matcher_steps_{active_wedding_id}"
                if steps_key in st.session_state and st.session_state[steps_key]:
                    with st.expander("How the AI built this shortlist", expanded=False):
                        for step in st.session_state[steps_key]:
                            st.markdown(f"- {step}")

                bookings = db.get_bookings(active_wedding_id)
                
                if bookings:
                    for bk in bookings:
                        is_venue = bk["venue_id"] is not None
                        vendor_name = bk["venue_name"] if is_venue else bk["supplier_name"]
                        category = "Venue" if is_venue else bk["supplier_category"].capitalize()
                        
                        st.markdown(f"<div class='card'>", unsafe_allow_html=True)
                        st.markdown(f"<h5>{vendor_name} ({category}) — {bk['status'].upper()}</h5>", unsafe_allow_html=True)
                        
                        # Find decision details
                        agent_logs = db.get_agent_logs(active_wedding_id)
                        matching_log = next((l for l in agent_logs if l["booking_id"] == bk["id"] and l["decision_type"] in ("venue_match", "supplier_match")), None)
                        
                        if matching_log:
                            out_payload = json.loads(matching_log["output_payload"])
                            shortlist_entry = next((s for s in out_payload.get("shortlist", []) if s["vendor_id"] == (bk["venue_id"] or bk["supplier_id"])), None)
                            
                            if shortlist_entry:
                                st.markdown(f"**AI Match Rationale**: {shortlist_entry['matching_rationale']}")
                                email_draft = st.text_area("Outbound Email Inquiry Draft", value=shortlist_entry["draft_inquiry_email"], key=f"email_{bk['id']}", height=120)
                                
                                if bk["status"] == "shortlisted":
                                    sc1, sc2 = st.columns([1, 1])
                                    with sc1:
                                        if st.button("Simulate Sending Inquiry", key=f"send_{bk['id']}"):
                                            db.update_booking_status(bk["id"], "inquired")
                                            conn = db.get_connection()
                                            cursor = conn.cursor()
                                            agents.log_user_action(
                                                cursor,
                                                wedding_id=active_wedding_id,
                                                booking_id=bk["id"],
                                                decision_type="inquiry_send",
                                                rationale_summary=f"Sent inquiry email to {vendor_name}.",
                                                parent_decision_id=matching_log["id"],
                                                user_id=st.session_state.current_user_id,
                                            )
                                            conn.commit()
                                            conn.close()
                                            st.success("Inquiry marked as sent!")
                                            st.rerun()
                                    with sc2:
                                        if st.button("Decline & Override Option", key=f"dec_{bk['id']}"):
                                            db.update_booking_status(bk["id"], "declined")
                                            conn = db.get_connection()
                                            cursor = conn.cursor()
                                            agents.log_user_override(
                                                cursor,
                                                parent_decision_id=matching_log["id"],
                                                overridden_by_user_id=st.session_state.current_user_id,
                                                wedding_id=active_wedding_id,
                                                booking_id=bk["id"],
                                                rationale_summary=f"Declined AI recommended vendor {vendor_name}.",
                                            )
                                            conn.commit()
                                            conn.close()
                                            st.warning("Recommendation declined.")
                                            st.rerun()
                                else:
                                    st.info(f"Booking status is {bk['status']}. Inquiry has been processed.")
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.info("No options shortlisted yet. Run the matcher agents on the left.")

# ==========================================
# TAB 3: INBOUND QUOTES
# ==========================================
with tab3:
    st.markdown("<h2>Quote Extraction & Ingestion Funnel</h2>", unsafe_allow_html=True)
    st.markdown(
        "When a vendor replies, the **Quote Extractor Agent** (`quote_extractor`) parses the raw prose, extracts "
        "priced line items, availability, and alerts if the total exceeds the allocated budget."
    )
    
    if not active_wedding_id:
        st.info("Select a wedding context in the sidebar.")
    else:
        # Get inquired bookings
        bookings = db.get_bookings(active_wedding_id)
        inquired_bookings = [b for b in bookings if b["status"] in ("inquired", "quoted")]
        
        if not inquired_bookings:
            st.info("No active inquired or quoted bookings found for this wedding. Go to the Sourcing tab to match and send inquiries first.")
        else:
            q_col1, q_col2 = st.columns([1, 1.2])
            
            with q_col1:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown("<h4>Ingest Supplier Reply</h4>", unsafe_allow_html=True)
                
                # Selector
                booking_options = {}
                for b in inquired_bookings:
                    name = b["venue_name"] if b["venue_id"] else b["supplier_name"]
                    cat = "Venue" if b["venue_id"] else b["supplier_category"].capitalize()
                    booking_options[f"{name} ({cat}) - Status: {b['status']}"] = b["id"]
                    
                selected_bk_label = st.selectbox("Select Active Inquiry", list(booking_options.keys()))
                sel_bk_id = booking_options[selected_bk_label]
                
                # Fetch details of selected booking
                active_bk_data = next(b for b in inquired_bookings if b["id"] == sel_bk_id)
                allocated_budget = 0.0
                cat_key = active_bk_data["supplier_category"] if active_bk_data["supplier_id"] else "venue"
                
                budgets = db.get_budget_lines(active_wedding_id)
                for bd_l in budgets:
                    if bd_l["category"] == cat_key:
                        allocated_budget = bd_l["allocated_amount"]
                        
                st.markdown(f"**Allocated Category Budget**: €{allocated_budget:,.2f}")
                
                # Preset Replier
                st.markdown("##### Quick Presets for Testing:")
                p1, p2, p3 = st.columns(3)
                preset_text = ""
                
                with p1:
                    if st.button("Castle Leslie (Ok/Dublin)", use_container_width=True):
                        preset_text = (
                            "Dear Clara & Sean,\n\nThank you for reaching out! We are delighted to confirm that we have "
                            "availability for your ceremony on August 15th, 2026.\n\nOur exclusive hire fee for the Castle "
                            "is €5,000, and our peak season catering package is €120 per head. For your 100 guests, this includes "
                            "welcome drinks, a 5-course banquet dinner, and service charge.\n\nWe look forward to hearing from you.\n\n"
                            "Best regards,\nCastle Leslie Estate Team"
                        )
                with p2:
                    if st.button("Dublin Photo (Over Budget)", use_container_width=True):
                        preset_text = (
                            "Hi Clara,\n\nI would be honored to shoot your wedding! I am free on your date. My luxury package is "
                            "€4,500, which includes full day coverage, a second photographer, an engagement session, and a luxury "
                            "linen wedding album.\n\nLet me know if you would like to book a call.\n\nBest,\nDublin Fine Art Photography"
                        )
                with p3:
                    if st.button("Declined/Full", use_container_width=True):
                        preset_text = (
                            "Hi Clara and Sean,\n\nThanks for checking in! Unfortunately, we are fully booked for all weekend dates "
                            "in August 2026. We wish you the absolute best with your wedding planning!\n\nBest,\nWild Connections Florals"
                        )
                
                email_input = st.text_area("Paste Supplier Email Response", value=preset_text, height=200)
                
                run_extractor_btn = st.button("Process Reply & Extract Quote", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
                if run_extractor_btn:
                    if not api_key:
                        st.error("Please configure the Gemini API Key.")
                    elif not email_input:
                        st.error("Paste an email to analyze first.")
                    else:
                        with st.spinner("Extracting quote line items..."):
                            try:
                                res = agents.run_quote_extractor(sel_bk_id, email_input, user_id=st.session_state.current_user_id, api_key=api_key)
                                st.success("Quote extracted and booking status updated!")
                                if res["budget_warning"]:
                                    st.warning("⚠️ **Budget Alert**: This quote exceeds the category's allocated budget! Budget monitor alert logged in the audit trail.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Extraction failed: {e}")
                                
            with q_col2:
                st.markdown("<h4>Extracted Quotes & Direct Payments</h4>", unsafe_allow_html=True)
                quotes = db.get_quotes(sel_bk_id)
                
                if quotes:
                    for qt in quotes:
                        st.markdown("<div class='card'>", unsafe_allow_html=True)
                        st.markdown(f"<h5>Quote Details — €{qt['total_amount']:,.2f} ({qt['status'].upper()})</h5>", unsafe_allow_html=True)
                        st.markdown(f"**AI Extraction Summary**: {qt['rationale_text']}")
                        
                        items_list = json.loads(qt["line_items"])
                        if items_list:
                            st.markdown("**Itemized Details:**")
                            df_items = pd.DataFrame(items_list)
                            st.dataframe(df_items, hide_index=True, use_container_width=True)
                            
                        # Show action to book/sign contract
                        if qt["status"] == "pending":
                            st.markdown("---")
                            st.markdown("##### Book Vendor & Record Deposit")
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                deposit_amount = st.number_input("Deposit Paid Directly (€)", min_value=0.0, value=qt["total_amount"]*0.1, step=100.0, key=f"dep_{qt['id']}")
                            with c2:
                                bank_ref = st.text_input("Receipt / Bank Reference", value="BANK-TRSF-593", key=f"ref_{qt['id']}")
                                
                            if st.button("Confirm Booking (Sign & Record)", key=f"bk_{qt['id']}"):
                                w_details = db.get_wedding_details(active_wedding_id)
                                couple_user_id = w_details["couple_user_id"] if w_details else "couple_1"
                                conn = db.get_connection()
                                cursor = conn.cursor()
                                
                                # Sign contract
                                contract_id = f"c_{uuid.uuid4().hex[:10]}"
                                cursor.execute("""
                                    INSERT INTO contracts (id, booking_id, signed_by, terms_snapshot, risk_flags, reviewed_by_agent_id)
                                    VALUES (?, ?, ?, ?, '[]', 'contract_reviewer')
                                """, (contract_id, sel_bk_id, json.dumps([couple_user_id, "vendor"]), f"Accepted quote items for {qt['total_amount']}."))
                                
                                # Record direct payment
                                pay_id = f"sp_{uuid.uuid4().hex[:10]}"
                                cursor.execute("""
                                    INSERT INTO supplier_payments (id, booking_id, amount, currency, kind, external_reference, paid_on)
                                    VALUES (?, ?, ?, 'EUR', 'deposit', ?, ?)
                                """, (pay_id, sel_bk_id, deposit_amount, bank_ref, datetime.today().strftime("%Y-%m-%d")))
                                
                                # Update quote status
                                cursor.execute("UPDATE quotes SET status = 'accepted' WHERE id = ?", (qt["id"],))
                                
                                # Update booking status
                                cursor.execute("UPDATE bookings SET status = 'booked' WHERE id = ?", (sel_bk_id,))
                                
                                # Update budget line spent amount
                                cursor.execute("""
                                    UPDATE budget_lines 
                                    SET spent_amount = spent_amount + ?, updated_at = CURRENT_TIMESTAMP 
                                    WHERE wedding_id = ? AND category = ?
                                """, (deposit_amount, active_wedding_id, cat_key))
                                
                                # If it's a venue booking, update the wedding venue_id and status
                                if active_bk_data["venue_id"]:
                                    cursor.execute("UPDATE weddings SET venue_id = ?, status = 'booked' WHERE id = ?", (active_bk_data["venue_id"], active_wedding_id))
                                    
                                # Audit log: quote_accept chains to the quote_draft that
                                # produced this quote, completing the matcher → inquiry_send
                                # → quote_draft → quote_accept chain.
                                agents.log_user_action(
                                    cursor,
                                    wedding_id=active_wedding_id,
                                    booking_id=sel_bk_id,
                                    decision_type="quote_accept",
                                    rationale_summary=f"Accepted quote for {qt['total_amount']}. Paid deposit €{deposit_amount:,.2f}.",
                                    parent_decision_id=agents._resolve_quote_accept_parent(cursor, sel_bk_id),
                                    user_id=st.session_state.current_user_id,
                                )
                                
                                conn.commit()
                                conn.close()
                                st.success("Vendor successfully booked! Budget updated.")
                                st.rerun()
                        else:
                            st.success(f"This quote has been {qt['status']}.")
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.info("No quotes extracted yet for this booking. Paste a response on the left.")

# ==========================================
# TAB 4: METRICS DASHBOARD
# ==========================================
with tab4:
    st.markdown("<h2>XPRIZE Submission Metrics Dashboard</h2>", unsafe_allow_html=True)
    st.markdown(
        "This dashboard aggregates agent performance and decision logs to fulfill the "
        "XPRIZE requirements: monitoring volume, latencies, guardrail blocks, and confidence."
    )
    
    logs = db.get_agent_logs()
    if not logs:
        st.info("No logs available yet. Run some onboarding or matching workflows to populate metrics.")
    else:
        df_metrics = pd.DataFrame(logs)
        
        # Core Aggregates
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM weddings")
        total_weddings = cursor.fetchone()[0]
        
        total_decisions = len(df_metrics)
        blocked_decisions = len(df_metrics[df_metrics["status"] == "blocked_by_guardrail"])
        error_decisions = len(df_metrics[df_metrics["status"] == "error"])
        success_decisions = len(df_metrics[df_metrics["status"] == "success"])
        
        avg_confidence = df_metrics["confidence_score"].mean()
        conn.close()
        
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"<div class='metric-box'><div class='metric-value'>{total_weddings}</div><div class='metric-label'>Total Weddings</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-box'><div class='metric-value'>{total_decisions}</div><div class='metric-label'>Agent Decisions</div></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-box'><div class='metric-value'>{blocked_decisions}</div><div class='metric-label'>Guardrail Blocks</div></div>", unsafe_allow_html=True)
        with m4:
            val_conf = f"{avg_confidence*100:.1f}%" if pd.notnull(avg_confidence) else "N/A"
            st.markdown(f"<div class='metric-box'><div class='metric-value'>{val_conf}</div><div class='metric-label'>Avg LLM Confidence</div></div>", unsafe_allow_html=True)
            
        st.markdown("---")
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("<h4>Decision Status Breakdown</h4>", unsafe_allow_html=True)
            status_counts = df_metrics["status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_status = px.pie(status_counts, values="Count", names="Status", hole=0.4,
                                color_discrete_sequence=px.colors.sequential.YlOrBr)
            fig_status.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=250)
            st.plotly_chart(fig_status, use_container_width=True)
            
        with col_right:
            st.markdown("<h4>Average Latency by Agent</h4>", unsafe_allow_html=True)
            df_latency = df_metrics[df_metrics["latency_ms"] > 0]
            if not df_latency.empty:
                avg_latency = df_latency.groupby("agent_id")["latency_ms"].mean().reset_index()
                avg_latency.columns = ["Agent", "Avg Latency (ms)"]
                fig_latency = px.bar(avg_latency, x="Agent", y="Avg Latency (ms)",
                                     color="Avg Latency (ms)", color_continuous_scale="Viridis")
                fig_latency.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=250, showlegend=False)
                st.plotly_chart(fig_latency, use_container_width=True)
            else:
                st.info("Latency metrics are not available yet.")
                
        st.markdown("---")
        st.markdown("<h4>Agent-Specific Activity Summary</h4>", unsafe_allow_html=True)
        agent_summary = df_metrics.groupby("agent_id").agg(
            Total_Decisions=("id", "count"),
            Successes=("status", lambda s: (s == "success").sum()),
            Blocks=("status", lambda s: (s == "blocked_by_guardrail").sum()),
            Errors=("status", lambda s: (s == "error").sum()),
            Avg_Confidence=("confidence_score", "mean")
        ).reset_index()
        agent_summary.columns = ["Agent ID", "Total Decisions", "Successes", "Blocks", "Errors", "Avg Confidence"]
        agent_summary["Avg Confidence"] = agent_summary["Avg Confidence"].apply(lambda c: f"{c*100:.1f}%" if pd.notnull(c) else "N/A")
        st.dataframe(agent_summary, use_container_width=True, hide_index=True)

# ==========================================
# TAB 5: AUDIT LOGS & DB EXPLORER
# ==========================================
with tab5:
    st.markdown("<h2>Agent Execution Logs (XPRIZE Submission Package)</h2>", unsafe_allow_html=True)
    st.markdown(
        "Under XPRIZE rules, **every single autonomous agent action** (sourcing, drafting, warnings) must be logged "
        "as a timestamped, reproducible record. Redaction is applied at export time."
    )
    
    logs = db.get_agent_logs()
    
    if logs:
        df_logs = pd.DataFrame(logs)
        
        # Display filters
        f_agent, f_status, f_type = st.columns(3)
        with f_agent:
            agents_list = ["ALL"] + sorted(list(df_logs["agent_id"].unique()))
            sel_agent = st.selectbox("Filter by Agent", agents_list)
        with f_status:
            status_list = ["ALL"] + sorted(list(df_logs["status"].unique()))
            sel_status = st.selectbox("Filter by Status", status_list)
        with f_type:
            types_list = ["ALL"] + sorted(list(df_logs["decision_type"].unique()))
            sel_type = st.selectbox("Filter by Decision Type", types_list)
            
        # Apply filters
        filtered_df = df_logs.copy()
        if sel_agent != "ALL":
            filtered_df = filtered_df[filtered_df["agent_id"] == sel_agent]
        if sel_status != "ALL":
            filtered_df = filtered_df[filtered_df["status"] == sel_status]
        if sel_type != "ALL":
            filtered_df = filtered_df[filtered_df["decision_type"] == sel_type]
            
        # Show Export CSV Button (PII Redacted)
        redacted_df = redact_pii(filtered_df)
        csv_data = redacted_df.to_csv(index=False)
        st.download_button(
            label="📤 Export Redacted AgentDecisionLogs (CSV)",
            data=csv_data,
            file_name=f"agent_decision_log_EXPORT_{datetime.today().strftime('%Y%m%d_T%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("#### Execution Log Feed")
        st.dataframe(
            filtered_df[["timestamp", "agent_id", "decision_type", "status", "rationale_summary", "latency_ms"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": "Time",
                "agent_id": "Agent",
                "decision_type": "Action",
                "status": "Result",
                "rationale_summary": "Decision Rationale",
                "latency_ms": "Latency (ms)"
            }
        )
        
        # Log Detail Explorer
        st.markdown("#### Log Detail Inspector")
        selected_log_id = st.selectbox("Select Log ID to inspect JSON payloads", filtered_df["id"].tolist())
        if selected_log_id:
            log_detail = filtered_df[filtered_df["id"] == selected_log_id].iloc[0].to_dict()
            l_col1, l_col2 = st.columns(2)
            with l_col1:
                st.markdown("**Input Payload:**")
                try:
                    st.json(json.loads(log_detail["input_payload"]))
                except (json.JSONDecodeError, TypeError):
                    st.text(log_detail["input_payload"])
            with l_col2:
                st.markdown("**Output Payload:**")
                try:
                    st.json(json.loads(log_detail["output_payload"]))
                except (json.JSONDecodeError, TypeError):
                    st.text(log_detail["output_payload"])
    else:
        st.info("No agent actions recorded yet. Run some onboarding or sourcing steps first.")
        
    # Database Table Explorer
    st.markdown("---")
    st.markdown("### Database Explorer")
    db_table = st.selectbox("Explore Database Table", ["weddings", "venues", "suppliers", "bookings", "quotes", "contracts", "budget_lines", "timeline_items", "users", "payments", "subscriptions", "venue_availability", "supplier_availability"])
    
    conn = db.get_connection()
    df_db = pd.read_sql_query(f"SELECT * FROM {db_table}", conn)
    conn.close()
    st.dataframe(df_db, use_container_width=True)
