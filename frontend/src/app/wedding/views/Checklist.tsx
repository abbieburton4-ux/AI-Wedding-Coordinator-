import { useCallback, useEffect, useId, useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "../../shared/Icon";
import { Switch } from "../../components/ui/switch";
import { useApi, USE_FASTAPI_BACKEND } from "../../api";
import { useActiveWedding } from "../WeddingProvider";
import { formatDay, formatInstantDay } from "./budget/money";
import type { Checklist as ChecklistData, ChecklistGroup, ChecklistTask, Filter } from "./checklist/types";

type Req = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;
type Run = (fn: () => Promise<unknown>) => Promise<boolean>;

const focusRing =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary";
const inputClass =
  `bg-surface-container-low border border-outline-variant/40 rounded-full px-4 py-2 text-sm text-on-surface focus:border-primary ${focusRing}`;
const primaryButton =
  `bg-primary text-on-primary rounded-full px-5 py-2 font-button-text text-sm disabled:opacity-60 ${focusRing}`;
const linkButton =
  `text-sm text-on-surface-variant hover:text-primary underline-offset-4 hover:underline disabled:opacity-60 rounded ${focusRing}`;
const dangerLink =
  `text-sm text-on-surface-variant hover:text-error underline-offset-4 hover:underline disabled:opacity-60 rounded ${focusRing}`;

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "not_done", label: "Not done" },
  { key: "overdue", label: "Overdue" },
];

function visibleTasks(group: ChecklistGroup, filter: Filter): ChecklistTask[] {
  if (filter === "not_done") return group.tasks.filter((t) => !t.done);
  if (filter === "overdue") return group.tasks.filter((t) => t.label === "overdue");
  return group.tasks;
}

/**
 * The wedding's shared planning checklist (PD-007): stages in order with a count each,
 * an overall progress bar, a tick box per task, and stages that fold away with the
 * current one open. Everyone on the access list sees the same list; only owners and
 * editors get controls, and the API refuses changes from anyone else.
 */
export function Checklist() {
  const { activeWedding, myLevel } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;
  const { request } = useApi();
  const base = `/weddings/${weddingId}/checklist`;
  const canEdit = myLevel === "owner" || myLevel === "editor";

  const [data, setData] = useState<ChecklistData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  // Groups the couple opened or closed themselves; the rest follow "current".
  const [toggled, setToggled] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return;
    try {
      setData(await request<ChecklistData>(`/weddings/${weddingId}/checklist`));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Couldn't load the checklist.");
    }
  }, [weddingId, request]);

  useEffect(() => {
    load();
  }, [load]);

  const run: Run = useCallback(
    async (fn) => {
      setBusy(true);
      setError(null);
      try {
        await fn();
        await load();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "That didn't work. Please try again.");
        return false;
      } finally {
        setBusy(false);
      }
    },
    [load],
  );

  const shell = (children: ReactNode) => (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-6">
        <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary mb-2">
          Checklist
        </h1>
        <p className="text-on-surface-variant">
          Everything to do before and after the wedding, stage by stage. You both see the same list.
        </p>
        {!canEdit && myLevel && (
          <p className="text-sm text-on-surface-variant mt-2">You can see the checklist but not change it.</p>
        )}
      </div>
      {children}
    </main>
  );

  if (!USE_FASTAPI_BACKEND) {
    return shell(<p className="text-on-surface-variant">The checklist needs the app's server, which is switched off.</p>);
  }
  if (loadError) {
    return shell(
      <div role="alert" className="text-on-surface">
        <p className="mb-2">The checklist didn't load: {loadError}</p>
        <button type="button" onClick={load} className={linkButton}>Try again</button>
      </div>,
    );
  }
  if (!data) {
    return shell(
      <div className="space-y-4" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 rounded-[2rem] bg-surface-container-low animate-pulse" />
        ))}
        <p className="sr-only">Loading the checklist…</p>
      </div>,
    );
  }

  const pct = data.total ? Math.round((data.done * 100) / data.total) : 0;
  const shown = data.groups
    .map((g) => ({ group: g, tasks: visibleTasks(g, filter) }))
    .filter(({ tasks }) => filter === "all" || tasks.length > 0);
  // "Catch up" is due on the same day as the first stage still ahead when the date was set.
  const catchUpDue = data.groups.find((g) => g.kind === "catch_up")?.due_on ?? null;
  const dueWith = catchUpDue ? data.groups.find((g) => g.kind === "stage" && g.due_on === catchUpDue)?.label ?? null : null;

  return shell(
    <>
      <DateCard base={base} data={data} canEdit={canEdit} run={run} request={request} busy={busy} />

      {error && <p role="alert" className="mb-6 text-sm text-error">{error}</p>}

      <section aria-label="Progress" className="mb-6 bg-surface-container-lowest rounded-[2rem] border border-outline-variant/20 p-5">
        <div className="flex items-baseline justify-between mb-2">
          <p className="font-button-text text-on-surface">
            {data.done} of {data.total} done
          </p>
          <p className="text-sm text-on-surface-variant">{pct}%</p>
        </div>
        <div
          role="progressbar"
          aria-label="Checklist progress"
          aria-valuemin={0}
          aria-valuemax={data.total}
          aria-valuenow={data.done}
          aria-valuetext={`${data.done} of ${data.total} tasks done`}
          className="h-3 rounded-full bg-surface-container-high overflow-hidden"
        >
          <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      </section>

      <div role="group" aria-label="Show" className="flex flex-wrap gap-2 mb-6">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            aria-pressed={filter === f.key}
            onClick={() => setFilter(f.key)}
            className={
              `px-4 py-2 rounded-full text-sm font-button-text border ${focusRing} ` +
              (filter === f.key
                ? "bg-primary text-on-primary border-primary"
                : "bg-surface-container-low text-on-surface border-outline-variant/40 hover:border-primary")
            }
          >
            {f.label}
            {f.key === "overdue" && data.overdue > 0 ? ` (${data.overdue})` : ""}
          </button>
        ))}
      </div>

      {data.total === 0 && (
        <p className="text-sm text-on-surface-variant mb-6">
          {canEdit
            ? "There are no tasks yet. Add your own to any stage below."
            : "There are no tasks yet."}
        </p>
      )}
      {filter !== "all" && shown.length === 0 && (
        <p className="text-sm text-on-surface-variant mb-6">
          {filter === "overdue" ? "Nothing is overdue." : "Everything is done."}
        </p>
      )}

      <div className="space-y-4">
        {shown.map(({ group, tasks }) => {
          const open = filter !== "all" ? true : toggled[group.key] ?? group.current;
          return (
            <GroupCard
              key={group.key}
              base={base}
              group={group}
              tasks={tasks}
              open={open}
              onToggle={() => setToggled((t) => ({ ...t, [group.key]: !open }))}
              dueWith={group.kind === "catch_up" ? dueWith : null}
              canEdit={canEdit}
              canAdd={canEdit && filter === "all"}
              run={run}
              request={request}
              busy={busy}
            />
          );
        })}
      </div>
    </>,
  );
}

// ---- The wedding date ------------------------------------------------------------------

function DateCard({
  base, data, canEdit, run, request, busy,
}: { base: string; data: ChecklistData; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(data.wedding_date ?? "");
  const id = useId();
  const confirmedId = useId();

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!value) return;
    const ok = await run(() => request(`${base}/date`, json("PUT", { wedding_date: value })));
    if (ok) setEditing(false);
  };

  return (
    <section aria-label="Wedding date" className="mb-6 bg-primary-container/10 border border-primary-container/20 rounded-[2rem] p-5">
      {data.wedding_date ? (
        <>
          <p className="text-xs text-on-surface-variant">Wedding date</p>
          <p className="font-headline-sm text-headline-sm text-on-surface">{formatDay(data.wedding_date)}</p>
          <p className="text-sm text-on-surface-variant mt-1 flex items-center gap-1">
            <Icon name={data.date_confirmed ? "event_available" : "info"} size={16} />
            {data.date_confirmed
              ? "Your date is confirmed. If it ever changes, every due date moves with it."
              : "Dates are provisional. Every due date moves if you change the wedding date."}
          </p>
          <div className="mt-3 flex items-center gap-3">
            <Switch
              id={confirmedId}
              checked={data.date_confirmed}
              // Viewers see the state; only owners and editors can change it (the API
              // checks too). Not disabled while saving, so keyboard focus stays put.
              disabled={!canEdit}
              aria-busy={busy}
              onCheckedChange={(confirmed) => {
                if (busy) return;
                run(() => request(`${base}/date-confirmed`, json("PUT", { confirmed })));
              }}
              className={focusRing}
            />
            <label
              htmlFor={confirmedId}
              className={`text-sm text-on-surface ${canEdit ? "cursor-pointer" : ""}`}
            >
              This date is confirmed
            </label>
          </div>
        </>
      ) : (
        <p className="text-on-surface">
          Set your wedding date to see when each stage is due.
          {!canEdit && " The couple can set it."}
        </p>
      )}
      {canEdit && !editing && (
        <button
          type="button"
          onClick={() => {
            setValue(data.wedding_date ?? "");
            setEditing(true);
          }}
          className={`${linkButton} mt-3`}
        >
          {data.wedding_date ? "Change the date" : "Set the date"}
        </button>
      )}
      {canEdit && editing && (
        <form onSubmit={save} className="mt-3 flex flex-wrap items-end gap-3">
          <span className="flex flex-col gap-1">
            <label htmlFor={id} className="text-xs text-on-surface-variant">Wedding date</label>
            <input
              id={id}
              type="date"
              required
              min={data.today}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className={inputClass}
            />
          </span>
          <button type="submit" disabled={busy || !value} className={primaryButton}>Save date</button>
          <button type="button" onClick={() => setEditing(false)} className={linkButton}>Cancel</button>
        </form>
      )}
    </section>
  );
}

// ---- A stage, or the "Catch up" group --------------------------------------------------

function GroupCard({
  base, group, tasks, open, onToggle, dueWith, canEdit, canAdd, run, request, busy,
}: {
  base: string; group: ChecklistGroup; tasks: ChecklistTask[]; open: boolean; onToggle: () => void;
  dueWith: string | null; canEdit: boolean; canAdd: boolean; run: Run; request: Req; busy: boolean;
}) {
  const panelId = useId();
  const overdue = group.tasks.some((t) => t.label === "overdue");
  const catchUp = group.kind === "catch_up";

  return (
    <section className="bg-wedding-white custom-shadow rounded-[2rem] border border-outline-variant/10">
      <h2>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={onToggle}
          className={`w-full flex items-center gap-3 p-5 text-left rounded-[2rem] hover:bg-primary/5 ${focusRing}`}
        >
          <Icon name={open ? "expand_less" : "expand_more"} className="text-on-surface-variant shrink-0" />
          <span className="flex-1 min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-headline-sm text-lg text-on-surface">{group.label}</span>
              {overdue && <Badge tone="error">Overdue</Badge>}
              {group.current && !catchUp && <Badge tone="primary">Now</Badge>}
            </span>
            {group.due_on && (
              <span className="block font-body-md text-sm text-on-surface-variant mt-0.5">
                Due {formatDay(group.due_on)}
                {catchUp && dueWith ? `, with ${dueWith}` : ""}
              </span>
            )}
          </span>
          <span className="text-sm font-button-text text-on-surface-variant shrink-0" aria-label={`${group.done} of ${group.total} done`}>
            {group.done} / {group.total}
          </span>
        </button>
      </h2>
      <div id={panelId} hidden={!open} className="px-5 pb-5">
        {catchUp && (
          <p className="text-sm text-on-surface-variant mb-3">
            These stages had already passed when the date was set, so they're gathered here to catch up on.
          </p>
        )}
        {tasks.length === 0 ? (
          <p className="text-sm text-on-surface-variant mb-3">No tasks in this stage yet.</p>
        ) : (
          <ul className="divide-y divide-outline-variant/10">
            {tasks.map((t) => (
              <TaskRow key={t.id} base={base} task={t} canEdit={canEdit} run={run} request={request} busy={busy} />
            ))}
          </ul>
        )}
        {canAdd && <AddTask base={base} stage={group.add_to_stage} groupLabel={group.label} run={run} request={request} busy={busy} />}
      </div>
    </section>
  );
}

function Badge({ tone, children }: { tone: "error" | "primary" | "catch"; children: ReactNode }) {
  const cls = {
    error: "bg-error/10 text-error",
    primary: "bg-primary/15 text-primary",
    catch: "bg-tertiary-fixed text-on-tertiary-fixed",
  }[tone];
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider ${cls}`}>{children}</span>;
}

// ---- One task ---------------------------------------------------------------------------

function TaskRow({
  base, task, canEdit, run, request, busy,
}: { base: string; task: ChecklistTask; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [notes, setNotes] = useState(task.notes ?? "");
  const id = useId();
  const url = `${base}/tasks/${task.id}`;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    const ok = await run(() => request(url, json("PATCH", { title, notes })));
    if (ok) setEditing(false);
  };

  if (editing) {
    return (
      <li className="py-3">
        <form onSubmit={save} className="flex flex-col gap-2">
          <label htmlFor={`${id}-t`} className="text-xs text-on-surface-variant">Task</label>
          <input id={`${id}-t`} required maxLength={300} value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
          <label htmlFor={`${id}-n`} className="text-xs text-on-surface-variant">Notes (optional)</label>
          <textarea
            id={`${id}-n`}
            maxLength={2000}
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className={`${inputClass} rounded-[1.25rem]`}
          />
          <span className="flex gap-3">
            <button type="submit" disabled={busy || !title.trim()} className={primaryButton}>Save</button>
            <button
              type="button"
              onClick={() => {
                setTitle(task.title);
                setNotes(task.notes ?? "");
                setEditing(false);
              }}
              className={linkButton}
            >
              Cancel
            </button>
          </span>
        </form>
      </li>
    );
  }

  return (
    <li className="py-3 flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={task.done}
        // Not disabled while saving, so keyboard focus stays on the box after a tick.
        disabled={!canEdit}
        aria-busy={busy}
        onChange={(e) => {
          if (busy) return;
          const done = e.target.checked;
          run(() => request(`${url}/done`, json("PUT", { done })));
        }}
        className={`mt-1 h-5 w-5 shrink-0 accent-primary cursor-pointer disabled:cursor-default ${focusRing}`}
      />
      <div className="flex-1 min-w-0">
        <label htmlFor={id} className={`block ${task.done ? "line-through text-on-surface-variant" : "text-on-surface"} ${canEdit ? "cursor-pointer" : ""}`}>
          {task.title}
        </label>
        <span className="flex flex-wrap items-center gap-2 mt-1">
          {task.label === "catch_up" && <Badge tone="catch">Catch up</Badge>}
          {task.label === "overdue" && <Badge tone="error">Overdue</Badge>}
          {task.done && task.done_by_name && (
            <span className="text-xs text-on-surface-variant">
              Ticked by {task.done_by_name}
              {task.done_at ? ` on ${formatInstantDay(task.done_at)}` : ""}
            </span>
          )}
        </span>
        {task.notes && <p className="text-sm text-on-surface-variant mt-1 whitespace-pre-line">{task.notes}</p>}
        {canEdit && (
          <span className="flex flex-wrap gap-3 mt-1">
            {confirm ? (
              <span className="flex flex-wrap items-center gap-2 text-sm">
                <span>Delete this task?</span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => request(url, json("DELETE")))}
                  className={`text-error font-bold underline-offset-4 hover:underline rounded ${focusRing}`}
                >
                  Yes, delete
                </button>
                <button type="button" disabled={busy} onClick={() => setConfirm(false)} className={linkButton}>Cancel</button>
              </span>
            ) : (
              <>
                <button type="button" onClick={() => setEditing(true)} className={linkButton} aria-label={`Edit "${task.title}"`}>
                  Edit
                </button>
                <button type="button" onClick={() => setConfirm(true)} className={dangerLink} aria-label={`Delete "${task.title}"`}>
                  Delete
                </button>
              </>
            )}
          </span>
        )}
      </div>
    </li>
  );
}

function AddTask({
  base, stage, groupLabel, run, request, busy,
}: { base: string; stage: string; groupLabel: string; run: Run; request: Req; busy: boolean }) {
  const [title, setTitle] = useState("");
  const id = useId();

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    const ok = await run(() => request(`${base}/tasks`, json("POST", { stage, title })));
    if (ok) setTitle("");
  };

  return (
    <form onSubmit={add} className="mt-3 flex flex-wrap items-end gap-2">
      <span className="flex flex-col gap-1 flex-grow min-w-[12rem]">
        <label htmlFor={id} className="text-xs text-on-surface-variant">Add a task to {groupLabel}</label>
        <input
          id={id}
          autoComplete="off"
          maxLength={300}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={inputClass}
        />
      </span>
      <button type="submit" disabled={busy || !title.trim()} className={primaryButton}>Add</button>
    </form>
  );
}
