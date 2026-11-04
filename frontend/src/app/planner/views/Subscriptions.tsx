import { Icon } from "../Icon";

const FEATURES = [
  "Unlimited Active Weddings",
  "AI Concierge Assistant",
  "Advanced Guest List Management",
  "Automated Budgeting Tools",
  "Custom Client Portals",
  "Priority Email & Chat Support",
];

export function Subscriptions() {
  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="mb-10">
          <h2 className="font-display-lg text-display-lg text-on-surface mb-2">Subscription & Billing</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant">
            Manage your agency's tier, view billing history, and update payment details.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <div className="lg:col-span-8">
            <div className="bg-wedding-white border border-outline-variant/30 p-8 rounded-[1rem]">
              <div className="flex justify-between items-start mb-8 pb-8 border-b border-outline-variant/20">
                <div>
                  <span className="inline-block bg-soft-clay/10 text-on-secondary-fixed-variant font-label-caps text-[10px] px-3 py-1 rounded-full mb-3 uppercase tracking-widest">
                    Current Plan
                  </span>
                  <h3 className="font-headline-md text-headline-md text-primary mb-2">Premium Coordinator</h3>
                  <p className="font-body-md text-body-md text-on-surface-variant flex items-center gap-2">
                    <Icon name="autorenew" size={18} className="text-tertiary" />
                    Billed monthly on the 15th
                  </p>
                </div>
                <div className="text-right">
                  <div className="font-display-lg text-[40px] leading-tight text-on-surface">
                    $149<span className="font-body-md text-body-md text-outline-variant">/mo</span>
                  </div>
                </div>
              </div>

              <div className="mb-10">
                <h4 className="font-label-caps text-label-caps text-secondary mb-4">Included in your plan</h4>
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-y-4 gap-x-8">
                  {FEATURES.map((feature) => (
                    <li key={feature} className="flex items-start gap-3">
                      <Icon name="check_circle" size={20} className="text-primary" />
                      <span className="font-body-md text-body-md text-on-surface">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="flex gap-4">
                <button
                  type="button"
                  className="bg-primary-container text-on-primary-container font-button-text text-button-text px-6 py-3 rounded-full hover:opacity-90 transition-opacity"
                >
                  Upgrade Plan
                </button>
                <button
                  type="button"
                  className="border border-outline-variant text-secondary font-button-text text-button-text px-6 py-3 rounded-full hover:bg-surface-container-lowest transition-colors"
                >
                  Cancel Subscription
                </button>
              </div>
            </div>
          </div>

          <div className="lg:col-span-4 space-y-8">
            <div className="bg-wedding-white border border-outline-variant/30 p-6 rounded-[1rem]">
              <h4 className="font-label-caps text-label-caps text-secondary mb-6 border-b border-outline-variant/20 pb-4">
                Payment Method
              </h4>
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-8 bg-surface-container-high rounded-[6px] flex items-center justify-center border border-outline-variant/40">
                  <span className="font-body-md text-on-surface font-semibold text-[10px] tracking-wider">VISA</span>
                </div>
                <div>
                  <p className="font-title-lg text-[16px] text-on-surface">•••• •••• •••• 4242</p>
                  <p className="font-body-md text-[12px] text-outline-variant">Expires 12/25</p>
                </div>
              </div>
              <button
                type="button"
                className="w-full border border-primary-container text-primary font-button-text text-button-text px-4 py-2 rounded-full hover:bg-primary-container/10 transition-colors"
              >
                Update Payment Details
              </button>
            </div>

            <div className="bg-surface-container-lowest border border-outline-variant/20 p-6 rounded-[1rem]">
              <h4 className="font-label-caps text-label-caps text-secondary mb-4">Next Billing Cycle</h4>
              <div className="flex justify-between items-end mb-2">
                <span className="font-body-md text-on-surface">October 15, 2024</span>
                <span className="font-title-lg text-[18px] text-on-surface">$149.00</span>
              </div>
              <p className="font-body-md text-[12px] text-outline-variant">
                Your card ending in 4242 will be charged automatically.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
