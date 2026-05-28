"""
VenueFlow.ie — REAL seed data (Irish venues + suppliers)
=========================================================
Drop-in replacement for the mock `venues` / `suppliers` lists in db.py / seed.

VERIFICATION POLICY (read before shipping to judges):
  - name, region, venue_type/category, website  -> VERIFIED real businesses
        (confirmed via public web search, May 2026).
  - capacity_min/max                            -> from published venue info where
        available; otherwise a realistic estimate for the venue type (flagged).
  - email / phone                               -> SHIP AS null BY DEFAULT.
        2026-05-28 reconciliation: an earlier draft pattern-filled the venue rows
        with `weddings@{domain}` guesses, all flagged `_verify: true` with zero
        nulls — which contradicted this very policy. Those guesses are now nulled.
        A guessed address is worse than a null: a judge emailing a fabricated
        address that bounces (or worse, reaches a real inbox that never opted in)
        destroys the honesty claim this file exists to make. `_verify: true` now
        means exactly "no confirmed contact; do NOT send." Absence is represented
        as null, never a guess. A separate web-verification pass upgrades specific
        nulls to confirmed enquiry contacts WITH a cited source (see commit history).
  - pricing (`pricing_summary` / `pricing`)     -> INDICATIVE only, grounded in
        published Irish 2026 ranges (weddingsonline avg venue spend €15,087;
        per-head €85–€200 by tier; halls €15–€30 pp). These are seed estimates for
        the matching agent to reason over, NOT confirmed quotes. `_indicative: true`.

SAFETY: even once a contact is confirmed real, the system must not email real
venues during the pilot. See agents.resolve_inquiry_recipient — every agent-
drafted inquiry routes to a founder-controlled inbox until a venue has explicitly
opted in. "Confirmed real" is not the same as "contactable".

Sources surfaced during research (May 2026): weddingsonline.ie, Ladybird Ever After
castle guide, Dasha Caffrey / Olga Hogan / Kevin Kheffache photographer venue guides,
Irish Wedding Awards 2026 finalists/winners (Oceanic Awards), irishweddingbands.ie,
individual supplier sites.
"""

import json

# =============================================================================
# VENUES  (id, name, address, region, venue_type, cap_min, cap_max,
#          indoor_outdoor[1=outdoor-option/2=indoor-only], on_site_accom[1/0],
#          contact_info, pricing_summary)
# =============================================================================
venues = [

    # ---- LUXURY CASTLE / COUNTRY HOUSE (top tier) ----
    ("venue_adare_manor", "Adare Manor", "Adare, Co. Limerick", "Limerick",
     "country_house", 100, 350, 1, 1,
     json.dumps({"website": "https://www.adaremanor.com", "email": None, "phone": "+35361605200", "enquiry_url": "https://www.adaremanor.com/weddings/weddings-enquiry/", "_method": "contact_form", "_checked": "2026-05-28"}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 250, "currency": "EUR", "min_spend": None,
                 "note": "5-star resort, 840 acres, Grand Ballroom to 350, Michelin restaurant. Ultra-luxury tier.", "_indicative": True})),

    ("venue_ashford_castle", "Ashford Castle", "Cong, Co. Mayo", "Mayo",
     "country_house", 20, 120, 1, 1,
     json.dumps({"website": "https://www.ashfordcastle.com", "email": None, "phone": "+353949546003", "enquiry_url": "https://www.ashfordcastle.com/weddings/", "_method": "contact_form", "_checked": "2026-05-28"}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 240, "currency": "EUR", "min_spend": None,
                 "note": "13th-century castle hotel on Lough Corrib. Crown-jewel luxury; intimate-to-mid weddings.", "_indicative": True})),

    ("venue_dromoland_castle", "Dromoland Castle", "Newmarket-on-Fergus, Co. Clare", "Clare",
     "country_house", 50, 250, 1, 1,
     json.dumps({"website": "https://www.dromoland.ie", "email": "sales@dromoland.ie", "phone": "+35361368144", "_method": "published_email", "_checked": "2026-05-28"}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 200, "currency": "EUR", "min_spend": None,
                 "note": "16th-century castle estate, 450 acres, golf. High-luxury.", "_indicative": True})),

    ("venue_luttrellstown", "Luttrellstown Castle Resort", "Clonsilla, Dublin 15", "Dublin",
     "country_house", 20, 180, 1, 1,
     json.dumps({"website": "https://www.luttrellstowncastle.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 185, "currency": "EUR", "min_spend": None,
                 "note": "15th-century exclusive-use estate just outside Dublin; 20 intimate to 180 grand.", "_indicative": True})),

    ("venue_castle_leslie", "Castle Leslie Estate", "Glaslough, Co. Monaghan", "Monaghan",
     "country_house", 70, 260, 1, 1,
     json.dumps({"website": "https://www.castleleslie.com", "email": "events@castleleslie.com", "phone": "+3534788100", "_method": "published_email", "_checked": "2026-05-28"}),
     json.dumps({"rental_fee": 5000, "average_cost_per_head": 120, "currency": "EUR", "min_spend": 18000,
                 "note": "19th-century castle, lakes & woodlands. Peak season ~150 guest min.", "_indicative": True})),

    ("venue_kilkea_castle", "Kilkea Castle", "Castledermot, Co. Kildare", "Kildare",
     "country_house", 40, 270, 1, 1,
     json.dumps({"website": "https://www.kilkeacastle.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 140, "currency": "EUR", "min_spend": None,
                 "note": "800+ yrs hosting; Baronial Hall to 270, Hermione's 120, Restaurant 1180 to 60.", "_indicative": True})),

    ("venue_markree_castle", "Markree Castle", "Collooney, Co. Sligo", "Sligo",
     "country_house", 50, 190, 1, 1,
     json.dumps({"website": "https://www.markreecastle.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": 4000, "average_cost_per_head": 110, "currency": "EUR", "min_spend": 14000,
                 "note": "Exclusive-hire Gothic castle, private chapel, gardens.", "_indicative": True})),

    ("venue_lough_eske", "Lough Eske Castle", "Donegal Town, Co. Donegal", "Donegal",
     "country_house", 60, 200, 1, 1,
     json.dumps({"website": "https://www.lougheskecastlehotel.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 110, "currency": "EUR", "min_spend": None,
                 "note": "5-star castle hotel; published packages ~€95–€119pp (120 guests).", "_indicative": True})),

    ("venue_tankardstown", "Tankardstown House", "Slane, Co. Meath", "Meath",
     "country_house", 50, 230, 1, 1,
     json.dumps({"website": "https://www.tankardstown.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 150, "currency": "EUR", "min_spend": None,
                 "note": "18th-c country house, 40 min from Dublin. Orangery to 230 + walled-garden ceremony.", "_indicative": True})),

    ("venue_virginia_park", "Virginia Park Lodge", "Virginia, Co. Cavan", "Cavan",
     "country_house", 40, 150, 1, 1,
     json.dumps({"website": "https://www.virginiaparklodge.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 145, "currency": "EUR", "min_spend": None,
                 "note": "Period hunting lodge on 100 acres; food-led, relaxed-luxury.", "_indicative": True})),

    # ---- HOTELS ----
    ("venue_marker_hotel", "The Marker Hotel", "Grand Canal Square, Dublin 2", "Dublin",
     "hotel", 60, 220, 2, 1,
     json.dumps({"website": "https://www.themarkerhoteldublin.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 125, "currency": "EUR", "min_spend": None,
                 "note": "5-star design hotel, Docklands. Packages from ~€125pp.", "_indicative": True})),

    ("venue_slieve_donard", "Slieve Donard Resort & Spa", "Newcastle, Co. Down", "Down",
     "hotel", 80, 350, 1, 1,
     json.dumps({"website": "https://www.marineandlawn.com/slieve-donard", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 95, "currency": "GBP", "min_spend": None,
                 "note": "NI seaside resort, Mourne Mountains. Published from ~£82pp Sun–Thu.", "_indicative": True})),

    ("venue_hotel_doolin", "Hotel Doolin", "Doolin, Co. Clare", "Clare",
     "hotel", 60, 300, 1, 1,
     json.dumps({"website": "https://www.hoteldoolin.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": 3000, "average_cost_per_head": 85, "currency": "EUR", "min_spend": 10000,
                 "note": "Eco-friendly, barn-style, near Cliffs of Moher; strong local seafood menu.", "_indicative": True})),

    # ---- FARM / BARN / ALTERNATIVE ----
    ("venue_ballymagarvey", "Ballymagarvey Village", "Balrath, Co. Meath", "Meath",
     "farm", 50, 220, 1, 1,
     json.dumps({"website": "https://www.ballymagarvey.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 110, "currency": "EUR", "min_spend": None,
                 "note": "Restored 800-yr 'village' around a courtyard; exclusive use; barn + banqueting hall.", "_indicative": True})),

    ("venue_cloughjordan", "Cloughjordan House", "Cloughjordan, Co. Tipperary", "Tipperary",
     "farm", 60, 220, 1, 1,
     json.dumps({"website": "https://www.cloughjordanhouse.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 100, "currency": "EUR", "min_spend": None,
                 "note": "Family-run country house, farm-to-table, sustainability-led, informal.", "_indicative": True})),

    ("venue_mount_druid", "Mount Druid", "Castletown Geoghegan, Co. Westmeath", "Westmeath",
     "farm", 50, 220, 1, 1,
     json.dumps({"website": "https://mountdruid.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": None, "average_cost_per_head": 90, "currency": "EUR", "min_spend": None,
                 "note": "Alternative/eco venue, 100 acres; Tin Chapel + Barn + Boathouse; organic, quirky.", "_indicative": True})),

    ("venue_millhouse", "The Millhouse Slane", "Slane, Co. Meath", "Meath",
     "farm", 80, 200, 1, 1,
     json.dumps({"website": "https://www.themillhouse.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": 3500, "average_cost_per_head": 95, "currency": "EUR", "min_spend": 12000,
                 "note": "Industrial heritage mill on the River Boyne; bohemian atmosphere.", "_indicative": True})),

    # ---- RESTAURANT (micro-wedding) ----
    ("venue_aniar", "Aniar Restaurant", "Lower Dominick St, Galway City, Co. Galway", "Galway",
     "restaurant", 10, 45, 2, 0,
     json.dumps({"website": "https://www.aniarrestaurant.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"rental_fee": 1000, "average_cost_per_head": 150, "currency": "EUR", "min_spend": 4000,
                 "note": "Michelin-star tasting-menu micro-weddings; max ~45 guests.", "_indicative": True})),

    # ---- BUDGET: GAA CLUB / COMMUNITY HALL ----
    # NOTE: GAA clubs & community halls rarely publish wedding-enquiry contacts.
    # These two rows are TEMPLATES so the budget venue_type is represented for the
    # matching agent. Replace name+contact with a specific local hall you verify.
    ("venue_gaa_template", "[TEMPLATE] Local GAA Clubhouse Hall", "Co. Offaly", "Offaly",
     "gaa_clubhouse", 40, 150, 2, 0,
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Replace with a real local GAA hall (e.g. confirm via club Facebook/secretary)."}),
     json.dumps({"rental_fee": 350, "average_cost_per_head": 25, "currency": "EUR", "min_spend": 0,
                 "note": "Dry-hire hall; self-catering allowed; bar staff sometimes included.", "_indicative": True})),

    ("venue_community_hall_template", "[TEMPLATE] Community Celebration Hall", "Co. Sligo", "Sligo",
     "community_hall", 30, 200, 2, 0,
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Replace with a real community hall you confirm (parish/community centre office)."}),
     json.dumps({"rental_fee": 200, "average_cost_per_head": 15, "currency": "EUR", "min_spend": 0,
                 "note": "Basic dry-hire; BYO caterers and drinks.", "_indicative": True})),
]

# =============================================================================
# SUPPLIERS  (id, name, category, region, contact_info, pricing, extra/styles)
# =============================================================================
suppliers = [

    # ---- PHOTOGRAPHY (real Irish wedding photographers) ----
    ("sup_dasha_caffrey", "Dasha Caffrey Photography", "photography", "Dublin",
     json.dumps({"website": "https://www.dashacaffrey.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 2800, "currency": "EUR", "note": "Full-day documentary coverage; nationwide.", "_indicative": True}),
     json.dumps({"styles": ["documentary", "natural_light", "storytelling"]})),

    ("sup_olga_hogan", "Olga Hogan Photography", "photography", "Dublin",
     json.dumps({"website": "https://www.olgahoganphotography.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 2600, "currency": "EUR", "note": "Relaxed, candid documentary style.", "_indicative": True}),
     json.dumps({"styles": ["documentary", "candid", "relaxed"]})),

    ("sup_kevin_kheffache", "Kevin Kheffache Photography", "photography", "Galway",
     json.dumps({"website": "https://www.kevinkheffache.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 2400, "currency": "EUR", "note": "Castle & countryside weddings nationwide.", "_indicative": True}),
     json.dumps({"styles": ["natural_light", "scenic", "story-driven"]})),

    # ---- VIDEOGRAPHY (real) ----
    ("sup_dear_oliver", "Dear Oliver", "videography", "Dublin",
     json.dumps({"website": "https://www.dearoliver.co", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 2900, "currency": "EUR", "note": "Luxury destination cinematic films; highlight + feature.", "_indicative": True}),
     json.dumps({"styles": ["cinematic", "luxury", "highlight-film"]})),

    ("sup_edit_house", "Edit House Productions", "videography", "Galway",
     json.dumps({"website": "https://edithouse.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 2200, "currency": "EUR", "note": "Documentary-led wedding films, west of Ireland.", "_indicative": True}),
     json.dumps({"styles": ["documentary", "natural", "coastal"]})),

    # ---- MUSIC: BANDS (real, via irishweddingbands.ie agency) ----
    ("sup_band_the_firm", "The Firm (Wedding Band)", "music", "Dublin",
     json.dumps({"website": "https://www.irishweddingbands.ie", "email": None, "phone": None, "_verify": True,
                 "note": "Booked via Irish Wedding Bands / Audionetworks agency."}),
     json.dumps({"package_price": 2600, "currency": "EUR", "note": "One of Ireland's most-booked party bands (5,000+ gigs).", "_indicative": True}),
     json.dumps({"styles": ["party", "pop", "rock", "crowd-pleaser"]})),

    ("sup_band_midnight_revellers", "The Midnight Revellers", "music", "Dublin",
     json.dumps({"website": "https://www.irishweddingbands.ie", "email": None, "phone": None, "_verify": True,
                 "note": "Booked via Irish Wedding Bands agency."}),
     json.dumps({"package_price": 2200, "currency": "EUR", "note": "Trad-meets-modern; scalable 3–4 piece, ceremony to party.", "_indicative": True}),
     json.dumps({"styles": ["trad", "folk", "modern", "party"]})),

    # ---- MUSIC: CEREMONY TRAD ----
    ("sup_sligo_trad_trio", "Sligo Trad Ceremony Trio", "music", "Sligo",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Generic trad-trio slot — verify a specific act (e.g. via weddingbandlist.com Sligo)."}),
     json.dumps({"package_price": 750, "currency": "EUR", "note": "Fiddle/harp/pipes for ceremony + drinks reception.", "_indicative": True}),
     json.dumps({"styles": ["traditional", "celtic", "instrumental"]})),

    # ---- FLORALS (real) ----
    ("sup_jill_wild", "Wild / Jill Wild Flowersmith", "florals", "Cork",
     json.dumps({"website": "https://www.wild.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 1800, "currency": "EUR", "note": "Botanical, sculptural, editorial floral design.", "_indicative": True}),
     json.dumps({"styles": ["botanical", "sculptural", "editorial", "wild"]})),

    ("sup_fleur_weddings", "Fleur Weddings", "florals", "Dublin",
     json.dumps({"website": "https://fleurweddings.ie", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 1500, "currency": "EUR", "note": "Boutique bridal florist + venue stylist; natural, timeless.", "_indicative": True}),
     json.dumps({"styles": ["natural", "elegant", "timeless"]})),

    ("sup_southgate_florist", "Southgate Florist", "florals", "Louth",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Drogheda; Irish Wedding Awards 2026 finalist. Confirm site/contact."}),
     json.dumps({"package_price": 1400, "currency": "EUR", "note": "Full bridal floral packages.", "_indicative": True}),
     json.dumps({"styles": ["classic", "seasonal"]})),

    # ---- CATERING (real, Irish Wedding Awards 2026 finalists) ----
    ("sup_skg_catering", "SKG Catering", "catering", "Galway",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Galway; Irish Wedding Awards 2026 finalist. Confirm site/contact."}),
     json.dumps({"per_head_price": 55, "currency": "EUR", "note": "Full-service wedding catering, west of Ireland.", "_indicative": True}),
     json.dumps({"styles": ["modern-irish", "plated", "buffet"]})),

    ("sup_andrew_holmes", "Andrew Holmes Catering", "catering", "Wicklow",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Kilcoole; Irish Wedding Awards 2026 finalist. Confirm site/contact."}),
     json.dumps({"per_head_price": 60, "currency": "EUR", "note": "Outside/marquee catering; Leinster.", "_indicative": True}),
     json.dumps({"styles": ["modern-irish", "marquee", "plated"]})),

    ("sup_hog_roast_meath", "Hog Roast Caterer (Co. Meath)", "catering", "Meath",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Co. Meath; Irish Wedding Awards 2026 finalist (casual category). Confirm contact."}),
     json.dumps({"per_head_price": 30, "currency": "EUR", "note": "Spit/hog roast casual catering.", "_indicative": True}),
     json.dumps({"styles": ["spit-roast", "casual", "rustic"]})),

    # ---- OFFICIANT / CELEBRANT (real, registered solemnisers) ----
    ("sup_daragh_doyle_celebrant", "Daragh Doyle Celebrant", "officiant", "Wicklow",
     json.dumps({"website": "https://www.daraghdoylecelebrant.com", "email": None, "phone": None, "_verify": True}),
     json.dumps({"package_price": 500, "currency": "EUR", "note": "Registered solemniser; Dublin/Wicklow/Wexford; legal + custom.", "_indicative": True}),
     json.dumps({"styles": ["personal", "warm", "secular-or-religious"]})),

    ("sup_rosemary_hartigan", "Rosemary Hartigan Celebrant", "officiant", "Wexford",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Wexford; Irish Wedding Awards 2026 Celebrant finalist. Confirm site/contact."}),
     json.dumps({"package_price": 450, "currency": "EUR", "note": "Personalised legal ceremonies.", "_indicative": True}),
     json.dumps({"styles": ["personal", "heartfelt"]})),

    ("sup_dominic_moore", "Cork Humanist Ceremonies (Dominic Moore)", "officiant", "Cork",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Legal solemniser + humanist celebrant, Cork. Confirm site/contact."}),
     json.dumps({"package_price": 450, "currency": "EUR", "note": "Humanist / secular legal ceremonies.", "_indicative": True}),
     json.dumps({"styles": ["humanist", "secular", "personal"]})),

    # ---- DJ ----
    ("sup_dj_template_kerry", "Kerry Wedding DJ", "dj", "Kerry",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Generic DJ slot — verify a specific act via weddingbandlist.com / weddingdates.ie Kerry."}),
     json.dumps({"package_price": 600, "currency": "EUR", "note": "Pro DJ, sound + lights, 10pm–2am.", "_indicative": True}),
     json.dumps({"styles": ["all-genres", "charts", "party"]})),

    # ---- CAKE ----
    ("sup_cake_template_dublin", "Dublin Wedding Cake Studio", "cake", "Dublin",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Generic cake slot — verify a specific baker via weddingdates.ie / IWA finalists."}),
     json.dumps({"package_price": 480, "currency": "EUR", "note": "3-tier, serves ~100; buttercream or fondant.", "_indicative": True}),
     json.dumps({"styles": ["modern", "buttercream", "floral-detail"]})),

    # ---- HAIR & MAKEUP (real) ----
    ("sup_edel_hennessy_hair", "Edel Hennessy Hair", "hair_makeup", "Cavan",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True,
                 "note": "Cavan; Irish Wedding Awards 2026 finalist. Confirm site/contact."}),
     json.dumps({"package_price": 650, "currency": "EUR", "note": "Bridal hair (bride + party), on-location, trial incl.", "_indicative": True}),
     json.dumps({"styles": ["bridal", "soft-glam"]})),

    # ---- TRANSPORT ----
    ("sup_transport_template_dublin", "Vintage Wedding Cars (Dublin)", "transport", "Dublin",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Generic transport slot — verify a specific operator (e.g. weddingdates.ie Dublin transport)."}),
     json.dumps({"package_price": 650, "currency": "EUR", "note": "Vintage car + chauffeur, ~3 hrs Dublin/Wicklow.", "_indicative": True}),
     json.dumps({"styles": ["vintage", "classic", "luxury"]})),

    # ---- STATIONERY ----
    ("sup_stationery_template", "Irish Letterpress Stationery", "stationery", "Sligo",
     json.dumps({"website": None, "email": None, "phone": None, "_verify": True, "_template": True,
                 "note": "Generic stationery slot — verify a specific studio (e.g. weddingdates.ie)."}),
     json.dumps({"package_price": 450, "currency": "EUR", "note": "~100 invite suites + day-of stationery.", "_indicative": True}),
     json.dumps({"styles": ["letterpress", "minimal", "earthy"]})),
]


def summary():
    real_v = sum(1 for v in venues if "_template" not in v[9])
    real_s = sum(1 for s in suppliers if "_template" not in s[4])
    print(f"Venues: {len(venues)} ({real_v} real, {len(venues)-real_v} template)")
    print(f"Suppliers: {len(suppliers)} ({real_s} real, {len(suppliers)-real_s} template)")
    cats = {}
    for s in suppliers:
        cats[s[2]] = cats.get(s[2], 0) + 1
    print("Supplier categories:", cats)
    vt = {}
    for v in venues:
        vt[v[4]] = vt.get(v[4], 0) + 1
    print("Venue types:", vt)


if __name__ == "__main__":
    summary()
