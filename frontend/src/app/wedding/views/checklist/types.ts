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
  groups: ChecklistGroup[];
}

export type Filter = "all" | "not_done" | "overdue";
