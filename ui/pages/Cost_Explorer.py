import streamlit as st
import plotly.express as px
from db import q

st.title("📊 Cost Explorer")

# --- โหลดตัวเลือก ---
accounts = q("SELECT DISTINCT account_id AS acct FROM raw.costs ORDER BY 1")
services = q("SELECT DISTINCT service AS svc FROM raw.costs ORDER BY 1")

colA, colB, colC = st.columns(3)
acct = colA.multiselect("Account", accounts["acct"].tolist())
svc  = colB.multiselect("Service", services["svc"].tolist())
days = colC.slider("Lookback (days)", 7, 180, 30)

# --- สร้าง WHERE clause ให้ตรง schema ---
where = ["usage_date >= current_date - make_interval(days => :days)"]
params: dict = {"days": days}

if acct:
    where.append("account_id = ANY(:acct)")
    params["acct"] = acct
if svc:
    where.append("service = ANY(:svc)")
    params["svc"] = svc

WHERE = "WHERE " + " AND ".join(where)

# --- Timeseries: Daily Cost ---
sql_ts = f"""
SELECT usage_date AS day,
       SUM(amount_usd) AS cost
FROM raw.costs
{WHERE}
GROUP BY 1
ORDER BY 1
"""
df_ts = q(sql_ts, params)

if df_ts.empty:
    st.warning("ไม่พบข้อมูลในช่วงที่เลือก")
else:
    st.plotly_chart(px.line(df_ts, x="day", y="cost", title="Daily Cost"), use_container_width=True)

# --- Breakdown: Cost by Service ---
sql_break = f"""
SELECT service,
       SUM(amount_usd) AS cost
FROM raw.costs
{WHERE}
GROUP BY 1
ORDER BY cost DESC
"""
st.subheader("Cost by Service")
st.dataframe(q(sql_break, params))