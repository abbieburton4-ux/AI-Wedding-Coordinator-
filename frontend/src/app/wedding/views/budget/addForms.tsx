import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

/**
 * The Budget screen's add forms (Add expense, Add payment, Add tip) stay closed until
 * asked for, and only one is open at a time (PD-020). Opening another closes the one
 * that's open; if something was typed in it, the couple are asked first.
 */
type AddForms = {
  openKey: string | null;
  /** Opens this form, closing any other. False if the couple chose to keep the other. */
  open: (key: string) => boolean;
  /** Closes this form if it's the open one. With ``ask``, checks first if anything was typed. */
  close: (key: string, ask?: boolean) => boolean;
  setDirty: (key: string, dirty: boolean) => void;
  /** Whether this form is the open one right now (not as of the last render). */
  isCurrent: (key: string) => boolean;
};

const AddFormsContext = createContext<AddForms | null>(null);

const DISCARD_OTHER = "You've started filling in another form. Close it and lose what you typed there?";
const DISCARD_THIS = "Close this form and lose what you typed?";

export function AddFormsProvider({ children }: { children: ReactNode }) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  // Read in the callbacks, so they never act on a stale open form.
  const current = useRef<string | null>(null);
  const dirty = useRef(new Set<string>());

  const open = useCallback((key: string) => {
    const other = current.current;
    if (other && other !== key) {
      if (dirty.current.has(other) && !window.confirm(DISCARD_OTHER)) return false;
      dirty.current.delete(other);
    }
    current.current = key;
    setOpenKey(key);
    return true;
  }, []);

  const close = useCallback((key: string, ask = false) => {
    if (current.current !== key) return true;
    if (ask && dirty.current.has(key) && !window.confirm(DISCARD_THIS)) return false;
    dirty.current.delete(key);
    current.current = null;
    setOpenKey(null);
    return true;
  }, []);

  const setDirty = useCallback((key: string, isDirty: boolean) => {
    if (isDirty) dirty.current.add(key);
    else dirty.current.delete(key);
  }, []);

  const isCurrent = useCallback((key: string) => current.current === key, []);

  const value = useMemo(
    () => ({ openKey, open, close, setDirty, isCurrent }), [openKey, open, close, setDirty, isCurrent],
  );
  return <AddFormsContext.Provider value={value}>{children}</AddFormsContext.Provider>;
}

/**
 * One add form's open state. ``opener`` is the button that opens it: focus goes back
 * there when the form closes. Without a provider the form works on its own.
 */
export function useAddForm(key: string) {
  const ctx = useContext(AddFormsContext);
  const [localOpen, setLocalOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const isOpen = ctx ? ctx.openKey === key : localOpen;

  const open = useCallback(() => {
    if (ctx) return ctx.open(key);
    setLocalOpen(true);
    return true;
  }, [ctx, key]);

  /** Closes the form and puts focus back on its button. ``ask`` is for closing with the button. */
  const close = useCallback((ask = false) => {
    // A save that lands after another form opened leaves focus where the couple are now.
    if (ctx && !ctx.isCurrent(key)) return false;
    const closed = ctx ? ctx.close(key, ask) : (setLocalOpen(false), true);
    if (closed) window.requestAnimationFrame(() => opener.current?.focus());
    return closed;
  }, [ctx, key]);

  /** Closes the form without moving focus, for a save that puts focus somewhere else. */
  const closeQuietly = useCallback(() => {
    if (ctx) ctx.close(key);
    else setLocalOpen(false);
  }, [ctx, key]);

  const toggle = useCallback(() => (isOpen ? close(true) : open()), [isOpen, close, open]);

  /** Whether this form is still the open one, for work that finishes after a wait. */
  const isCurrent = useCallback(() => (ctx ? ctx.isCurrent(key) : true), [ctx, key]);

  return { isOpen, open, close, closeQuietly, toggle, isCurrent, opener };
}

/**
 * Opens an add form by its key from outside it (the main Add expense chooser), so the
 * chooser stays open if the couple keep another form's typing. Always true without a provider.
 */
export function useOpenAddForm() {
  const ctx = useContext(AddFormsContext);
  return useCallback((key: string) => (ctx ? ctx.open(key) : true), [ctx]);
}

/** Tells the screen whether anything has been typed in an open add form. */
export function useReportDirty(key: string, isDirty: boolean) {
  const ctx = useContext(AddFormsContext);
  const setDirty = ctx?.setDirty;
  useEffect(() => { setDirty?.(key, isDirty); }, [setDirty, key, isDirty]);
  useEffect(() => () => setDirty?.(key, false), [setDirty, key]);
}

/** Moves focus to the first field in a form that has just opened, scrolling it into view. */
export function focusFirstField(container: HTMLElement | null) {
  const field = container?.querySelector<HTMLElement>("input, select, textarea");
  if (!field) return;
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  field.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
  field.focus({ preventScroll: true });
}
