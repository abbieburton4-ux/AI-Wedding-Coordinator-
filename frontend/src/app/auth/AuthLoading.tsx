/** Full-page loading state shown while the session resolves. */
export function AuthLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <span className="w-8 h-8 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
        <span className="font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant">
          Loading…
        </span>
      </div>
    </div>
  );
}
