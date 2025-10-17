import streamlit as st
import plotly.express as px
from db import q

st.title("📊 Cost Explorer")

# ดึงค่าตัวเลือก
accounts = q("SELECT DISTINCT payer_account_id AS acct FROM cur_costs ORDER BY 1")
services = q("SELECT DISTINCT product_service AS svc FROM cur_costs ORDER BY 1")

colA, colB, colC = st.columns(3)
acct = colA.multiselect("Account", accounts["acct"])
svc  = colB.multiselect("Service", services["svc"])
days = colC.slider("Lookback (days)", 7, 180, 30)

# สร้าง where แบบยืดหยุ่น
where = ["usage_start_time >= now() - INTERVAL ':d days'".replace(":d", str(days))]
params = {}
if acct:
    where.append("payer_account_id = ANY(:acct)")
    params["acct"] = acct
if svc:
    where.append("product_service = ANY(:svc)")
    params["svc"] = svc
WHERE = "WHERE " + " AND ".join(where)

sql_ts = f"""
SELECT date_trunc('day', usage_start_time) AS day,
       SUM(unblended_cost) AS cost
FROM cur_costs
{WHERE}
GROUP BY 1 ORDER BY 1
"""
df = q(sql_ts, params)
st.plotly_chart(px.line(df, x="day", y="cost", title="Daily Cost"), use_container_width=True)

sql_break = f"""
SELECT product_service AS service, SUM(unblended_cost) AS cost
FROM cur_costs
{WHERE}
GROUP BY 1 ORDER BY cost DESC
"""
st.subheader("Cost by Service")
st.dataframe(q(sql_break, params))
