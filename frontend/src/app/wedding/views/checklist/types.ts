/** The checklist as GET /weddings/{id}/checklist returns it (PD-007). */

export type TaskLabel = "catch_up" | "overdue" | null;

export interface ChecklistTask {
  id: string;
  stage: string;
  title: string;
  notes: string | null;
  position: number;
  done: boolean;
  done_at: string | null;
  done_by_name: string | null;
  label: TaskLabel;
}

export interface ChecklistGroup {
  key: string;
  label: string;
  kind: "catch_up" | "stage";
  stage_keys: string[];
  due_on: string | null;
  add_to_stage: string;
  current: boolean;
  done: number;
  total: number;
  tasks: ChecklistTask[];
}

export interface Checklist {
  wedding_date: string | null;
  date_set_on: string | null;
  /** The couple's "This date is confirmed" switch (B48); false means provisional. */
  date_confirmed: boolean;
  today: string;
  done: number;
  total: number;
  overdue: number;
  /** Whether "Load my checklist" has run (PD-011); it runs once. */
  imported: boolean;
  groups: ChecklistGroup[];
}

/** What POST /weddings/{id}/checklist/import added, or would add on a practice run. */
export interface ImportResult {
  saved: boolean;
  wedding_date: string | null;
  owner_tasks: number;
  tradition_tasks: number;
  venue_tasks: number;
  ai_added: number;
  ai_skipped: number;
  timeline_rows_removed: number;
}

export type Filter = "all" | "not_done" | "overdue";
