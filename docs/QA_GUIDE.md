# Multi-Agent Retail Analytics System
# Questions and Answers

---

## Part 1: Why This Project Exists

**Q: What problem does this project solve?**

This project solves the last-mile problem in enterprise analytics. The Enterprise Analytics and Terraform IaC projects built a complete data warehouse with a star schema and Terraform infrastructure, but the data still requires technical skills to access. Business users need to write SQL, navigate dashboards, or ask an analyst every time they want an answer. This project puts a natural language interface on top of that data layer so anyone can ask questions like "Which products are at risk of stockout?" and get a data-grounded answer in seconds.

**Q: Why build AI agents instead of just dashboards?**

Dashboards are static. They show pre-defined views of data and require the user to know which dashboard to open, which filters to apply, and how to interpret the results. Agents are dynamic. They interpret the question, decide which data to query, execute the SQL, and synthesize a natural language answer. An agent can also combine data from multiple domains in a single response, something that would require switching between several dashboards manually.

**Q: Why is this relevant for a GCP Solutions Architect role?**

Solutions architects are increasingly expected to design systems that integrate AI with cloud infrastructure. This project demonstrates the ability to connect an LLM (Gemini) to a production data warehouse (BigQuery) through a structured agent framework (ADK), all running on Google Cloud. It shows architectural thinking (why three agents instead of one), security awareness (fixed SQL instead of text-to-SQL), and practical integration skills.

**Q: How does this project connect to the other projects in the portfolio?**

The Enterprise Analytics project built the data. The Terraform IaC project automated the infrastructure. This project makes the data conversational. The three labs form a complete vertical: raw data flows into a star schema (Enterprise Analytics), infrastructure is reproducible via Terraform (Terraform IaC), and AI agents provide a natural language interface to the results (this project). Future projects (streaming, RAG, anomaly detection) will add more capabilities that agents can orchestrate.

---

## Part 2: Architecture Decisions

**Q: Why use multiple agents instead of a single agent with all 11 tools?**

A single agent with 11 tools would work, but it creates three problems. First, the LLM has to read descriptions of all 11 tools every time it processes a query, which increases the chance of selecting the wrong tool. Second, the system prompt has to cover three distinct domains (inventory, sales, customers) in a single block of text, diluting the instructions for each domain. Third, you cannot test or improve one domain without risking regressions in the others.

With three specialist agents, each one sees only its own 3 to 4 tools and has a focused system prompt tuned to its domain. The inventory agent knows about reorder points and stockout thresholds. The sales agent thinks in terms of margins and revenue mix. The customer agent focuses on lifetime value and retention. This separation improves tool selection accuracy, reduces hallucination, and allows independent testing.

**Q: What is the orchestrator and how does routing work?**

The orchestrator is the root agent that receives every user query first. It has no tools of its own. Its only job is to read the query, compare it against the descriptions of its three sub-agents, and decide which specialist should handle it. Gemini does this by calling an internal function called `transfer_to_agent` with the name of the chosen specialist.

For example, if you ask "Which products are at risk of stockout?", Gemini reads the inventory_analyst description ("Handles questions about stock levels, stockouts, overstock situations...") and routes the query there. For cross-functional queries like "Give me an executive summary," the orchestrator may engage multiple agents sequentially.

**Q: Why did you choose Google ADK over LangGraph or CrewAI?**

Three reasons. First, ADK has native integration with Google Cloud services. BigQuery, Vertex AI, and Cloud Run all work out of the box without custom adapters. Second, ADK includes a built-in evaluation framework with tool trajectory matching, which means I can write test cases that verify not just the final answer but the exact sequence of tool calls the agent made. Third, ADK has a built-in Dev UI that provides a web-based chat interface with full trace visibility, showing every routing decision and tool call. For a portfolio targeting GCP roles, using Google's own agent framework makes the most sense.

**Q: Why Gemini 2.5 Flash instead of a larger model?**

Gemini 2.5 Flash provides strong reasoning at low latency and is available on the free tier through AI Studio. The free tier gives 15 requests per minute and 1,500 requests per day, which is more than enough for development and demos. The agents do not need creative writing or complex reasoning. They need reliable tool selection and accurate data summarization, which Flash handles well. If the use case required more sophisticated multi-step reasoning, upgrading to Gemini 2.5 Pro would be straightforward.

**Q: Why use AI Studio instead of Vertex AI for the Gemini API?**

The Vertex AI endpoint (`aiplatform.googleapis.com`) requires a billing-enabled GCP project. AI Studio uses a different endpoint (`generativelanguage.googleapis.com`) that works with a free API key and no billing required. Both provide access to the same Gemini models with the same quality. The only difference is rate limits: AI Studio has a lower free tier than Vertex AI's paid tier. For production deployment, switching to Vertex AI requires changing two environment variables, not rewriting code.

**Q: Why fixed SQL queries instead of letting the agent generate SQL dynamically?**

Text-to-SQL sounds powerful but introduces several risks in a production context. The agent could generate syntactically invalid SQL, causing errors. It could write inefficient queries that scan entire tables, running up BigQuery costs. It could be manipulated through prompt injection to access data it should not see. And the generated SQL is not version-controlled or reviewable.

Fixed SQL queries solve all of these problems. Each tool function contains a pre-written, optimized query that has been tested against the actual schema. The queries are predictable, secure, and auditable. The trade-off is flexibility: users cannot ask arbitrary questions outside the 11 predefined tools. In practice, these 11 tools cover the most common analytical questions, and additional tools can be added as needed.

---

## Part 3: Implementation Details

**Q: How does the BigQuery connection work?**

The BigQuery Python client (`google-cloud-bigquery`) automatically discovers credentials from the application default credentials file. This file is created by running `gcloud auth application-default login`, which stores an OAuth token at a known location on the filesystem. When the code calls `bigquery.Client()` with no arguments, it finds this token and uses it to authenticate API calls. The client also auto-discovers the project ID from the gcloud configuration.

**Q: What does a tool function look like and how does ADK use it?**

A tool function is a standard Python function with type hints and a docstring:

```python
def get_revenue_by_region() -> dict:
    """Get total revenue broken down by store region.

    Returns:
        Dictionary with revenue data by region.
    """
    sql = "SELECT store_region, SUM(total_amount) ..."
    return {"status": "success", "result": query_bigquery(sql)}
```

ADK reads the function signature and docstring, then passes them to Gemini as a tool description. When Gemini decides to call this tool, ADK invokes the Python function and returns the result to Gemini for summarization. The type hints tell Gemini what parameter types to pass. The docstring tells Gemini when and why to use this tool.

**Q: Why do all tools return the same dictionary format?**

Consistency. Every tool returns `{"status": "success", "result": <text>}` or `{"status": "error", "result": <error_message>}`. This means the agent instructions can be generic: "If a tool returns an error status, inform the user." It also means the result is always pre-formatted text rather than raw data structures, which is more token-efficient for LLM processing and avoids issues with complex nested JSON.

**Q: Why is fct_sales denormalized instead of joining fact and dimension tables?**

The Enterprise Analytics project's `fct_sales` table is a wide, denormalized fact table that already contains fields like `store_region`, `category_l1`, `product_name`, `brand`, `txn_year`, and `txn_month`. These fields would normally live in dimension tables and require joins. Because they are embedded in the fact table, most sales queries do not need any joins at all, which means simpler SQL, faster queries, and lower BigQuery costs. BigQuery's columnar storage handles wide tables efficiently, so the additional storage cost of denormalization is negligible.

**Q: How does the query_bigquery helper function work?**

It takes a SQL string, submits it to BigQuery, waits for results, and formats them as numbered text rows. Each row is displayed as pipe-delimited key-value pairs. If the query returns no results, it returns "No results found." If an exception occurs (invalid SQL, permission denied, table not found), it catches the error and returns it as text rather than raising an exception. This is important because if a tool raises an exception, ADK may not pass a useful error message to the agent. By returning errors as text, the agent can tell the user what went wrong.

**Q: What is the __init__.py file for?**

It marks the `retail_analytics_agents` directory as a Python package. ADK requires agent code to live in a Python package (a directory with `__init__.py`). Without this file, the relative import `from . import tools` in `agent.py` would fail, and ADK would not discover the agents when scanning for packages.

**Q: What is the .env file and why is there one inside the agent folder?**

The `.env` file contains `GOOGLE_API_KEY=your-key-here`. ADK uses the `python-dotenv` library to automatically load environment variables from `.env` files in the agent package directory. The API key tells ADK which Gemini API key to use when making LLM calls. The `.env` file is listed in `.gitignore` so it is never committed to version control, keeping the API key private.

---

## Part 4: The Data Layer

**Q: What data does the system query?**

The agents query the `retail_gold` dataset in BigQuery, which is a star schema built by Enterprise Analytics. It contains 7 tables:

Fact tables:
- `fct_sales` (204,549 rows): Individual sales transactions with embedded store, product, and date attributes. Contains total_amount, gross_profit, margin_pct, quantity, and denormalized fields.
- `fct_inventory` (180,000 rows): Daily inventory snapshots per product per store. Contains stock_on_hand, reorder_point, is_stockout, is_below_reorder_point, inventory_status, and days_since_last_sale.
- `fct_daily_sales` (40,361 rows): Aggregated daily metrics by store, region, and channel.

Dimension tables:
- `dim_customer` (5,000 rows): Customer profiles with customer_segment, loyalty_tier, lifetime_revenue, lifetime_orders, avg_order_value, activity_status, and days_since_last_purchase.
- `dim_product` (500 rows): Product catalog with product_name, category_l1, category_l2, category_l3, brand, and price_tier.
- `dim_store` (50 rows): Store locations with store_name, region, store_type, city, and country_code.
- `dim_date` (2,922 rows): Date dimension with year, quarter, month, day_of_week, and is_weekend.

**Q: How much revenue does the system cover?**

Approximately $214 million across three regions: AMERICAS (40.36%, $86.37M), EMEA (36.23%, $77.52M), and APAC (23.56%, $50.42M). Five product categories: Electronics (45.78%), Home (37.31%), Clothing, Beauty, and Grocery.

**Q: Why did the gold layer need to be rebuilt?**

The Terraform IaC project only created the bronze layer tables (raw data ingested from CSV files). The silver layer (cleaned, validated data) and gold layer (star schema with business metrics) require additional SQL transformations that run as part of The Enterprise Analytics project's build process. When we started this project, the `retail_gold` dataset existed but was empty. Running `rebuild.sh` populated all three layers in about 15 minutes.

**Q: What schema issues did you encounter?**

The initial agent tools were written assuming a normalized star schema with surrogate keys like `product_key` and `store_key`. The actual schema uses natural keys (`product_id`, `store_id`, `customer_id`) and denormalized fact tables. Column names were also different from assumptions: `quantity_on_hand` was actually `stock_on_hand`, `category` was `category_l1`, and `region` in dim_store was `store_region` in fct_sales. We discovered these by inspecting schemas with `bq show --schema --format=prettyjson` and rewriting all SQL queries to match.

---

## Part 5: Agent Behavior

**Q: Walk through what happens when someone asks "Which products are at risk of stockout?"**

Step 1: The user types the query in the ADK Dev UI at localhost:8000.

Step 2: ADK sends the query to the root orchestrator along with descriptions of all three sub-agents.

Step 3: Gemini reads the descriptions and identifies this as an inventory question. It calls `transfer_to_agent(agent_name="inventory_analyst")`.

Step 4: ADK transfers control to the inventory_analyst agent, passing along the original query and the inventory agent's tools and instructions.

Step 5: The inventory agent's Gemini instance reads its tools and decides to call `get_inventory_stockout_risk(threshold=10)`.

Step 6: ADK invokes the Python function, which constructs a SQL query that selects products with stock_on_hand below 10 from the latest snapshot date, limited to 20 results.

Step 7: The BigQuery client executes the SQL and returns rows of products with 0 units in stock.

Step 8: The tool formats the results as numbered text rows and returns them to the agent.

Step 9: Gemini reads the data and composes a response: "The following 20 products are currently at risk of stockout as they have 0 units in stock..." followed by the list of product IDs, store IDs, and reorder points.

Step 10: ADK sends the response back to the user in the Dev UI.

All of these steps are visible in the Trace tab of the ADK Dev UI, showing timing, routing decisions, and tool call parameters.

**Q: What happens with cross-functional queries like "Give me an executive summary"?**

The orchestrator recognizes this requires multiple domains. It routes to the Sales Analyst first, which fires three tools in parallel: `get_revenue_by_region`, `get_sales_trends_by_month`, and `get_revenue_by_category`. The Sales Analyst produces a comprehensive breakdown covering $214M total revenue, regional performance (AMERICAS leading at 40%), monthly trends (peak in December), and category mix (Electronics at 46%). It then notes that for a complete executive summary covering Inventory and Customer performance, those specialists should also be consulted.

**Q: Can agents call each other directly?**

No. In ADK's hierarchical model, only the root orchestrator can route to sub-agents via `transfer_to_agent`. Sub-agents cannot call each other directly. If the inventory agent needs sales data, the orchestrator must coordinate by engaging both agents and synthesizing their responses. This is a design choice that keeps the routing logic centralized and auditable.

**Q: What if an agent cannot answer a question?**

If a tool returns an error (for example, a BigQuery table is not found), the error text is returned to the agent as a normal tool result. The agent then tells the user what went wrong. If the question falls outside the agent's domain, the orchestrator should have routed it to a different specialist. If no specialist can handle it, the orchestrator will respond directly, explaining that the question is outside the system's current capabilities.

---

## Part 6: Evaluation and Testing

**Q: What is an evalset and how does it work?**

An evalset is a JSON file containing test cases for ADK agents. Each test case specifies a user query, the expected sequence of tool calls (called the tool trajectory), and an approximate expected response. When you run the eval, ADK replays each test case, records the actual tool calls and response, and compares them against the expected values using scoring metrics.

**Q: What metrics does the eval use?**

Two metrics. `tool_trajectory_avg_score` compares the expected tool call sequence against the actual sequence. A score of 1.0 means the agent called exactly the right tools in exactly the right order. The threshold is set at 0.6, allowing some flexibility because the orchestrator may add extra reasoning steps. `response_match_score` uses ROUGE-1 (word overlap) to compare the actual response against the expected response. The threshold is set at 0.4 because agents use live data and wording varies between runs.

**Q: Why are the eval thresholds set so low?**

Because the system is non-deterministic. The same query can produce slightly different tool call sequences and differently worded responses across runs. The orchestrator might add a reasoning step before routing. The agent might call tools in a different order. The response wording depends on the specific data returned. Setting thresholds at 0.6 and 0.4 catches genuine regressions (wrong agent, wrong tool) while tolerating normal variation.

**Q: What do the 10 test cases cover?**

Three inventory tests: stockout risk, overstock detection, and regional inventory summary. Four sales tests: top products by revenue, regional revenue breakdown, monthly sales trends, and category performance. Three customer tests: segment analysis, top customers by lifetime revenue, and loyalty tier comparison. Each test verifies both routing (correct sub-agent selected) and tool selection (correct BigQuery function called).

**Q: What is the verification script and what does it check?**

The verification script (`verify.sh`) runs 62 checks to validate the entire data layer that supports the agents. It checks that all 5 BigQuery datasets exist, all 7 gold layer tables have the expected minimum row counts, 20+ critical columns are populated (not null), all 11 agent tool queries execute successfully against live data, and data integrity is maintained (revenue totals, region coverage, margin ranges). It produces a PASS/FAIL report for each check.

---

## Part 7: Development Process

**Q: What was the development sequence?**

1. Installed Python 3.14 on Windows with PATH and long path support enabled
2. Created a virtual environment and installed google-adk and google-cloud-bigquery
3. Installed gcloud CLI and configured authentication with `gcloud init` and `gcloud auth application-default login`
4. Generated a free Gemini API key from AI Studio
5. Discovered that the gold layer was empty and ran `rebuild.sh` to populate it (15 minutes)
6. Inspected the actual BigQuery schemas with `bq show --schema --format=prettyjson`
7. Wrote tools.py with 11 BigQuery tool functions based on the actual column names
8. Wrote agent.py with the root orchestrator and 3 specialist agents
9. Launched with `adk web .` and tested with the ADK Dev UI
10. Fixed schema mismatches (column names, denormalized vs normalized assumptions)
11. Tested all query types: inventory, sales, customer, and cross-functional
12. Created the evalset with 10 test cases
13. Wrote and ran the verification script (62/62 passing)

**Q: What were the biggest blockers?**

The gold layer being empty was the biggest blocker. The tools returned "table not found" errors because `retail_gold` had no tables. This was solved by running the Enterprise Analytics rebuild script.

The second blocker was schema assumptions. The initial tools assumed a normalized star schema with surrogate keys, but the actual schema uses denormalized fact tables with natural keys and embedded dimension fields. Every SQL query had to be rewritten after inspecting the actual schemas.

The third blocker was the `adk web` command. Running `adk web retail_analytics_agents` failed with "No agents found" because it looked for subpackages inside the agent folder. The correct command is `adk web .` from the parent directory.

**Q: How long did the full build take?**

About 4 hours from zero to a working multi-agent system with passing tests. Roughly 1 hour for environment setup (Python, gcloud, Gemini API key), 30 minutes for data layer rebuild, 1.5 hours for agent development and debugging, and 1 hour for testing, evaluation, and documentation.

**Q: What would you do differently next time?**

Inspect the actual BigQuery schema before writing any tool code. The assumption-based approach cost at least 30 minutes of debugging. Also, start with a single agent and verify the BigQuery connection works before splitting into multiple agents. Adding the multi-agent orchestration on top of a working single agent is easier than debugging routing and tool issues simultaneously.

---

## Part 8: Production Considerations

**Q: How would you deploy this to production?**

ADK agents can be deployed to Cloud Run as a containerized FastAPI service. You would create a Dockerfile that installs the dependencies, copies the agent code, and runs `adk api_server` instead of `adk web`. The Gemini API key would move from a `.env` file to Secret Manager. Authentication would switch from application-default credentials to a service account. A Cloud Run service with 1 vCPU and 512MB RAM is sufficient for the current workload.

**Q: What are the scaling limits?**

The Gemini free tier allows 15 requests per minute and 1,500 per day. Each user query requires 2 to 4 Gemini calls (orchestrator routing plus specialist tool calls), so the system supports roughly 4 to 7 concurrent queries per minute. For higher throughput, upgrading to a paid Gemini tier through Vertex AI removes these limits. BigQuery handles concurrent queries well and auto-scales, so the data layer is not a bottleneck.

**Q: What about security?**

The current system uses fixed SQL queries, which eliminates SQL injection risk. The Gemini API key is stored in a `.env` file excluded from version control. BigQuery access is controlled by IAM roles on the service account. In production, additional measures would include: moving the API key to Secret Manager, adding authentication to the Cloud Run service (IAM or API keys), implementing rate limiting, and adding audit logging for all queries.

**Q: How would you add new analytical capabilities?**

Add a new tool function to `tools.py` and assign it to the appropriate agent (or create a new specialist agent). For example, to add year-over-year comparison, write a `get_yoy_revenue_comparison()` function and add it to the sales agent's tool list. ADK discovers tools automatically from the agent's `tools` parameter. No framework code changes are needed.

**Q: Could this system use text-to-SQL for ad-hoc queries?**

Yes, as a future enhancement. You could add a "power user" agent that generates SQL from natural language using the schema as context. This would handle questions outside the predefined 11 tools. The risk mitigation approach would be to run generated SQL in a read-only context with query cost limits, validate the SQL before execution, and log all generated queries for audit. This would complement rather than replace the fixed-query tools.

---

## Part 9: Cost and Resource Summary

**Q: What does this cost to run?**

$0. The entire system runs on free resources: BigQuery free tier, Gemini free tier through AI Studio (no credit card required), and local Python execution for the agent framework. There are no cloud compute costs because the agent runs locally.

**Q: What GCP services are used?**

BigQuery (data warehouse), Cloud Storage (used by Enterprise Analytics for staging), and the Gemini Developer API (via AI Studio). No Vertex AI, no Cloud Run, no Compute Engine, and no Cloud Functions are required for local development.

**Q: What are the data volumes?**

Total rows across all gold layer tables: approximately 433,000 (204K sales + 180K inventory + 40K daily sales + 5K customers + 500 products + 50 stores + 2.9K dates). Total revenue: approximately $214 million. Coverage: 50 stores across 3 regions (AMERICAS, EMEA, APAC), 500 products in 5 categories, 5,000 customers across multiple segments and loyalty tiers.
