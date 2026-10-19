import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const UPC = "036000291452";
const GTIN = "0036000291452";

test("[SCAN-1] [SCAN-9] [PAGE-1] type a barcode, see the scored product and its rules", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Or type the barcode number").fill(UPC);
  await page.getByRole("button", { name: "Look up" }).click();

  await expect(page).toHaveURL(`/p/${GTIN}`);
  await expect(page.getByRole("heading", { name: "Crunchy Oat Bars" })).toBeVisible();
  await expect(page.getByText("/ 100", { exact: true })).toBeVisible();
  await expect(page.locator("article").getByText("Mediocre", { exact: true })).toBeVisible(); // 41: a D grade, and E250 caps it (ADD-5, ENGINE-14)
  await expect(page.getByRole("heading", { name: "Every rule applied" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Source for Sugars" })).toHaveAttribute(
    "href",
    /^https:\/\//,
  );
  await expect(
    page.locator("footer").getByText("Educational information, not medical advice."),
  ).toBeVisible();
});

test("[PAGE-14] product and home pages have no WCAG 2.1 AA violations", async ({ page }) => {
  for (const path of ["/", `/p/${GTIN}`]) {
    await page.goto(path);
    await page.getByRole("heading", { level: 1 }).waitFor();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations, `${path}: ${results.violations.map((v) => v.id)}`).toEqual([]);
  }
});

test("[PAGE-11] invalid and unreachable barcodes show a message, not a crash", async ({ page }) => {
  await page.goto("/p/123");
  await expect(page.getByRole("heading", { name: "That barcode isn't valid" })).toBeVisible();

  // Not in the DB, and OFF is unreachable in e2e, so the API answers 503.
  await page.goto("/p/4006381333931");
  await expect(page.getByRole("heading", { name: "Try again in a moment" })).toBeVisible();
});

test("[SCAN-2] [SCAN-11] scanning loads nothing from third-party hosts", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["camera"]);
  const hosts = new Set<string>();
  page.on("request", (req) => hosts.add(new URL(req.url()).hostname));

  await page.goto("/scan");
  await page.getByRole("button", { name: "Scan a barcode" }).click();
  await expect(page.getByRole("button", { name: "Stop scanning" })).toBeVisible();
  await page.waitForTimeout(1500); // let the detector (and WASM, if used) load and run
  await page.getByRole("button", { name: "Stop scanning" }).click();

  expect([...hosts].filter((h) => h !== "127.0.0.1" && h !== "localhost")).toEqual([]);
});

test("[PWA-2] home opens offline; product data is never served from the cache", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload(); // now controlled by the service worker
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: /Know what's really/ })).toBeVisible();

  const failed = await page.goto(`/p/${GTIN}`).catch(() => null);
  if (failed) await expect(page.getByText("Crunchy Oat Bars")).toHaveCount(0);
  await context.setOffline(false);
});

test("[ALT-10] [RECALL-12] the recall banner shows, and an alternative opens its product page", async ({
  page,
}) => {
  await page.goto(`/p/${GTIN}`);
  const banner = page.getByRole("status").filter({ hasText: "FDA" });
  await expect(
    banner.getByRole("heading", { name: "A related FDA recall is on record" }),
  ).toBeVisible();
  await expect(banner).toContainText("Undeclared peanut");

  const strip = page.getByRole("region", { name: "Better-scored alternatives" });
  await expect(strip).toContainText("In cereal bars");
  await strip.getByRole("link", { name: /Plain Oat Bars/ }).click();

  await expect(page).toHaveURL("/p/0000000000017");
  await expect(page.getByRole("heading", { name: "Plain Oat Bars", level: 1 })).toBeVisible();
});

test("[SEARCH-7] [SEARCH-8] search by name, pick a suggestion, open the product", async ({
  page,
}) => {
  await page.goto("/");
  const box = page.getByRole("combobox", { name: "Search by name or brand" });
  await box.fill("oat bars");
  await expect(page.getByRole("option", { name: /Plain Oat Bars/ })).toBeVisible();
  await box.press("ArrowDown");
  await box.press("Enter");
  await expect(page).toHaveURL(/\/p\/\d{13}$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Oat Bars");
});

test("[ACC-4] [ACC-16] signed out: a Sign in button, an account prompt, and the privacy page", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  await page.goto("/account");
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  for (const path of ["/account", "/privacy"]) {
    await page.goto(path);
    await page.getByRole("heading", { level: 1 }).waitFor();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(results.violations, `${path}: ${results.violations.map((v) => v.id)}`).toEqual([]);
  }
});

test("[METH-8] methodology and about pages are accessible and show the API's numbers", async ({ page }) => {
  await page.goto("/methodology");
  await expect(page.getByText("60·N + 30·A + 10·P")).toBeVisible();
  for (const path of ["/methodology", "/about"]) {
    await page.goto(path);
    await page.getByRole("heading", { level: 1 }).waitFor();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(results.violations, `${path}: ${results.violations.map((v) => v.id)}`).toEqual([]);
  }
});

test("[ASSIST-9] [ASSIST-11] the assistant answers a typed health question and is accessible", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Ask the assistant/ }).click();
  await expect(page).toHaveURL("/assistant");
  await page.getByLabel("Your question").fill("I'm diabetic, can I eat crunchy oat bars?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const conversation = page.getByRole("list", { name: "Conversation" });
  await expect(conversation).toContainText("Crunchy Oat Bars");
  await expect(conversation).toContainText("For blood sugar: Sugars: 12 g per 100 g, which is medium");
  await expect(conversation).toContainText("not medical advice");
  await expect(conversation.getByRole("link", { name: "See the product" })).toHaveAttribute(
    "href",
    "/p/0036000291452",
  );
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations, results.violations.map((v) => v.id).join(",")).toEqual([]);
});

test("[EXPLORE-8] [EXPLORE-7] the landing page leads into the app tabs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: /Know what's really/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No camera? Look it up." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Three ways in. One honest score." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "The best in each aisle" })).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "App" });
  await tabs.getByRole("link", { name: "Explore" }).click();
  await expect(page).toHaveURL("/explore");
  await expect(page.getByRole("heading", { level: 1, name: "Top foods in every aisle" })).toBeVisible();
  await expect(tabs.getByRole("link", { name: "Explore" })).toHaveAttribute("aria-current", "page");
  await tabs.getByRole("link", { name: "Lookup" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Find any product" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Search by name or brand" })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});
