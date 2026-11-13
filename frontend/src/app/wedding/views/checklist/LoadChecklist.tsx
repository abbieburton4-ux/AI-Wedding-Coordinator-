import { useId, useRef, useState, type ChangeEvent } from "react";
import { formatDay } from "../budget/money";
import { tapArea } from "../budget/sections";
import type { ImportResult } from "./types";

type Req = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;

const focusRing =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary";
const primaryButton =
  `bg-primary text-on-primary rounded-full px-5 py-2 font-button-text text-sm disabled:opacity-60 min-h-11 sm:min-h-0 ${focusRing}`;
const linkButton =
  `text-sm text-on-surface-variant hover:text-primary-text underline-offset-4 hover:underline disabled:opacity-60 rounded ${tapArea} ${focusRing}`;

// The owner's file is about 10 kB; the server refuses anything near this size too.
const MAX_FILE_BYTES = 800_000;

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * "Load my checklist" (PD-011): the owner's checklist file, loaded once from the browser.
 * Picking the file runs a practice run that saves nothing and shows what it would add;
 * only "Add these tasks" saves. The file's text stays in this component's memory until
 * then and is never stored in the browser.
 */
export function LoadChecklist({
  base, request, onLoaded, onStale,
}: {
  base: string; request: Req; onLoaded: (added: number) => Promise<void>;
  /** Reloads the checklist, for when someone else loaded it first. */
  onStale: () => Promise<void>;
}) {
  const [text, setText] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"checking" | "saving" | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const id = useId();

  const send = (fileText: string, apply: boolean) =>
    request<ImportResult>(`${base}/import`, {
      method: "POST",
      body: JSON.stringify({ text: fileText, apply }),
    });

  const reset = () => {
    setText(null);
    setPreview(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const message = (err: unknown) =>
    (err instanceof Error ? err.message : "That didn't work").replace(/[.\s]+$/, "");

  const pick = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setError(null);
    setPreview(null);
    setText(null);
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setError("That file is too big to be your checklist. Nothing was saved.");
      return;
    }
    setBusy("checking");
    try {
      const fileText = await file.text();
      const result = await send(fileText, false);
      setText(fileText);
      setPreview(result);
    } catch (err) {
      // Cleared so the same file, once fixed, can be picked again.
      if (fileRef.current) fileRef.current.value = "";
      setError(`${message(err)}. Nothing was saved.`);
      await onStale();
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    if (text === null) return;
    setBusy("saving");
    setError(null);
    try {
      const result = await send(text, true);
      reset();
      await onLoaded(result.owner_tasks + result.tradition_tasks + result.venue_tasks + result.chicago_tasks + result.ai_added);
    } catch (err) {
      // If the connection dropped after saving, the reload below shows the tasks.
      setError(`${message(err)}. Look at the checklist below before trying again.`);
      await onStale();
    } finally {
      setBusy(null);
    }
  };

  const lines = preview
    ? [
        plural(preview.owner_tasks, "task from your list", "tasks from your list"),
        plural(preview.tradition_tasks, "Jewish-tradition task", "Jewish-tradition tasks"),
        `${plural(preview.venue_tasks, "Wildman BT payment task", "Wildman BT payment tasks")}, with ` +
          "the due date in the wording. Nothing is marked as paid.",
        plural(preview.chicago_tasks, "Chicago and Wildman BT planning task", "Chicago and Wildman BT planning tasks"),
        ...(preview.ai_added
          ? [`${plural(preview.ai_added, "task", "tasks")} from the AI planner's old timeline, each put in the nearest stage`]
          : []),
        ...(preview.ai_skipped
          ? [`${plural(preview.ai_skipped, "AI planner task is", "AI planner tasks are")} already on your list, so ` +
              "not added twice (any tick or note moves onto your task)"]
          : []),
        ...(preview.timeline_rows_removed
          ? [`The AI planner's old timeline (${plural(preview.timeline_rows_removed, "entry", "entries")}) is then removed`]
          : []),
      ]
    : [];

  return (
    <section aria-label="Load my checklist" className="mb-6 bg-surface-container-lowest rounded-[2rem] border border-outline-variant/20 p-5">
      <h2 className="font-headline-sm text-lg text-on-surface mb-1">Load my checklist</h2>
      <p className="text-sm text-on-surface-variant mb-3">
        Pick your checklist file. The app checks it and shows you what it will add before anything is
        saved. You can only do this once.
      </p>

      {!preview && (
        <span className="flex flex-col gap-1">
          <label htmlFor={id} className="text-xs text-on-surface-variant">Your checklist file</label>
          <input
            id={id}
            ref={fileRef}
            type="file"
            accept=".md,.json,.txt,text/markdown,application/json,text/plain"
            disabled={busy !== null}
            onChange={pick}
            className={`text-sm text-on-surface file:mr-3 file:rounded-full file:border-0 file:bg-primary file:text-on-primary file:px-4 file:py-3 sm:file:py-2 file:font-button-text ${focusRing}`}
          />
        </span>
      )}
      {busy && (
        <p className="text-sm text-on-surface-variant mt-3" role="status">
          {busy === "saving" ? "Adding your tasks…" : "Checking your file…"}
        </p>
      )}
      {error && <p role="alert" className="text-sm text-error mt-3">{error}</p>}

      {preview && (
        <div className="mt-1">
          <p className="text-on-surface mb-2">This file is ready. Nothing has been saved yet. It will add:</p>
          <ul className="list-disc pl-5 text-sm text-on-surface space-y-1 mb-3">
            {lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
          <p className="text-sm text-on-surface-variant mb-4">
            {preview.wedding_date
              ? `Due dates count back from your wedding date, ${formatDay(preview.wedding_date)}.`
              : "No wedding date is set yet, so the tasks won't have due dates until you set one."}
          </p>
          <span className="flex flex-wrap items-center gap-3">
            <button type="button" disabled={busy !== null} onClick={save} className={primaryButton}>
              Add these tasks
            </button>
            <button type="button" disabled={busy !== null} onClick={() => { reset(); setError(null); }} className={linkButton}>
              Cancel
            </button>
          </span>
        </div>
      )}
    </section>
  );
}
