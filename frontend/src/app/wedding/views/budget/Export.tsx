import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../../shared/Icon";
import { API_BASE_URL } from "../../../api";
import { useAuth } from "../../../auth/AuthProvider";
import { linkButton, primaryButton } from "./parts";
import { FoldBody, SECTION_SCROLL, SectionHeading, sectionId } from "./sections";

/**
 * Download the budget as a CSV, or open the print page to save it as a PDF (PD-013
 * step 5). The API builds the file from the same figures as the screen, and it goes
 * straight to this person's own device: nothing is sent to anyone.
 */
export function BudgetExport({ weddingId, today }: { weddingId: string; today: string }) {
  const { getToken } = useAuth();
  const [archived, setArchived] = useState(false);
  const [contacts, setContacts] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (archived) params.set("include_archived", "true");
      if (contacts) params.set("include_contacts", "true");
      const token = await getToken();
      const query = params.toString();
      const res = await fetch(
        `${API_BASE_URL}/api/v1/weddings/${weddingId}/budget/export.csv${query ? `?${query}` : ""}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {}, cache: "no-store" },
      );
      if (!res.ok) throw new Error(`The download didn't work (status ${res.status}). Please try again.`);
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      // The server's name carries its own Chicago date; the page's is the fallback when
      // the browser can't read that header.
      const named = /filename="(wedding-budget-\d{4}-\d{2}-\d{2}\.csv)"/.exec(
        res.headers.get("Content-Disposition") ?? "",
      );
      a.download = named ? named[1] : `wedding-budget-${today}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Let the browser start the download before the file is let go.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The download didn't work. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      id={sectionId("export")} tabIndex={-1} aria-labelledby="export-heading"
      className={`mb-10 bg-surface-container-lowest border border-outline-variant/20 rounded-[2rem] p-5 ${SECTION_SCROLL} focus:outline-none`}
    >
      <SectionHeading section="export" id="export-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">
        Export
      </SectionHeading>
      <FoldBody section="export">
      <p className="text-sm text-on-surface-variant mb-4">
        Download the budget as a spreadsheet file (CSV) that opens in Google Sheets or Excel, or open a page to
        print or save as a PDF. The file goes to this device only; nothing is sent to anyone.
      </p>
      <div className="space-y-2 mb-4">
        <label className="flex items-start gap-2 text-sm text-on-surface">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} className="mt-1" />
          <span>Include archived expenses (they're listed, but never added to the totals)</span>
        </label>
        <label className="flex items-start gap-2 text-sm text-on-surface">
          <input type="checkbox" checked={contacts} onChange={(e) => setContacts(e.target.checked)} className="mt-1" />
          <span>
            Include vendor contact details (contact name, email and phone)
            {contacts && (
              <span className="block text-xs text-on-surface-variant mt-1">
                The file will contain vendors' contact details. Keep it somewhere private and think before sharing it.
              </span>
            )}
          </span>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <button type="button" onClick={download} disabled={busy} className={`${primaryButton} flex items-center gap-2`}>
          <Icon name="download" size={18} />
          {busy ? "Preparing the file…" : "Download CSV"}
        </button>
        <Link to="/wedding/budget/print" className={`${linkButton} flex items-center gap-1`}>
          <Icon name="print" size={18} /> Print / save as PDF
        </Link>
      </div>
      {error && <p role="alert" className="text-sm text-error mt-3">{error}</p>}
      </FoldBody>
    </section>
  );
}
