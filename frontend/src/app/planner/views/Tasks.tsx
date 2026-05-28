import { Icon } from "../Icon";
import { Avatar } from "../Avatar";

const PRIORITY_TASKS: {
  client: string;
  due: string;
  dueAccent: "error" | "secondary";
  title: string;
  desc: string;
}[] = [
  {
    client: "Emma & James",
    due: "Due Today",
    dueAccent: "error",
    title: "Finalize Floral Contract",
    desc: "Review the updated proposal from 'Bloom & Co' regarding the archway installation.",
  },
  {
    client: "Sophia & Liam",
    due: "Due Tomorrow",
    dueAccent: "secondary",
    title: "Send Deposit to Venue",
    desc: "Ensure the 50% retainer is wired to The Grand Estate to secure the September date.",
  },
];

const WEEK_TASKS: {
  tag: string;
  date: string;
  title: string;
  desc: string;
  assignee: { label: string; initials?: string };
}[] = [
  {
    tag: "Internal",
    date: "Oct 14",
    title: "Update Vendor List",
    desc: "Refresh the preferred catering contacts document with new seasonal menus.",
    assignee: { label: "Assigned to You", initials: "AM" },
  },
  {
    tag: "Chloe & Noah",
    date: "Oct 16",
    title: "Schedule Tasting",
    desc: "Coordinate a time for the couple to sample the artisanal cake options.",
    assignee: { label: "Unassigned" },
  },
];

const COMPLETED = [
  { title: "Draft Timeline", meta: "Emma & James • Yesterday" },
  { title: "Confirm String Quartet", meta: "Sophia & Liam • Monday" },
  { title: "Send Welcome Packets", meta: "Internal • Last Week" },
];

export function Tasks() {
  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 mb-10">
          <div>
            <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight mb-2">Coordination Board</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">Your curated task flow for upcoming ceremonies.</p>
          </div>
          <div className="flex gap-4">
            <button
              type="button"
              className="px-6 py-2 rounded-full border border-outline-variant/50 text-on-surface font-button-text text-button-text hover:bg-surface-container transition-colors flex items-center gap-2"
            >
              <Icon name="filter_list" size={18} />
              Filter
            </button>
            <button
              type="button"
              className="px-6 py-2 rounded-full bg-primary text-on-primary font-button-text text-button-text hover:bg-primary/90 transition-colors shadow-[0_4px_20px_rgba(115,92,0,0.15)] flex items-center gap-2"
            >
              <Icon name="add" size={18} />
              New Task
            </button>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
            <section className="bg-wedding-white rounded-[3rem] border border-outline-variant/20 p-8 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-primary-container/5 rounded-bl-full -z-10 pointer-events-none" />
              <div className="flex items-center gap-3 mb-6">
                <Icon name="priority_high" filled className="text-error" />
                <h3 className="font-title-lg text-title-lg text-on-surface">Immediate Attention</h3>
              </div>
              <div className="flex flex-col gap-4">
                {PRIORITY_TASKS.map((task) => (
                  <div
                    key={task.title}
                    className="group flex items-start justify-between p-5 rounded-[2rem] border border-outline-variant/10 hover:border-primary/30 hover:bg-surface-bright transition-all cursor-pointer"
                  >
                    <div className="flex items-start gap-4">
                      <div className="mt-1 w-5 h-5 rounded-[6px] border-2 border-outline-variant flex items-center justify-center group-hover:border-primary transition-colors" />
                      <div>
                        <div className="flex items-center gap-3 mb-1">
                          <span className="font-label-caps text-label-caps px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">
                            {task.client}
                          </span>
                          <span
                            className={
                              "font-label-caps text-label-caps " +
                              (task.dueAccent === "error" ? "text-error" : "text-secondary")
                            }
                          >
                            {task.due}
                          </span>
                        </div>
                        <h4 className="font-title-lg text-title-lg text-on-surface mb-1">{task.title}</h4>
                        <p className="font-body-md text-body-md text-on-surface-variant">{task.desc}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      aria-label="Edit task"
                      className="text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-surface-container rounded-full"
                    >
                      <Icon name="edit" />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section className="flex flex-col gap-6">
              <div className="flex items-center gap-3 px-2">
                <Icon name="calendar_month" className="text-on-surface-variant" />
                <h3 className="font-title-lg text-title-lg text-on-surface">Later This Week</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {WEEK_TASKS.map((task) => (
                  <div
                    key={task.title}
                    className="bg-wedding-white p-6 rounded-[3rem] border border-outline-variant/20 hover:shadow-[0_8px_30px_rgba(142,103,73,0.04)] transition-shadow cursor-pointer flex flex-col h-full"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <span className="font-label-caps text-label-caps px-2 py-0.5 rounded-full bg-surface-container-low text-on-surface-variant border border-outline-variant/20">
                        {task.tag}
                      </span>
                      <span className="text-on-surface-variant font-body-md text-body-md">{task.date}</span>
                    </div>
                    <h4 className="font-title-lg text-title-lg text-on-surface mb-2">{task.title}</h4>
                    <p className="font-body-md text-body-md text-on-surface-variant mb-6 flex-1">{task.desc}</p>
                    <div className="flex items-center gap-2 mt-auto border-t border-outline-variant/10 pt-4">
                      {task.assignee.initials ? (
                        <Avatar initials={task.assignee.initials} className="w-6 h-6 text-[10px]" />
                      ) : (
                        <div className="w-6 h-6 rounded-full bg-surface-container flex items-center justify-center">
                          <Icon name="person" size={14} className="text-on-surface-variant" />
                        </div>
                      )}
                      <span className="font-body-md text-body-md text-on-surface-variant">{task.assignee.label}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className="col-span-12 lg:col-span-4">
            <section className="bg-surface-container-low rounded-[3rem] border border-outline-variant/20 p-6 h-full min-h-[600px]">
              <div className="flex items-center justify-between mb-8">
                <h3 className="font-title-lg text-title-lg text-on-surface flex items-center gap-2">
                  <Icon name="check_circle" className="text-outline" />
                  Completed
                </h3>
                <button type="button" className="text-primary font-button-text text-button-text hover:underline">
                  View All
                </button>
              </div>
              <div className="flex flex-col gap-4">
                {COMPLETED.map((item) => (
                  <div
                    key={item.title}
                    className="p-4 rounded-[2rem] bg-wedding-white/50 border border-outline-variant/10 opacity-70"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 text-primary">
                        <Icon name="check_box" filled size={20} />
                      </div>
                      <div>
                        <h4 className="font-body-md text-body-md font-medium text-on-surface line-through decoration-outline-variant/50">
                          {item.title}
                        </h4>
                        <p className="font-label-caps text-label-caps text-on-surface-variant mt-1">{item.meta}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-12 text-center flex flex-col items-center opacity-50">
                <Icon name="done_all" size={48} className="text-outline-variant mb-4" />
                <p className="font-body-md text-body-md text-on-surface-variant">Great work maintaining the rhythm.</p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
