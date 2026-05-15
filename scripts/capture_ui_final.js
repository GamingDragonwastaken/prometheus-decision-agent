const { chromium } = require("playwright");

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 3200 } });

  await page.goto("http://127.0.0.1:8507", { waitUntil: "networkidle" });
  await page.locator('[data-testid="stSelectbox"]').click();
  await page.getByRole("option", { name: "Should I compete with OpenAI in enterprise AI?" }).click();
  await page.getByRole("button", { name: /Load cached result/ }).click();

  await page.getByText("NO-GO").first().waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("Where They Disagreed").waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("Recommendation 1").waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("PROMETHEUS · Built for AI Agent Olympics").waitFor({
    state: "visible",
    timeout: 30000,
  });

  await page.screenshot({ path: "docs/screenshot_ui_final.png", fullPage: true });
  await browser.close();
}

main().catch(async (error) => {
  console.error(error);
  process.exit(1);
});
