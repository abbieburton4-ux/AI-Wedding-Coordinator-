import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Icon } from "../../shared/Icon";
import { useApi } from "../../api/useApi";
import { useAuth } from "../../auth/AuthProvider";
import { useActiveWedding } from "../WeddingProvider";

interface Member {
  id: string;
  email: string;
  level: "viewer" | "editor" | "owner";
  signed_in: boolean;
}

const LEVEL_LABEL: Record<Member["level"], string> = {
  owner: "Can edit and manage access",
  editor: "Can edit",
  viewer: "View only",
};

const selectClass =
  "bg-surface-container-low border border-outline-variant/40 rounded-full px-4 py-2 text-sm text-on-surface focus:border-primary focus:outline-none";

/**
 * Who has access to the wedding (PD-002 step 2). Only owners reach it, and the API
 * refuses everyone else too. Adding someone sends them nothing (hard rule 1).
 * Owner rows are read-only here: only the team changes them, on request (PD-002 note).
 */
export function Access() {
  const { activeWedding, myLevel, myLevelLoading } = useActiveWedding();
  const { user } = useAuth();
  const { request } = useApi();
  const weddingId = activeWedding?.id ?? null;

  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [level, setLevel] = useState<"editor" | "viewer">("viewer");
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!weddingId) return;
    try {
      setMembers(await request<Member[]>(`/weddings/${weddingId}/members`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the list.");
    }
  }, [weddingId, request]);

  useEffect(() => {
    if (myLevel === "owner") load();
  }, [myLevel, load]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const add = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      const added = await request<Member>(`/weddings/${weddingId}/members`, {
        method: "POST",
        body: JSON.stringify({ email, level }),
      });
      setEmail("");
      setNotice(
        `${added.email} has been added. We haven't sent them anything, so let them know ` +
          "yourself and ask them to sign in with this email address.",
      );
      await load();
    });
  };

  const isMe = (m: Member) => !!user?.email && m.email === user.email.trim().toLowerCase();

  const change = (m: Member, next: "editor" | "viewer") =>
    run(async () => {
      await request(`/weddings/${weddingId}/members/${m.id}`, {
        method: "PATCH",
        body: JSON.stringify({ level: next }),
      });
      await load();
    });

  const remove = (m: Member) =>
    run(async () => {
      await request(`/weddings/${weddingId}/members/${m.id}`, { method: "DELETE" });
      setConfirmRemove(null);
      await load();
    });

  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-8">
        <h1 className="font-display-lg-mobile text-display-lg-mobile text-on-surface mb-2">Who has access</h1>
        <p className="text-on-surface-variant">
          Add the people who can open your wedding plans, and choose what each person can do.
        </p>
      </div>

      {myLevelLoading ? (
        <p className="text-on-surface-variant">Loading…</p>
      ) : myLevel !== "owner" ? (
        <p className="text-on-surface-variant">
          Only the people who manage access can see and change this list.
        </p>
      ) : (
        <>
          <div className="bg-primary-container/20 border border-primary/20 rounded-[1.5rem] p-4 mb-8 flex gap-3">
            <Icon name="info" className="text-primary-text shrink-0" />
            <p className="text-sm text-on-surface">
              Adding someone here doesn't send them an invitation or any email. Let them know yourself,
              and ask them to sign in with the email address you add.
            </p>
          </div>

          <section aria-labelledby="add-heading" className="mb-10">
            <h2 id="add-heading" className="font-headline-sm text-headline-sm text-on-surface mb-3">Add someone</h2>
            <form onSubmit={add} className="flex flex-col sm:flex-row gap-3">
              <label className="sr-only" htmlFor="access-email">Email address</label>
              <input
                id="access-email"
                type="email"
                required
                autoComplete="off"
                placeholder="Their email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-grow bg-surface-container-low border border-outline-variant/40 rounded-full px-5 py-2.5 text-on-surface focus:border-primary focus:outline-none"
              />
              <label className="sr-only" htmlFor="access-level">What they can do</label>
              <select
                id="access-level"
                value={level}
                onChange={(e) => setLevel(e.target.value as "editor" | "viewer")}
                className={selectClass}
              >
                <option value="viewer">View only</option>
                <option value="editor">Can edit</option>
              </select>
              <button
                type="submit"
                disabled={busy}
                className="bg-primary text-on-primary rounded-full px-6 py-2.5 font-button-text text-button-text disabled:opacity-60"
              >
                Add
              </button>
            </form>
            <p className="text-xs text-on-surface-variant mt-2">
              "View only" people can see everything, including the budget and guest notes, but can't
              change anything. "Can edit" people can change the plans too.
            </p>
          </section>

          {notice && <p role="status" className="mb-4 text-sm text-on-surface">{notice}</p>}
          {error && <p role="alert" className="mb-4 text-sm text-error">{error}</p>}

          <section aria-labelledby="list-heading">
            <h2 id="list-heading" className="font-headline-sm text-headline-sm text-on-surface mb-3">
              People with access
            </h2>
            {members === null ? (
              <p className="text-on-surface-variant">Loading…</p>
            ) : (
              <ul className="divide-y divide-outline-variant/30 border-y border-outline-variant/30">
                {members.map((m) => (
                  <li key={m.id} className="py-4 flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex-grow min-w-0">
                      <p className="text-on-surface break-all">
                        {m.email}
                        {isMe(m) && <span className="text-on-surface-variant"> (you)</span>}
                      </p>
                      <p className="text-xs text-on-surface-variant">
                        {m.signed_in ? "Has signed in" : "Hasn't signed in yet"}
                      </p>
                    </div>

                    {m.level === "owner" ? (
                      <p className="text-sm text-on-surface sm:px-4">{LEVEL_LABEL.owner}</p>
                    ) : (
                      <>
                        <label className="sr-only" htmlFor={`level-${m.id}`}>What {m.email} can do</label>
                        <select
                          id={`level-${m.id}`}
                          value={m.level}
                          disabled={busy}
                          onChange={(e) => change(m, e.target.value as "editor" | "viewer")}
                          className={selectClass}
                        >
                          <option value="editor">{LEVEL_LABEL.editor}</option>
                          <option value="viewer">{LEVEL_LABEL.viewer}</option>
                        </select>
                      </>
                    )}

                    {m.level === "owner" ? null : confirmRemove === m.id ? (
                      <span className="flex items-center gap-2 text-sm">
                        <span>Remove them?</span>
                        <button type="button" disabled={busy} onClick={() => remove(m)}
                          className="text-error font-bold underline-offset-4 hover:underline">
                          Yes, remove
                        </button>
                        <button type="button" disabled={busy} onClick={() => setConfirmRemove(null)}
                          className="text-on-surface-variant underline-offset-4 hover:underline">
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <button type="button" disabled={busy} onClick={() => setConfirmRemove(m.id)}
                        className="text-sm text-on-surface-variant hover:text-error underline-offset-4 hover:underline">
                        Remove
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-on-surface-variant mt-3">
              Only the team can remove or change people who manage access, if you ask them to.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
