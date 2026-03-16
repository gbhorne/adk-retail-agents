"""BigQuery tools for retail analytics agents.

These tools query the Lab 01 star schema (retail_gold dataset) in BigQuery.
Each tool is a Python function that ADK agents can invoke.

Gold layer tables:
- fct_sales: denormalized fact with store/product/date fields embedded
- fct_inventory: stock_on_hand, reorder_point, is_stockout, inventory_status
- fct_daily_sales: aggregated daily metrics by store/region/channel
- dim_customer: includes lifetime_revenue, lifetime_orders, customer_segment
- dim_product: product_name, category_l1/l2/l3, brand, price_tier
- dim_store: store_name, region, store_type, city, country_code
- dim_date: date_day, year, quarter, month, day_of_week, is_weekend
"""

from google.cloud import bigquery

# Initialize BigQuery client (uses application-default credentials)
bq_client = bigquery.Client()

PROJECT_ID = bq_client.project
GOLD = f"{PROJECT_ID}.retail_gold"


def query_bigquery(sql: str) -> str:
    """Execute a BigQuery SQL query and return results as formatted text."""
    try:
        query_job = bq_client.query(sql)
        results = query_job.result()
        rows = [dict(row) for row in results]
        if not rows:
            return "No results found."
        # Format as readable text
        output_lines = []
        for i, row in enumerate(rows, 1):
            row_str = " | ".join(f"{k}: {v}" for k, v in row.items())
            output_lines.append(f"  {i}. {row_str}")
        return f"Query returned {len(rows)} row(s):\n" + "\n".join(output_lines)
    except Exception as e:
        return f"BigQuery error: {str(e)}"


# ============================================================
# INVENTORY ANALYST TOOLS
# ============================================================

def get_inventory_stockout_risk(threshold: int = 10) -> dict:
    """Get products at risk of stockout (stock_on_hand below threshold).

    Args:
        threshold: Minimum stock quantity to flag as at-risk. Default is 10.

    Returns:
        Dictionary with stockout risk data including product IDs, stores, and current stock levels.
    """
    sql = f"""
    SELECT
        i.product_id,
        i.store_id,
        i.stock_on_hand,
        i.reorder_point,
        i.inventory_status,
        i.days_since_last_sale,
        i.snapshot_date
    FROM `{GOLD}.fct_inventory` i
    WHERE i.stock_on_hand < {threshold}
        AND i.snapshot_date = (SELECT MAX(snapshot_date) FROM `{GOLD}.fct_inventory`)
    ORDER BY i.stock_on_hand ASC
    LIMIT 20
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_overstock_products(multiplier: float = 3.0) -> dict:
    """Get products that are overstocked (stock_on_hand significantly above reorder point).

    Args:
        multiplier: How many times above reorder point to flag as overstock. Default is 3.0.

    Returns:
        Dictionary with overstock data including product IDs, stores, and stock levels.
    """
    sql = f"""
    SELECT
        i.product_id,
        i.store_id,
        i.stock_on_hand,
        i.reorder_point,
        ROUND(i.stock_on_hand / NULLIF(i.reorder_point, 0), 1) AS overstock_ratio,
        i.inventory_status,
        i.days_since_last_sale
    FROM `{GOLD}.fct_inventory` i
    WHERE i.stock_on_hand > i.reorder_point * {multiplier}
        AND i.reorder_point > 0
        AND i.snapshot_date = (SELECT MAX(snapshot_date) FROM `{GOLD}.fct_inventory`)
    ORDER BY overstock_ratio DESC
    LIMIT 20
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_inventory_summary_by_region() -> dict:
    """Get inventory summary aggregated by store region.

    Returns:
        Dictionary with regional inventory totals, averages, and stockout counts.
    """
    sql = f"""
    SELECT
        s.region,
        COUNT(DISTINCT i.product_id) AS product_count,
        COUNT(DISTINCT i.store_id) AS store_count,
        SUM(i.stock_on_hand) AS total_stock,
        ROUND(AVG(i.stock_on_hand), 1) AS avg_stock,
        SUM(CASE WHEN i.is_stockout THEN 1 ELSE 0 END) AS stockout_count,
        SUM(CASE WHEN i.is_below_reorder_point THEN 1 ELSE 0 END) AS below_reorder_count
    FROM `{GOLD}.fct_inventory` i
    JOIN `{GOLD}.dim_store` s ON i.store_id = s.store_id
    WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM `{GOLD}.fct_inventory`)
    GROUP BY s.region
    ORDER BY total_stock DESC
    """
    return {"status": "success", "result": query_bigquery(sql)}


# ============================================================
# SALES ANALYST TOOLS
# ============================================================

def get_revenue_by_region() -> dict:
    """Get total revenue broken down by store region.

    Returns:
        Dictionary with revenue data by region including transaction counts and averages.
    """
    sql = f"""
    SELECT
        store_region,
        COUNT(*) AS transaction_count,
        ROUND(SUM(total_amount), 2) AS total_revenue,
        ROUND(AVG(total_amount), 2) AS avg_transaction_value,
        ROUND(SUM(gross_profit), 2) AS total_profit,
        ROUND(AVG(margin_pct), 2) AS avg_margin_pct
    FROM `{GOLD}.fct_sales`
    GROUP BY store_region
    ORDER BY total_revenue DESC
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_top_products_by_revenue(top_n: int = 10) -> dict:
    """Get the top-selling products by total revenue.

    Args:
        top_n: Number of top products to return. Default is 10.

    Returns:
        Dictionary with top product revenue data.
    """
    sql = f"""
    SELECT
        product_name,
        category_l1,
        brand,
        COUNT(*) AS times_sold,
        SUM(quantity) AS total_units_sold,
        ROUND(SUM(total_amount), 2) AS total_revenue,
        ROUND(SUM(gross_profit), 2) AS total_profit,
        ROUND(AVG(margin_pct), 2) AS avg_margin_pct
    FROM `{GOLD}.fct_sales`
    GROUP BY product_name, category_l1, brand
    ORDER BY total_revenue DESC
    LIMIT {top_n}
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_sales_trends_by_month() -> dict:
    """Get monthly sales trends showing revenue and transaction volume over time.

    Returns:
        Dictionary with monthly sales trend data.
    """
    sql = f"""
    SELECT
        txn_year,
        txn_month,
        COUNT(*) AS transaction_count,
        ROUND(SUM(total_amount), 2) AS monthly_revenue,
        ROUND(SUM(gross_profit), 2) AS monthly_profit,
        ROUND(AVG(total_amount), 2) AS avg_transaction_value
    FROM `{GOLD}.fct_sales`
    GROUP BY txn_year, txn_month
    ORDER BY txn_year, txn_month
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_revenue_by_category() -> dict:
    """Get revenue breakdown by product category (category_l1).

    Returns:
        Dictionary with revenue data by product category.
    """
    sql = f"""
    SELECT
        category_l1,
        COUNT(DISTINCT product_name) AS product_count,
        COUNT(*) AS transaction_count,
        SUM(quantity) AS total_units_sold,
        ROUND(SUM(total_amount), 2) AS total_revenue,
        ROUND(SUM(gross_profit), 2) AS total_profit,
        ROUND(AVG(margin_pct), 2) AS avg_margin_pct
    FROM `{GOLD}.fct_sales`
    GROUP BY category_l1
    ORDER BY total_revenue DESC
    """
    return {"status": "success", "result": query_bigquery(sql)}


# ============================================================
# CUSTOMER STRATEGIST TOOLS
# ============================================================

def get_customer_segments() -> dict:
    """Get customer distribution across segments with key metrics.

    Returns:
        Dictionary with customer segment data including counts, revenue, and order metrics.
    """
    sql = f"""
    SELECT
        customer_segment,
        COUNT(*) AS customer_count,
        ROUND(AVG(lifetime_revenue), 2) AS avg_lifetime_revenue,
        ROUND(AVG(lifetime_orders), 1) AS avg_lifetime_orders,
        ROUND(AVG(avg_order_value), 2) AS avg_order_value,
        ROUND(AVG(days_since_last_purchase), 0) AS avg_days_since_last_purchase
    FROM `{GOLD}.dim_customer`
    GROUP BY customer_segment
    ORDER BY avg_lifetime_revenue DESC
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_top_customers(top_n: int = 10) -> dict:
    """Get the top customers by lifetime revenue.

    Args:
        top_n: Number of top customers to return. Default is 10.

    Returns:
        Dictionary with top customer data.
    """
    sql = f"""
    SELECT
        customer_id,
        first_name,
        last_name,
        customer_segment,
        loyalty_tier,
        country_code,
        lifetime_orders,
        ROUND(lifetime_revenue, 2) AS lifetime_revenue,
        ROUND(avg_order_value, 2) AS avg_order_value,
        first_purchase_date,
        last_purchase_date,
        days_since_last_purchase
    FROM `{GOLD}.dim_customer`
    ORDER BY lifetime_revenue DESC
    LIMIT {top_n}
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_customer_distribution_by_region() -> dict:
    """Get customer count and average lifetime revenue by country/region.

    Returns:
        Dictionary with customer distribution data across regions.
    """
    sql = f"""
    SELECT
        country_code,
        COUNT(*) AS customer_count,
        ROUND(AVG(lifetime_revenue), 2) AS avg_lifetime_revenue,
        ROUND(SUM(lifetime_revenue), 2) AS total_lifetime_revenue,
        ROUND(AVG(lifetime_orders), 1) AS avg_lifetime_orders,
        COUNTIF(activity_status = 'Active') AS active_customers,
        COUNTIF(activity_status != 'Active') AS inactive_customers
    FROM `{GOLD}.dim_customer`
    GROUP BY country_code
    ORDER BY total_lifetime_revenue DESC
    """
    return {"status": "success", "result": query_bigquery(sql)}


def get_loyalty_tier_analysis() -> dict:
    """Get customer metrics broken down by loyalty tier.

    Returns:
        Dictionary with loyalty tier data including counts and revenue.
    """
    sql = f"""
    SELECT
        loyalty_tier,
        COUNT(*) AS customer_count,
        ROUND(AVG(lifetime_revenue), 2) AS avg_lifetime_revenue,
        ROUND(AVG(lifetime_orders), 1) AS avg_lifetime_orders,
        ROUND(AVG(avg_order_value), 2) AS avg_order_value,
        ROUND(AVG(online_pct), 2) AS avg_online_pct
    FROM `{GOLD}.dim_customer`
    GROUP BY loyalty_tier
    ORDER BY avg_lifetime_revenue DESC
    """
    return {"status": "success", "result": query_bigquery(sql)}