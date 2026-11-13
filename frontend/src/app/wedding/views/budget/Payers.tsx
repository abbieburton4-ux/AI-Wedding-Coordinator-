import { useState, type FormEvent } from "react";
import {
  Confirm, PAYERS_INPUT_ID, TextInput, dangerLink, json, linkButton, primaryButton, type Req,
} from "./parts";
import { FormError, useFormError } from "./formError";
import { FoldBody, SECTION_SCROLL, SectionHeading, sectionId } from "./sections";
import type { Payer, Run } from "./types";

/**
 * The "People who pay" list (PD-016 call a): the names the "Who paid" dropdowns offer.
 * The couple type them here, so real names live only in the wedding's database, never
 * in the app's code. Owners and editors add, rename and remove; viewers read. Someone
 * chosen on a payment can't be removed (the API refuses), so no record of who paid is
 * lost by accident; renaming them is always fine.
 */
export function Payers({
  base, payers, canEdit, run, request, busy,
}: { base: string; payers: Payer[]; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null);
  // One message at a time: "add" for the add form, or the row (a payer's id) it's about.
  const { error, setError, clear } = useFormError();
  const failed = (at: string) => (message: string) => setError(message, at);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    clear();
    const ok = await run(() => request(`${base}/payers`, json("POST", { name })), failed("add"));
    if (ok) setName("");
  };
  const rename = async (e: FormEvent, id: string) => {
    e.preventDefault();
    clear();
    const ok = await run(() => request(`${base}/payers/${id}`, json("PATCH", { name: newName })), failed(id));
    if (ok) setEditing(null);
  };
  const remove = async (id: string) => {
    clear();
    const ok = await run(() => request(`${base}/payers/${id}`, json("DELETE")), failed(id));
    if (ok) setConfirm(null);
  };

  return (
    <section id={sectionId("payers")} tabIndex={-1} aria-labelledby="payers-heading" className={`mb-10 ${SECTION_SCROLL} focus:outline-none`}>
      <SectionHeading section="payers" id="payers-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">
        People who pay
      </SectionHeading>
      <FoldBody section="payers">
        <p className="text-sm text-on-surface-variant mb-3">
          {payers.length === 0
            ? canEdit
              ? "Nobody yet. Add the people who pay for things, such as each of you, the two of you together, or family. You'll then choose who paid on each payment."
              : "Nobody has been added yet."
            : "The names you can choose as who paid on each payment. This is what actually got paid, not what someone promised (that's Who's contributing)."}
        </p>
        {payers.length > 0 && (
          <ul className="divide-y divide-outline-variant/30 border-y border-outline-variant/30 mb-4">
            {payers.map((p) => (
              <li key={p.id} className="py-3 flex flex-wrap items-center justify-between gap-2">
                {editing === p.id ? (
                  <form onSubmit={(e) => rename(e, p.id)} onChange={clear} className="flex flex-wrap items-end gap-3 w-full">
                    <TextInput id={`payer-name-${p.id}`} label="Name" value={newName} onChange={setNewName} wide />
                    <button type="submit" disabled={busy} className={primaryButton}>Save</button>
                    <button type="button" disabled={busy} onClick={() => { clear(); setEditing(null); }} className={linkButton}>Cancel</button>
                    <FormError error={error} at={p.id} />
                  </form>
                ) : (
                  <>
                    <span>
                      <span className="text-on-surface">{p.name}</span>
                      <span className="text-sm text-on-surface-variant">
                        {" · "}{p.payment_count === 0 ? "not on any payment yet" : `on ${p.payment_count} payment${p.payment_count === 1 ? "" : "s"}`}
                      </span>
                    </span>
                    {canEdit && (confirm === p.id ? (
                      p.payment_count > 0 ? (
                        <span role="alert" className="flex flex-wrap items-center gap-2 text-sm">
                          <span>
                            {p.name} is chosen as who paid on {p.payment_count} payment{p.payment_count === 1 ? "" : "s"}, so
                            they can't be removed. Choose someone else on those payments first, or rename them instead.
                          </span>
                          <button type="button" onClick={() => setConfirm(null)} className={linkButton}>OK</button>
                        </span>
                      ) : (
                        <Confirm busy={busy} text={`Remove ${p.name} from the list?`}
                          onYes={() => remove(p.id)}
                          onNo={() => { clear(); setConfirm(null); }} />
                      )
                    ) : (
                      <span className="flex gap-4">
                        <button type="button" onClick={() => { clear(); setNewName(p.name); setEditing(p.id); }} className={linkButton}>
                          Rename<span className="sr-only"> {p.name}</span>
                        </button>
                        <button type="button" onClick={() => { clear(); setConfirm(p.id); }} className={dangerLink}>
                          Remove<span className="sr-only"> {p.name}</span>
                        </button>
                      </span>
                    ))}
                    {confirm === p.id && <FormError error={error} at={p.id} />}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
        {canEdit && (
          <form onSubmit={add} onChange={clear} className="flex flex-wrap items-end gap-3">
            <TextInput id={PAYERS_INPUT_ID} label="Name" value={name} onChange={setName} placeholder="For example, Both of us" wide />
            <button type="submit" disabled={busy} className={primaryButton}>Add person</button>
            <FormError error={error} at="add" />
          </form>
        )}
      </FoldBody>
    </section>
  );
}
