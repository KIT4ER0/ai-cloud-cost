import streamlit as st
import plotly.express as px
from db import q

st.set_page_config(page_title="AI Cloud Cost", page_icon="💸", layout="wide")
st.title("💸 Cloud Cost Dashboard — Overview")

# --- กำหนดชื่อ table ให้ตรงกับของคุณ ---
# สมมติ ETL สร้างตารางชื่อ cur_costs และ recommendations, metrics_ec2
# ปรับชื่อคอลัมน์ให้ตรง (ตัวอย่างด้านล่างเป็น pattern ทั่วไปของ CUR)
SQL_TOTAL = """
SELECT date_trunc('month', usage_start_time) AS month,
       SUM(unblended_cost) AS cost
FROM cur_costs
GROUP BY 1
ORDER BY 1
"""
df_month = q(SQL_TOTAL)

col1, col2, col3 = st.columns(3)
this_month = df_month.iloc[-1]["cost"] if len(df_month) else 0
prev_month = df_month.iloc[-2]["cost"] if len(df_month) > 1 else 0
pct = (this_month - prev_month) / prev_month * 100 if prev_month else 0

col1.metric("This month cost", f"${this_month:,.2f}", f"{pct:+.1f}% vs prev")
col2.metric("Prev month cost", f"${prev_month:,.2f}")
col3.metric("Months tracked", f"{len(df_month)}")

fig = px.bar(df_month, x="month", y="cost", title="Monthly Cost")
st.plotly_chart(fig, use_container_width=True)

# Top services
SQL_SVC = """
SELECT product_service AS service, SUM(unblended_cost) AS cost
FROM cur_costs
WHERE usage_start_time >= date_trunc('month', now())
GROUP BY 1 ORDER BY cost DESC LIMIT 10
"""
st.subheader("Top Services (This Month)")
st.dataframe(q(SQL_SVC))
