import streamlit as st
from streamlit_option_menu import option_menu
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests
from datetime import datetime

# Config
# Config
st.set_page_config(page_title="Cloud Cost Opt", layout="wide", page_icon="☁️")
API_URL = "http://127.0.0.1:8001"

# Session State for Auth
if "token" not in st.session_state:
    st.session_state.token = None
if "page" not in st.session_state:
    st.session_state.page = "Home"

# --- Auth Functions ---
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

# --- Custom CSS ---
def inject_custom_css():
    st.markdown("""
    <style>
    /* Global Styles */
    .stApp {
        background-color: #FFFFFF;
        color: #1F2937;
    }
    
    /* Headings */
    h1, h2, h3 {
        color: #111827 !important;
        font-family: 'Inter', sans-serif;
    }
    h1 {
        background: -webkit-linear-gradient(45deg, #7C3AED, #9333EA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #F3F4F6;
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #7C3AED;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    label[data-testid="stMetricLabel"] {
        color: #6B7280 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #111827 !important;
        font-weight: 700;
    }
    
    /* Dashboard Cards */
    .dashboard-card {
        background-color: white;
        /* border: 1px solid #7C3AED;  Removed per user request */
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(124, 58, 237, 0.1), 0 2px 4px -1px rgba(124, 58, 237, 0.06);
        height: 400px;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
    
    /* Chart Cards (Targeting Plotly container to look like a card) */
    .stPlotlyChart {
        background-color: white;
        /* border: 1px solid #7C3AED; Removed per user request */
        border-radius: 16px;
        padding: 10px;
        box-shadow: 0 4px 6px -1px rgba(124, 58, 237, 0.1), 0 2px 4px -1px rgba(124, 58, 237, 0.06);
        height: 400px !important; /* Force height match */
    }    
    /* Warning Item */
    .warning-item {
        display: flex;
        align-items: center;
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .warning-item:hover {
        transform: translateX(4px);
        border-color: #7C3AED;
    }
    .warning-badge {
        background: #F3F4F6;
        color: #4C1D95;
        font-weight: bold;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        margin-right: 12px;
        border: 1px solid #7C3AED;
    }

    /* Buttons */
    div.stButton > button {
        background: linear-gradient(90deg, #7C3AED 0%, #6D28D9 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #6D28D9 0%, #5B21B6 100%);
        box-shadow: 0 0 10px rgba(124, 58, 237, 0.5);
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #F9FAFB;
        border-right: 1px solid #E5E7EB;
    }
    
    /* Tables */
    div[data-testid="stTable"] {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 10px;
    }
    
    /* Alerts/Toasts */
    div[data-baseweb="notification"] {
        background-color: #F3F4F6;
        border-left: 5px solid #7C3AED;
        color: #1F2937;
    }
    
    /* Recommendations Page Styles - Hacking st.container(border=True) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: all 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 8px 16px -4px rgba(124, 58, 237, 0.1);
        border-color: #7C3AED;
        transform: translateY(-2px);
    }
    
    .rec-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 5px;
        display: block;
    }
    .rec-desc {
        color: #6B7280;
        font-size: 0.9rem;
        line-height: 1.5;
        margin-bottom: 20px;
    }
    .rec-badge {
        font-size: 0.75rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 9999px;
        display: inline-block;
        margin-bottom: 10px;
    }
    .badge-high { background-color: #FEF2F2; color: #DC2626; border: 1px solid #FEE2E2; }
    .badge-medium { background-color: #FFFBEB; color: #D97706; border: 1px solid #FEF3C7; }
    .badge-low { background-color: #ECFDF5; color: #059669; border: 1px solid #D1FAE5; }
    
    </style>
    """, unsafe_allow_html=True)

# --- API Helpers ---
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

# --- Pages ---

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

def show_home_page():
    st.title("Cost Management")
    
    # Mock date picker for visual match
    # col_header, col_date = st.columns([3, 1])
    # with col_date:
    #     st.selectbox("", ["October", "November", "December"], index=0, label_visibility="collapsed")

    data = fetch_summary()
    if not data:
        st.error("Failed to load data")
        return

    # Layout: Top Row
    c1, c2 = st.columns(2)
    
    with c1:
        # My Cost Chart
        current_cost = data['total_cost_current_month']
        avg_cost = current_cost * 0.9 # Mock
        forecast = data['forecast_cost_current_month']
        
        cost_df = pd.DataFrame({
            "Period": ["Last month", "Current", "Forecast"],
            "Cost": [avg_cost, current_cost, forecast]
        })
        
        fig = go.Figure(data=[go.Bar(
            x=cost_df['Period'],
            y=cost_df['Cost'],
            marker_color='#7C3AED',
            width=0.4,
            text=cost_df['Cost'].apply(lambda x: f"${x:,.0f}"),
            textposition='auto',
        )])
        fig.update_layout(
            title=dict(
                text="My Cost",
                font=dict(size=18, color="#4C1D95", family="Inter, sans-serif"),
                x=0, y=0.95
            ),
            margin=dict(l=20, r=20, t=50, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(showgrid=True, gridcolor='#F3F4F6'),
            xaxis=dict(showgrid=False),
            height=380
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        # My Service List
        instances = fetch_instances()
        list_items = ""
        
        if instances:
            # Robustly handle list of dicts or Pydantic models
            try:
                df = pd.DataFrame(instances)
                if 'service_type' in df.columns:
                    srv_counts = df['service_type'].value_counts()
                    
                    for srv, count in srv_counts.items():
                        # Use flush-left string to avoid markdown code block interpretation
                        list_items += f"""<div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #E5E7EB; font-size: 0.9rem;">
    <span style="font-weight: 500; color: #374151;">{srv}</span>
    <span style="font-weight: 600; color: #1F2937;">{count}</span>
</div>"""
                else:
                    list_items = "<div style='color: #EF4444; padding: 20px;'>Error: Missing service_type data</div>"
            except Exception as e:
                list_items = f"<div style='color: #EF4444; padding: 20px;'>Error processing data: {e}</div>"
        else:
            list_items = "<div style='color: #9CA3AF; text-align: center; padding: 20px;'>No active services found</div>"
            
        st.markdown(f"""
        <div class="dashboard-card">
            <h3 style="color: #4C1D95; font-size: 1.1rem; font-weight: 700; margin-top: 0; margin-bottom: 15px;">My Service</h3>
            <div>{list_items}</div>
        </div>
        """, unsafe_allow_html=True)

    # Spacing
    st.write("")

    # Layout: Bottom Row
    c3, c4 = st.columns(2)
    
    with c3:
        # Cost by Services (Pie Chart)
        costs_data = fetch_costs("1m")
        if costs_data:
            df = pd.DataFrame(costs_data)
            df_grouped = df.groupby("service")["cost"].sum().reset_index()
            
            # Pie chart (hole=0 for cake style)
            fig = px.pie(df_grouped, values="cost", names="service", hole=0, 
                         color_discrete_sequence=["#7C3AED", "#A78BFA", "#C4B5FD", "#E9D5FF"])
            fig.update_layout(
                title=dict(
                    text="Cost by Services",
                    font=dict(size=18, color="#4C1D95", family="Inter, sans-serif"),
                    x=0, y=0.95
                ),
                margin=dict(t=50, b=20, l=20, r=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), # Legend at bottom
                height=380
            )
            fig.update_traces(textinfo='percent+label', textposition='inside')
            st.plotly_chart(fig, use_container_width=True)
            
    with c4:
        # Warning List
        alerts = data.get('top_anomalies', [])
        points_html = f"<div style='text-align: right; color: #6B7280; font-size: 0.8rem;'>{len(alerts)} points</div>"
        
        if alerts:
            warnings_html = ""
            for i, alert in enumerate(alerts):
                # Synthesize severity if missing
                severity = alert.get('severity')
                if not severity:
                    p_score = alert.get('priority_score', 1)
                    if p_score >= 4: severity = "High"
                    elif p_score == 3: severity = "Medium"
                    else: severity = "Low"
                
                warnings_html += f"""<div class="warning-item">
    <div class="warning-badge">{i+1}</div>
    <div style="flex-grow: 1;">
        <div style="font-weight: 600; font-size: 0.85rem; color: #1F2937;">{alert.get('message', alert.get('title', 'Unknown Issue'))}</div>
        <div style="font-size: 0.75rem; color: #6B7280;">{severity} Priority</div>
    </div>
    <div style="color: #7C3AED; font-weight: bold;">›</div>
</div>"""
        else:
            warnings_html = "<div style='color: #9CA3AF; text-align: center; padding: 20px;'>No alerts</div>"
            
        st.markdown(f"""
        <div class="dashboard-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="color: #4C1D95; font-size: 1.1rem; font-weight: 700; margin: 0;">Warning!</h3>
                {points_html}
            </div>
            <div>{warnings_html}</div>
        </div>
        """, unsafe_allow_html=True)


def show_cost_analysis_page():
    st.title("Cost Analysis")
    
    # Filter Section
    with st.container(border=True):
        col_filter, col_metric = st.columns([2, 1])
        with col_filter:
            st.subheader("Filter Settings")
            range_opt = st.select_slider("Select Time Range", options=["1w", "1m", "6m", "1y"], value="1m")
            
        with col_metric:
            data = fetch_costs(range_opt)
            total_spend = 0
            if data:
                df = pd.DataFrame(data)
                total_spend = df["cost"].sum()
            
            st.metric("Total Spend", f"${total_spend:,.2f}", delta=None)

    if not data:
        st.info("No cost data available for the selected range.")
        return

    df = pd.DataFrame(data)
    
    # Charts Section
    st.write("### Data Visualization")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        # Stacked Bar Chart (No external container/subheader to avoid double border)
        fig_bar = px.bar(df, x="date", y="cost", color="service", 
                         color_discrete_sequence=px.colors.qualitative.Prism)
        fig_bar.update_layout(
            title=dict(
                text="Daily Cost Trend",
                font=dict(size=18, color="#111827", family="Inter, sans-serif"),
                x=0, y=0.95
            ),
            xaxis_title="Date", yaxis_title="Cost ($)",
            # Adjust legend and margins to prevent overlap
            legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="left", x=0),
            margin=dict(l=20, r=20, t=50, b=100), # Increased bottom margin
            height=400 # Slightly taller to accommodate legend
        )
        fig_bar.update_xaxes(tickangle=-45) # Rotate dates to avoid collision
        st.plotly_chart(fig_bar, use_container_width=True)
            
    with c2:
        # Service Distribution (No external container)
        # Aggregation for Pie Chart
        pie_df = df.groupby("service")["cost"].sum().reset_index()
        # Match Home Page Style: hole=0, Purple Color Palette
        fig_pie = px.pie(pie_df, values="cost", names="service", hole=0,
                         color_discrete_sequence=["#7C3AED", "#A78BFA", "#C4B5FD", "#E9D5FF"])
        fig_pie.update_layout(
            title=dict(
                text="Service Distribution",
                font=dict(size=18, color="#111827", family="Inter, sans-serif"),
                x=0, y=0.95
            ),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=50, b=80), # Increased bottom margin
            height=400
        )
        fig_pie.update_traces(textinfo='percent+label', textposition='inside')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Data Table Section
    with st.expander("View Detailed Data Table", expanded=False):
        st.dataframe(df, use_container_width=True)
    
    # Drill Down Section
    st.write("")
    st.subheader("Service Drill Down")
    st.markdown("Select a service to view detailed breakdown.")
    
    services = df["service"].unique().tolist()
    d_cols = st.columns(4) # Grid for buttons
    
    for i, s in enumerate(services):
        with d_cols[i % 4]:
            if st.button(f"🔍 {s}", key=f"drill_{s}", use_container_width=True):
                st.session_state.selected_service = s
                st.session_state.page = "CostDetail"
                st.rerun()

def show_cost_detail_page():
    service_name = st.session_state.get("selected_service", "EC2")
    
    # Navigation Header
    c_back, c_title = st.columns([1, 5])
    with c_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.page = "Cost Analysis"
            st.rerun()
            
    with c_title:
        st.title(f"Service Detail: {service_name}")
    
    data = fetch_cost_details(service_name)
    if not data:
        st.error("Could not load details")
        return

    # Summary Metrics
    with st.container(border=True):
        st.subheader("Total Cost")
        st.metric(label="Current Month", value=f"${data['total_cost']:,.2f}")
        st.caption(f"Breakdown of costs for {service_name}")
        
    st.write("")
    
    # Detailed Table
    st.subheader("Cost Items")
    with st.container(border=True):
        # Convert dict to clean DF
        df_display = pd.DataFrame(list(data['breakdown'].items()), columns=["Usage Type", "Cost ($)"])
        # Format Cost column
        df_display["Cost ($)"] = df_display["Cost ($)"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

def show_forecast_page():
    st.header("AI Cost Forecasting")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Configuration")
        horizon = st.slider("Forecast Horizon (Months)", 1, 12, 3)
        model_type = st.selectbox("Model Type", ["Prophet", "ARIMA", "LSTM"], index=0)
        st.info(f"Using {model_type} model for prediction.")
        if st.button("Run Forecast"):
            st.toast("Forecasting updated!")
            
    with col2:
        hist_df, forecast_df = fetch_forecast_data(horizon)
        
        # Combine for visualization
        fig = go.Figure()
        
        # Historical Data
        fig.add_trace(go.Scatter(
            x=hist_df['date'], 
            y=hist_df['cost'], 
            mode='lines', 
            name='Historical Cost',
            line=dict(color='#22D3EE') # Cyan
        ))
        
        # Forecast Data
        fig.add_trace(go.Scatter(
            x=forecast_df['date'], 
            y=forecast_df['cost'], 
            mode='lines', 
            name='Forecast',
            line=dict(color='#F97316', dash='dash') # Orange
        ))
        
        # Confidence Interval (Upper & Lower)
        fig.add_trace(go.Scatter(
            x=list(forecast_df['date']) + list(forecast_df['date'])[::-1],
            y=list(forecast_df['upper']) + list(forecast_df['lower'])[::-1],
            fill='toself',
            fillcolor='rgba(249, 115, 22, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=True,
            name='Confidence Interval'
        ))
        
        fig.update_layout(
            title="Cost Projections",
            xaxis_title="Date",
            yaxis_title="Cost ($)",
            template="plotly_white",
            margin=dict(t=30, b=0, l=0, r=0),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    # --- Forecast Insights (Full Width) ---
    st.write("")
    st.subheader("Forecast Insights")
    
    avg_forecast = forecast_df['cost'].mean()
    avg_hist = hist_df['cost'].mean()
    diff = ((avg_forecast - avg_hist) / avg_hist) * 100
    peak_forecast = forecast_df['cost'].max()
    
    # Styled Insights Cards matching reference
    ic1, ic2, ic3 = st.columns(3)
    
    def insight_card(title, value, sub_text=None, sub_color="green"):
        return f"""
        <div style="
            background-color: #F9FAFB;
            border-left: 5px solid #7C3AED;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            height: 130px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        ">
            <div>
                 <div style="color: #6B7280; font-size: 0.85rem; margin-bottom: 2px;">{title}</div>
                 <div style="color: #111827; font-size: 1.6rem; font-weight: 700;">{value}</div>
            </div>
            {f'<div style="background-color: #DCFCE7; color: #166534; display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; width: fit-content;">{sub_text}</div>' if sub_text else '<div style="height: 20px;"></div>'}
        </div>
        """

    with ic1:
        st.markdown(insight_card(
            "Avg Projected Cost", 
            f"${avg_forecast:,.2f}", 
            f"↑ {diff:.1f}% vs Hist"
        ), unsafe_allow_html=True)
        
    with ic2:
        st.markdown(insight_card(
            "Peak Projected Cost", 
            f"${peak_forecast:,.2f}"
        ), unsafe_allow_html=True)
        
    with ic3:
        st.markdown(insight_card(
            "Confidence Level", 
            "95%"
        ), unsafe_allow_html=True)

def show_monitoring_page():
    st.header("Monitoring")
    
    # Service Type Filter
    service_type = st.radio("Service Type", ["EC2", "RDS", "Lambda", "S3"], horizontal=True)
    
    instances = fetch_instances()
    # Filter by type
    filtered_inst = [i for i in instances if service_type in i["service_type"]]
    
    if not filtered_inst:
        st.info("No instances found")
        return

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

# --- Content Data ---
REMEDIATION_GUIDES = {
    "Right-size EC2 Instances": """
    ### How to fix:
    1. **Analyze Utilization**: Check CloudWatch metrics for CPU/Memory averaging < 20% over 30 days.
    2. **Select New Type**: Identify a smaller instance family (e.g., move from `m5.large` to `t3.medium`).
    3. **Schedule Downtime**: Stop the instance (if EBS backed).
    4. **Resize**: Change instance type via Console or CLI:
       ```bash
       aws ec2 modify-instance-attribute --instance-id i-xxxx --instance-type t3.medium
       ```
    5. **Restart**: Start the instance and verify application health.
    """,
    "Delete Unattached EBS Volumes": """
    ### How to fix:
    1. **Identify Orphans**: List volumes with status `available` (not `in-use`).
    2. **Verify Data**: Ensure no critical data is needed (create a snapshot if unsure).
    3. **Delete**:
       ```bash
       aws ec2 delete-volume --volume-id vol-xxxx
       ```
    """,
    "Upgrade to GP3 Volumes": """
    ### How to fix:
    1. **Select Volume**: Identify GP2 volumes.
    2. **Modify**: Use Console or CLI to change type to GP3 (20% cheaper).
       ```bash
       aws ec2 modify-volume --volume-id vol-xxxx --volume-type gp3
       ```
    3. **Wait**: Optimization happens in background (no downtime required).
    """,
    "Purchase Reserved Instances": """
    ### How to fix:
    1. **Review Coverage**: Check Cost Explorer for steady-state usage.
    2. **Purchase**: Commit to a 1-year or 3-year term for consistent workloads.
    """
}

def show_recommend_page():
    st.title("Optimization Recommendations")
    
    # State Management for Master-Detail View
    if 'rec_selected_item' not in st.session_state:
        st.session_state.rec_selected_item = None

    # --- DETAIL VIEW ---
    if st.session_state.rec_selected_item:
        item = st.session_state.rec_selected_item
        
        # Back Button
        if st.button("← Back to List"):
            st.session_state.rec_selected_item = None
            st.rerun()
            
        st.markdown(f"## {item['title']}")
        
        # Metadata
        c1, c2, c3 = st.columns(3)
        with c1: st.info(f"**Impact**: {item['impact']}")
        with c2: st.warning(f"**Category**: {item.get('category', 'Cost')}")
        with c3: st.success(f"**Status**: {item.get('status', 'Active')}")
        
        st.write("### Description")
        st.write(item['description'])
        
        st.write("")
        
        # Remediation Steps
        st.markdown("---")
        st.subheader("🛠️ Remediation Steps")
        
        guide = REMEDIATION_GUIDES.get(item['title'])
        if guide:
            st.markdown(guide)
        else:
            st.markdown("""
            ### General Fix:
            1. Review usage metrics in your Cloud Provider Console.
            2. Consult your team lead for approval.
            3. Apply changes during a maintenance window.
            """)
            
        st.button("Validate Fix", type="primary") # Mock action

    # --- LIST VIEW ---
    else:
        st.markdown("Identified opportunities to reduce costs and apply best practices.")
        st.write("")
        
        recs = fetch_recommendations()
        if not recs:
            st.info("No recommendations found. Your infrastructure is optimized!")
            return

        cols = st.columns(2)
        for i, item in enumerate(recs):
            with cols[i % 2]:
                # Use st.container(border=True) which is now styled via CSS to look like our card
                with st.container(border=True):
                    # Header Section (Title + Badge)
                    score = item.get('priority_score', 1)
                    if score >= 4:
                         badge_class = "badge-high"
                         badge_text = "High Priority"
                    elif score == 3:
                         badge_class = "badge-medium"
                         badge_text = "Medium Priority"
                    else:
                         badge_class = "badge-low"
                         badge_text = "Low Priority"
                    
                    # Custom HTML for Header content inside the container
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <span class="rec-title">{item['title']}</span>
                        <span class="rec-badge {badge_class}">{badge_text}</span>
                    </div>
                    <div class="rec-desc">{item['description']}</div>
                    <div style="font-weight: 600; color: #7C3AED; font-size: 0.9rem; margin-bottom: 15px;">
                        💡 {item.get('impact', 'Cost Saving')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Native Streamlit Button (Preserves Session!)
                    if st.button("View & Fix", key=f"btn_{i}", use_container_width=True):
                        st.session_state.rec_selected_item = item
                        st.rerun()

# --- Main App Logic ---

if not st.session_state.token:
    show_login_page()
else:
    inject_custom_css()
    
    # Check Query Params for Navigation State
    query_params = st.query_params
    default_idx = 0
    if query_params.get("page") == "Recommend":
        default_idx = 4
    
    # Sidebar
    with st.sidebar:
        st.title("CloudCostOpt")
        selected = option_menu(
            "Menu", 
            ["Home", "Cost Analysis", "Forecasting", "Monitoring", "Recommend"], 
            icons=['house', 'graph-up', 'magic', 'activity', 'lightbulb'], 
            menu_icon="cast", 
            default_index=default_idx
        )
        
        if st.button("Logout"):
            logout()
            
    # Navigation
    if st.session_state.page == "CostDetail":
        show_cost_detail_page()
    else:
        if selected == "Home":
            show_home_page()
        elif selected == "Cost Analysis":
            show_cost_analysis_page()
        elif selected == "Forecasting":
            show_forecast_page()
        elif selected == "Monitoring":
            show_monitoring_page()
        elif selected == "Recommend":
            show_recommend_page()
