from altair import Padding
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
            font=dict(size=20, color="#4C1D95", family="Inter, sans-serif"), # Increased to 20px
            x=0, y=0.95,
            pad=dict(b=10) # 10px bottom padding
        ),
        margin=dict(l=40, r=40, t=80, b=40), # Increased margins to shrink chart
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor='#F3F4F6', tickfont=dict(size=14)), # Reduced by 10%
        xaxis=dict(showgrid=False, tickfont=dict(size=14)), # Reduced by 10%
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

with c2:
    # My Service List (Restored to Top Right)
    instances = fetch_instances()
    list_items = ""
    
    if instances:
        try:
            df = pd.DataFrame(instances)
            if 'service_type' in df.columns:
                srv_counts = df['service_type'].value_counts()
                
                for srv, count in srv_counts.items():
                    list_items += f"""<div style="display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px dashed #E5E7EB; font-size: 1rem;">
<span style="font-weight: 500; color: #374151;">{srv}</span>
<span style="font-weight: 600; color: #1F2937;">{count}</span>
</div>"""
            else:
                list_items = "<div style='color: #EF4444; padding: 20px; font-size: 1rem;'>Error: Missing service_type data</div>"
        except Exception as e:
            list_items = f"<div style='color: #EF4444; padding: 20px; font-size: 1rem;'>Error processing data: {e}</div>"
    else:
        list_items = "<div style='color: #9CA3AF; text-align: center; padding: 20px; font-size: 1rem;'>No active services found</div>"
        
    st.markdown(f"""
    <div class="dashboard-card">
        <h3 style="color: #4C1D95; font-size: 1.25rem; font-weight: 700; margin-top: 0; margin-bottom: 15px;">My Service</h3>
        <div>{list_items}</div>
    </div>
    """, unsafe_allow_html=True)

# Spacing
st.write("")

# Layout: Bottom Row
c3, c4 = st.columns(2)

with c3:
    # Cost by Services (Pie Chart) - Restored to Bottom Left
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
                font=dict(size=20, color="#4C1D95", family="Inter, sans-serif"), # Increased font size
                x=0, y=0.95,
                pad=dict(b=10)
            ),
            margin=dict(t=80, b=40, l=40, r=40), # Increased margins to shrink chart
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5, font=dict(size=12)), # Legend at bottom
            height=500,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
        )
        fig.update_traces(textinfo='percent+label', textposition='inside')
        st.plotly_chart(fig, use_container_width=True)

with c4:
    # Warning List (Restored to Bottom Right)
    alerts = data.get('top_anomalies', [])
    
    # Outer "Big Box" using st.container for interactivity
    with st.container(border=True, height=500):
        # Header area
        hc1, hc2 = st.columns([3, 1])
        # Marker for CSS targeting
        st.markdown('<div id="warning-list-group" style="display:none;"></div>', unsafe_allow_html=True)
        hc1.markdown("<h3 style='color: #4C1D95; font-size: 1.25rem; font-weight: 700; margin: 0;'>Warning!</h3>", unsafe_allow_html=True)
        hc2.markdown(f"<div style='text-align: right; color: #6B7280; font-size: 1rem;'>{len(alerts)} points</div>", unsafe_allow_html=True)
        
        st.write("") # Spacer
        
        if not alerts:
             st.info("No alerts")
        else:
            for i, alert in enumerate(alerts):
                severity = alert.get('severity')
                if not severity:
                    p_score = alert.get('priority_score', 1)
                    if p_score >= 4: severity_label = "High"
                    elif p_score == 3: severity_label = "Medium"
                    else: severity_label = "Low"
                else:
                    severity_label = severity

                if severity_label == "High":
                    icon = "🔴"
                elif severity_label == "Medium":
                    icon = "🟠"
                else:
                    icon = "🟢"
                
                title = alert.get('message', alert.get('title', 'Unknown Issue'))
                
                # Clean format: Title on line 1, Subtitle on line 2
                # CSS handles Number Badge (::before) and Title Boldness (::first-line)
                button_label = f"{title}\n{severity_label} Priority"
                
                if st.button(button_label, key=f"alert_{i}", use_container_width=True):
                    st.session_state['selected_alert'] = alert
                    st.switch_page("pages/4_Recommendations.py")
