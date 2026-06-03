from __future__ import annotations

from pathlib import Path

import pandas as pd


OUT = Path(__file__).resolve().parent


def write_distributor() -> None:
    distributor_monthly = pd.DataFrame(
        {
            "month": ["2026-04", "2026-04", "2026-04", "2026-05", "2026-05", "2026-05"],
            "region": ["华东", "华东", "华南", "华东", "华东", "华南"],
            "distributor_id": ["D001", "D002", "D003", "D001", "D002", "D003"],
            "distributor_level": ["高阶", "中阶", "中阶", "高阶", "中阶", "中阶"],
            "team_id": ["T1", "T1", "T2", "T1", "T1", "T2"],
            "sales_amount": [12000, 9000, 8000, 9000, 7000, 9200],
            "order_count": [120, 90, 80, 80, 70, 92],
            "customer_count": [80, 60, 50, 62, 52, 55],
            "target_amount": [11000, 9000, 8500, 11000, 9000, 8500],
        }
    )
    sales_order = pd.DataFrame(
        {
            "order_id": [f"O{i:03d}" for i in range(1, 13)],
            "order_date": pd.date_range("2026-04-03", periods=12, freq="5D"),
            "month": ["2026-04"] * 6 + ["2026-05"] * 6,
            "region": ["华东", "华东", "华南", "华东", "华东", "华南"] * 2,
            "distributor_id": ["D001", "D002", "D003", "D001", "D002", "D003"] * 2,
            "customer_id_hash": [f"C{i:03d}" for i in range(1, 13)],
            "product_id": ["P1", "P2", "P3", "P1", "P2", "P3", "P1", "P3", "P3", "P1", "P2", "P3"],
            "product_category": ["营养", "护肤", "家居", "营养", "护肤", "家居", "营养", "家居", "家居", "营养", "护肤", "家居"],
            "sales_amount": [2400, 1800, 1600, 2600, 1700, 1800, 2100, 1500, 1600, 2300, 1550, 1900],
            "quantity": [2, 2, 1, 2, 1, 2, 2, 1, 1, 2, 1, 2],
        }
    )
    product_master = pd.DataFrame(
        {"product_id": ["P1", "P2", "P3"], "product_name": ["营养A", "护肤B", "家居C"], "product_category": ["营养", "护肤", "家居"]}
    )
    with pd.ExcelWriter(OUT / "distributor_performance_sample.xlsx") as writer:
        distributor_monthly.to_excel(writer, sheet_name="distributor_monthly", index=False)
        sales_order.to_excel(writer, sheet_name="sales_order", index=False)
        product_master.to_excel(writer, sheet_name="product_master", index=False)


def write_subscription() -> None:
    subscription_customer = pd.DataFrame(
        {
            "customer_id_hash": [f"C{i:03d}" for i in range(1, 9)],
            "distributor_id": ["D001", "D001", "D002", "D003", "D003", "D004", "D004", "D005"],
            "region": ["华东", "华东", "华东", "华南", "华南", "华北", "华北", "华东"],
            "subscription_start_date": pd.date_range("2026-04-01", periods=8, freq="4D"),
            "subscription_status": ["active", "active", "churned", "active", "active", "active", "churned", "active"],
            "product_id": ["P1", "P1", "P2", "P1", "P3", "P2", "P2", "P3"],
            "product_category": ["营养", "营养", "护肤", "营养", "家居", "护肤", "护肤", "家居"],
            "total_subscription_revenue": [1200, 1500, 400, 1300, 1000, 900, 300, 1100],
        }
    )
    subscription_monthly = pd.DataFrame(
        {
            "month": ["2026-04", "2026-04", "2026-05", "2026-05"],
            "region": ["华东", "华南", "华东", "华南"],
            "distributor_id": ["D001", "D003", "D002", "D003"],
            "new_subscriber_count": [20, 12, 24, 15],
            "active_subscriber_count": [85, 40, 96, 50],
            "churned_subscriber_count": [5, 4, 6, 3],
            "retained_subscriber_count": [78, 35, 84, 45],
            "subscription_revenue": [88000, 42000, 102000, 51000],
        }
    )
    sales_order = pd.DataFrame(
        {
            "order_id": [f"SO{i:03d}" for i in range(1, 9)],
            "order_date": pd.date_range("2026-05-01", periods=8),
            "month": ["2026-05"] * 8,
            "region": subscription_customer["region"],
            "distributor_id": subscription_customer["distributor_id"],
            "customer_id_hash": subscription_customer["customer_id_hash"],
            "product_id": subscription_customer["product_id"],
            "product_category": subscription_customer["product_category"],
            "sales_amount": [600, 700, 300, 800, 520, 480, 260, 620],
        }
    )
    product_master = pd.DataFrame({"product_id": ["P1", "P2", "P3"], "product_name": ["订阅A", "订阅B", "订阅C"], "product_category": ["营养", "护肤", "家居"]})
    with pd.ExcelWriter(OUT / "subscription_sample.xlsx") as writer:
        subscription_customer.to_excel(writer, sheet_name="subscription_customer", index=False)
        subscription_monthly.to_excel(writer, sheet_name="subscription_monthly", index=False)
        sales_order.to_excel(writer, sheet_name="sales_order", index=False)
        product_master.to_excel(writer, sheet_name="product_master", index=False)


def write_prysm() -> None:
    prysm_usage = pd.DataFrame(
        {
            "month": ["2026-05"] * 6,
            "region": ["华东", "华东", "华南", "华南", "华北", "华北"],
            "distributor_id": [f"D{i:03d}" for i in range(1, 7)],
            "eligible_flag": [1, 1, 1, 1, 1, 1],
            "activated_flag": [1, 1, 0, 1, 0, 1],
            "usage_count": [22, 3, 0, 15, 0, 8],
            "active_days": [12, 2, 0, 9, 0, 5],
            "feature_used_count": [5, 1, 0, 4, 0, 3],
        }
    )
    distributor_monthly = pd.DataFrame(
        {
            "month": ["2026-05"] * 6,
            "region": prysm_usage["region"],
            "distributor_id": prysm_usage["distributor_id"],
            "sales_amount": [18000, 7000, 5200, 15000, 4300, 9800],
            "order_count": [160, 60, 50, 130, 42, 82],
        }
    )
    with pd.ExcelWriter(OUT / "prysm_io_sample.xlsx") as writer:
        prysm_usage.to_excel(writer, sheet_name="prysm_usage", index=False)
        distributor_monthly.to_excel(writer, sheet_name="distributor_monthly", index=False)


def write_community() -> None:
    project = pd.DataFrame(
        {"community_project_id": ["CP001"], "project_name": ["五月陪跑"], "start_date": ["2026-05-01"], "end_date": ["2026-05-31"], "project_type": ["增长陪跑"]}
    )
    participants = pd.DataFrame(
        {
            "community_project_id": ["CP001"] * 6,
            "distributor_id": [f"D{i:03d}" for i in range(1, 7)],
            "region": ["华东", "华东", "华南", "华南", "华北", "华北"],
            "treatment_flag": [1, 1, 1, 0, 0, 0],
            "control_group_flag": [0, 0, 0, 1, 1, 1],
            "participation_level": ["高", "中", "低", "对照", "对照", "对照"],
            "checkin_count": [18, 10, 4, 0, 0, 0],
            "task_completion_rate": [0.9, 0.65, 0.3, 0, 0, 0],
        }
    )
    distributor_monthly = pd.DataFrame(
        {
            "month": ["2026-04"] * 6 + ["2026-05"] * 6,
            "region": list(participants["region"]) * 2,
            "distributor_id": list(participants["distributor_id"]) * 2,
            "sales_amount": [9000, 8000, 7000, 8800, 7600, 6800, 12000, 9600, 7400, 9300, 7800, 6900],
            "order_count": [90, 80, 70, 88, 76, 68, 118, 95, 72, 91, 77, 69],
        }
    )
    with pd.ExcelWriter(OUT / "community_operation_sample.xlsx") as writer:
        project.to_excel(writer, sheet_name="community_project", index=False)
        participants.to_excel(writer, sheet_name="community_participant", index=False)
        distributor_monthly.to_excel(writer, sheet_name="distributor_monthly", index=False)


def write_product_campaign() -> None:
    product_sales = pd.DataFrame(
        {
            "month": ["2026-04", "2026-04", "2026-04", "2026-05", "2026-05", "2026-05"],
            "region": ["华东", "华东", "华南", "华东", "华东", "华南"],
            "product_id": ["P1", "P2", "P3", "P1", "P2", "P3"],
            "product_name": ["营养A", "护肤B", "家居C", "营养A", "护肤B", "家居C"],
            "product_category": ["营养", "护肤", "家居", "营养", "护肤", "家居"],
            "sales_amount": [50000, 32000, 21000, 62000, 30000, 26000],
            "quantity": [500, 260, 180, 610, 240, 220],
            "order_count": [300, 180, 120, 360, 160, 150],
            "gross_margin": [18000, 13000, 7000, 22500, 12000, 8600],
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O1", "O2", "O2", "O3", "O4", "O4", "O5", "O5", "O6"],
            "order_date": pd.date_range("2026-05-01", periods=10),
            "month": ["2026-05"] * 10,
            "region": ["华东"] * 10,
            "distributor_id": ["D001", "D001", "D002", "D002", "D003", "D004", "D004", "D005", "D005", "D006"],
            "product_id": ["P1", "P2", "P1", "P3", "P2", "P1", "P3", "P2", "P3", "P1"],
            "product_category": ["营养", "护肤", "营养", "家居", "护肤", "营养", "家居", "护肤", "家居", "营养"],
            "sales_amount": [500, 300, 520, 260, 310, 540, 280, 320, 300, 560],
        }
    )
    product_master = pd.DataFrame({"product_id": ["P1", "P2", "P3"], "product_name": ["营养A", "护肤B", "家居C"], "product_category": ["营养", "护肤", "家居"]})
    campaign_master = pd.DataFrame({"campaign_id": ["CA001"], "campaign_name": ["五月主推"], "start_date": ["2026-05-01"], "end_date": ["2026-05-15"], "campaign_type": ["主推"]})
    campaign_sales = orders.assign(campaign_id="CA001")
    with pd.ExcelWriter(OUT / "product_campaign_sample.xlsx") as writer:
        product_sales.to_excel(writer, sheet_name="product_sales", index=False)
        orders.to_excel(writer, sheet_name="sales_order", index=False)
        product_master.to_excel(writer, sheet_name="product_master", index=False)
        campaign_master.to_excel(writer, sheet_name="campaign_master", index=False)
        campaign_sales.to_excel(writer, sheet_name="campaign_sales", index=False)


if __name__ == "__main__":
    write_distributor()
    write_subscription()
    write_prysm()
    write_community()
    write_product_campaign()
    print(f"Sample workbooks written to {OUT}")
