# VenueFlow — AI Wedding Coordinator

> An AI Wedding Coordinator for couples and independent wedding planners.
> Fully rewritten as a modern React SPA running on Vite + Tailwind CSS with self-contained autonomous agent workflows.

---

## 1 · Overview

The average Irish wedding costs €33,000 and takes 250+ planning hours. A human coordinator charges €4,000–€8,500 — and **80% of couples can't afford one.** VenueFlow puts a wedding coordinator in every couple's pocket for **€299–€999 one-time**, and gives independent planners a way to clone themselves and serve 5× more clients for **€199–€499/mo.**

The product provides an autonomous coordinator experience that does the heavy lifting of a professional planner:
- **Intake & Planning Engine**: Validates budget realism against regional market benchmarks and drafts full budget lines and timelines.
- **Venue & Supplier Matcher**: Matches curated Irish venues and suppliers (photographers, florists, music, catering) based on region, capacity, budget, and aesthetic preferences.
- **Inquiry Drafting**: Generates ready-to-send personalized inquiry emails.
- **Concierge Assistant**: Real-time wedding coordinator advice grounded in live wedding details, budget status, and milestones.
- **Role-based Workspaces**:
  - **Couple Workspace**: Dashboard, Intake, Budget Breakdown, Vendor Shortlist, Timeline & Milestones, Guest Management, Seating Plan, and Concierge.
  - **Planner Workspace**: Multi-client Overview, Tasks, Subscriptions, Analytics, and Planner Concierge.
  - **Admin Workspace**: System metrics, Planners directory, and Agent Decision Logs with confidence scores and latency metrics.

---

## 2 · Technical Stack

- **Framework**: React 18 with TypeScript and Vite
- **Routing**: `react-router` v7 with role-based protected navigation
- **Styling**: Tailwind CSS v4 with custom warm-ivory / muted-gold typography (Cormorant Garamond, Montserrat, Great Vibes)
- **UI Components**: Vendored Radix UI primitives, Lucide icons, Material Symbols
- **Data & Agents**: Self-contained client-side state service (`mockService`) with localStorage persistence, supporting realistic simulated agent matching, budget calculation, and decision logging.
- **Port & Host**: Listens on port 3000 on host `0.0.0.0`

---

## 3 · Quick Start

```bash
# Install dependencies
npm install

# Run the development server
npm run dev

# Build for production
npm run build
```
