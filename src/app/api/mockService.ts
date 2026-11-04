/**
 * VenueFlow Client Mock Service & Local Database
 *
 * Implements full backend API simulation so the React app runs 100% self-contained
 * without requiring a separate Python/FastAPI backend process.
 * Grounded in the real Irish venue/supplier catalog, agent workflows, and data models.
 */

export interface UserRecord {
  id: string;
  role: "couple" | "planner" | "admin";
  name: string;
  email: string;
  phone?: string;
}

export interface WeddingRecord {
  id: string;
  couple_user_id: string;
  planner_user_id?: string | null;
  venue_id?: string | null;
  status: "intake" | "preview" | "planning" | "booked" | "completed" | "cancelled";
  region: string;
  ceremony_type: string;
  guest_count_estimate: number;
  budget_total: number;
  currency: string;
  couple_name?: string;
  style_notes?: string;
  wedding_date?: string;
  created_at: string;
}

export interface BudgetLineRecord {
  id: string;
  wedding_id: string;
  category: string;
  allocated_amount: number;
  spent_amount: number;
}

export interface TimelineItemRecord {
  id: string;
  wedding_id: string;
  title: string;
  description?: string;
  due_at: string;
  status: "pending" | "in_progress" | "done" | "completed";
  kind: "milestone" | "task" | "day_of";
}

export interface BookingRecord {
  id: string;
  wedding_id: string;
  venue_id?: string;
  supplier_id?: string;
  status: "shortlisted" | "inquired" | "quoted" | "confirmed" | "declined";
  sourced_by_agent_id?: string;
  vendor_name?: string;
  vendor_kind: "venue" | "supplier";
  vendor_category?: string;
  vendor_location?: string;
  pricing_summary?: Record<string, unknown> | null;
  matching_rationale?: string;
  draft_inquiry_email?: string;
  quote_total?: number | null;
  quote_currency?: string | null;
  quote_rationale?: string | null;
  allocated_amount?: number | null;
  over_budget?: boolean | null;
}

export interface AgentDecisionRecord {
  id: string;
  wedding_id: string;
  agent_id: string;
  status: "pending" | "running" | "success" | "blocked_by_guardrail" | "error";
  rationale_summary?: string;
  error_message?: string;
  confidence_score?: number;
  latency_ms?: number;
  timestamp: string;
  input_payload?: Record<string, unknown>;
  output_payload?: Record<string, unknown>;
}

const STORAGE_KEY = "vf_mock_db_v1";

const INITIAL_USERS: UserRecord[] = [
  {
    id: "couple_1",
    role: "couple",
    name: "Clara & Sean",
    email: "clara.sean@wedding.ie",
    phone: "+353871234567",
  },
  {
    id: "couple_2",
    role: "couple",
    name: "Priya & David",
    email: "priya.david@gmail.com",
    phone: "+353869876543",
  },
  {
    id: "planner_1",
    role: "planner",
    name: "Mary-Aoife (Wedding Wonders)",
    email: "maryaoife@weddingwonders.ie",
    phone: "+353855551234",
  },
  {
    id: "planner_2",
    role: "planner",
    name: "Pilot Planner Two",
    email: "planner2@venueflow.ie",
    phone: "+353870000002",
  },
  {
    id: "admin",
    role: "admin",
    name: "Administrator",
    email: "admin@venueflow.ie",
  },
];

const INITIAL_VENUES = [
  {
    id: "venue_powerscourt",
    name: "Powerscourt House & Gardens",
    address: "Enniskerry, Co. Wicklow",
    region: "Wicklow",
    venue_type: "Country House & Gardens",
    capacity_min: 80,
    capacity_max: 220,
    pricing_summary: { rental_fee: 9000, average_cost_per_head: 165, currency: "EUR" },
    matching_rationale: "Classic Georgian Palladian estate with panoramic Wicklow mountain terraces. Ideal fit for 120-150 guests wanting timeless elegance.",
    draft_inquiry_email: "Dear Powerscourt Events Team,\n\nWe are writing on behalf of Priya & David who are planning their Civil ceremony and reception for ~130 guests in Summer 2027. We would love to check availability for the Georgian Ballroom and discuss your catering packages.\n\nWarm regards,\nVenueFlow AI Coordinator",
  },
  {
    id: "venue_tankardstown",
    name: "Tankardstown House",
    address: "Slane, Co. Meath",
    region: "Meath",
    venue_type: "Boutique Country Manor",
    capacity_min: 60,
    capacity_max: 180,
    pricing_summary: { rental_fee: 8000, average_cost_per_head: 155, currency: "EUR" },
    matching_rationale: "Orangery reception with exceptional farm-to-plate culinary focus. Fits the couple's preference for seasonal Irish dining.",
    draft_inquiry_email: "Dear Tankardstown House Team,\n\nOur couple Priya & David are interested in your Orangery reception space for a wedding with approximately 130 guests. Could you kindly share your 2026/2027 brochure and weekend date availability?\n\nBest wishes,\nVenueFlow AI Coordinator",
  },
  {
    id: "venue_adare_manor",
    name: "Adare Manor",
    address: "Adare, Co. Limerick",
    region: "Limerick",
    venue_type: "5-Star Castle Resort",
    capacity_min: 100,
    capacity_max: 350,
    pricing_summary: { rental_fee: 14000, average_cost_per_head: 250, currency: "EUR" },
    matching_rationale: "World-class luxury estate with Grand Ballroom and Michelin-grade dining for high-touch bespoke celebrations.",
    draft_inquiry_email: "Dear Adare Manor Wedding Concierge,\n\nWe would love to inquire about availability and package details for Priya & David's upcoming wedding celebration.\n\nWarm regards,\nVenueFlow AI Coordinator",
  },
  {
    id: "venue_fallon_byrne",
    name: "Fallon & Byrne Dining Room",
    address: "Exchequer Street, Dublin 2",
    region: "Dublin",
    venue_type: "Urban Chic & Fine Dining",
    capacity_min: 50,
    capacity_max: 140,
    pricing_summary: { rental_fee: 3500, average_cost_per_head: 120, currency: "EUR" },
    matching_rationale: "Cosmopolitan Dublin city-centre heritage dining room with exceptional wine pairings and warm candlelit intimacy.",
    draft_inquiry_email: "Dear Fallon & Byrne Events,\n\nPriya & David are planning their Dublin civil ceremony and reception for ~120 guests. We would love to enquire regarding availability and wine menus.\n\nBest,\nVenueFlow AI Coordinator",
  },
];

const INITIAL_SUPPLIERS = [
  {
    id: "sup_dasha_caffrey",
    name: "Dasha Caffrey Photography",
    category: "photography",
    location: "Dublin / Nationwide",
    pricing_summary: { package_name: "Full Day Documentary", total_amount: 3200, currency: "EUR" },
    matching_rationale: "Documentary editorial style, natural candid light with zero intrusive staging. Highly reviewed across Dublin.",
    draft_inquiry_email: "Hi Dasha,\n\nWe love your natural, documentary style and are checking availability for a wedding on August 15 in Dublin. Would love to review your latest full-day collections!\n\nBest regards,\nVenueFlow Coordinator",
  },
  {
    id: "sup_wild_bunch_florals",
    name: "The Wild Bunch Organic Florals",
    category: "florals",
    location: "Wicklow / Dublin",
    pricing_summary: { package_name: "Botanical Meadow Arch & Tables", total_amount: 2800, currency: "EUR" },
    matching_rationale: "Irish-grown seasonal foliage and wild romantic textures. Perfectly matches the organic aesthetic notes.",
    draft_inquiry_email: "Hi Wild Bunch team,\n\nInquiring on behalf of Priya & David for seasonal botanical florals and ceremony arch for Summer 2027.\n\nWarmly,\nVenueFlow AI Coordinator",
  },
  {
    id: "sup_manor_house_strings",
    name: "Manor House String Quartet",
    category: "music",
    location: "Dublin / Leinster",
    pricing_summary: { package_name: "Ceremony & Drinks Reception", total_amount: 1450, currency: "EUR" },
    matching_rationale: "Versatile classical and contemporary acoustic arrangements for outdoor and church ceremonies.",
    draft_inquiry_email: "Hi there,\n\nWe would love to check availability for ceremony and cocktail hour accompaniment for 130 guests.\n\nBest regards,\nVenueFlow Coordinator",
  },
];

interface MockDatabase {
  users: UserRecord[];
  weddings: WeddingRecord[];
  budgetLines: BudgetLineRecord[];
  timelineItems: TimelineItemRecord[];
  bookings: BookingRecord[];
  decisionLogs: AgentDecisionRecord[];
}

function getDefaultDB(): MockDatabase {
  const weddings: WeddingRecord[] = [
    {
      id: "wedding_planning_test",
      couple_user_id: "couple_2",
      planner_user_id: "planner_1",
      venue_id: "venue_powerscourt",
      status: "planning",
      region: "Dublin",
      ceremony_type: "Civil/Humanist",
      guest_count_estimate: 130,
      budget_total: 42000,
      currency: "EUR",
      couple_name: "Priya & David",
      style_notes: "Elegant floral garden party with documentary photography and live strings",
      wedding_date: "2027-06-20",
      created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    },
    {
      id: "wedding_intake_test",
      couple_user_id: "couple_1",
      status: "intake",
      region: "Sligo",
      ceremony_type: "Civil/Humanist",
      guest_count_estimate: 100,
      budget_total: 30000,
      currency: "EUR",
      couple_name: "Clara & Sean",
      style_notes: "Wild Atlantic coast, relaxed seafood banquet",
      wedding_date: "2027-09-12",
      created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    },
  ];

  const budgetLines: BudgetLineRecord[] = [
    { id: "bl-1", wedding_id: "wedding_planning_test", category: "venue", allocated_amount: 14000, spent_amount: 9000 },
    { id: "bl-2", wedding_id: "wedding_planning_test", category: "catering", allocated_amount: 11000, spent_amount: 0 },
    { id: "bl-3", wedding_id: "wedding_planning_test", category: "photography", allocated_amount: 3500, spent_amount: 3200 },
    { id: "bl-4", wedding_id: "wedding_planning_test", category: "florals", allocated_amount: 3000, spent_amount: 0 },
    { id: "bl-5", wedding_id: "wedding_planning_test", category: "music", allocated_amount: 2200, spent_amount: 1450 },
    { id: "bl-6", wedding_id: "wedding_planning_test", category: "attire", allocated_amount: 3000, spent_amount: 2100 },
    { id: "bl-7", wedding_id: "wedding_planning_test", category: "stationery", allocated_amount: 1200, spent_amount: 450 },
    { id: "bl-8", wedding_id: "wedding_planning_test", category: "hair_makeup", allocated_amount: 1100, spent_amount: 0 },
    { id: "bl-9", wedding_id: "wedding_planning_test", category: "cake", allocated_amount: 800, spent_amount: 0 },
    { id: "bl-10", wedding_id: "wedding_planning_test", category: "coordinator", allocated_amount: 2200, spent_amount: 299 },
  ];

  const timelineItems: TimelineItemRecord[] = [
    {
      id: "tl-1",
      wedding_id: "wedding_planning_test",
      title: "Lock in Venue & Reserve Date",
      description: "Sign formal venue agreement and pay holding deposit.",
      due_at: new Date(Date.now() + 14 * 86400000).toISOString(),
      status: "done",
      kind: "milestone",
    },
    {
      id: "tl-2",
      wedding_id: "wedding_planning_test",
      title: "Confirm Photographer & Engagement Shoot",
      description: "Review documentary portfolio and lock date with deposit.",
      due_at: new Date(Date.now() + 30 * 86400000).toISOString(),
      status: "in_progress",
      kind: "milestone",
    },
    {
      id: "tl-3",
      wedding_id: "wedding_planning_test",
      title: "Send Save-the-Dates to Guests",
      description: "Digital cards dispatched to 130 guests with accommodation blocks.",
      due_at: new Date(Date.now() + 60 * 86400000).toISOString(),
      status: "pending",
      kind: "milestone",
    },
    {
      id: "tl-4",
      wedding_id: "wedding_planning_test",
      title: "Menu & Wine Tasting Session",
      description: "Sample three-course tasting with sommelier recommendations.",
      due_at: new Date(Date.now() + 120 * 86400000).toISOString(),
      status: "pending",
      kind: "milestone",
    },
    {
      id: "tl-5",
      wedding_id: "wedding_planning_test",
      title: "Final Seating Chart & Dietary Submissions",
      description: "Lock table allocations and communicate all allergies to catering team.",
      due_at: new Date(Date.now() + 280 * 86400000).toISOString(),
      status: "pending",
      kind: "day_of",
    },
  ];

  const bookings: BookingRecord[] = [
    {
      id: "bk-1",
      wedding_id: "wedding_planning_test",
      venue_id: "venue_powerscourt",
      status: "shortlisted",
      sourced_by_agent_id: "venue_matcher",
      vendor_name: "Powerscourt House & Gardens",
      vendor_kind: "venue",
      vendor_category: "Country House & Gardens",
      vendor_location: "Wicklow",
      pricing_summary: { rental_fee: 9000, average_cost_per_head: 165, currency: "EUR" },
      matching_rationale: "Top fit for 130 guests in Wicklow / Greater Dublin. Exceptional garden terrace backdrop.",
      draft_inquiry_email: "Dear Powerscourt Events,\n\nInquiring on behalf of Priya & David for June 20, 2027...",
      quote_total: 9000,
      quote_currency: "EUR",
      allocated_amount: 14000,
      over_budget: false,
    },
    {
      id: "bk-2",
      wedding_id: "wedding_planning_test",
      venue_id: "venue_tankardstown",
      status: "shortlisted",
      sourced_by_agent_id: "venue_matcher",
      vendor_name: "Tankardstown House",
      vendor_kind: "venue",
      vendor_category: "Boutique Country Manor",
      vendor_location: "Meath",
      pricing_summary: { rental_fee: 8000, average_cost_per_head: 155, currency: "EUR" },
      matching_rationale: "Superb organic dining emphasis in Orangery. 45 min drive from Dublin.",
      draft_inquiry_email: "Dear Tankardstown Events,\n\nInquiring for Priya & David...",
      quote_total: 8000,
      quote_currency: "EUR",
      allocated_amount: 14000,
      over_budget: false,
    },
    {
      id: "bk-3",
      wedding_id: "wedding_planning_test",
      supplier_id: "sup_dasha_caffrey",
      status: "inquired",
      sourced_by_agent_id: "supplier_matcher",
      vendor_name: "Dasha Caffrey Photography",
      vendor_kind: "supplier",
      vendor_category: "photography",
      vendor_location: "Dublin / Nationwide",
      pricing_summary: { package_name: "Full Day Documentary", total_amount: 3200, currency: "EUR" },
      matching_rationale: "Matches couple's preference for candid, unposed documentary coverage.",
      draft_inquiry_email: "Hi Dasha, inquiring for wedding in Dublin on June 20...",
      quote_total: 3200,
      quote_currency: "EUR",
      allocated_amount: 3500,
      over_budget: false,
    },
    {
      id: "bk-4",
      wedding_id: "wedding_planning_test",
      supplier_id: "sup_wild_bunch_florals",
      status: "shortlisted",
      sourced_by_agent_id: "supplier_matcher",
      vendor_name: "The Wild Bunch Organic Florals",
      vendor_kind: "supplier",
      vendor_category: "florals",
      vendor_location: "Wicklow / Dublin",
      pricing_summary: { package_name: "Botanical Meadow Arch & Tables", total_amount: 2800, currency: "EUR" },
      matching_rationale: "Irish grown seasonal flora. Perfect tonal match for garden style.",
      draft_inquiry_email: "Hi Wild Bunch, checking availability...",
      quote_total: 2800,
      quote_currency: "EUR",
      allocated_amount: 3000,
      over_budget: false,
    },
  ];

  const decisionLogs: AgentDecisionRecord[] = [
    {
      id: "log-1",
      wedding_id: "wedding_planning_test",
      agent_id: "intake_planner",
      status: "success",
      rationale_summary: "Analyzed 130 guests, Civil ceremony, €42,000 budget. Formulated 10 budget allocations and 5 planning milestones based on Irish 2026/2027 market indices.",
      confidence_score: 95,
      latency_ms: 1240,
      timestamp: new Date(Date.now() - 7 * 86400000).toISOString(),
    },
    {
      id: "log-2",
      wedding_id: "wedding_planning_test",
      agent_id: "venue_matcher",
      status: "success",
      rationale_summary: "Filtered 45 verified Irish venues down to top 2 fits (Powerscourt & Tankardstown) matching capacity, Leinster region, and aesthetic profile.",
      confidence_score: 92,
      latency_ms: 2150,
      timestamp: new Date(Date.now() - 6 * 86400000).toISOString(),
    },
    {
      id: "log-3",
      wedding_id: "wedding_planning_test",
      agent_id: "supplier_matcher",
      status: "success",
      rationale_summary: "Sourced documentary photographer (Dasha Caffrey) and organic florist within budget envelope.",
      confidence_score: 91,
      latency_ms: 1850,
      timestamp: new Date(Date.now() - 5 * 86400000).toISOString(),
    },
  ];

  return {
    users: INITIAL_USERS,
    weddings,
    budgetLines,
    timelineItems,
    bookings,
    decisionLogs,
  };
}

class MockService {
  private db: MockDatabase;

  constructor() {
    this.db = this.loadDB();
  }

  private loadDB(): MockDatabase {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return JSON.parse(stored);
      } catch (e) {
        console.warn("Could not load from localStorage", e);
      }
    }
    return getDefaultDB();
  }

  private saveDB(): void {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.db));
      } catch (e) {
        console.warn("Could not save to localStorage", e);
      }
    }
  }

  public getMe(token?: string | null): UserRecord {
    if (!token) return this.db.users[1]; // default couple_2
    const clean = token.replace("Bearer ", "").replace("mock-", "");
    const user = this.db.users.find((u) => u.id === clean || u.email.includes(clean));
    if (user) return user;
    if (clean.includes("planner")) {
      const newPlanner: UserRecord = {
        id: clean,
        role: "planner",
        name: `Pilot Planner (${clean})`,
        email: `${clean}@venueflow.ie`,
      };
      this.db.users.push(newPlanner);
      this.saveDB();
      return newPlanner;
    }
    const newCouple: UserRecord = {
      id: clean,
      role: "couple",
      name: `Couple (${clean})`,
      email: `${clean}@example.com`,
    };
    this.db.users.push(newCouple);
    this.saveDB();
    return newCouple;
  }

  public handleRequest(path: string, options: RequestInit = {}, token?: string | null): any {
    const cleanPath = path.replace(/^\/api\/v1/, "").replace(/\/$/, "");
    const method = (options.method || "GET").toUpperCase();
    const currentUser = this.getMe(token);

    // 1. Auth: /auth/me
    if (cleanPath === "/auth/me") {
      return currentUser;
    }

    // 1.1 Auth: /auth/planner
    if (cleanPath === "/auth/planner" && method === "POST") {
      const body = options.body ? JSON.parse(options.body as string) : {};
      const email = body.email || "planner@venueflow.ie";
      const user = this.db.users.find((u) => u.email === email && u.role === "planner") || {
        id: "planner_1",
        role: "planner" as const,
        name: "Mary-Aoife (Wedding Wonders)",
        email,
      };
      return {
        token: `mock-${user.id}`,
        role: "planner",
        name: user.name,
      };
    }

    // 2. Weddings listing: GET /weddings
    if (cleanPath === "/weddings" && method === "GET") {
      if (currentUser.role === "planner") {
        return this.db.weddings.filter(
          (w) => w.planner_user_id === currentUser.id || !w.planner_user_id
        );
      }
      if (currentUser.role === "admin") {
        return this.db.weddings;
      }
      return this.db.weddings.filter((w) => w.couple_user_id === currentUser.id);
    }

    // 3. Create wedding: POST /weddings
    if (cleanPath === "/weddings" && method === "POST") {
      const body = options.body ? JSON.parse(options.body as string) : {};
      const newId = `wedding_${Date.now()}`;
      const totalBudget = Number(body.budget_total) || 35000;
      const guests = Number(body.guest_count_estimate) || 120;
      const coupleName = body.couple_name || currentUser.name || "Our Wedding";

      const wedding: WeddingRecord = {
        id: newId,
        couple_user_id: currentUser.id,
        planner_user_id: currentUser.role === "planner" ? currentUser.id : null,
        status: "planning",
        region: body.region || "Dublin",
        ceremony_type: body.ceremony_type || "Civil/Humanist",
        guest_count_estimate: guests,
        budget_total: totalBudget,
        currency: "EUR",
        couple_name: coupleName,
        style_notes: body.style_notes || "",
        wedding_date: body.wedding_date || "2027-08-15",
        created_at: new Date().toISOString(),
      };

      // Generate realistic budget lines
      const breakdown = [
        { cat: "venue", pct: 0.35 },
        { cat: "catering", pct: 0.28 },
        { cat: "photography", pct: 0.09 },
        { cat: "florals", pct: 0.07 },
        { cat: "music", pct: 0.05 },
        { cat: "attire", pct: 0.06 },
        { cat: "stationery", pct: 0.02 },
        { cat: "hair_makeup", pct: 0.03 },
        { cat: "cake", pct: 0.02 },
        { cat: "coordinator", pct: 0.03 },
      ];

      const newBudgetLines: BudgetLineRecord[] = breakdown.map((item, idx) => ({
        id: `bl_${newId}_${idx}`,
        wedding_id: newId,
        category: item.cat,
        allocated_amount: Math.round(totalBudget * item.pct),
        spent_amount: 0,
      }));

      // Generate planning milestones
      const weddingDateMs = wedding.wedding_date ? new Date(wedding.wedding_date).getTime() : Date.now() + 365 * 86400000;
      const newTimeline: TimelineItemRecord[] = [
        {
          id: `tl_${newId}_1`,
          wedding_id: newId,
          title: `Reserve ${wedding.region} Ceremony & Reception Venue`,
          description: `Contract signing and initial deposit for ${guests} guests.`,
          due_at: new Date(weddingDateMs - 300 * 86400000).toISOString(),
          status: "pending",
          kind: "milestone",
        },
        {
          id: `tl_${newId}_2`,
          wedding_id: newId,
          title: "Book Lead Photographer & Videographer",
          description: "Full day coverage and timeline alignment.",
          due_at: new Date(weddingDateMs - 240 * 86400000).toISOString(),
          status: "pending",
          kind: "milestone",
        },
        {
          id: `tl_${newId}_3`,
          wedding_id: newId,
          title: "Florals & Design Scheme Signoff",
          description: "Arches, tablescapes, and seasonal botanical sourcing.",
          due_at: new Date(weddingDateMs - 180 * 86400000).toISOString(),
          status: "pending",
          kind: "milestone",
        },
        {
          id: `tl_${newId}_4`,
          wedding_id: newId,
          title: "Catering Menu & Wine Tasting",
          description: "Course selection and allergen management.",
          due_at: new Date(weddingDateMs - 90 * 86400000).toISOString(),
          status: "pending",
          kind: "milestone",
        },
        {
          id: `tl_${newId}_5`,
          wedding_id: newId,
          title: "Final Guest Count & Day-of Schedule",
          description: "Run-of-show handoff to wedding party and vendors.",
          due_at: new Date(weddingDateMs - 14 * 86400000).toISOString(),
          status: "pending",
          kind: "day_of",
        },
      ];

      // Auto-shortlist initial matches from our rich database
      const matchedVenues = INITIAL_VENUES.filter((v) => v.region === wedding.region || v.capacity_max >= guests);
      const chosenVenue = matchedVenues[0] || INITIAL_VENUES[0];

      const newBookings: BookingRecord[] = [
        {
          id: `bk_${newId}_v1`,
          wedding_id: newId,
          venue_id: chosenVenue.id,
          status: "shortlisted",
          sourced_by_agent_id: "venue_matcher",
          vendor_name: chosenVenue.name,
          vendor_kind: "venue",
          vendor_category: chosenVenue.venue_type,
          vendor_location: chosenVenue.region,
          pricing_summary: chosenVenue.pricing_summary,
          matching_rationale: chosenVenue.matching_rationale,
          draft_inquiry_email: chosenVenue.draft_inquiry_email,
          quote_total: chosenVenue.pricing_summary.rental_fee,
          quote_currency: "EUR",
          allocated_amount: Math.round(totalBudget * 0.35),
          over_budget: false,
        },
        {
          id: `bk_${newId}_s1`,
          wedding_id: newId,
          supplier_id: INITIAL_SUPPLIERS[0].id,
          status: "shortlisted",
          sourced_by_agent_id: "supplier_matcher",
          vendor_name: INITIAL_SUPPLIERS[0].name,
          vendor_kind: "supplier",
          vendor_category: INITIAL_SUPPLIERS[0].category,
          vendor_location: INITIAL_SUPPLIERS[0].location,
          pricing_summary: INITIAL_SUPPLIERS[0].pricing_summary,
          matching_rationale: INITIAL_SUPPLIERS[0].matching_rationale,
          draft_inquiry_email: INITIAL_SUPPLIERS[0].draft_inquiry_email,
          quote_total: INITIAL_SUPPLIERS[0].pricing_summary.total_amount,
          quote_currency: "EUR",
          allocated_amount: Math.round(totalBudget * 0.09),
          over_budget: false,
        },
      ];

      const newLog: AgentDecisionRecord = {
        id: `log_${newId}_init`,
        wedding_id: newId,
        agent_id: "intake_planner",
        status: "success",
        rationale_summary: `Created customized budget breakdown (€${totalBudget.toLocaleString()}) and 5-stage timeline for ${guests} guests in ${wedding.region}.`,
        confidence_score: 96,
        latency_ms: 1100,
        timestamp: new Date().toISOString(),
      };

      this.db.weddings.unshift(wedding);
      this.db.budgetLines.push(...newBudgetLines);
      this.db.timelineItems.push(...newTimeline);
      this.db.bookings.push(...newBookings);
      this.db.decisionLogs.unshift(newLog);
      this.saveDB();

      return wedding;
    }

    // Single wedding route matching: /weddings/:id
    const weddingMatch = cleanPath.match(/^\/weddings\/([^/]+)$/);
    if (weddingMatch) {
      const weddingId = weddingMatch[1];
      const wedding = this.db.weddings.find((w) => w.id === weddingId);
      if (method === "GET") {
        return wedding || this.db.weddings[0];
      }
      if (method === "PATCH") {
        const body = options.body ? JSON.parse(options.body as string) : {};
        if (wedding) {
          Object.assign(wedding, body);
          this.saveDB();
          return wedding;
        }
      }
    }

    // 4. Sub-resources: /weddings/:id/budget
    const budgetMatch = cleanPath.match(/^\/weddings\/([^/]+)\/budget$/);
    if (budgetMatch) {
      const weddingId = budgetMatch[1];
      const items = this.db.budgetLines.filter((b) => b.wedding_id === weddingId);
      return items.length > 0 ? items : this.db.budgetLines.filter((b) => b.wedding_id === "wedding_planning_test");
    }

    // 5. Sub-resources: /weddings/:id/timeline
    const timelineMatch = cleanPath.match(/^\/weddings\/([^/]+)\/timeline$/);
    if (timelineMatch) {
      const weddingId = timelineMatch[1];
      const items = this.db.timelineItems.filter((t) => t.wedding_id === weddingId);
      return items.length > 0 ? items : this.db.timelineItems.filter((t) => t.wedding_id === "wedding_planning_test");
    }

    // 6. Sub-resources: /weddings/:id/bookings
    const bookingsMatch = cleanPath.match(/^\/weddings\/([^/]+)\/bookings$/);
    if (bookingsMatch) {
      const weddingId = bookingsMatch[1];
      const items = this.db.bookings.filter((b) => b.wedding_id === weddingId);
      return items.length > 0 ? items : this.db.bookings.filter((b) => b.wedding_id === "wedding_planning_test");
    }

    // 7. Sub-resources: /weddings/:id/decisions or /weddings/:id/logs
    const decisionsMatch = cleanPath.match(/^\/weddings\/([^/]+)\/(decisions|logs)$/);
    if (decisionsMatch) {
      const weddingId = decisionsMatch[1];
      const items = this.db.decisionLogs.filter((l) => l.wedding_id === weddingId);
      return items.length > 0 ? items : this.db.decisionLogs.filter((l) => l.wedding_id === "wedding_planning_test");
    }

    // 8. Match venue: POST /weddings/:id/match
    const matchVenueMatch = cleanPath.match(/^\/weddings\/([^/]+)\/match$/);
    if (matchVenueMatch && method === "POST") {
      const weddingId = matchVenueMatch[1];
      const wedding = this.db.weddings.find((w) => w.id === weddingId) || this.db.weddings[0];

      // Add fresh venue shortlist
      const available = INITIAL_VENUES.filter((v) => !this.db.bookings.some((b) => b.wedding_id === weddingId && b.venue_id === v.id));
      const nextVenue = available[0] || INITIAL_VENUES[0];

      const newBooking: BookingRecord = {
        id: `bk_${weddingId}_v_${Date.now()}`,
        wedding_id: weddingId,
        venue_id: nextVenue.id,
        status: "shortlisted",
        sourced_by_agent_id: "venue_matcher",
        vendor_name: nextVenue.name,
        vendor_kind: "venue",
        vendor_category: nextVenue.venue_type,
        vendor_location: nextVenue.region,
        pricing_summary: nextVenue.pricing_summary,
        matching_rationale: nextVenue.matching_rationale,
        draft_inquiry_email: nextVenue.draft_inquiry_email,
        quote_total: nextVenue.pricing_summary.rental_fee,
        quote_currency: "EUR",
        allocated_amount: Math.round(wedding.budget_total * 0.35),
        over_budget: false,
      };

      this.db.bookings.push(newBooking);

      const decision: AgentDecisionRecord = {
        id: `dec_${Date.now()}`,
        wedding_id: weddingId,
        agent_id: "venue_matcher",
        status: "success",
        rationale_summary: `Shortlisted ${nextVenue.name} (${nextVenue.region}) for ${wedding.guest_count_estimate} guests. Matches aesthetic criteria and capacity.`,
        confidence_score: 94,
        latency_ms: 1450,
        timestamp: new Date().toISOString(),
      };
      this.db.decisionLogs.unshift(decision);
      this.saveDB();

      return { status: "pending", message: "Venue matching agent executed successfully." };
    }

    // 9. Match suppliers: POST /weddings/:id/suppliers
    const matchSupplierMatch = cleanPath.match(/^\/weddings\/([^/]+)\/suppliers$/);
    if (matchSupplierMatch && method === "POST") {
      const weddingId = matchSupplierMatch[1];
      const body = options.body ? JSON.parse(options.body as string) : {};
      const category = body.category || "photography";

      const sup = INITIAL_SUPPLIERS.find((s) => s.category.toLowerCase().includes(category.toLowerCase())) || INITIAL_SUPPLIERS[1];
      const newBooking: BookingRecord = {
        id: `bk_${weddingId}_s_${Date.now()}`,
        wedding_id: weddingId,
        supplier_id: sup.id,
        status: "shortlisted",
        sourced_by_agent_id: "supplier_matcher",
        vendor_name: sup.name,
        vendor_kind: "supplier",
        vendor_category: sup.category,
        vendor_location: sup.location,
        pricing_summary: sup.pricing_summary,
        matching_rationale: sup.matching_rationale,
        draft_inquiry_email: sup.draft_inquiry_email,
        quote_total: sup.pricing_summary.total_amount,
        quote_currency: "EUR",
        allocated_amount: 3000,
        over_budget: false,
      };

      this.db.bookings.push(newBooking);

      const decision: AgentDecisionRecord = {
        id: `dec_${Date.now()}`,
        wedding_id: weddingId,
        agent_id: "supplier_matcher",
        status: "success",
        rationale_summary: `Matched ${sup.name} for ${category}. Pricing verified against Leinster 2026/2027 market benchmarks.`,
        confidence_score: 93,
        latency_ms: 1200,
        timestamp: new Date().toISOString(),
      };
      this.db.decisionLogs.unshift(decision);
      this.saveDB();

      return { status: "pending", message: `Supplier matching agent for ${category} executed successfully.` };
    }

    // 10. Replan: POST /weddings/:id/replan
    const replanMatch = cleanPath.match(/^\/weddings\/([^/]+)\/replan/);
    if (replanMatch && method === "POST") {
      const weddingId = replanMatch[1];
      const wedding = this.db.weddings.find((w) => w.id === weddingId);
      if (wedding) {
        wedding.status = "planning";
        this.saveDB();
      }
      return { status: "pending", message: "Intake planner re-enqueued." };
    }

    // 11. Concierge: POST /weddings/:id/concierge
    const conciergeMatch = cleanPath.match(/^\/weddings\/([^/]+)\/concierge$/);
    if (conciergeMatch && method === "POST") {
      const weddingId = conciergeMatch[1];
      const body = options.body ? JSON.parse(options.body as string) : {};
      const msg = (body.message || "").toLowerCase();
      const wedding = this.db.weddings.find((w) => w.id === weddingId) || this.db.weddings[0];

      let reply = `Based on your ${wedding.guest_count_estimate}-guest wedding plan in ${wedding.region} (€${wedding.budget_total.toLocaleString()} budget), here are my recommendations:`;

      if (msg.includes("budget") || msg.includes("cost") || msg.includes("spend")) {
        reply = `You have allocated €${wedding.budget_total.toLocaleString()} across 10 categories. The largest commitments are your venue (~€14,000) and catering (~€11,000). Your allocated contingency remains healthy at ~€2,000. Would you like me to identify any cost-optimization opportunities?`;
      } else if (msg.includes("venue") || msg.includes("hall") || msg.includes("estate")) {
        reply = `For ${wedding.guest_count_estimate} guests in ${wedding.region}, Powerscourt Estate and Tankardstown House are your top matched options. Both accommodate indoor/outdoor civil ceremonies and have availability for your seasonal window.`;
      } else if (msg.includes("photo") || msg.includes("camera") || msg.includes("video")) {
        reply = `We've matched Dasha Caffrey Photography for documentary coverage. Her full-day collection comes in at €3,200, which sits comfortably within your €3,500 photography budget.`;
      } else if (msg.includes("timeline") || msg.includes("next") || msg.includes("schedule")) {
        reply = `Your next critical milestone is locking in your venue agreement within the next 2 weeks to guarantee date availability. Following that, booking your photographer by next month will ensure top vendor retention.`;
      } else {
        reply = `I have updated your plan notes. For your celebration in ${wedding.region}, all vendor contracts, timeline milestones, and RSVPs are tracking smoothly. Let me know if you would like me to draft an inquiry email or adjust budget limits!`;
      }

      const decision: AgentDecisionRecord = {
        id: `dec_chat_${Date.now()}`,
        wedding_id: weddingId,
        agent_id: "concierge",
        status: "success",
        rationale_summary: `Answered question regarding "${msg.slice(0, 40)}" grounded in wedding state and budget allocations.`,
        confidence_score: 97,
        latency_ms: 820,
        timestamp: new Date().toISOString(),
      };
      this.db.decisionLogs.unshift(decision);
      this.saveDB();

      return { reply };
    }

    // 12. Payments: POST /payments/create-checkout-session or /checkout
    if (cleanPath.startsWith("/payments") || cleanPath.includes("checkout")) {
      // Unlock all weddings
      for (const w of this.db.weddings) {
        if (w.status === "preview" || w.status === "intake") {
          w.status = "planning";
        }
      }
      this.saveDB();
      return { status: "success", session_url: "/wedding" };
    }

    // 13. Metrics: GET /metrics
    if (cleanPath === "/metrics" || cleanPath === "/metrics/summary") {
      return {
        active_weddings: this.db.weddings.length,
        total_gmv: this.db.weddings.reduce((acc, w) => acc + w.budget_total, 0),
        avg_budget: Math.round(
          this.db.weddings.reduce((acc, w) => acc + w.budget_total, 0) / (this.db.weddings.length || 1)
        ),
        agent_decisions_count: this.db.decisionLogs.length,
        time_saved_hours: 48.5,
      };
    }

    // Default fallback: return empty array or success
    return [];
  }
}

export const mockService = new MockService();
