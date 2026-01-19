import streamlit as st
import pandas as pd
import plotly.express as px
from utils.api import fetch_costs, fetch_cost_details
from utils.styles import inject_custom_css
from utils.auth import show_login_page

st.set_page_config(page_title="Cost Analysis", layout="wide", page_icon="💰")

if "token" not in st.session_state or not st.session_state.token:
    show_login_page()
    st.stop()

inject_custom_css()

# State for Drill Down
if "selected_service" not in st.session_state:
    st.session_state.selected_service = None

def show_cost_analysis_main():
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
                st.rerun()

def show_cost_detail_page():
    service_name = st.session_state.get("selected_service", "EC2")
    
    # Navigation Header
    c_back, c_title = st.columns([1, 5])
    with c_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.selected_service = None
            st.rerun()
            
    with c_title:
        st.title(f"Service Detail: {service_name}")
    
    data = fetch_cost_details(service_name)
    if not data:
        st.error("Could not load details")
        return

    # Summary Metrics
    c1, c2 = st.columns([1, 2])
    with c1:
        with st.container(border=True):
            st.metric(label="Total Cost (Current Month)", value=f"${data['total_cost']:,.2f}")
            st.caption(f"Spending for {service_name}")

    with c2:
        # Add a mini chart here if data permits, or just leave as cleaner layout
        # Let's add the breakdown pie chart here for better context
        df_display = pd.DataFrame(list(data['breakdown'].items()), columns=["Usage Type", "Cost"])
        if not df_display.empty:
            fig = px.pie(df_display, values="Cost", names="Usage Type", hole=0.4, 
                         color_discrete_sequence=px.colors.qualitative.Prism)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=150, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        
    st.write("")
    
    # Detailed Table
    st.subheader("Cost Breakdown Details")
    with st.container(border=True):
        if not df_display.empty:
            # Add formatted column
            df_display["Cost ($)"] = df_display["Cost"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(
                df_display[["Usage Type", "Cost ($)"]], 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Usage Type": st.column_config.TextColumn("Usage Type", width="medium"),
                    "Cost ($)": st.column_config.TextColumn("Cost", width="small"),
                }
            )
        else:
            st.info("No detailed breakdown available")

if st.session_state.selected_service:
    show_cost_detail_page()
else:
    show_cost_analysis_main()
