import { BrowserRouter, Routes, Route } from "react-router";
import { Layout } from "./design-system/Layout";
import { Landing } from "./views/Landing";
import { Experience } from "./views/Experience";
import { PlannerLayout } from "./planner/PlannerLayout";
import { Overview } from "./planner/views/Overview";
import { Clients } from "./planner/views/Clients";
import { Tasks } from "./planner/views/Tasks";
import { Subscriptions } from "./planner/views/Subscriptions";
import { Analytics } from "./planner/views/Analytics";
import { Concierge } from "./planner/views/Concierge";
import { WeddingLayout } from "./wedding/WeddingLayout";
import { Dashboard } from "./wedding/views/Dashboard";
import { Vendors } from "./wedding/views/Vendors";
import { Budget } from "./wedding/views/Budget";
import { Guests } from "./wedding/views/Guests";
import { Timeline } from "./wedding/views/Timeline";
import { SeatingPlan } from "./wedding/views/SeatingPlan";
import { Concierge as WeddingConcierge } from "./wedding/views/Concierge";

const basename = import.meta.env.BASE_URL.replace(/\/$/, "") || "/";

export default function App() {
  return (
    <BrowserRouter basename={basename}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/experience" element={<Experience />} />
          <Route path="*" element={<Landing />} />
        </Route>
        <Route path="/planner" element={<PlannerLayout />}>
          <Route index element={<Overview />} />
          <Route path="clients" element={<Clients />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="subscriptions" element={<Subscriptions />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="concierge" element={<Concierge />} />
          <Route path="*" element={<Overview />} />
        </Route>
        <Route path="/wedding" element={<WeddingLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="vendors" element={<Vendors />} />
          <Route path="budget" element={<Budget />} />
          <Route path="guests" element={<Guests />} />
          <Route path="seating" element={<SeatingPlan />} />
          <Route path="timeline" element={<Timeline />} />
          <Route path="concierge" element={<WeddingConcierge />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
