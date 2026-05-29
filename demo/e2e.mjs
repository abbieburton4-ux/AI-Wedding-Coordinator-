import { chromium } from "playwright";

const BASE = "http://localhost:5173/VenueFlow";
const SHOTS = "/tmp/vf-e2e";
const errs = [];

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
page.on("pageerror", (e) => errs.push("pageerror: " + e.message));

const log = (...a) => console.log(...a);

try {
  // 1) Signup (dev mode shows an identity picker, no Firebase needed)
  await page.goto(`${BASE}/signup`, { waitUntil: "load" });
  await page.waitForTimeout(800);
  log("STEP1 signup url:", page.url(), "| title:", await page.title());
  await page.screenshot({ path: `${SHOTS}/01-signup.png` });

  await page.getByText("Create a new couple account").click();

  // 2) New couple has 0 weddings -> WeddingProvider redirects into intake
  await page.waitForURL("**/wedding/intake", { timeout: 25000 });
  await page.getByText("Tell us about your wedding").waitFor({ timeout: 10000 });
  log("STEP2 intake url:", page.url());
  await page.screenshot({ path: `${SHOTS}/02-intake.png` });

  // 3) Submit intake (form has sensible defaults) -> POST /weddings -> agents run
  await page.getByRole("button", { name: /Build my plan/i }).click();

  // 4) Activation moment: "building your plan" (best-effort — it's brief-ish)
  try {
    await page.getByText(/building your plan/i).waitFor({ timeout: 12000 });
    log("STEP3 building-state shown");
    await page.screenshot({ path: `${SHOTS}/03-building.png` });
  } catch { log("STEP3 building-state not captured (moved on quickly)"); }

  // 5) Live dashboard once intake_planner finishes (status -> planning)
  await page.getByText("Budget lines").waitFor({ timeout: 100000 });
  log("STEP4 dashboard reached:", page.url());
  await page.screenshot({ path: `${SHOTS}/04-dashboard.png`, fullPage: true });

  // 6) The dashboard should keep polling until the venue/supplier shortlist lands
  log("STEP5 waiting for the shortlist to populate (cascade)...");
  try {
    await page.getByText(/shortlisted \d+ venue/i).waitFor({ timeout: 115000 });
    log("STEP5 shortlist populated without a manual refresh");
  } catch {
    log("STEP5 shortlist did NOT populate within timeout");
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/05-dashboard-shortlist.png`, fullPage: true });

  const text = await page.locator("main").first().innerText();
  log("---- dashboard main text (excerpt) ----");
  log(text.replace(/\n{2,}/g, "\n").slice(0, 900));
} catch (e) {
  log("E2E ERROR:", e.message);
  await page.screenshot({ path: `${SHOTS}/error.png` }).catch(() => {});
} finally {
  log("CONSOLE ERRORS:", errs.length ? errs.slice(0, 12) : "none");
  await browser.close();
}
