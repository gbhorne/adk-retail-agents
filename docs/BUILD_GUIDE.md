# Complete Build Guide

## Multi-Agent Retail Analytics System with Google ADK with Google ADK

This document provides a full explanation of how this project was built from scratch, what every command does, and how each component fits together. It is intended as both a learning reference and a reproducibility guide.

---

## Table of Contents

1. Prerequisites and Dependencies
2. Local Environment Setup
3. Google Cloud Authentication
4. Gemini API Configuration
5. Project Structure and File Roles
6. Agent Code Walkthrough
7. Tool Code Walkthrough
8. Running and Testing the System
9. Evaluation Framework
10. Verification Script
11. Troubleshooting

---

## 1. Prerequisites and Dependencies

### What You Need Before Starting

**Enterprise Analytics Platform** must be deployed first. The agents query the BigQuery star schema created in Enterprise Analytics. Without it, there is no data to query.

**Terraform IaC Project** is optional but recommended. It provisions the BigQuery datasets and tables via Terraform. If Terraform IaC was used, the bronze tables already exist and `rebuild.sh` will populate the silver and gold layers.

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Agent runtime and BigQuery client |
| pip | 25+ | Python package manager |
| Google Cloud SDK | 536+ | Authentication and BigQuery CLI |
| Google ADK | 1.25+ | Agent framework |
| google-cloud-bigquery | 3.40+ | BigQuery Python client |

### Accounts Required

| Account | Purpose | Cost |
|---------|---------|------|
| GCP project | BigQuery data warehouse | Free (sandbox) |
| Google AI Studio | Gemini API key | Free (no credit card) |

---

## 2. Local Environment Setup

### 2.1 Install Python

Download Python 3.13 or 3.14 from https://www.python.org/downloads/

On Windows, the installer is now a "Python Install Manager" (.msix). During installation:

```
Install Python Install Manager?
-> Click "Install Python"

Windows is not configured to allow paths longer than 260 characters.
Update setting now? [y/N]
-> Type: y
```

This enables long file paths, which is important because Python packages (especially ADK with its many dependencies) create deeply nested directory structures that can exceed 260 characters on Windows.

```
The global shortcuts directory is not configured.
Add commands directory to your PATH now? [y/N]
-> Type: y
```

This adds `C:\Users\<username>\AppData\Local\Python\bin` to your system PATH so you can run `py`, `python`, and `pip` from any terminal.

```
Install CPython now? [Y/n]
-> Type: Y
```

This installs the actual Python runtime (CPython is the standard Python implementation written in C).

After installation, reboot the PC (required for long path setting to take effect), then verify:

```powershell
py --version
# Expected: Python 3.14.x

py -m pip --version
# Expected: pip 25.x from C:\Users\...\site-packages\pip (python 3.14)
```

`py` is the Python launcher for Windows. It finds and runs the correct Python version. `py -m pip` runs pip as a module under the Python interpreter, which is more reliable than calling `pip` directly.

### 2.2 Create Project Directory and Virtual Environment

```powershell
cd C:\Users\gbhor
mkdir adk-retail-agents
cd adk-retail-agents
py -m venv .venv
```

`py -m venv .venv` creates a virtual environment in a folder called `.venv`. A virtual environment is an isolated Python installation that keeps this project's packages separate from the system Python. This prevents version conflicts between projects.

### 2.3 Activate the Virtual Environment

```powershell
.venv\Scripts\Activate.ps1
```

If you get a "running scripts is disabled" error, run this first:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

This changes the PowerShell execution policy to allow locally created scripts to run. `RemoteSigned` means local scripts run freely but downloaded scripts need a digital signature. This is a one-time setting per user.

After activation, your prompt changes to `(.venv) PS C:\...` indicating the virtual environment is active. All `pip install` commands now install into `.venv/` instead of system Python.

### 2.4 Install Dependencies

```powershell
pip install google-adk google-cloud-bigquery
```

This installs:
- `google-adk` (1.25.1): The Agent Development Kit framework, which brings in Gemini client, FastAPI server, evaluation tools, and many transitive dependencies
- `google-cloud-bigquery` (3.40.1): The BigQuery Python client for executing SQL queries

The ADK install pulls in approximately 80 packages including FastAPI (web server for Dev UI), uvicorn (ASGI server), google-genai (Gemini client), protobuf (serialization), and others.

---

## 3. Google Cloud Authentication

### 3.1 Install Google Cloud SDK

Download from https://cloud.google.com/sdk/docs/install

The Windows installer bundles its own Python and does not interfere with your project Python. During installation, leave all defaults checked including "Run gcloud init" at the end.

### 3.2 Initialize gcloud

```
gcloud init
```

This interactive command:
1. Opens a browser for Google account login
2. Lists available GCP projects and asks you to select one
3. Asks for a default compute zone

For the project, select your sandbox project (e.g., `playground-s-11-4c6f9668`).

For the zone, enter `us-central1-f`. Note: it asks for a zone (e.g., `us-central1-f`), not a region (e.g., `us-central1`). A zone is a specific data center within a region.

After init completes, your gcloud config is stored at `C:\Users\<username>\.boto` and `C:\Users\<username>\AppData\Roaming\gcloud\`.

### 3.3 Set Application Default Credentials

```
gcloud auth application-default login
```

This creates a credential file that Python client libraries use automatically. When your code creates a `bigquery.Client()`, it finds these credentials without any explicit configuration. The credential file is stored at:

```
C:\Users\<username>\AppData\Roaming\gcloud\application_default_credentials.json
```

### 3.4 Verify Connection

```powershell
py -c "from google.cloud import bigquery; client = bigquery.Client(); print(f'Connected to: {client.project}')"
```

This one-liner imports the BigQuery client, creates an instance (which auto-discovers the project from gcloud config), and prints the project ID. If this works, your authentication chain is complete:

```
gcloud config (project) -> application default credentials -> BigQuery client
```

---

## 4. Gemini API Configuration

### 4.1 Get an API Key

Go to https://aistudio.google.com/apikey and click "Create API Key". This creates a key for the Gemini Developer API, which uses the endpoint `generativelanguage.googleapis.com`.

This is different from Vertex AI, which uses `aiplatform.googleapis.com`. The sandbox blocks Vertex AI but not the AI Studio endpoint. Both provide access to the same Gemini models.

Free tier limits: 15 requests per minute, 1,500 requests per day. No credit card required.

### 4.2 Store the Key

Create a `.env` file inside the `retail_analytics_agents/` folder:

```
GOOGLE_API_KEY=AIzaSy...your-key-here
```

ADK automatically reads `.env` files in the agent package directory. The `GOOGLE_API_KEY` variable tells the ADK which API key to use when calling Gemini.

### 4.3 Verify Gemini Access

```powershell
py -c "import os; from dotenv import load_dotenv; load_dotenv(); from google import genai; client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY')); response = client.models.generate_content(model='gemini-2.5-flash', contents='Say hello in one sentence'); print(response.text)"
```

This loads the API key from `.env`, creates a Gemini client, and sends a simple prompt. If you see a response like "Hello there!", the Gemini connection is working.

---

## 5. Project Structure and File Roles

```
adk-retail-agents/
├── .env                           # Top-level env (optional)
├── .venv/                         # Virtual environment (not committed)
├── retail_analytics_agents/       # ADK agent package
│   ├── __init__.py                # Makes this a Python package
│   ├── agent.py                   # Agent definitions (root + 3 sub-agents)
│   ├── tools.py                   # 11 BigQuery tool functions
│   ├── .env                       # Gemini API key (not committed)
│   ├── retail_analytics_eval.evalset.json  # Evaluation test cases
│   └── test_config.json           # Evaluation thresholds
├── docs/
│   ├── ARCHITECTURE.md            # Architecture Decision Records
│   ├── VERIFICATION_REPORT.txt    # 62/62 verification output
│   ├── architecture_diagram.mermaid # Colored Mermaid diagram
│   ├── BUILD_GUIDE.md             # This document
│   └── screenshots/               # ADK Dev UI screenshots
├── verify.sh                # Verification script (Cloud Shell)
├── rebuild.sh               # Full rebuild script
├── README.md                      # Project documentation
├── requirements.txt               # Python dependencies
├── LICENSE                        # MIT license
└── .gitignore                     # Excludes .env, .venv, __pycache__
```

### File Roles Explained

**`__init__.py`**: A nearly empty file that tells Python this directory is a package. ADK requires agent code to live in a Python package. Without this file, `from . import tools` in `agent.py` would fail.

**`agent.py`**: Defines four `LlmAgent` instances. The `root_agent` variable name is special to ADK. When you run `adk web .`, ADK scans for packages containing a `root_agent` and uses it as the entry point.

**`tools.py`**: Contains Python functions that agents can call. Each function has a docstring with Args/Returns sections. ADK reads these docstrings and passes them to Gemini as tool descriptions, so the LLM knows what each tool does and what parameters it accepts.

**`.env`**: Contains `GOOGLE_API_KEY=...`. ADK loads this automatically using `python-dotenv`. This file is listed in `.gitignore` so the API key is never committed to version control.

**`.gitignore`**: Tells git which files to exclude. Critical entries: `.env` (API keys), `.venv/` (large virtual environment), `__pycache__/` (Python bytecode), `.adk/` (ADK session state).

---

## 6. Agent Code Walkthrough

### The LlmAgent Class

Every agent is an instance of `LlmAgent` from `google.adk.agents`:

```python
from google.adk.agents import LlmAgent
```

An `LlmAgent` wraps a Gemini model with:
- `name`: Unique identifier used in routing (e.g., "inventory_analyst")
- `model`: Which Gemini model to use (e.g., "gemini-2.5-flash")
- `description`: Tells the parent agent when to route to this agent. The orchestrator reads all sub-agent descriptions to decide routing.
- `instruction`: System prompt that shapes the agent's behavior and personality
- `tools`: List of Python functions the agent can call
- `sub_agents`: List of child agents (only used by the root orchestrator)

### Routing Mechanism

When the root orchestrator receives a user query, Gemini reads the `description` of each sub-agent and decides which one to delegate to. It calls an internal `transfer_to_agent` function with the chosen agent's name. The ADK framework then passes control to that sub-agent, which processes the query using its own tools and instructions.

For cross-functional queries, the orchestrator may engage multiple sub-agents sequentially or direct one agent to handle the query comprehensively.

### The Root Agent

```python
root_agent = LlmAgent(
    name="retail_orchestrator",
    model="gemini-2.5-flash",
    description="Root orchestrator that routes retail analytics questions to specialist agents.",
    instruction="...",
    sub_agents=[inventory_agent, sales_agent, customer_agent],
)
```

The `sub_agents` parameter is what makes this a multi-agent system. The root agent has no tools of its own. Its only job is to understand the query domain and route to the right specialist.

---

## 7. Tool Code Walkthrough

### BigQuery Client Initialization

```python
from google.cloud import bigquery

bq_client = bigquery.Client()
PROJECT_ID = bq_client.project
GOLD = f"{PROJECT_ID}.retail_gold"
```

`bigquery.Client()` with no arguments auto-discovers the project from:
1. `GOOGLE_CLOUD_PROJECT` environment variable (if set)
2. gcloud application default credentials (set by `gcloud auth application-default login`)

`GOLD` is a string like `playground-s-11-4c6f9668.retail_gold` used as a prefix in SQL queries.

### Tool Function Pattern

Every tool follows this pattern:

```python
def get_some_data(param: int = 10) -> dict:
    """Description of what this tool does.

    Args:
        param: Explanation of the parameter. Default is 10.

    Returns:
        Dictionary with the query results.
    """
    sql = f"""
    SELECT columns
    FROM `{GOLD}.table_name`
    WHERE conditions
    """
    return {"status": "success", "result": query_bigquery(sql)}
```

Key design decisions:

**Type hints** (`param: int = 10`): ADK uses these to tell Gemini the expected parameter types. Without type hints, Gemini might pass strings instead of integers.

**Docstrings**: ADK extracts the function docstring and sends it to Gemini as the tool description. The Args section tells Gemini what each parameter means and what defaults are available.

**Default values**: Most parameters have sensible defaults so the agent can call tools without specifying every parameter.

**Return format**: All tools return `{"status": "success", "result": <text>}`. This consistent shape simplifies agent instructions. The result is pre-formatted text that is easy for Gemini to read and summarize.

### The query_bigquery Helper

```python
def query_bigquery(sql: str) -> str:
    try:
        query_job = bq_client.query(sql)
        results = query_job.result()
        rows = [dict(row) for row in results]
        if not rows:
            return "No results found."
        output_lines = []
        for i, row in enumerate(rows, 1):
            row_str = " | ".join(f"{k}: {v}" for k, v in row.items())
            output_lines.append(f"  {i}. {row_str}")
        return f"Query returned {len(rows)} row(s):\n" + "\n".join(output_lines)
    except Exception as e:
        return f"BigQuery error: {str(e)}"
```

This function:
1. Submits the SQL query to BigQuery
2. Waits for results (blocking call)
3. Converts each row to a dictionary
4. Formats rows as numbered, pipe-delimited text
5. Catches any errors and returns them as text (not exceptions)

The error handling is important because if a tool raises an exception, ADK may not pass a useful error message to the agent. By catching errors and returning them as text, the agent can tell the user what went wrong.

---

## 8. Running and Testing the System

### ADK Web UI

```powershell
adk web .
```

This command:
1. Scans the current directory for Python packages containing a `root_agent`
2. Finds `retail_analytics_agents/agent.py` and loads the agent tree
3. Starts a FastAPI server on http://127.0.0.1:8000
4. Serves the ADK Dev UI (a web-based chat interface)

The Dev UI provides:
- **Chat interface**: Send queries and see agent responses
- **Trace view**: See every routing decision and tool call with timing
- **State tab**: Inspect session state
- **Eval tab**: Run evaluation test cases

### ADK CLI

```powershell
adk run retail_analytics_agents
```

This runs the agent in text mode directly in your terminal. Useful for quick testing without a browser.

### What Happens During a Query

1. User types "Which products are at risk of stockout?"
2. ADK sends the message to `retail_orchestrator` with the sub-agent descriptions
3. Gemini analyzes the query and determines it is an inventory question
4. Gemini calls `transfer_to_agent(agent_name="inventory_analyst")`
5. ADK transfers control to `inventory_analyst`
6. `inventory_analyst` receives the query and its tool list
7. Gemini decides to call `get_inventory_stockout_risk(threshold=10)`
8. ADK calls the Python function, which executes SQL against BigQuery
9. BigQuery returns rows of products with stock below 10
10. The tool returns formatted text to the agent
11. Gemini reads the data and composes a natural language response
12. ADK sends the response back to the user

---

## 9. Evaluation Framework

### Evalset Format

The file `retail_analytics_eval.evalset.json` contains 10 test cases in ADK's evalset format:

```json
{
  "eval_set_id": "retail_analytics_eval",
  "eval_cases": [
    {
      "eval_id": "inventory_stockout_check",
      "conversation": [
        {
          "user_content": { "parts": [{ "text": "Which products are at risk of stockout?" }] },
          "expected_tool_use": [
            { "tool_name": "transfer_to_agent", "tool_input": { "agent_name": "inventory_analyst" } },
            { "tool_name": "get_inventory_stockout_risk" }
          ],
          "final_response": { "parts": [{ "text": "Several products are currently at risk..." }] }
        }
      ]
    }
  ]
}
```

Each test case specifies:
- **user_content**: The input query
- **expected_tool_use**: The expected sequence of tool calls (routing + data retrieval)
- **final_response**: An approximate expected response for ROUGE matching

### Test Config

```json
{
  "criteria": {
    "tool_trajectory_avg_score": 0.6,
    "response_match_score": 0.4
  }
}
```

- `tool_trajectory_avg_score: 0.6` means the agent must match at least 60% of the expected tool call sequence. Set below 1.0 because the orchestrator may add extra reasoning steps.
- `response_match_score: 0.4` means the response must have at least 40% word overlap (ROUGE-1) with the expected response. Set low because agents use live data and wording varies between runs.

### Running Evals

```powershell
adk eval --config_file_path retail_analytics_agents\test_config.json retail_analytics_agents retail_analytics_agents\retail_analytics_eval.evalset.json --print_detailed_results
```

This replays all 10 test cases, compares actual tool trajectories and responses against expected values, and reports pass/fail for each case.

---

## 10. Verification Script

The `verify.sh` script runs 62 checks in Google Cloud Shell to validate the entire data layer:

| Section | Checks | What It Validates |
|---------|--------|-------------------|
| 1. Datasets | 5 | All BigQuery datasets exist |
| 2. Gold Tables | 7 | All gold layer tables exist and have rows |
| 3. Row Counts | 7 | Minimum row counts met (e.g., fct_sales >= 200K) |
| 4. Key Columns | 20 | Critical columns populated (not null) across all tables |
| 5. Tool Queries | 11 | Every agent tool query executes successfully against live data |
| 6. Data Integrity | 5 | Revenue totals, region coverage, margin ranges, null checks |
| 7. Architecture | 7 | Documents agent structure (agents, tools, LLM, eval count) |

Run in Cloud Shell:

```bash
chmod +x verify.sh
./verify.sh
```

---

## 11. Troubleshooting

### "No agents found in current folder"

Run `adk web .` from the parent directory of `retail_analytics_agents/`, not from inside it. ADK scans subdirectories for packages with `agent.py`.

### "Table not found" errors from agents

The gold layer tables may not exist. Run `rebuild.sh` in Cloud Shell to create them. Verify with `bq ls retail_gold`.

### "running scripts is disabled on this system"

Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` in PowerShell, then retry.

### gcloud "not recognized"

Close and reopen PowerShell after installing Google Cloud SDK. The PATH update requires a new terminal session.

### "GOOGLE_API_KEY" not working

Make sure the `.env` file is inside `retail_analytics_agents/` (not just the project root). ADK looks for `.env` in the agent package directory.

### BigQuery "permission denied"

Run `gcloud auth application-default login` again. Credentials may have expired, especially on sandbox environments with time limits.
