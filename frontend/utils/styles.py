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
        color: #111827;
        font-family: 'Inter', sans-serif;
    }
    h1 {
        font-size: 2.5rem !important; /* Increased */
        background: -webkit-linear-gradient(45deg, #7C3AED, #9333EA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    h2 { font-size: 2rem !important; } /* Added */
    h3 { font-size: 1.5rem; } /* Added/Increased */
    
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
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(124, 58, 237, 0.1), 0 2px 4px -1px rgba(124, 58, 237, 0.06);
        height: 500px; /* Unified to 500px */
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
    
    /* Chart Cards (Targeting Plotly container to look like a card) */
    .stPlotlyChart {
        background-color: white;
        /* border: 1px solid #7C3AED; Removed per user request */
        border-radius: 16px;
        padding: 5px;
        box-shadow: 0 4px 6px -1px rgba(124, 58, 237, 0.1), 0 2px 4px -1px rgba(124, 58, 237, 0.06);
        height: 500px !important; /* Unified to 500px */
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

    /* Warning List Buttons (Secondary/Ghost style) - targeted via key or general override if needed */
    /* Targeting buttons in the main area specifically if we can, or just adding a specific class helper? 
       Streamlit doesn't support adding classes easily. 
       We will overwrite the default button style for "secondary" type logic if we use type="secondary", 
       but st.button doesn't strictly have types like "primary" that imply distinct CSS classes easily accessible. 
       
       Let's try to style ALL buttons with a specific look, OR assume the Sidebar "Logout" is the only other button.
       Logout button is usually small.
       
       We'll style buttons to be 100% width and align left for the warning list feel. 
    */
    /* Container reset for counters */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) {
        counter-reset: warning-counter;
    }

    /* Target ONLY buttons inside the Warning Box */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) .stButton button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        height: auto !important;
        white-space: pre-wrap !important;
        padding: 16px !important;
        padding-left: 60px !important; /* Space for Badge */
        padding-right: 40px !important; /* Space for Chevron */
        background: white !important;
        color: #111827 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
        font-weight: 400 !important;
        margin-bottom: 8px !important;
        position: relative !important;
        display: flex !important;
        align-items: center !important;
    }
    
    /* Boxed Number Badge via ::before */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) .stButton button::before {
        counter-increment: warning-counter;
        content: counter(warning-counter);
        position: absolute;
        left: 16px;
        top: 50%;
        transform: translateY(-50%);
        width: 28px;
        height: 28px;
        background: #F3F4F6;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
        color: #4B5563;
        font-weight: 600;
        font-size: 0.85rem;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1;
    }

    /* Chevron */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) .stButton button::after {
        content: "›";
        position: absolute;
        right: 15px;
        top: 50%;
        transform: translateY(-55%);
        font-size: 1.5rem;
        color: #9CA3AF;
        font-weight: 400;
        line-height: 1;
    }

    /* Hover State */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) .stButton button:hover {
        background: #F9FAFB !important;
        border-color: #D1D5DB !important;
        color: #111827 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        transform: translateY(-1px);
    }
    
    /* Text styling wrapper */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) .stButton button p {
        width: 100%;
        margin: 0;
        line-height: 1.4;
    }
    
    /* Title (First Line) Bold */
    [data-testid="stVerticalBlockBorderWrapper"]:has(#warning-list-group) .stButton button p::first-line {
        font-weight: 600;
        color: #111827;
        font-size: 0.95rem;
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
        font-size: 1.25rem; /* Increased */
        font-weight: 700;
        color: #111827;
        margin-bottom: 5px;
        display: block;
    }
    .rec-desc {
        color: #6B7280;
        font-size: 1rem; /* Increased */
        line-height: 1.6;
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
