import streamlit as st
from db import q

st.title("🧠 Optimization Recommendations")

sql = """
SELECT id, created_at, category, resource_id, rule_id, impact_monthly_usd,
       risk_level, details
FROM recommendations
ORDER BY created_at DESC
"""
df = q(sql)
st.dataframe(df, use_container_width=True)

st.download_button("Export CSV", df.to_csv(index=False).encode("utf-8"), "recommendations.csv", "text/csv")
