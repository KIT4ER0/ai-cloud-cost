import requests
import streamlit as st
import pandas as pd
from datetime import datetime

import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def fetch_summary():
    res = requests.get(f"{API_URL}/api/summary", headers=get_auth_headers())
    return res.json() if res.status_code == 200 else None

def fetch_costs(range_val):
    res = requests.get(f"{API_URL}/api/costs", params={"range": range_val}, headers=get_auth_headers())
    return res.json() if res.status_code == 200 else []

def fetch_cost_details(service_name):
    res = requests.get(f"{API_URL}/api/cost-details/{service_name}", headers=get_auth_headers())
    return res.json() if res.status_code == 200 else None

def fetch_instances():
    res = requests.get(f"{API_URL}/api/instances", headers=get_auth_headers())
    return res.json() if res.status_code == 200 else []

def fetch_metrics(instance_id):
    res = requests.get(f"{API_URL}/api/metrics/{instance_id}", headers=get_auth_headers())
    return res.json() if res.status_code == 200 else []

def fetch_recommendations():
    res = requests.get(f"{API_URL}/api/recommendations", headers=get_auth_headers())
    return res.json() if res.status_code == 200 else []

def fetch_forecast_data(horizon_months=3):
    # TODO: Replace with real API call
    # res = requests.post(f"{API_URL}/api/forecast", json={"horizon": horizon_months}, headers=get_auth_headers())
    # Mock data for demonstration
    dates = pd.date_range(start=datetime.now(), periods=horizon_months*30, freq='D')
    historical_dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    
    # Mock Historical
    hist_df = pd.DataFrame({
        "date": historical_dates,
        "cost": [100 + i + (i%7)*5 for i in range(60)],
        "type": "Historical"
    })
    
    # Mock Forecast with some trend
    base_cost = hist_df["cost"].iloc[-1]
    forecast_values = [base_cost + i*0.5 + (i%7)*5 for i in range(len(dates))]
    upper_bound = [v * 1.1 for v in forecast_values]
    lower_bound = [v * 0.9 for v in forecast_values]
    
    forecast_df = pd.DataFrame({
        "date": dates,
        "cost": forecast_values,
        "upper": upper_bound,
        "lower": lower_bound,
        "type": "Forecast"
    })
    
    return hist_df, forecast_df
