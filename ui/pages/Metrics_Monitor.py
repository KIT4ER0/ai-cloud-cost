import streamlit as st
import plotly.express as px
from db import q

st.title("📈 Resource Metrics")

inst = q("SELECT DISTINCT instance_id FROM metrics_ec2 ORDER BY 1")
target = st.selectbox("Instance", inst["instance_id"] if len(inst) else [])
if target:
    df = q("""
        SELECT ts, cpu_utilization
        FROM metrics_ec2
        WHERE instance_id = :iid
        ORDER BY ts
    """, {"iid": target})
    st.plotly_chart(px.line(df, x="ts", y="cpu_utilization", title=f"CPU {target}"), use_container_width=True)
[]