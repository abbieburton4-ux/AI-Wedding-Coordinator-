import { Icon } from "./Icon";
import { Avatar } from "./Avatar";

export function PlannerTopBar() {
  return (
    <header className="w-full h-16 bg-surface-bright/90 backdrop-blur-md flex justify-between items-center px-margin-mobile md:px-margin-desktop border-b border-outline-variant/20 sticky top-0 z-30 shrink-0">
      <div className="flex items-center w-56 md:w-80 bg-surface-container-low rounded-full px-4 py-2 border border-outline-variant/30 focus-within:border-primary transition-colors">
        <Icon name="search" className="text-on-surface-variant mr-2 text-[20px]" />
        <input
          type="text"
          placeholder="Search clients, tasks..."
          className="bg-transparent border-none focus:ring-0 focus:outline-none text-body-md w-full placeholder:text-on-surface-variant/60 p-0 text-on-surface"
        />
      </div>

      <div className="flex items-center gap-6">
        <button
          type="button"
          aria-label="Notifications"
          className="relative text-on-surface-variant hover:text-primary transition-colors duration-200 active:opacity-70"
        >
          <Icon name="notifications" />
          <span className="absolute top-0 right-0 w-2 h-2 bg-error rounded-full" />
        </button>
        <button
          type="button"
          aria-label="Help"
          className="text-on-surface-variant hover:text-primary transition-colors duration-200 active:opacity-70"
        >
          <Icon name="help_outline" />
        </button>
        <Avatar initials="AM" className="w-8 h-8 text-[11px] border border-outline-variant/30" />
      </div>
    </header>
  );
}
