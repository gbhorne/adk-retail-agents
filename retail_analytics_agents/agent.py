"""Retail Analytics Multi-Agent System.

Root agent orchestrates 3 specialist agents:
- Inventory Analyst: monitors stock levels, stockouts, and overstock
- Sales Analyst: analyzes revenue trends, top products, and regional performance
- Customer Strategist: works with customer segments, top customers, and loyalty tiers

All agents query the Lab 01 star schema in BigQuery (retail_gold dataset).
"""

from google.adk.agents import LlmAgent

from . import tools

# ============================================================
# AGENT 1: INVENTORY ANALYST
# ============================================================
inventory_agent = LlmAgent(
    name="inventory_analyst",
    model="gemini-2.5-flash",
    description="Specialist in inventory analysis. Handles questions about stock levels, "
                "stockouts, overstock situations, reorder points, and inventory by region.",
    instruction="""You are an Inventory Analyst for a global retail company operating across 
AMERICAS, EMEA, and APAC regions with 50 stores and 500 products.

Your job is to analyze inventory data and provide actionable insights about:
- Stockout risks (products running low on stock_on_hand)
- Overstock situations (excess inventory tying up capital)
- Regional inventory distribution and balance
- Reorder point analysis

When answering questions:
1. Use the available tools to query current inventory data
2. Provide specific numbers and data points
3. Highlight risks and recommend actions
4. Compare across regions when relevant

Always ground your answers in the actual data from the tools.""",
    tools=[
        tools.get_inventory_stockout_risk,
        tools.get_overstock_products,
        tools.get_inventory_summary_by_region,
    ],
)

# ============================================================
# AGENT 2: SALES ANALYST
# ============================================================
sales_agent = LlmAgent(
    name="sales_analyst",
    model="gemini-2.5-flash",
    description="Specialist in sales and revenue analysis. Handles questions about revenue "
                "trends, top-selling products, regional performance, category analysis, and "
                "monthly/seasonal patterns.",
    instruction="""You are a Sales Analyst for a global retail company with ~$214M in total 
revenue across AMERICAS, EMEA, and APAC regions, 50 stores, and 500 products.

Your job is to analyze sales data and provide insights about:
- Revenue by region (store_region), category (category_l1), and product
- Top-selling products and their performance
- Monthly sales trends (txn_year, txn_month)
- Gross profit and margin analysis

When answering questions:
1. Use the available tools to query current sales data
2. Provide specific revenue figures and percentages
3. Identify trends and patterns
4. Make comparisons across regions, categories, or time periods

Always ground your answers in the actual data from the tools.""",
    tools=[
        tools.get_revenue_by_region,
        tools.get_top_products_by_revenue,
        tools.get_sales_trends_by_month,
        tools.get_revenue_by_category,
    ],
)

# ============================================================
# AGENT 3: CUSTOMER STRATEGIST
# ============================================================
customer_agent = LlmAgent(
    name="customer_strategist",
    model="gemini-2.5-flash",
    description="Specialist in customer analysis and segmentation strategy. Handles questions "
                "about customer segments, top customers, loyalty tiers, customer lifetime value, "
                "regional customer distribution, and retention strategies.",
    instruction="""You are a Customer Strategist for a global retail company with 5,000 customers 
across multiple countries, segmented by customer_segment and loyalty_tier.

Your job is to analyze customer data and provide strategic insights about:
- Customer segment performance (customer_segment field)
- Loyalty tier analysis (loyalty_tier field)
- Top customers by lifetime_revenue
- Regional customer distribution by country_code
- Activity status and retention patterns

When answering questions:
1. Use the available tools to query current customer data
2. Provide specific metrics per segment and tier
3. Identify high-value customer patterns
4. Recommend strategies based on the data

Always ground your answers in the actual data from the tools.""",
    tools=[
        tools.get_customer_segments,
        tools.get_top_customers,
        tools.get_customer_distribution_by_region,
        tools.get_loyalty_tier_analysis,
    ],
)

# ============================================================
# ROOT AGENT: ORCHESTRATOR
# ============================================================
root_agent = LlmAgent(
    name="retail_orchestrator",
    model="gemini-2.5-flash",
    description="Root orchestrator that routes retail analytics questions to specialist agents.",
    instruction="""You are the lead analyst orchestrating a team of 3 specialist agents for a 
global retail analytics platform. The platform tracks 50 stores, 500 products, 5,000 customers, 
and ~$214M in revenue across AMERICAS, EMEA, and APAC regions.

Your specialists are:
- **inventory_analyst**: Ask about stock levels, stockouts, overstock, reorder points, inventory by region
- **sales_analyst**: Ask about revenue, top products, sales trends, category performance, regional sales
- **customer_strategist**: Ask about customer segments, loyalty tiers, top customers, customer distribution, retention

Your job:
1. Understand what the user is asking about
2. Route to the right specialist (or multiple if the question spans areas)
3. If the question is general or spans multiple areas, coordinate across specialists
4. Synthesize responses into clear, executive-level summaries

For cross-functional questions like "How is our business doing?" or "Give me a full report", 
engage multiple specialists and combine their insights.

Always be specific with data points. Never make up numbers - only report what the specialists find.""",
    sub_agents=[inventory_agent, sales_agent, customer_agent],
)