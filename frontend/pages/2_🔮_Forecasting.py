import streamlit as st
import plotly.graph_objects as go
from utils.api import fetch_forecast_data
from utils.styles import inject_custom_css
from utils.auth import show_login_page

st.set_page_config(page_title="Forecasting", layout="wide", page_icon="🔮")

if "token" not in st.session_state or not st.session_state.token:
    show_login_page()
    st.stop()

inject_custom_css()

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
