import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../../shared/Icon";

/**
 * Which sections of a screen are folded, remembered on this device per wedding
 * (PD-015). It's a screen preference, not wedding data, so localStorage is fine for it.
 * Everything starts unfolded. Without a wedding id nothing is remembered.
 */
export type Folds<K extends string> = {
  folded: (key: K) => boolean;
  toggle: (key: K) => void;
  open: (key: K) => void;
  setAll: (fold: boolean) => void;
};

function readFolds<K extends string>(storageKey: string | null, keys: readonly K[]): K[] {
  if (!storageKey) return [];
  try {
    const raw = JSON.parse(window.localStorage.getItem(storageKey) ?? "[]");
    return Array.isArray(raw)
      ? raw.filter((k): k is K => typeof k === "string" && (keys as readonly string[]).includes(k))
      : [];
  } catch {
    return [];
  }
}

/** `storageKey` names this screen and wedding, e.g. `venueflow.vendorFolds.<wedding id>`. */
export function useRememberedFolds<K extends string>(storageKey: string | null, keys: readonly K[]): Folds<K> {
  const [folded, setFolded] = useState<K[]>(() => readFolds(storageKey, keys));
  const loadedFor = useRef(storageKey);
  const keysRef = useRef(keys);
  keysRef.current = keys;

  // Another wedding on the same device has its own preference. When the key changes,
  // this effect reads the new wedding's folds from storage before the save effect runs.
  // That save still writes the old folds under the new key once, and the next render
  // writes the folds just read over them. Keep this effect first so the read comes
  // before that write.
  useEffect(() => {
    if (loadedFor.current === storageKey) return;
    loadedFor.current = storageKey;
    setFolded(readFolds(storageKey, keysRef.current));
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey || loadedFor.current !== storageKey) return;
    try {
      if (folded.length) window.localStorage.setItem(storageKey, JSON.stringify(folded));
      else window.localStorage.removeItem(storageKey);
    } catch {
      // Private browsing or a full store: folding still works, it just isn't remembered.
    }
  }, [storageKey, folded]);

  return useMemo<Folds<K>>(() => ({
    folded: (key) => folded.includes(key),
    toggle: (key) => setFolded((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key])),
    open: (key) => setFolded((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : prev)),
    setAll: (fold) => setFolded(fold ? [...keysRef.current] : []),
  }), [folded]);
}

/** Scrolls a section into view (instantly if the person prefers less motion) and focuses it. */
export function scrollToElement(el: HTMLElement) {
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  el.focus({ preventScroll: true });
}

/** The arrow on a fold's heading button: down when open, sideways when folded. */
export function FoldChevron({ folded }: { folded: boolean }) {
  return (
    <Icon
      name="expand_more"
      size={22}
      className={`shrink-0 text-on-surface-variant transition-transform motion-reduce:transition-none ${folded ? "-rotate-90" : ""}`}
    />
  );
}
