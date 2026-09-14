# TripLedger · Personal Travel Copilot

A personal project by **Pankaj Kumar**: turn receipt text into reviewed expenses, track a trip budget and explore spending with natural-language questions.

**Try it without an API key.** The offline demo includes a fictional London weekend, editable receipt drafts and interactive charts. Optional OpenAI or Anthropic mode adds model-based extraction, query planning and grounded answers.

This repository contains an independent portfolio application and fictional fixtures. It does not contain employer source code, customer data or claims about company production performance.

## Start here

Use **Python 3.12**. An internet connection is needed for the initial package installation.

From this repository's root folder:

~~~bash
python -m venv .venv
~~~

Activate the environment:

- macOS / Linux: source .venv/bin/activate
- Windows PowerShell: .venv\Scripts\Activate.ps1
- Windows Command Prompt: .venv\Scripts\activate.bat

Then:

~~~bash
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m expense_ai_copilot
~~~

Open **http://127.0.0.1:8000**. No Docker, database server, account or API key is needed for the demo. If that port is busy, run with --port 8001 and open the matching address.

The lock file records the tested Python 3.12 runtime. Linux/Python 3.12 was verified; other platforms have not been tested here.

## A two-minute walkthrough

1. Open the fictional **London weekend** trip: budget £650; saved spending £454.20.
2. Click **Dinner**, then **Review receipt**. The reference number should not become the amount.
3. Check the £32.50 result and select **Confirm & save**. Spending becomes £486.70.
4. Ask **Daily spending trend**, switch to a line chart, then filter a category or date range.
5. Ask **What is my daily meal budget?** and inspect the cited personal rules.
6. Try **Hotel over budget** or **Missing total** to see the review and correction flow.
7. Create your own trip and use **Download CSV** to export its ledger.

Drafts, confirmed expenses and the activity history survive a restart. Repeating the same receipt does not create another expense.

## What is implemented

| Feature | Implementation |
| --- | --- |
| Receipt review | Actual LangGraph nodes: extraction → rule retrieval → validation |
| Durable workflow | SQLite saves drafts; confirmation rechecks current spending inside a transaction |
| Human control | Review and explicit confirmation for every receipt; editable extracted fields |
| Money handling | Decimal validation at the boundary; integer minor units in storage |
| Conversational analytics | A validated query plan is compiled into allowlisted, parameterized SQL |
| Visualisations | Bar, line, donut and table views with category/date filters |
| Grounded budget answers | Lexical retrieval over personal trip rules; source IDs accompany answers |
| Model adapters | OpenAI Responses structured output and Anthropic structured tool results |
| Failure handling | Refusals, incomplete responses, invalid fields and unknown citations fail explicitly |
| Local-first interface | FastAPI, SQLite and packaged HTML/CSS/JavaScript; no frontend CDN |

The model never supplies executable SQL. It cannot write expenses directly. LangGraph handles the review graph; the application database, not a LangGraph checkpointer, persists the human-review boundary.

## Offline and live behaviour

| Operation | Offline demo | Live model mode |
| --- | --- | --- |
| Receipt extraction | Explicit total/date/currency labels and category keywords | Model returns validated structured fields |
| Analytics language | The supported phrases below | More phrasing within the same bounded query schema |
| Budget answers | Retrieved rule text | Model explanation grounded in retrieved rules |
| Expense writes | User confirmation | User confirmation |
| Network | None after installation | Configured model provider |

Supported offline questions:

- Show spending by category
- Daily spending trend
- Top merchants
- How much have I spent?
- Average expense by category
- How many expenses per category

A chart suffix such as "as a donut chart" is supported. Use the visible controls for category and date filters. Other offline questions return a clear limitation; they are not silently approximated.

Receipt input is **text**, not an image/PDF OCR service. Use ISO dates or UK day/month/year dates and a labelled total. Multiple dates, currencies or conflicting totals require correction. Category inference is deliberately conservative.

## Optional live AI

Copy .env.example to .env in the folder where you run the app. Set:

~~~dotenv
TRIPLEDGER_PROVIDER=openai
TRIPLEDGER_MODEL=YOUR_SUPPORTED_MODEL_ID
TRIPLEDGER_API_KEY=YOUR_API_KEY
~~~

For Anthropic, set the provider to anthropic and use an appropriate model ID and key. Use a model that supports the required structured-output/tool-use API. Restart the app after changing configuration.

**Live mode sends the supplied receipt text and questions to your chosen provider and can incur API charges.** Keys stay on the backend. There are no automatic paid retries and no silent demo fallback. Confirm generated fields before saving them.

Provider request/response contracts and error handling were tested with mock transports. Real model calls and account-specific model compatibility were **not** tested with credentials in this handover.

Official integration references:
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [Anthropic tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)

## Development and checks

~~~bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m build --wheel
python scripts/smoke.py
~~~

Tests cover receipt ambiguity, exact money values, persistent drafts, duplicate/concurrent requests, budget rechecks, trip isolation, unsupported questions, API boundaries and provider failures. A GitHub Actions workflow runs lint, tests and a wheel build when this revision is pushed.

For the optional JavaScript interaction tests:

~~~bash
npm ci
npm test
~~~

These use a DOM test environment, not a visual browser. See docs/VERIFICATION.md for the exact checks completed.

API documentation is at http://127.0.0.1:8000/docs. Example requests and implementation decisions are in docs/ARCHITECTURE.md.

## Data and scope

Data is stored in .tripledger/tripledger.sqlite3 beneath the launch directory. Set TRIPLEDGER_DATA_DIR to choose another folder. Stop the app before copying the database for backup. Raw pasted receipt text is not retained; extracted fields, its deduplication hash and review metadata are retained.

Each trip uses one of GBP, EUR, USD or INR. There is no exchange-rate conversion, bank integration, booking, reimbursement approval, financial advice, cloud deployment or production authentication. Keep this personal app on your own machine. Docker's supplied port mapping is also loopback-only.

SQLite intentionally keeps the download self-contained. The old repository's unconnected ClickHouse/AWS diagrams have been removed; this revision does not claim to run either service.

Docker Compose is provided as an optional local path:

~~~bash
docker compose up --build
~~~

Docker was not available for validation here; the Python quickstart is the verified path.

## Portfolio wording

**TripLedger — Personal Travel Copilot**  
Built a personal travel-budget application with FastAPI, LangGraph and SQLite, combining receipt review, human-confirmed expense capture, grounded budget answers and natural-language analytics with interactive charts.

Do not call offline template matching a live LLM demonstration. When recording a demo, show the visible mode badge and explain whether a model is configured.

MIT licensed. See LICENSE.
