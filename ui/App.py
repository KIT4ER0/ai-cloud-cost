import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.title("AI Cloud Cost Optimizer - Dashboard")

st.subheader("Health Check")
try:
    r = requests.get(f"{API_URL}/health", timeout=5)
    st.json(r.json())
except Exception as e:
    st.error(f"API not reachable: {e}")

st.subheader("Database Check")
try:
    r = requests.get(f"{API_URL}/db-check", timeout=5)
    st.json(r.json())
except Exception as e:
    st.error(f"DB check error: {e}")
