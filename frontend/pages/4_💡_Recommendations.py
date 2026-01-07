import streamlit as st
from utils.api import fetch_recommendations
from utils.styles import inject_custom_css
from utils.auth import show_login_page

st.set_page_config(page_title="Recommendations", layout="wide", page_icon="💡")

if "token" not in st.session_state or not st.session_state.token:
    show_login_page()
    st.stop()

inject_custom_css()

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
        st.stop()

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
