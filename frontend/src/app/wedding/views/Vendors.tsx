import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "../../shared/Icon";
import { useApi, USE_FASTAPI_BACKEND } from "../../api";
import { useReviewedRequest } from "../../api/review";
import { useActiveWedding } from "../WeddingProvider";
import { dangerLink, inputClass, linkButton, primaryButton } from "./budget/parts";
import { tapArea } from "./budget/sections";
import { FoldChevron, scrollToElement, useRememberedFolds, type Folds } from "./folds";

/**
 * The couple's own vendors, by section (PD-012, B62). Everyone on the access list can
 * see them; owners and editors add, edit and remove them, and the API refuses anyone
 * else. The status is only what the couple set: the app never marks anything booked.
 */

type VendorStatus = "looking" | "contacted" | "booked" | "not_selected";

interface LineItem {
  item: string;
  amount_cents: number | null;
}

interface Reply {
  total_cents: number | null;
  currency: string | null;
  is_available: boolean | null;
  line_items: LineItem[];
  summary: string | null;
  read_at: string;
}

interface Vendor {
  id: string;
  section: string;
  name: string;
  website: string | null;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  status: VendorStatus;
  notes: string | null;
  updated_at: string;
  latest_reply: Reply | null;
}

/** A section's status, worked out by the server: its furthest vendor still in play,
 *  or "todo" when it has none (Not selected vendors don't count). */
type CategoryStatus = Exclude<VendorStatus, "not_selected"> | "todo";

/** Anything a badge can show: a vendor's status, or a section's. */
type BadgeStatus = VendorStatus | "todo";

interface VendorsResponse {
  sections: string[];
  vendors: Vendor[];
  section_status: Record<string, CategoryStatus>;
}

const SECTIONS = [
  { key: "venue", title: "Venue", icon: "location_city" },
  { key: "food_drink", title: "Food & drink", icon: "restaurant" },
  { key: "flowers_decoration", title: "Flowers & decoration", icon: "local_florist" },
  { key: "photo_video", title: "Photographer & videographer", icon: "photo_camera" },
  { key: "entertainment", title: "Entertainment", icon: "music_note" },
  { key: "hair_makeup", title: "Hair & makeup", icon: "brush" },
  { key: "transportation", title: "Transportation", icon: "directions_car" },
] as const;

type SectionKey = (typeof SECTIONS)[number]["key"];
const SECTION_KEYS: readonly SectionKey[] = SECTIONS.map((s) => s.key);

const STATUSES: { value: VendorStatus; label: string }[] = [
  { value: "looking", label: "Looking" },
  { value: "contacted", label: "Contacted" },
  { value: "booked", label: "Booked" },
  { value: "not_selected", label: "Not selected" },
];

// Colour is never the only cue: every badge carries the word, and an icon too.
const STATUS_STYLE: Record<BadgeStatus, { label: string; icon: string; badge: string; edge: string }> = {
  todo: {
    label: "Still to do", icon: "priority_high",
    badge: "bg-status-todo text-status-todo-foreground", edge: "border-l-status-todo",
  },
  looking: {
    label: "Looking", icon: "search",
    badge: "bg-status-looking text-status-looking-foreground", edge: "border-l-status-looking-foreground",
  },
  contacted: {
    label: "Contacted", icon: "mail",
    badge: "bg-status-contacted text-status-contacted-foreground", edge: "border-l-status-contacted-foreground",
  },
  booked: {
    label: "Booked", icon: "check_circle",
    badge: "bg-status-booked text-status-booked-foreground", edge: "border-l-status-booked-foreground",
  },
  not_selected: {
    label: "Not selected", icon: "block",
    badge: "bg-status-not-selected text-status-not-selected-foreground",
    edge: "border-l-status-not-selected-foreground/50",
  },
};

// A ruled-out vendor's tile fades (surface and border only, so the text keeps its
// contrast) and sits after the ones still in play.
const TILE_SURFACE = "border-outline-variant/30 bg-surface-container-low/60";
const TILE_FADED = "border-outline-variant/15 bg-surface-container-low/20";

function inPlayFirst(vendors: Vendor[]): Vendor[] {
  const out = (v: Vendor) => (v.status === "not_selected" ? 1 : 0);
  return [...vendors].sort((a, b) => out(a) - out(b));
}

function StatusBadge({ status, srPrefix = "Status: " }: { status: BadgeStatus; srPrefix?: string }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 text-xs font-button-text ${s.badge}`}>
      <Icon name={s.icon} size={14} />
      <span className="sr-only">{srPrefix}</span>{s.label}
    </span>
  );
}

const sectionDomId = (key: string) => `vendor-category-${key}`;

const textArea =
  "w-full rounded-2xl border border-outline-variant/40 bg-surface-container-low px-4 py-2 text-sm text-on-surface focus:border-primary focus:outline-none";
// On a phone, links in a vendor's details are 44px tall so they're easy to tap (B80).
const phoneTallLink = "max-sm:inline-flex max-sm:min-h-11 max-sm:items-center";

/** Adds https:// when someone types "example.com"; anything with another scheme is left
 *  as typed, so the server refuses it rather than us guessing. */
function withScheme(url: string): string {
  const t = url.trim();
  if (!t) return "";
  return /^[a-z][a-z0-9+.-]*:/i.test(t) ? t : `https://${t}`;
}

/** Only http and https links are ever rendered as links. */
function safeHref(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    if (u.username || u.password) return null;
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** A tel: link that dials the main number; an extension follows a pause (","). */
function telHref(phone: string): string {
  const [main, ext] = phone.split(/\s*(?:ext\.?|x)\s*/i);
  const digits = main.replace(/[^\d+]/g, "");
  return `tel:${digits}${ext ? `,${ext.replace(/\D/g, "")}` : ""}`;
}

function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
}

function formatMoney(cents: number, currency: string | null): string {
  const amount = cents / 100;
  if (currency) {
    try {
      return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
    } catch {
      /* an unusual code: fall through to a plain number */
    }
  }
  const plain = amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${plain} ${currency}` : `${plain} (currency not stated)`;
}

// ---- The add / edit form -------------------------------------------------------------

interface Draft {
  name: string;
  website: string;
  contact_name: string;
  email: string;
  phone: string;
  status: VendorStatus;
  notes: string;
}

const emptyDraft: Draft = {
  name: "", website: "", contact_name: "", email: "", phone: "", status: "looking", notes: "",
};

function draftOf(v: Vendor): Draft {
  return {
    name: v.name, website: v.website ?? "", contact_name: v.contact_name ?? "",
    email: v.email ?? "", phone: v.phone ?? "", status: v.status, notes: v.notes ?? "",
  };
}

function VendorForm({
  idPrefix, initial, submitLabel, onSave, onCancel,
}: {
  idPrefix: string;
  initial: Draft;
  submitLabel: string;
  onSave: (d: Draft) => Promise<string | null>;
  onCancel: () => void;
}) {
  const [d, setD] = useState<Draft>(initial);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof Draft) => (value: string) => setD((prev) => ({ ...prev, [k]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!d.name.trim()) {
      setError("Please type the vendor's name.");
      return;
    }
    setSaving(true);
    setError(await onSave({ ...d, website: withScheme(d.website) }));
    setSaving(false);
  }

  const field = (k: keyof Draft, label: string, type = "text", extra: Record<string, string> = {}, focus = false) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={`${idPrefix}-${k}`} className="text-sm text-on-surface-variant">{label}</label>
      <input
        id={`${idPrefix}-${k}`}
        type={type}
        value={d[k]}
        onChange={(e) => set(k)(e.target.value)}
        className={inputClass}
        autoFocus={focus}
        {...extra}
      />
    </div>
  );

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-2xl bg-surface-container-low/60 p-4" noValidate>
      {field("name", "Name (required)", "text", { maxLength: "200", autoComplete: "off" }, true)}
      {field("website", "Website", "url", { maxLength: "500", placeholder: "https://", inputMode: "url" })}
      {field("contact_name", "Contact person", "text", { maxLength: "200", autoComplete: "off", placeholder: "The person you deal with" })}
      {field("email", "Email", "email", { maxLength: "254", autoComplete: "off" })}
      {field("phone", "Phone", "tel", { maxLength: "40", autoComplete: "off" })}
      <div className="flex flex-col gap-1">
        <label htmlFor={`${idPrefix}-status`} className="text-sm text-on-surface-variant">Status</label>
        <select
          id={`${idPrefix}-status`}
          value={d.status}
          onChange={(e) => set("status")(e.target.value)}
          className={inputClass}
        >
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${idPrefix}-notes`} className="text-sm text-on-surface-variant">Notes</label>
        <textarea
          id={`${idPrefix}-notes`}
          value={d.notes}
          onChange={(e) => set("notes")(e.target.value)}
          rows={3}
          maxLength={2000}
          className={textArea}
        />
      </div>
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className={primaryButton}>
          {saving ? "Saving…" : submitLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className={linkButton}>Cancel</button>
      </div>
    </form>
  );
}

// ---- Pasting a vendor's reply --------------------------------------------------------

function ReplyPanel({ reply }: { reply: Reply }) {
  return (
    <div className="rounded-2xl border border-primary-container/30 bg-primary-container/10 p-3 flex flex-col gap-1">
      <p className="text-xs text-on-surface-variant">
        What the AI read from their reply. Check it against the email; it isn't a confirmed quote.
      </p>
      {reply.total_cents !== null ? (
        <p className="font-title-lg text-title-lg text-on-surface leading-tight">
          {formatMoney(reply.total_cents, reply.currency)}
        </p>
      ) : (
        <p className="text-sm text-on-surface">No total price in the reply.</p>
      )}
      {reply.is_available !== null && (
        <p className="text-sm text-on-surface">
          {reply.is_available ? "They say they're available." : "They say they aren't available."}
        </p>
      )}
      {reply.line_items.length > 0 && (
        <ul className="text-sm text-on-surface-variant list-disc pl-5">
          {reply.line_items.map((li, i) => (
            <li key={i}>
              {li.item}
              {li.amount_cents !== null && `: ${formatMoney(li.amount_cents, reply.currency)}`}
            </li>
          ))}
        </ul>
      )}
      {reply.summary && <p className="text-sm text-on-surface-variant">{reply.summary}</p>}
    </div>
  );
}

function PasteReply({
  base, vendor, reload, onClose,
}: { base: string; vendor: Vendor; reload: () => Promise<Vendor[] | null>; onClose: () => void }) {
  const sendReviewed = useReviewedRequest();
  const [text, setText] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const id = `reply-${vendor.id}`;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setWorking(true);
    setError(null);
    const before = vendor.latest_reply?.read_at ?? null;
    try {
      // Shows the cleaned text first; nothing goes to the AI until they click (PD-008).
      const sent = await sendReviewed<{ status: string }>(`${base}/${vendor.id}/reply`, { email_body: text });
      if (sent === null) return;
      // On a queued run the reading lands a little later, so look a few times.
      for (let i = 0; i < 10 && mounted.current; i++) {
        const list = await reload();
        const now = list?.find((v) => v.id === vendor.id)?.latest_reply?.read_at ?? null;
        if (now && now !== before) {
          if (mounted.current) onClose();
          return;
        }
        if (sent.status === "completed") break;
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (mounted.current) setError("It's still being read. Refresh the page in a moment.");
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "The reply couldn't be read. Please try again.");
    } finally {
      if (mounted.current) setWorking(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm text-on-surface-variant">
        Paste their email reply. The AI reads the price and whether they're free. You'll see exactly
        what goes to the AI before it's sent, with names, emails and phone numbers taken out.
      </label>
      <textarea
        id={id}
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        autoFocus
        className={textArea}
      />
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={working || !text.trim()} className={primaryButton}>
          {working ? "Reading…" : "Check what the AI will see"}
        </button>
        <button type="button" onClick={onClose} disabled={working} className={linkButton}>Cancel</button>
      </div>
    </form>
  );
}

// ---- One vendor ----------------------------------------------------------------------

function VendorCard({
  base, vendor, canEdit, reload, request,
}: {
  base: string;
  vendor: Vendor;
  canEdit: boolean;
  reload: () => Promise<Vendor[] | null>;
  request: ReturnType<typeof useApi>["request"];
}) {
  const [mode, setMode] = useState<"view" | "edit" | "reply" | "confirm">("view");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const href = safeHref(vendor.website);

  async function save(d: Draft): Promise<string | null> {
    try {
      await request(`${base}/${vendor.id}`, { method: "PATCH", body: JSON.stringify(d) });
      await reload();
      setMode("view");
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : "That didn't save. Please try again.";
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await request(`${base}/${vendor.id}`, { method: "DELETE" });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work. Please try again.");
      setBusy(false);
      setMode("view");
    }
  }

  if (mode === "edit") {
    return (
      <li>
        <VendorForm idPrefix={`edit-${vendor.id}`} initial={draftOf(vendor)} submitLabel="Save changes"
          onSave={save} onCancel={() => setMode("view")} />
      </li>
    );
  }

  return (
    <li
      className={`flex flex-col gap-2 rounded-2xl border border-l-4 ${vendor.status === "not_selected" ? TILE_FADED : TILE_SURFACE} ${STATUS_STYLE[vendor.status].edge} p-4`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-title-lg text-title-lg text-on-surface leading-tight break-words min-w-0">{vendor.name}</p>
        <StatusBadge status={vendor.status} />
      </div>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex max-sm:min-h-11 items-center gap-1 self-start text-sm font-button-text text-primary-text underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary rounded-sm"
        >
          {shortUrl(vendor.website ?? "")}
          <Icon name="open_in_new" size={14} />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      )}
      {(vendor.contact_name || vendor.email || vendor.phone) && (
        <dl className="text-sm text-on-surface-variant grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 max-sm:items-center max-sm:auto-rows-[minmax(2.75rem,auto)]">
          {vendor.contact_name && (<><dt>Contact</dt><dd className="text-on-surface break-words">{vendor.contact_name}</dd></>)}
          {vendor.email && (
            <>
              <dt>Email</dt>
              <dd className="break-all max-sm:flex"><a href={`mailto:${encodeURI(vendor.email)}`} className={`text-primary-text underline underline-offset-2 ${phoneTallLink}`}>{vendor.email}</a></dd>
            </>
          )}
          {vendor.phone && (
            <>
              <dt>Phone</dt>
              <dd className="max-sm:flex"><a href={telHref(vendor.phone)} className={`text-primary-text underline underline-offset-2 ${phoneTallLink}`}>{vendor.phone}</a></dd>
            </>
          )}
        </dl>
      )}
      {vendor.notes && <p className="text-sm text-on-surface-variant whitespace-pre-line break-words">{vendor.notes}</p>}
      {vendor.latest_reply && <ReplyPanel reply={vendor.latest_reply} />}
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      {canEdit && mode === "reply" && (
        <PasteReply base={base} vendor={vendor} reload={reload} onClose={() => setMode("view")} />
      )}
      {canEdit && mode === "confirm" && (
        <p className="flex flex-wrap items-center gap-3 max-sm:gap-y-6 text-sm">
          <span>Remove {vendor.name}{vendor.latest_reply ? " and what the AI read from their reply" : ""}?</span>
          <button type="button" autoFocus disabled={busy} onClick={remove} className={`text-error font-bold underline-offset-4 hover:underline ${tapArea}`}>
            Yes, remove
          </button>
          <button type="button" disabled={busy} onClick={() => setMode("view")} className={linkButton}>Cancel</button>
        </p>
      )}
      {canEdit && mode === "view" && (
        <div className="flex flex-wrap items-center gap-4">
          <button type="button" onClick={() => setMode("edit")} className={linkButton}>
            Edit<span className="sr-only"> {vendor.name}</span>
          </button>
          <button type="button" onClick={() => setMode("reply")} className={linkButton}>
            Paste a reply<span className="sr-only"> from {vendor.name}</span>
          </button>
          <button type="button" onClick={() => setMode("confirm")} className={dangerLink}>
            Remove<span className="sr-only"> {vendor.name}</span>
          </button>
        </div>
      )}
    </li>
  );
}

// ---- One section ---------------------------------------------------------------------

function SectionCard({
  section, vendors, status, base, canEdit, reload, request, folded, onToggle,
}: {
  section: (typeof SECTIONS)[number];
  vendors: Vendor[];
  status: CategoryStatus;
  base: string;
  canEdit: boolean;
  reload: () => Promise<Vendor[] | null>;
  request: ReturnType<typeof useApi>["request"];
  folded: boolean;
  onToggle: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const headingId = `vendor-section-${section.key}`;
  const bodyId = `${sectionDomId(section.key)}-body`;
  const count = `${vendors.length} ${vendors.length === 1 ? "vendor" : "vendors"}`;

  async function add(d: Draft): Promise<string | null> {
    try {
      await request(base, { method: "POST", body: JSON.stringify({ ...d, section: section.key }) });
      await reload();
      setAdding(false);
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : "That didn't save. Please try again.";
    }
  }

  return (
    <section
      id={sectionDomId(section.key)}
      tabIndex={-1}
      aria-labelledby={headingId}
      className="scroll-mt-24 bg-surface-container-lowest rounded-[2rem] border border-outline-variant/20 p-gutter flex flex-col gap-4 focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className="w-10 h-10 shrink-0 rounded-full bg-primary/10 flex items-center justify-center">
          <Icon name={section.icon} size={20} className="text-primary-text" />
        </span>
        <h3 id={headingId} className="min-w-0 font-headline-sm text-headline-sm text-on-surface">
          <button
            type="button"
            aria-expanded={!folded}
            aria-controls={bodyId}
            onClick={onToggle}
            className="inline-flex min-h-11 items-center gap-2 text-left hover:text-primary-text rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <span className="break-words">{section.title}</span>
            <FoldChevron folded={folded} />
          </button>
        </h3>
        <span className="ml-auto flex items-center gap-3">
          <span className="text-sm text-on-surface-variant whitespace-nowrap">{count}</span>
          <StatusBadge status={status} srPrefix="Section status: " />
        </span>
      </div>
      <div id={bodyId} hidden={folded} className="flex flex-col gap-4">
      {vendors.length > 0 ? (
        <ul className="flex flex-col gap-4">
          {inPlayFirst(vendors).map((v) => (
            <VendorCard key={v.id} base={base} vendor={v} canEdit={canEdit} reload={reload} request={request} />
          ))}
        </ul>
      ) : (
        !adding && <p className="text-sm text-on-surface-variant">Nothing added yet</p>
      )}
      {canEdit && (adding ? (
        <VendorForm idPrefix={`add-${section.key}`} initial={emptyDraft} submitLabel="Add vendor"
          onSave={add} onCancel={() => setAdding(false)} />
      ) : (
        <button type="button" onClick={() => setAdding(true)}
          className="self-start inline-flex max-sm:min-h-11 items-center gap-1 text-sm font-button-text text-primary-text hover:opacity-80">
          <Icon name="add" size={18} /> Add a vendor<span className="sr-only"> to {section.title}</span>
        </button>
      ))}
      </div>
    </section>
  );
}

// ---- The summary at the top ----------------------------------------------------------

// Still to do stands out most, then looking; contacted and booked stay calm.
const calmItem = "border border-outline-variant/30 bg-surface-container-low/60";
const SUMMARY_ITEM: Record<CategoryStatus, string> = {
  todo: "border-[3px] border-status-todo bg-status-todo/10",
  looking: "border-2 border-status-looking-foreground bg-surface-container-lowest",
  contacted: calmItem,
  booked: calmItem,
};

function CategorySummary({
  sectionStatus, folds,
}: { sectionStatus: Record<string, CategoryStatus>; folds: Folds<SectionKey> }) {
  // Opens a folded section first, then scrolls once it's shown again.
  const goToSection = (key: SectionKey) => {
    folds.open(key);
    window.requestAnimationFrame(() => {
      const el = document.getElementById(sectionDomId(key));
      if (el) scrollToElement(el);
    });
  };
  const rows = SECTIONS.map((s) => ({ section: s, status: sectionStatus[s.key] ?? "todo" }));
  const count = (st: CategoryStatus) => rows.filter((r) => r.status === st).length;
  const parts = (["todo", "looking", "contacted", "booked"] as const)
    .filter((st) => count(st) > 0)
    .map((st) => `${count(st)} ${STATUS_STYLE[st].label.toLowerCase()}`);

  return (
    <section aria-labelledby="vendor-summary-heading" className="px-margin-mobile md:px-margin-desktop pt-2">
      <h3 id="vendor-summary-heading" className="font-headline-sm text-headline-sm text-on-surface">
        Where each section stands
      </h3>
      <p className="text-sm text-on-surface-variant mt-1">
        {parts.join(", ")}. This shows only what you've set; the app never changes a status.
      </p>
      <p className="flex flex-wrap gap-x-6 gap-y-2 mt-3">
        <button type="button" onClick={() => folds.setAll(false)} className={linkButton}>
          Expand all<span className="sr-only"> vendor sections</span>
        </button>
        <button type="button" onClick={() => folds.setAll(true)} className={linkButton}>
          Collapse all<span className="sr-only"> vendor sections</span>
        </button>
      </p>
      <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {rows.map(({ section, status }) => (
          <li key={section.key}>
            <a
              href={`#${sectionDomId(section.key)}`}
              onClick={(e) => {
                e.preventDefault();
                goToSection(section.key);
              }}
              className={`flex min-h-12 flex-wrap items-center justify-between gap-x-2 gap-y-1 rounded-2xl px-4 py-3 text-on-surface hover:bg-surface-container focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${SUMMARY_ITEM[status]}`}
            >
              <span className="flex min-w-0 items-center gap-2">
                <Icon name={section.icon} size={18} className="text-on-surface-variant" />
                <span className="min-w-0 text-sm font-button-text break-words">{section.title}</span>
              </span>
              <StatusBadge status={status} srPrefix=": " />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---- The screen ----------------------------------------------------------------------

export function Vendors() {
  const { activeWedding, myLevel } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;
  const { request } = useApi();
  const base = `/weddings/${weddingId}/vendors`;
  const canEdit = myLevel === "owner" || myLevel === "editor";
  const [vendors, setVendors] = useState<Vendor[] | null>(null);
  const [sectionStatus, setSectionStatus] = useState<Record<string, CategoryStatus>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const folds = useRememberedFolds(weddingId ? `venueflow.vendorFolds.${weddingId}` : null, SECTION_KEYS);

  const reload = useCallback(async (): Promise<Vendor[] | null> => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return null;
    try {
      const res = await request<VendorsResponse>(`/weddings/${weddingId}/vendors`);
      setVendors(res.vendors);
      setSectionStatus(res.section_status);
      setLoadError(null);
      return res.vendors;
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Your vendors didn't load.");
      return null;
    }
  }, [weddingId, request]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <main className="pt-16 md:pl-72 pb-20 md:pb-8">
      <section className="px-margin-mobile md:px-margin-desktop py-8 md:py-12 bg-surface">
        <h2 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary-text">
          Vendors
        </h2>
        <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mt-2">
          The people and places you choose for the day, by section.
        </p>
        {!canEdit && myLevel && (
          <p className="text-sm text-on-surface-variant mt-2">You can see the vendors but not change them.</p>
        )}
      </section>

      {!USE_FASTAPI_BACKEND ? (
        <p className="px-margin-mobile md:px-margin-desktop py-6 text-on-surface-variant">
          Vendors need the app's server, which is switched off in this build.
        </p>
      ) : loadError ? (
        <div role="alert" className="px-margin-mobile md:px-margin-desktop py-6 text-on-surface">
          <p className="mb-2">Your vendors didn't load: {loadError}</p>
          <button type="button" onClick={() => reload()} className={linkButton}>Try again</button>
        </div>
      ) : vendors === null ? (
        <p className="px-margin-mobile md:px-margin-desktop py-6 text-on-surface-variant" aria-busy="true">Loading your vendors…</p>
      ) : (
        <>
          <CategorySummary sectionStatus={sectionStatus} folds={folds} />
          <div className="px-margin-mobile md:px-margin-desktop py-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter items-start">
            {SECTIONS.map((s) => (
              <SectionCard key={s.key} section={s} vendors={vendors.filter((v) => v.section === s.key)}
                status={sectionStatus[s.key] ?? "todo"}
                base={base} canEdit={canEdit} reload={reload} request={request}
                folded={folds.folded(s.key)} onToggle={() => folds.toggle(s.key)} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
