import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from "react";
import { Icon } from "../../../shared/Icon";

// The same look as parts.tsx's linkButton; not imported, since parts.tsx imports this file.
const linkButton =
  "text-sm text-on-surface-variant hover:text-primary underline-offset-4 hover:underline disabled:opacity-60";

/**
 * The Budget screen's sections (PD-015 steps 3 and 4): a jump-to bar at the top and
 * a fold on each section. Which sections are folded is a screen preference kept on
 * this device per wedding, not wedding data, so localStorage is fine for it.
 */
export type SectionKey =
  | "overview" | "upcoming" | "charts" | "expenses" | "categories" | "export" | "contributions";

/** In page order, so the bar reads the way the page scrolls. */
export const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "upcoming", label: "Upcoming payments" },
  { key: "charts", label: "Charts" },
  { key: "expenses", label: "All expenses" },
  { key: "categories", label: "Categories" },
  { key: "export", label: "Export" },
  { key: "contributions", label: "Who's contributing" },
];

const KEYS = new Set<string>(SECTIONS.map((s) => s.key));

export const sectionId = (key: SectionKey) => `budget-${key}`;
const bodyId = (key: SectionKey) => `budget-${key}-body`;

/**
 * Clears the sticky app header (h-16, 64px) and this bar (about 90px, two rows) when a
 * section is scrolled to, with room to spare. IN_VIEW_PX matches it, for aria-current.
 */
export const SECTION_SCROLL = "scroll-mt-48";
const IN_VIEW_PX = 200;

type Folds = {
  folded: (key: SectionKey) => boolean;
  toggle: (key: SectionKey) => void;
  open: (key: SectionKey) => void;
  setAll: (fold: boolean) => void;
  /** Opens a section if it's folded, then scrolls to it and moves focus there. */
  jumpTo: (key: SectionKey, target?: HTMLElement | null) => void;
};

const FoldContext = createContext<Folds | null>(null);

export function useFolds(): Folds | null {
  return useContext(FoldContext);
}

function storageKey(weddingId: string) {
  return `venueflow.budgetFolds.${weddingId}`;
}

function readFolds(weddingId: string | null): SectionKey[] {
  if (!weddingId) return [];
  try {
    const raw = JSON.parse(window.localStorage.getItem(storageKey(weddingId)) ?? "[]");
    return Array.isArray(raw) ? raw.filter((k): k is SectionKey => typeof k === "string" && KEYS.has(k)) : [];
  } catch {
    return [];
  }
}

export function scrollToElement(el: HTMLElement) {
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  el.focus({ preventScroll: true });
}

export function FoldProvider({ weddingId, children }: { weddingId: string | null; children: ReactNode }) {
  const [folded, setFolded] = useState<SectionKey[]>(() => readFolds(weddingId));
  const loadedFor = useRef(weddingId);

  // Another wedding on the same device has its own preference. This effect must stay
  // before the one that saves: it reads the new wedding's folds before that effect can
  // write the old wedding's folds under the new key in the same render.
  useEffect(() => {
    if (loadedFor.current === weddingId) return;
    loadedFor.current = weddingId;
    setFolded(readFolds(weddingId));
  }, [weddingId]);

  useEffect(() => {
    if (!weddingId || loadedFor.current !== weddingId) return;
    try {
      if (folded.length) window.localStorage.setItem(storageKey(weddingId), JSON.stringify(folded));
      else window.localStorage.removeItem(storageKey(weddingId));
    } catch {
      // Private browsing or a full store: folding still works, it just isn't remembered.
    }
  }, [weddingId, folded]);

  const value = useMemo<Folds>(() => {
    const open = (key: SectionKey) => setFolded((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : prev));
    return {
      folded: (key) => folded.includes(key),
      toggle: (key) => setFolded((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key])),
      open,
      setAll: (fold) => setFolded(fold ? SECTIONS.map((s) => s.key) : []),
      jumpTo: (key, target) => {
        open(key);
        // After the section is shown again, so there's something to scroll to.
        window.requestAnimationFrame(() => {
          const el = target ?? document.getElementById(sectionId(key));
          if (el) scrollToElement(el);
        });
      },
    };
  }, [folded]);

  return <FoldContext.Provider value={value}>{children}</FoldContext.Provider>;
}

/**
 * A section's heading, as a button that folds and unfolds it. Without a FoldProvider
 * (another screen reusing the section) it's a plain heading.
 */
export function SectionHeading({
  section, id, className, children,
}: { section: SectionKey; id: string; className: string; children: ReactNode }) {
  const folds = useFolds();
  if (!folds) return <h2 id={id} className={className}>{children}</h2>;
  const isFolded = folds.folded(section);
  return (
    <h2 id={id} className={className}>
      <button
        type="button"
        aria-expanded={!isFolded}
        aria-controls={bodyId(section)}
        onClick={() => folds.toggle(section)}
        className="inline-flex items-center gap-2 text-left hover:text-primary rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
      >
        {children}
        <Icon
          name="expand_more"
          size={22}
          className={`text-on-surface-variant transition-transform motion-reduce:transition-none ${isFolded ? "-rotate-90" : ""}`}
        />
      </button>
    </h2>
  );
}

/** What a section's heading folds away. Kept mounted, so a half-typed form survives a fold. */
export function FoldBody({ section, children }: { section: SectionKey; children: ReactNode }) {
  const folds = useFolds();
  return (
    <div id={bodyId(section)} hidden={folds?.folded(section) ?? false}>
      {children}
    </div>
  );
}

/**
 * The jump-to bar: links to each section on the page, staying at the top while the
 * page scrolls, sideways-scrolling on a phone. The section in view is marked with
 * aria-current. Clicking one opens it if it's folded.
 */
export function JumpBar({ present }: { present: SectionKey[] }) {
  const folds = useFolds();
  const shown = SECTIONS.filter((s) => present.includes(s.key));
  const [current, setCurrent] = useState<SectionKey | null>(shown[0]?.key ?? null);
  const presentKey = shown.map((s) => s.key).join("|");

  // The section in view is the last one whose top has passed under the bar.
  useEffect(() => {
    const keys = presentKey ? (presentKey.split("|") as SectionKey[]) : [];
    const update = () => {
      let inView: SectionKey | null = keys[0] ?? null;
      for (const key of keys) {
        const el = document.getElementById(sectionId(key));
        if (el && el.getBoundingClientRect().top <= IN_VIEW_PX) inView = key;
      }
      // At the bottom of the page, the last section counts as in view even if it's short.
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) {
        inView = keys[keys.length - 1] ?? inView;
      }
      setCurrent(inView);
    };
    update();
    let frame = 0;
    const onScroll = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [presentKey]);

  if (!folds || shown.length === 0) return null;
  const allFolded = shown.every((s) => folds.folded(s.key));
  const noneFolded = shown.every((s) => !folds.folded(s.key));

  return (
    <div className="sticky top-16 z-30 -mx-margin-mobile md:mx-0 mb-8 bg-wedding-white/95 backdrop-blur-md border-b border-outline-variant/20">
      <nav aria-label="Budget sections" className="overflow-x-auto">
        <ul className="flex gap-2 px-margin-mobile md:px-0 py-3 w-max">
          {shown.map((s) => (
            <li key={s.key}>
              <a
                href={`#${sectionId(s.key)}`}
                aria-current={current === s.key ? "location" : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  setCurrent(s.key);
                  folds.jumpTo(s.key);
                }}
                className={`block whitespace-nowrap rounded-full border px-4 py-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                  current === s.key
                    ? "bg-primary text-on-primary border-primary"
                    : "border-outline-variant/50 text-on-surface hover:border-primary"
                }`}
              >
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <p className="flex gap-4 px-margin-mobile md:px-0 pb-2">
        <button type="button" onClick={() => folds.setAll(false)} disabled={noneFolded} className={`${linkButton} text-xs`}>
          Expand all
        </button>
        <button type="button" onClick={() => folds.setAll(true)} disabled={allFolded} className={`${linkButton} text-xs`}>
          Collapse all
        </button>
      </p>
    </div>
  );
}
