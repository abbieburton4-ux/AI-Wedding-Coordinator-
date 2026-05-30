import { chromium } from "playwright";
import * as fs from "fs";
import * as path from "path";

const BASE = "http://127.0.0.1:5173/VenueFlow";
const VIDEO_DIR = "/Users/alanmaizon/.gemini/antigravity-ide/brain/2c81af9c-3cbd-466a-9a28-44ce50ab1d99";

const log = (...a) => console.log(...a);

async function run() {
  log("Starting browser recording...");
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    recordVideo: {
      dir: VIDEO_DIR,
      size: { width: 1280, height: 900 }
    }
  });

  const page = await ctx.newPage();
  
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  page.on("pageerror", (e) => errs.push("pageerror: " + e.message));
  
  // Natural typing simulator
  async function typeText(selector, text) {
    await page.locator(selector).fill("");
    for (const char of text) {
      await page.locator(selector).press(char);
      await page.waitForTimeout(40 + Math.random() * 40);
    }
  }

  // 1) Go to Signup
  log("1. Navigating to signup page...");
  await page.goto(`${BASE}/signup`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  log("Current URL:", page.url());
  log("Current Title:", await page.title());
  if (errs.length > 0) {
    log("Errors during load:", errs);
  }

  // Click "Create a new couple account"
  log("2. Creating a new couple account...");
  await page.getByText("Create a new couple account").click();

  // 2) Guided intake
  log("3. Waiting for the intake form...");
  await page.waitForURL("**/wedding/intake", { timeout: 25000 });
  await page.getByText("Tell us about your wedding").waitFor({ timeout: 10000 });
  await page.waitForTimeout(2000);

  // Fill Style notes to trigger the AI agent flow
  log("4. Typing style notes...");
  await typeText("textarea[placeholder*='relaxed']", "A coastal, relaxed, candlelit boho wedding with around 120 guests, local food and a live jazz band.");
  await page.waitForTimeout(1500);

  // Click "Build my plan"
  log("5. Submitting the intake form...");
  await page.getByRole("button", { name: /Build my plan/i }).click();

  // 3) Loader
  log("6. Waiting for the plan building animation...");
  try {
    await page.getByText(/building your plan/i).waitFor({ timeout: 12000 });
    await page.waitForTimeout(4000); // pause to show loader animation
  } catch (e) {
    log("Building animation skipped or too fast:", e.message);
  }

  // 4) Couple Dashboard - Wait for budget to load
  log("7. Waiting for Dashboard to load...");
  await page.getByText("Budget lines").waitFor({ timeout: 100000 });
  await page.waitForTimeout(4000);

  // Wait for the vendor shortlist
  log("8. Waiting for the vendor shortlist to populate...");
  try {
    await page.getByText(/shortlisted \d+ venue/i).waitFor({ timeout: 115000 });
  } catch (e) {
    log("Shortlist didn't show up in time, carrying on.");
  }
  await page.waitForTimeout(3000);

  // 5) Explore Couple views
  log("9. Exploring couple planning views...");
  
  // Go to Vendors
  log("   - Vendors...");
  await page.click("text=Vendors");
  await page.waitForTimeout(4000);

  // Go to Budget
  log("   - Budget...");
  await page.click("text=Budget");
  await page.waitForTimeout(4000);

  // Go to Guests & Seating
  log("   - Guests & Seating...");
  await page.click("text=Guests & Seating");
  await page.waitForTimeout(4000);

  // Go to Seating Plan
  log("   - Seating Plan...");
  await page.click("text=Seating Plan");
  await page.waitForTimeout(4000);

  // Go to Timeline
  log("   - Timeline...");
  await page.click("text=Timeline");
  await page.waitForTimeout(4000);

  // Open Concierge (Aurelia chat assistant)
  log("10. Opening Aurelia AI Concierge...");
  await page.click("button[aria-label='Account']");
  await page.waitForTimeout(1000);
  await page.click("text=Concierge");
  await page.waitForTimeout(2000);

  // Type a question
  log("11. Typing query to Aurelia...");
  await typeText("input[placeholder*='anything']", "How can we keep our florist costs within budget?");
  await page.waitForTimeout(1000);
  await page.press("input[placeholder*='anything']", "Enter");
  await page.waitForTimeout(5000); // let user read response/loading state

  // Sign out
  log("12. Signing out...");
  await page.click("button[aria-label='Back']");
  await page.waitForTimeout(1500);
  await page.click("button[aria-label='Account']");
  await page.waitForTimeout(1000);
  await page.click("text=Sign out");
  await page.waitForTimeout(2000);

  // 6) Planner flow
  log("13. Logging in as a planner...");
  await page.click("text=Continue as a planner (Mary-Aoife)");
  await page.waitForURL("**/planner", { timeout: 15000 });
  await page.waitForTimeout(3000);

  // View Clients tab
  log("14. Navigating to Planner Clients...");
  await page.click("text=Clients");
  await page.waitForTimeout(3000);

  // View Priya & David client details (drill-in)
  log("15. Drilling into client workspace...");
  await page.getByRole("button", { name: /Open workspace/i }).first().click();
  await page.waitForTimeout(5000);

  // Go back to planner Overview or other tabs
  log("16. Returning to planner home...");
  await page.goto(`${BASE}/planner`);
  await page.waitForTimeout(2000);

  log("17. Navigating to Planner Tasks...");
  await page.click("text=Tasks");
  await page.waitForTimeout(3000);

  log("18. Navigating to Planner Subscriptions...");
  await page.click("text=Subscriptions");
  await page.waitForTimeout(3000);

  log("19. Navigating to Planner Analytics...");
  await page.click("text=Analytics");
  await page.waitForTimeout(3000);

  // Finish video
  log("Closing browser and finishing video...");
  const video = page.video();
  let videoPath = null;
  if (video) {
    videoPath = await video.path();
  }
  
  await ctx.close();
  await browser.close();

  if (videoPath && fs.existsSync(videoPath)) {
    const dest = path.join(VIDEO_DIR, "demo_video.webm");
    fs.copyFileSync(videoPath, dest);
    log("Demo video successfully saved to:", dest);
    try {
      fs.unlinkSync(videoPath);
    } catch {}
  } else {
    log("Could not find generated video path.");
  }
}

run().catch((e) => {
  log("Error recording video:", e);
});
