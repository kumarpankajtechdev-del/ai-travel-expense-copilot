"use strict";
const $ = (id) => document.getElementById(id);
let tripId = "",
  currentTrip = null,
  activeReview = null,
  busy = false;
const colors = [
  "#176457",
  "#a3bf57",
  "#d6a15d",
  "#6987a1",
  "#bd8077",
  "#84b9aa",
];
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function notify(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "success";
}
async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Check the entered fields and try again.",
    );
  return data;
}
async function task(action) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach((b) => {
    b.disabled = true;
  });
  $("trip").disabled = true;
  try {
    await action();
  } catch (error) {
    notify(error.message, true);
  } finally {
    busy = false;
    document.querySelectorAll("button").forEach((b) => {
      b.disabled = false;
    });
    $("trip").disabled = false;
  }
}
function money(cents) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: currentTrip.currency,
  }).format(cents / 100);
}
function formValues(form) {
  return Object.fromEntries(new FormData(form));
}
async function refresh() {
  const data = await api("/api/trips/" + encodeURIComponent(tripId));
  currentTrip = data.trip;
  $("budget").textContent = money(currentTrip.budget_cents);
  $("spent").textContent = money(currentTrip.spent_cents);
  $("remaining").textContent = money(
    currentTrip.budget_cents - currentTrip.spent_cents,
  );
  $("trip-context").textContent =
    currentTrip.city +
    " · " +
    currentTrip.start_date +
    " – " +
    currentTrip.end_date +
    " · " +
    currentTrip.expense_count +
    " saved expenses" +
    (tripId === "london-weekend" ? " · Fictional sample data" : "");
  $("ledger").replaceChildren();
  for (const item of data.expenses) {
    const row = el("tr");
    [item.date, item.vendor, item.category, money(item.amount_cents)].forEach(
      (v, i) => row.append(el("td", v, i === 3 ? "number" : "")),
    );
    $("ledger").append(row);
  }
  if (!data.expenses.length) {
    const row = el("tr");
    const cell = el("td", "No expenses yet. Review a receipt to get started.");
    cell.colSpan = 4;
    row.append(cell);
    $("ledger").append(row);
  }
  $("draft-list").replaceChildren();
  if (data.reviews.length)
    $("draft-list").append(el("h3", "Unfinished reviews"));
  for (const draft of data.reviews) {
    const button = el(
      "button",
      draft.receipt.vendor || "Receipt draft",
      "draft-item",
    );
    button.type = "button";
    button.addEventListener("click", () => showReview(draft));
    $("draft-list").append(button);
  }
  $("export").href = "/api/trips/" + encodeURIComponent(tripId) + "/export";
}
function showReview(review) {
  activeReview = review;
  $("review-form").hidden = false;
  $("review-status").textContent =
    review.status === "pending"
      ? "Nothing has been saved yet. Correct any missing or inaccurate details."
      : "This receipt has already been " + review.status + ".";
  for (const [key, value] of Object.entries(review.receipt))
    if ($("review-form").elements[key])
      $("review-form").elements[key].value = value === null ? "" : value;
  $("review-form").elements.acknowledge_warnings.checked = false;
  $("review-messages").replaceChildren();
  for (const message of review.issues)
    $("review-messages").append(el("p", message, "error"));
  for (const message of review.warnings)
    $("review-messages").append(el("p", message, "warning"));
  $("review-trace").textContent = JSON.stringify(
    { mode: review.mode, trace: review.trace, sources: review.sources },
    null,
    2,
  );
  $("review-form").querySelector(".actions").hidden =
    review.status !== "pending";
}
function svgNode(tag, attrs, text) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (text !== undefined) n.textContent = text;
  return n;
}
function drawChart(result) {
  $("chart-area").replaceChildren();
  $("analytics-table").replaceChildren();
  const header = el("tr");
  header.append(
    el("th", "Group"),
    el("th", result.metric + " · " + result.unit, "number"),
  );
  const head = el("thead");
  head.append(header);
  $("analytics-table").append(head);
  const body = el("tbody");
  result.rows.forEach((row) => {
    const tr = el("tr");
    tr.append(
      el("td", row.label),
      el("td", row.value.toFixed(result.unit === "expenses" ? 0 : 2), "number"),
    );
    body.append(tr);
  });
  $("analytics-table").append(body);
  $("chart-note").textContent = result.truncated
    ? "Showing the first 100 groups. Narrow your filters."
    : result.rows.length
      ? "Values include confirmed expenses only."
      : "No expenses match these filters.";
  if (result.chart === "table" || !result.rows.length) return;
  const rows = result.rows.slice(0, 12),
    max = Math.max(...rows.map((r) => r.value), 1);
  const svg = svgNode("svg", {
    viewBox: "0 0 480 230",
    role: "img",
    "aria-label":
      result.chart +
      " chart of " +
      result.metric +
      " by " +
      result.plan.group_by,
  });
  if (result.chart === "bar") {
    const step = 205 / rows.length;
    rows.forEach((row, i) => {
      const y = 10 + i * step;
      svg.append(
        svgNode(
          "text",
          { x: 0, y: y + 13, fill: "#627773", "font-size": 11 },
          String(row.label).slice(0, 19),
        ),
      );
      svg.append(
        svgNode("rect", {
          x: 135,
          y,
          width: Math.max(1, (row.value / max) * 270),
          height: Math.min(22, step - 5),
          rx: 3,
          fill: colors[i % colors.length],
        }),
      );
      svg.append(
        svgNode(
          "text",
          { x: 410, y: y + 13, fill: "#183e3a", "font-size": 10 },
          row.value.toFixed(result.unit === "expenses" ? 0 : 2),
        ),
      );
    });
  } else if (result.chart === "line") {
    const points = rows.map((r, i) => [
      40 + (i * 395) / Math.max(1, rows.length - 1),
      190 - (r.value / max) * 155,
    ]);
    svg.append(
      svgNode("line", { x1: 35, x2: 445, y1: 195, y2: 195, stroke: "#dce4dd" }),
    );
    svg.append(
      svgNode("polyline", {
        points: points.map((p) => p.join(",")).join(" "),
        fill: "none",
        stroke: "#176457",
        "stroke-width": 3,
      }),
    );
    points.forEach((p, i) => {
      svg.append(
        svgNode("circle", { cx: p[0], cy: p[1], r: 4, fill: "#176457" }),
      );
      svg.append(
        svgNode(
          "text",
          {
            x: p[0],
            y: p[1] - 10,
            "text-anchor": "middle",
            fill: "#183e3a",
            "font-size": 10,
          },
          rows[i].value,
        ),
      );
    });
    [0, rows.length - 1]
      .filter((v, i, a) => a.indexOf(v) === i)
      .forEach((i) =>
        svg.append(
          svgNode(
            "text",
            {
              x: points[i][0],
              y: 217,
              "text-anchor": i ? "end" : "start",
              fill: "#627773",
              "font-size": 11,
            },
            rows[i].label,
          ),
        ),
      );
  } else {
    const total = rows.reduce((sum, r) => sum + r.value, 0);
    if (total <= 0) {
      $("chart-area").append(el("p", "No positive values to chart."));
      return;
    }
    let offset = 0;
    const circumference = 2 * Math.PI * 75;
    rows.forEach((row, i) => {
      const length = (row.value / total) * circumference;
      svg.append(
        svgNode("circle", {
          cx: 135,
          cy: 110,
          r: 75,
          fill: "none",
          stroke: colors[i % colors.length],
          "stroke-width": 30,
          "stroke-dasharray": length + " " + (circumference - length),
          "stroke-dashoffset": -offset,
          transform: "rotate(-90 135 110)",
        }),
      );
      offset += length;
      svg.append(
        svgNode(
          "text",
          {
            x: 250,
            y: 24 + i * 17,
            fill: colors[i % colors.length],
            "font-size": 11,
          },
          String(row.label).slice(0, 22) +
            " · " +
            Math.round((row.value / total) * 100) +
            "%",
        ),
      );
    });
    svg.append(
      svgNode(
        "text",
        {
          x: 135,
          y: 113,
          "text-anchor": "middle",
          fill: "#183e3a",
          "font-size": 20,
        },
        total.toFixed(result.unit === "expenses" ? 0 : 2),
      ),
    );
  }
  $("chart-area").append(svg);
  if (result.rows.length > 12)
    $("chart-note").textContent +=
      " Chart shows the first 12 groups; the table contains all returned groups.";
}
async function analytics() {
  $("chart-area").replaceChildren();
  $("analytics-table").replaceChildren();
  $("query-trace").textContent = "";
  $("chart-note").textContent = "Loading spending…";
  const data = {
    trip_id: tripId,
    question: $("question").value,
    chart: $("chart").value,
  };
  for (const [id, key] of [
    ["category", "category"],
    ["from", "start_date"],
    ["to", "end_date"],
  ])
    if ($(id).value) data[key] = $(id).value;
  let result;
  try {
    result = await api("/api/analytics", data);
  } catch (error) {
    $("chart-note").textContent = "No result. Check the question or filters and try again.";
    throw error;
  }
  drawChart(result);
  $("query-trace").textContent = JSON.stringify(result, null, 2);
}
async function loadTrips(preferred) {
  const trips = await api("/api/trips");
  $("trip").replaceChildren();
  trips.forEach((t) => {
    const option = el("option", t.title);
    option.value = t.id;
    $("trip").append(option);
  });
  tripId = preferred || trips[0].id;
  $("trip").value = tripId;
  await refresh();
  await analytics();
}
$("trip").addEventListener("change", () =>
  task(async () => {
    tripId = $("trip").value;
    activeReview = null;
    $("review-form").hidden = true;
    $("rules-answer").textContent = "";
    $("sources").replaceChildren();
    $("events").textContent = "";
    $("from").value = "";
    $("to").value = "";
    await refresh();
    await analytics();
  }),
);
$("new-trip").addEventListener("click", () => {
  $("create-panel").hidden = !$("create-panel").hidden;
});
$("create-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(async () => {
    const trip = await api("/api/trips", formValues(event.target));
    $("create-panel").hidden = true;
    $("review-form").hidden = true;
    await loadTrips(trip.id);
    notify("Your trip is ready.");
  });
});
document.querySelectorAll("[data-sample]").forEach((button) =>
  button.addEventListener("click", () => {
    const date = currentTrip.end_date,
      currency = currentTrip.currency;
    const samples = {
      meal:
        "Harbour Café\n" +
        date +
        "\nDinner\nReference: 987654321\nTotal: " +
        currency +
        " 32.50",
      hotel:
        "Garden House Hotel\n" +
        date +
        "\n1 night\nSubtotal: " +
        currency +
        " 190.00\nTax: " +
        currency +
        " 20.00\nGrand total: " +
        currency +
        " 210.00",
      ambiguous:
        "City Taxi\n" + date + "\nBooking reference: 987654321\nPaid by card",
    };
    $("receipt-text").value = samples[button.dataset.sample];
  }),
);
document.querySelectorAll("[data-question]").forEach((button) =>
  button.addEventListener("click", () => {
    $("question").value = button.dataset.question;
    task(analytics);
  }),
);
$("receipt-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(async () => {
    const review = await api("/api/reviews", {
      trip_id: tripId,
      receipt_text: $("receipt-text").value,
    });
    await refresh();
    showReview(review);
    notify(
      review.status === "pending"
        ? "Receipt reviewed. Check the details before saving."
        : "This receipt was already reviewed; no duplicate was created.",
    );
  });
});
$("review-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(async () => {
    const values = formValues(event.target);
    values.units = Number(values.units);
    values.acknowledge_warnings =
      event.target.elements.acknowledge_warnings.checked;
    await api("/api/reviews/" + activeReview.id + "/confirm", values);
    $("review-form").hidden = true;
    activeReview = null;
    await refresh();
    await analytics();
    notify("Expense saved to your trip.");
  });
});
$("discard").addEventListener("click", () =>
  task(async () => {
    await api("/api/reviews/" + activeReview.id + "/discard", {});
    $("review-form").hidden = true;
    activeReview = null;
    await refresh();
    notify("Draft discarded.");
  }),
);
$("analytics-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(analytics);
});
$("rules-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(async () => {
    $("rules-answer").textContent = "";
    $("sources").replaceChildren();
    const answer = await api("/api/rules/ask", {
      trip_id: tripId,
      question: $("rules-question").value,
    });
    $("rules-answer").textContent = answer.answer;
    answer.sources.forEach((s) => {
      const source = el("span", s.id, "source");
      source.title = s.text;
      $("sources").append(source);
    });
  });
});
$("load-events").addEventListener("click", () =>
  task(async () => {
    $("events").textContent = JSON.stringify(
      await api("/api/trips/" + tripId + "/events"),
      null,
      2,
    );
  }),
);
task(async () => {
  const meta = await api("/api/meta");
  $("mode").textContent =
    meta.mode === "demo" ? "Offline demo · no API key" : "Live · " + meta.mode;
  if (meta.mode !== "demo")
    $("mode-note").textContent =
      "Live mode sends receipt text and questions to your configured model provider. Review all generated results.";
  await loadTrips("london-weekend");
});
