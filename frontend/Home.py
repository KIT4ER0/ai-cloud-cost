import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.auth import login, register, logout, show_login_page
from utils.styles import inject_custom_css
from utils.api import fetch_summary, fetch_instances, fetch_costs

# Config
st.set_page_config(page_title="Cloud Cost Opt", layout="wide", page_icon="☁️")

# Session State for Auth
if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.token:
    show_login_page()
    st.stop() # Stop execution if not logged in

# If logged in, show Home Page
inject_custom_css()

# Sidebar Logout
with st.sidebar:
    if st.button("Logout"):
        logout()

st.title("Cost Management")

# Mock date picker for visual match
# col_header, col_date = st.columns([3, 1])
# with col_date:
#     st.selectbox("", ["October", "November", "December"], index=0, label_visibility="collapsed")

data = fetch_summary()
if not data:
    st.error("Failed to load data")
    st.stop()

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
