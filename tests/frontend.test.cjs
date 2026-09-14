const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const asset = path.join(__dirname, "../src/expense_ai_copilot/assets");
const sampleTrip = {
  id: "london-weekend",
  title: "London weekend",
  city: "London",
  currency: "GBP",
  start_date: "2026-08-14",
  end_date: "2026-08-16",
  budget_cents: 65000,
  spent_cents: 45420,
  expense_count: 8,
};
const receipt = {
  vendor: "Harbour Café",
  amount: "32.50",
  currency: "GBP",
  date: "2026-08-16",
  category: "meal",
  units: 1,
};
const draft = {
  id: "draft-1",
  trip_id: "london-weekend",
  status: "pending",
  receipt,
  issues: [],
  warnings: [],
  trace: [],
  sources: [],
  mode: "demo",
};
async function ready(window) {
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setImmediate(r));
    if (!window.document.getElementById("trip").disabled) return;
  }
  throw Error("UI stayed busy");
}
async function fixture() {
  const dom = new JSDOM(
    fs.readFileSync(path.join(asset, "index.html"), "utf8"),
    { url: "http://localhost:8000", runScripts: "outside-only" },
  );
  const { window } = dom;
  const calls = [];
  let saved = false,
    drafted = false;
  window.fetch = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ url, body });
    let data,
      ok = true;
    if (url === "/api/meta") data = { mode: "demo" };
    else if (url === "/api/trips") data = [sampleTrip];
    else if (url === "/api/trips/london-weekend")
      data = {
        trip: { ...sampleTrip, spent_cents: saved ? 48670 : 45420 },
        expenses: [],
        reviews: drafted && !saved ? [draft] : [],
      };
    else if (url === "/api/reviews") {
      drafted = true;
      data = draft;
    } else if (url === "/api/reviews/draft-1/confirm") {
      saved = true;
      data = { id: "saved-1" };
    } else if (url === "/api/analytics") {
      if (body.question === "unsupported") {
        ok = false;
        data = { detail: "Unsupported question" };
      } else
        data = {
          rows: [
            { label: "hotel", value: 315, expense_count: 2 },
            { label: "meal", value: 66, expense_count: 3 },
          ],
          chart: body.chart === "auto" ? "bar" : body.chart,
          metric: "sum",
          unit: "GBP",
          truncated: false,
          plan: { group_by: "category" },
        };
    } else if (url === "/api/rules/ask")
      data = {
        answer: "<script>untrusted feed text</script>",
        sources: [{ id: "meal-limit", text: "GBP 60 per day" }],
      };
    else throw Error("Unexpected UI request: " + url);
    return { ok, json: async () => data };
  };
  window.eval(fs.readFileSync(path.join(asset, "app.js"), "utf8"));
  await ready(window);
  return {
    window,
    calls,
    close: () => window.close(),
    $: (id) => window.document.getElementById(id),
  };
}
function submit(window, form) {
  form.dispatchEvent(
    new window.Event("submit", { bubbles: true, cancelable: true }),
  );
}
test("loads the trip, renders analytics and never requests external assets", async () => {
  const f = await fixture();
  try {
    assert.match(f.$("mode").textContent, /Offline demo/);
    assert.equal(f.$("spent").textContent, "£454.20");
    assert.equal(f.$("chart-area").querySelectorAll("svg").length, 1);
    assert.ok(f.calls.every((c) => c.url.startsWith("/api/")));
    for (const chart of ["line", "donut", "table"]) {
      f.$("chart").value = chart;
      submit(f.window, f.$("analytics-form"));
      await ready(f.window);
      assert.equal(
        f.$("chart-area").querySelectorAll("svg").length,
        chart === "table" ? 0 : 1,
      );
    }
  } finally {
    f.close();
  }
});
test("sample receipt review, form population and confirmation update the ledger", async () => {
  const f = await fixture();
  try {
    f.window.document.querySelector('[data-sample="meal"]').click();
    assert.match(f.$("receipt-text").value, /Total: GBP 32.50/);
    submit(f.window, f.$("receipt-form"));
    await ready(f.window);
    assert.equal(f.$("review-form").hidden, false);
    assert.equal(f.$("review-form").elements.amount.value, "32.50");
    f.$("review-form").elements.acknowledge_warnings.checked = true;
    submit(f.window, f.$("review-form"));
    await ready(f.window);
    const request = f.calls.find((c) => c.url.endsWith("/confirm"));
    assert.equal(request.body.amount, "32.50");
    assert.equal(request.body.acknowledge_warnings, true);
    assert.equal(f.$("spent").textContent, "£486.70");
    assert.equal(f.$("review-form").hidden, true);
  } finally {
    f.close();
  }
});
test("source text is escaped and unsupported questions do not leave a stale chart", async () => {
  const f = await fixture();
  try {
    submit(f.window, f.$("rules-form"));
    await ready(f.window);
    assert.equal(f.$("rules-answer").querySelectorAll("script").length, 0);
    assert.match(f.$("rules-answer").textContent, /<script>/);
    f.$("question").value = "unsupported";
    submit(f.window, f.$("analytics-form"));
    await ready(f.window);
    assert.equal(f.$("chart-area").childElementCount, 0);
    assert.equal(f.$("analytics-table").childElementCount, 0);
    assert.match(f.$("notice").textContent, /Unsupported question/);
  } finally {
    f.close();
  }
});
