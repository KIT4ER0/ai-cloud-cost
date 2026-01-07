import streamlit as st
import pandas as pd
from utils.api import fetch_instances, fetch_metrics
from utils.styles import inject_custom_css
from utils.auth import show_login_page

st.set_page_config(page_title="Monitoring", layout="wide", page_icon="📉")

if "token" not in st.session_state or not st.session_state.token:
    show_login_page()
    st.stop()

inject_custom_css()

st.header("Monitoring")

# Service Type Filter
service_type = st.radio("Service Type", ["EC2", "RDS", "Lambda", "S3"], horizontal=True)

instances = fetch_instances()
# Filter by type
filtered_inst = [i for i in instances if service_type in i.get("service_type", "")]

if not filtered_inst:
    st.info("No instances found")
    st.stop()

# Table with selection
df = pd.DataFrame(filtered_inst)

# Streamlit dataframe with selection is tricky without plugins like aggrid, 
# but st.dataframe has on_select in newer versions or we use a selectbox
# Let's use a selectbox for simplicity and robustness
selected_id = st.selectbox("Select Instance to Monitor", df["instance_id"].tolist(), format_func=lambda x: f"{x} ({df[df['instance_id']==x]['name'].values[0]})")

st.dataframe(df)

if selected_id:
    st.subheader(f"Metrics: {selected_id}")
    metrics = fetch_metrics(selected_id)
    if metrics:
        m_df = pd.DataFrame(metrics)
        m_df['timestamp'] = pd.to_datetime(m_df['timestamp'])
        
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        with c1:
            st.caption("CPU Usage (%)")
            st.line_chart(m_df, x="timestamp", y="cpu_usage")
        with c2:
            st.caption("Network In (Bytes)")
            st.line_chart(m_df, x="timestamp", y="network_in")
        with c3:
            st.caption("Network Out (Bytes)")
            st.line_chart(m_df, x="timestamp", y="network_out")
        with c4:
            st.caption("Disk I/O")
            st.line_chart(m_df, x="timestamp", y="disk_io")
