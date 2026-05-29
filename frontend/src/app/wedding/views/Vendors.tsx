import { Icon } from "../../planner/Icon";
import { IMG } from "../../design-system/assets";
import { useAgentMatcher, USE_FASTAPI_BACKEND } from "../../../app/api";
import type { AgentStatus } from "../../../app/api";
import { useActiveWedding } from "../WeddingProvider";

const STATIC_VENDORS = [
  { title: "The Glasshouse Estate", cat: "Venue", rating: "4.9", img: IMG.showroom },
  { title: "Ethereal Lens Studio", cat: "Photography", rating: "5.0", img: IMG.weddingConfetti },
  { title: "Culinary Canvas", cat: "Catering", rating: "4.8", img: IMG.fineDining },
];

function SkeletonCard() {
  return (
    <div className="bg-surface-container-lowest rounded-[3rem] border border-outline-variant/20 overflow-hidden flex flex-col animate-pulse">
      <div className="h-48 w-full bg-surface-container-low" />
      <div className="p-gutter flex flex-col gap-3">
        <div className="h-3 bg-surface-container-low rounded-full w-1/3" />
        <div className="h-5 bg-surface-container-low rounded-full w-2/3" />
        <div className="h-3 bg-surface-container-low rounded-full w-1/2" />
      </div>
    </div>
  );
}

function AgentThinkingBanner({ rationale }: { rationale: string }) {
  return (
    <div className="bg-primary-container/20 border border-primary-container/40 rounded-[2rem] p-5 mb-6 flex items-start gap-3 animate-in fade-in duration-500">
      <div className="relative mt-0.5">
        <Icon name="psychology" size={22} className="text-primary animate-pulse" />
      </div>
      <div className="flex-1">
        <p className="font-button-text text-primary text-sm mb-1">AI Agent Working</p>
        <p className="font-body-md text-on-surface-variant text-sm leading-relaxed">
          {rationale}
        </p>
      </div>
    </div>
  );
}

function GuardrailBlockPanel({ rationale }: { rationale: string }) {
  return (
    <div className="bg-tertiary-container/20 border border-tertiary-container/50 rounded-[2rem] p-6 mb-6">
      <div className="flex items-center gap-3 mb-3">
        <Icon name="shield" size={22} className="text-tertiary" />
        <h3 className="font-title-lg text-title-lg text-tertiary">AI Safety Guardrail</h3>
      </div>
      <p className="font-body-md text-on-surface-variant text-sm leading-relaxed mb-4">
        {rationale}
      </p>
      <div className="flex gap-3">
        <button
          type="button"
          className="px-5 py-2.5 bg-tertiary text-on-tertiary rounded-full font-button-text text-sm hover:opacity-90 transition-opacity"
        >
          Edit Parameters
        </button>
        <button
          type="button"
          className="px-5 py-2.5 bg-surface-container border border-outline-variant/30 rounded-full font-button-text text-sm text-on-surface hover:bg-surface-container-high transition-colors"
        >
          Override Safeguard
        </button>
      </div>
    </div>
  );
}

function AgentErrorBanner({ message }: { message: string }) {
  return (
    <div className="bg-error-container/20 border border-error-container/40 rounded-[2rem] p-5 mb-6 flex items-start gap-3">
      <Icon name="error" size={22} className="text-error" />
      <div className="flex-1">
        <p className="font-button-text text-error text-sm mb-1">Matching Error</p>
        <p className="font-body-md text-on-surface-variant text-sm">
          {message}
        </p>
      </div>
    </div>
  );
}

export function Vendors() {
  const { activeWedding } = useActiveWedding();
  const weddingId = activeWedding?.id ?? "";
  const {
    triggerVenueMatch,
    triggerSupplierMatch,
    status,
    rationale,
    errorMsg,
    reset,
  } = useAgentMatcher(weddingId);

  const isRunning = status === "running";
  const showResults = !USE_FASTAPI_BACKEND || status === "idle" || status === "success";

  return (
    <main className="pt-16 md:pl-72 pb-20 md:pb-8">
      <section className="px-margin-mobile md:px-margin-desktop py-8 md:py-12 bg-surface">
        <div className="flex flex-col gap-6">
          <div>
            <h2 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary">
              Curated Vendors
            </h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mt-2">
              Discover and manage the professionals bringing your vision to life.
            </p>
          </div>
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Icon name="search" className="absolute left-4 top-1/2 -translate-y-1/2 text-outline" />
              <input
                className="w-full h-12 pl-12 pr-4 bg-surface-container-lowest border-b border-outline-variant/20 rounded-t-[2rem] focus:outline-none"
                placeholder="Search vendors..."
                type="text"
              />
            </div>
            {USE_FASTAPI_BACKEND && (
              <button
                type="button"
                disabled={isRunning}
                onClick={() => triggerVenueMatch()}
                className="flex items-center gap-2 px-6 h-12 bg-primary/10 rounded-full border border-primary/20 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50 disabled:cursor-wait"
              >
                {isRunning ? (
                  <>
                    <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <span className="font-button-text">Matching...</span>
                  </>
                ) : (
                  <>
                    <Icon name="auto_awesome" size={18} />
                    <span className="font-button-text">Run AI Venue Matcher</span>
                  </>
                )}
              </button>
            )}
            {!USE_FASTAPI_BACKEND && (
              <button
                type="button"
                className="flex items-center gap-2 px-6 h-12 bg-soft-clay/10 rounded-full border border-soft-clay/20 text-tertiary"
              >
                <Icon name="auto_awesome" size={18} />
                <span className="font-button-text">Recommended by AI</span>
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="px-margin-mobile md:px-margin-desktop py-6">
        {/* Agent Status Banners */}
        {isRunning && <AgentThinkingBanner rationale={rationale} />}
        {status === "blocked" && <GuardrailBlockPanel rationale={rationale} />}
        {status === "error" && <AgentErrorBanner message={errorMsg} />}
        {status === "timeout" && (
          <AgentThinkingBanner rationale="Matching is taking longer than expected. Results will appear when the agent completes." />
        )}

        {/* Success celebration */}
        {status === "success" && (
          <div className="bg-primary-container/10 border border-primary-container/30 rounded-[2rem] p-5 mb-6 flex items-center gap-3">
            <Icon name="check_circle" size={22} className="text-primary" />
            <p className="font-button-text text-primary text-sm">
              Venue matching complete! Here are your AI-curated recommendations.
            </p>
          </div>
        )}

        {/* Vendor Grid — skeleton or real cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
          {isRunning ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : (
            showResults &&
            STATIC_VENDORS.map((v) => (
              <div
                key={v.title}
                className="bg-surface-container-lowest rounded-[3rem] border border-outline-variant/20 overflow-hidden flex flex-col group hover:shadow-lg transition-all"
              >
                <div className="relative h-48 w-full">
                  <img src={v.img} alt={v.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                  <div className="absolute top-3 right-3 bg-surface-container-lowest/90 px-3 py-1 rounded-full flex items-center gap-1">
                    <Icon name="auto_awesome" filled size={14} className="text-tertiary" />
                    <span className="font-label-caps text-[10px] text-tertiary font-bold">MATCH</span>
                  </div>
                </div>
                <div className="p-gutter flex flex-col flex-1 gap-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-label-caps text-[10px] text-outline tracking-widest uppercase">{v.cat}</span>
                      <h3 className="font-title-lg text-title-lg text-on-surface mt-1">{v.title}</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      <Icon name="star" filled size={16} className="text-primary" />
                      <span className="font-body-md">{v.rating}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
