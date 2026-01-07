import streamlit as st

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
