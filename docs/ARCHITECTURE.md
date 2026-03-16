# Architecture Decisions: ADK Multi-Agent System

## ADR-01: Google ADK over LangGraph/CrewAI

**Decision:** Use Google Agent Development Kit (ADK) as the agent framework.

**Context:** Multiple frameworks exist for building multi-agent systems: LangGraph, CrewAI, AutoGen, and Google ADK. This portfolio targets GCP Solutions Architect roles.

**Rationale:**
- Native integration with Google Cloud services (BigQuery, Vertex AI, Cloud Run)
- Built-in ADK Dev UI for interactive testing and debugging
- First-class evaluation framework with tool trajectory matching
- Sub-agent routing via `transfer_to_agent` provides a clean delegation pattern
- Deployment path to Cloud Run and Vertex AI Agent Engine
- Aligns with GCP-focused portfolio positioning

**Trade-offs:** ADK is newer (GA 2025) with a smaller community than LangGraph. However, its Google ecosystem integration and built-in eval tooling outweigh this for a GCP portfolio.

---

## ADR-02: Gemini 2.5 Flash via AI Studio (Not Vertex AI)

**Decision:** Use Gemini 2.5 Flash through the AI Studio Developer API, not Vertex AI.

**Context:** GCP sandbox environments block `aiplatform.googleapis.com`, making Vertex AI unavailable. Gemini is accessible through two separate endpoints.

**Rationale:**
- AI Studio API uses `generativelanguage.googleapis.com`, which is not blocked by sandbox
- Free tier: 15 RPM, 1,500 requests per day, sufficient for development and demos
- No credit card required
- Gemini 2.5 Flash provides strong reasoning at low latency
- Same model quality whether accessed via AI Studio or Vertex AI

**Trade-offs:** AI Studio has lower rate limits than Vertex AI. For production deployment, migration to Vertex AI is straightforward (change env vars to use `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`).

---

## ADR-03: Specialist Agent Pattern (3 Agents + Orchestrator)

**Decision:** Implement 3 domain-specialist agents coordinated by a root orchestrator, rather than a single monolithic agent.

**Context:** The retail analytics platform has three distinct domains: inventory, sales, and customers. A single agent could handle all queries, but separation provides benefits.

**Rationale:**
- **Focused instructions**: Each agent has domain-specific prompts, reducing hallucination
- **Tool isolation**: Agents only see tools relevant to their domain (3 to 4 tools each vs. 11 total)
- **Parallel execution**: Cross-functional queries can engage multiple agents simultaneously
- **Independent testing**: Each agent can be evaluated separately
- **Scalability pattern**: New domains (e.g., supply chain) can be added as new sub-agents without modifying existing ones

**Trade-offs:** Adds one LLM call for routing (orchestrator to sub-agent). In practice, this adds roughly 1 second latency, which is acceptable for the analytical use case.

---

## ADR-04: Direct BigQuery Queries (Not Text-to-SQL)

**Decision:** Implement fixed SQL queries as tool functions rather than generating SQL dynamically.

**Context:** Two approaches exist: (a) predefined SQL functions that agents call with parameters, or (b) text-to-SQL where the agent writes queries from natural language.

**Rationale:**
- **Reliability**: Fixed queries always return valid results with no SQL syntax errors
- **Security**: No SQL injection risk from user input
- **Performance**: Queries are optimized and tested against the actual schema
- **Cost control**: Predictable BigQuery costs with no runaway full-table scans
- **Auditability**: Every query is version-controlled and reviewable

**Trade-offs:** Less flexible. Users cannot ask arbitrary questions. Mitigated by providing 11 tools that cover the most common analytical questions. Text-to-SQL could be added as a future enhancement for power users.

---

## ADR-05: Denormalized Gold Layer Queries

**Decision:** Query the gold layer's denormalized `fct_sales` table directly rather than joining fact and dimension tables.

**Context:** The Enterprise Analytics project's `fct_sales` is a wide, denormalized fact table that embeds store, product, and date fields. Traditional star schema queries would join `fct_sales` with `dim_store`, `dim_product`, and other dimension tables.

**Rationale:**
- `fct_sales` already contains `store_region`, `category_l1`, `product_name`, `brand`, `txn_year`, `txn_month`, so no joins are needed for most sales queries
- Fewer joins means faster queries and lower BigQuery costs
- Simpler SQL is easier to maintain and debug
- `dim_customer` has lifetime metrics embedded (no separate summary table needed)
- `fct_inventory` joins with `dim_store` only when regional aggregation is needed

**Trade-offs:** Denormalized tables use more storage, but BigQuery's columnar storage and per-column pricing make this negligible. The simplicity benefit outweighs the storage cost.

---

## ADR-06: Tool Return Format (Dict with Status)

**Decision:** All tools return `{"status": "success", "result": <formatted_text>}` rather than raw data structures.

**Context:** ADK tools can return any JSON-serializable object. The agent (LLM) processes the return value to formulate its response.

**Rationale:**
- **Consistent contract**: Every tool returns the same shape, making agent instructions simpler
- **Pre-formatted text**: Query results are formatted as numbered rows with labeled fields, which is easy for the LLM to parse and summarize
- **Error handling**: Errors return `{"status": "error", "result": "BigQuery error: ..."}` so the agent can report issues gracefully
- **Token efficiency**: Formatted text is more token-efficient than nested JSON for tabular data

**Trade-offs:** Less structured than returning raw dictionaries or dataframes. If downstream tools needed to process the data programmatically, structured output would be better. For LLM consumption, formatted text works well.
