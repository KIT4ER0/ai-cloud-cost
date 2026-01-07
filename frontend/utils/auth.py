
import requests
import streamlit as st
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def login(username, password):
    try:
        res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if res.status_code == 200:
            st.session_state.token = res.json()["access_token"]
            st.rerun()
        else:
            st.error("Invalid credentials")
    except Exception as e:
        st.error(f"Connection error: {e}")

def register(username, password):
    try:
        res = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if res.status_code == 200:
            st.success("Registered! Logging in...")
            st.session_state.token = res.json()["access_token"]
            st.rerun()
        else:
            st.error(f"Registration failed: {res.json().get('detail', 'Unknown error')}")
    except Exception as e:
        st.error(f"Connection error: {e}")

def logout():
    st.session_state.token = None
    st.rerun()

def show_login_page():
    st.title("Cloud Cost Optimizer")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            login(username, password)
            
    with tab2:
        r_username = st.text_input("Username", key="reg_user")
        r_password = st.text_input("Password", type="password", key="reg_pw")
        if st.button("Register"):
            register(r_username, r_password)
