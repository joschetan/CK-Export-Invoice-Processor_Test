import streamlit as st

# 📌 1. मुख्य पेज कॉन्फ़िगरेशन
st.set_page_config(
    page_title="CK Export Invoice Processor Pro", 
    page_icon="🚢",
    layout="wide", 
    initial_sidebar_state="expanded"  # साइडबार को इनेबल कर दिया ताकि प्रोफाइल अच्छे से दिखे
)

# 📌 2. सेशन स्टेट इनिशियलाइज़ेशन (ग्लोबल ऐप लॉक के लिए)
if "app_authenticated" not in st.session_state:
    st.session_state["app_authenticated"] = False

# 🔒 यदि ऐप अनलॉक नहीं है, तो पहले पासवर्ड स्क्रीन दिखाएँ
if not st.session_state["app_authenticated"]:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>🚢 CK Export Invoice Processor Pro</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>कृपया आगे बढ़ने के लिए ऐप का पासवर्ड दर्ज करें।</p>", unsafe_allow_html=True)
        
        # 🚀 Form का उपयोग ताकि Enter दबाने पर सीधे लॉगिन हो जाए
        with st.form(key="login_form"):
            pass_input = st.text_input("पासवर्ड दर्ज करें:", type="password", key="global_lock_pwd")
            submit_button = st.form_submit_button("Unlock App", use_container_width=True, type="primary")
            
            if submit_button:
                if pass_input == "CK":
                    st.session_state["app_authenticated"] = True
                    st.rerun()
                else:
                    st.error("❌ गलत पासवर्ड! कृपया सही पासवर्ड दर्ज करें।")
    
    # जब तक पासवर्ड सही न हो, आगे का कोड रन न हो
    st.stop()

# ==========================================
# 🚀 पासवर्ड सही होने के बाद दिखने वाला मुख्य ऐप कोड
# ==========================================

# 📌 साइडबार प्रोफाइल और CSS स्टाइलिंग
st.markdown("""
    <style>
        [data-testid="stSidebarCollapseButton"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        .creator-card {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 15px;
            border-radius: 12px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        .creator-name {
            font-size: 18px;
            font-weight: 700;
            margin-top: 8px;
            margin-bottom: 2px;
        }
        .creator-title {
            font-size: 12px;
            color: #d1d8e0;
            letter-spacing: 1px;
            text-transform: uppercase;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

# --- 🚀 CREATOR / FOUNDER PROFILE SECTION (Sidebar) ---
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    
    # यहाँ आपकी फोटो सीधे रेंडर होगी
    try:
        st.image("ck_photo.jpg", use_container_width=True)
    except:
        st.info("Photo loading...")
        
    st.markdown("""
        <div class="creator-card">
            <div class="creator-name">Chetan Joshi</div>
            <div class="creator-title">📞 +91 98253 06898</div>
            <hr style="border-color: rgba(255,255,255,0.2); margin: 8px 0;">
            <p style='font-size: 11px; color: #f1f2f6; margin: 0;'>
                <b>CK Export Invoice Pro v2.0</b><br>
                Engineered for Enterprise Automation & Precision.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # ऐप लॉक आउट बटन (साइडबार में)
    if st.button("🔒 Lock App", use_container_width=True):
        st.session_state["app_authenticated"] = False
        st.rerun()
        
    st.markdown("---")

import pandas as pd
import requests
import json
import base64

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbwEsmWdnkVW3H7_fD99vPMrqhvmY6iJHP1ZooKuwDlj2VE4cht_FBgFyem9xDRFlbjuNw/exec"
SPREADSHEET_ID = "182qRuH7R0jZqWVKHCg_oAG1SK5CUSkQpxVPxH2O8QUQ"

@st.cache_data(show_spinner=False)
def load_data_from_gsheet():
    """गूगल शीट से ग्लोबल मास्टर्स और रूल्स को कैच करके लोड करता है"""
    shipper_db = {}
    master_rules_template = {}
    
    try:
        master_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=Global_Masters"
        df_m = pd.read_csv(master_url)
        if not df_m.empty:
            df_m.columns = df_m.columns.str.strip()
            for _, row in df_m.iterrows():
                if "FieldName" in df_m.columns and pd.notna(row["FieldName"]):
                    f_name = str(row["FieldName"]).strip()
                    master_rules_template[f_name] = {
                        "keyword": row["Keyword"] if "Keyword" in df_m.columns and pd.notna(row["Keyword"]) else "",
                        "position": row["Position"] if "Position" in df_m.columns and pd.notna(row["Position"]) else "Right (आगे)",
                        "cell": row["Cell"] if "Cell" in df_m.columns and pd.notna(row["Cell"]) else "",
                        "match_mode": row["MatchMode"] if "MatchMode" in df_m.columns and pd.notna(row["MatchMode"]) else "Exact Word",
                        "stop_kw": row["StopKw"] if "StopKw" in df_m.columns and pd.notna(row["StopKw"]) else "",
                        "filter": row["Filter"] if "Filter" in df_m.columns and pd.notna(row["Filter"]) else "None",
                        "logic": row["Logic"] if "Logic" in df_m.columns and pd.notna(row["Logic"]) else "None",
                        "fallback": row["Fallback"] if "Fallback" in df_m.columns and pd.notna(row["Fallback"]) else ""
                    }
    except Exception:
        pass

    try:
        rules_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=Shipper_Rules"
        df_rules = pd.read_csv(rules_url)
        if not df_rules.empty:
            df_rules.columns = df_rules.columns.str.strip()
            for _, row in df_rules.iterrows():
                if "ShipperName" in df_rules.columns and pd.notna(row["ShipperName"]):
                    s_name = str(row["ShipperName"]).strip()
                    if s_name and s_name.lower() != "nan":
                        if s_name not in shipper_db:
                            shipper_db[s_name] = {
                                "allowed_uploads": ["Full Job Excel Format File"], 
                                "uploaded_files": {}, 
                                "mapping_rules": {},
                                "item_table_rules": {},
                                "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                            }
                        
                        field = str(row["FieldName"]).strip() if "FieldName" in df_rules.columns else None
                        rule_kind = str(row["RuleKind"]).strip().lower() if "RuleKind" in df_rules.columns and pd.notna(row["RuleKind"]) else "header"
                        
                        if field and pd.notna(row["FieldName"]):
                            if "item" in rule_kind:
                                shipper_db[s_name].setdefault("item_table_rules", {})[field] = {
                                    "col": str(row["Cell"]).strip().upper() if "Cell" in df_rules.columns and pd.notna(row["Cell"]) else "K",
                                    "type": str(row["MatchMode"]).strip() if "MatchMode" in df_rules.columns and pd.notna(row["MatchMode"]) else "PDF Row Item",
                                    "rule": str(row["Keyword"]).strip() if "Keyword" in df_rules.columns and pd.notna(row["Keyword"]) else ""
                                }
                            elif "igst_config" in rule_kind or field.lower() in ["lut_keywords", "paid_keywords"]:
                                shipper_db[s_name].setdefault("igst_config", {})[field] = str(row["Keyword"]).strip() if "Keyword" in df_rules.columns and pd.notna(row["Keyword"]) else ""
                            else:
                                shipper_db[s_name].setdefault("mapping_rules", {})[field] = {
                                    "keyword": row["Keyword"] if "Keyword" in df_rules.columns and pd.notna(row["Keyword"]) else "",
                                    "position": row["Position"] if "Position" in df_rules.columns and pd.notna(row["Position"]) else "Right (आगे)",
                                    "cell": row["Cell"] if "Cell" in df_rules.columns and pd.notna(row["Cell"]) else "",
                                    "match_mode": row["MatchMode"] if "MatchMode" in df_rules.columns and pd.notna(row["MatchMode"]) else "Exact Word",
                                    "stop_kw": row["StopKw"] if "StopKw" in df_rules.columns and pd.notna(row["StopKw"]) else "",
                                    "filter": row["Filter"] if "Filter" in df_rules.columns and pd.notna(row["Filter"]) else "None",
                                    "logic": row["Logic"] if "Logic" in df_rules.columns and pd.notna(row["Logic"]) else "None",
                                    "fallback": row["Fallback"] if "Fallback" in df_rules.columns and pd.notna(row["Fallback"]) else ""
                                }
    except Exception:
        pass

    try:
        files_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=Shipper_Files"
        df_files = pd.read_csv(files_url)
        if not df_files.empty:
            df_files.columns = df_files.columns.str.strip()
            for _, row in df_files.iterrows():
                if "ShipperName" in df_files.columns and pd.notna(row["ShipperName"]):
                    s_name = str(row["ShipperName"]).strip()
                    if s_name not in shipper_db:
                        shipper_db[s_name] = {
                            "allowed_uploads": ["Full Job Excel Format File"], 
                            "uploaded_files": {}, 
                            "mapping_rules": {},
                            "item_table_rules": {},
                            "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                        }
                    if "FileBase64" in df_files.columns and pd.notna(row["FileBase64"]):
                        shipper_db[s_name]["uploaded_files"]["Full Job Excel Format File"] = base64.b64decode(str(row["FileBase64"]).strip())
    except Exception:
        pass
                    
    return shipper_db, master_rules_template

# 🔄 डेटा लोड इंजन
if "shipper_database" not in st.session_state or "master_rules_template" not in st.session_state:
    db, m_template = load_data_from_gsheet()
    st.session_state["shipper_database"] = db
    st.session_state["master_rules_template"] = m_template
    st.session_state["master_types"] = ["Full Job Excel Format File"]

if "admin_authenticated" not in st.session_state: st.session_state["admin_authenticated"] = False
if "processed_file_ready" not in st.session_state: st.session_state["processed_file_ready"] = None

# ==========================================
# 🖥️ MAIN PAGE ROUTING DISPLAY
# ==========================================
if st.session_state["admin_authenticated"]:
    top_col1, top_col2 = st.columns([8, 2])
    with top_col1:
        st.title("🚢 CK Export Processor - Admin Mode")
    with top_col2:
        if st.button("🚪 Log Out Admin", type="primary", use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.rerun()
            
    st.write("---")
    
    sub_menu = st.radio(
        "📋 एडमिन सेटिंग्स चुनें:", 
        ["i. 🏢 Add Shipper Name & Setup", "iii. 🌍 Global Masters & Common Dictionaries"],
        horizontal=True
    )
    st.write("---")
    
    from shipper_data import render_shipper_data
    from global_masters import render_global_masters
    
    if sub_menu == "i. 🏢 Add Shipper Name & Setup": 
        render_shipper_data()
    elif sub_menu == "iii. 🌍 Global Masters & Common Dictionaries": 
        render_global_masters()

else:
    from processor import render_processor
    
    col_l, col_c, col_r = st.columns([1, 5, 1])
    with col_c:
        st.title("🚢 CK Export Invoice Processor Pro")
        st.write("---")
        render_processor()
        
        st.write("---")
        st.write("---")
        
        with st.expander("🛠️ Admin Settings Access"):
            pwd = st.text_input("एडमिन पासवर्ड दर्ज करें:", type="password", key="main_admin_pwd")
            if st.button("लॉगिन करें"):
                if pwd == "CK@SOHAM":
                    st.session_state["admin_authenticated"] = True
                    st.rerun()
                else:
                    st.error("गलत पासवर्ड!")
