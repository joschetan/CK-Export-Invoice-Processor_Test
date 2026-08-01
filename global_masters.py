import streamlit as st
import requests
import json

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbwEsmWdnkVW3H7_fD99vPMrqhvmY6iJHP1ZooKuwDlj2VE4cht_FBgFyem9xDRFlbjuNw/exec"

@st.dialog("➕ Add New Global Master Field")
def add_master_field_dialog():
    new_master_name = st.text_input("Master Field Name:", placeholder="यहाँ नाम लिखें...")
    if st.button("Confirm & Add to Master", type="primary"):
        if new_master_name.strip() and new_master_name not in st.session_state.get("master_rules_template", {}):
            st.session_state.setdefault("master_rules_template", {})[new_master_name] = {
                "keyword": "", "position": "Right (आगे)", "cell": "",
                "match_mode": "Exact Word", "stop_kw": "", "filter": "None", "logic": "None", "fallback": ""
            }
            st.success(f"🎉 मास्टर फ़ील्ड '{new_master_name}' जुड़ गया!")
            st.rerun()

def render_global_masters():
    st.header("🌍 Global Master Fields & 8-Column Rules Template")
    st.caption("परमानेंट मास्टर टेम्पलेट बोर्ड एवं एडवांस कॉमन डिक्शनरीज़।")
    st.write("---")
    
    col_t, col_add = st.columns([8, 2])
    with col_t: st.subheader("🛠️ Master Rules Template Builder (Advanced)")
    with col_add:
        if st.button("➕ Add Master Row", type="secondary", use_container_width=True):
            add_master_field_dialog()
            
    current_masters = st.session_state.get("master_rules_template", {})
    updated_masters = {}
    
    pos_options = ["Right (आगे)", "Below (नीचे)", "2 Lines Below", "Table Row Item", "Table Row Index"]
    match_options = ["Exact Word", "Word Position", "Full Line", "After Word", "Between Keywords", "Table Row Match"]
    filter_options = [
        "None", 
        "Text Inside Parentheses ()", 
        "Numbers Only", 
        "Letters Only", 
        "Container Number (ISO Format)", 
        "Container Size (20/40 Only)", 
        "Clean Date (DD/MM/YYYY)",
        "Exact Keyword Paste (If Found)",
        "Remove All Spaces"
    ]
    
    c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([1.8, 2.2, 1.3, 0.7, 1.5, 1.3, 1.5, 1.5, 0.7])
    with c1: st.markdown("**Field Name**")
    with c2: st.markdown("**Keyword**")
    with c3: st.markdown("**Position**")
    with c4: st.markdown("**Cell**")
    with c5: st.markdown("**Match Mode**")
    with c6: st.markdown("**Stop / Word**")
    with c7: st.markdown("**Filter/Logic**")
    with c8: st.markdown("**Fallback Value**")
    with c9: st.markdown("**Del**")
    st.write("---")
    
    for field in list(current_masters.keys()):
        s_val = current_masters[field]
        c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([1.8, 2.2, 1.3, 0.7, 1.5, 1.3, 1.5, 1.5, 0.7])
        
        with c1: edited_name = st.text_input(f"m_f_{field}", value=field, label_visibility="collapsed")
        with c2: ky = st.text_input(f"m_k_{field}", value=s_val.get("keyword", ""), label_visibility="collapsed")
        
        saved_pos = s_val.get("position", "Right (आगे)")
        pos_idx = pos_options.index(saved_pos) if saved_pos in pos_options else 0
        with c3: pos = st.selectbox(f"m_p_{field}", pos_options, index=pos_idx, label_visibility="collapsed")
        
        with c4: cl = st.text_input(f"m_c_{field}", value=s_val.get("cell", ""), label_visibility="collapsed")
        
        saved_mode = s_val.get("match_mode", "Exact Word")
        mode_idx = match_options.index(saved_mode) if saved_mode in match_options else 0
        with c5: m_mode = st.selectbox(f"m_mm_{field}", match_options, index=mode_idx, label_visibility="collapsed")
        
        with c6: stop_kw = st.text_input(f"m_sk_{field}", value=s_val.get("stop_kw", ""), label_visibility="collapsed")
        
        saved_flt = s_val.get("filter", "None")
        if saved_flt in ["Inside Parentheses ()", "Text Inside ()"]:
            saved_flt = "Text Inside Parentheses ()"
        flt_idx = filter_options.index(saved_flt) if saved_flt in filter_options else 0
        with c7: final_flt = st.selectbox(f"m_flt_{field}", filter_options, index=flt_idx, label_visibility="collapsed")
        
        with c8: fb_val = st.text_input(f"m_fb_{field}", value=s_val.get("fallback", ""), placeholder="फॉलबैक", label_visibility="collapsed")
        
        with c9:
            if st.button("🗑️", key=f"m_del_{field}"):
                del st.session_state["master_rules_template"][field]
                st.rerun()
                
        updated_masters[edited_name] = {
            "keyword": ky, "position": pos, "cell": cl,
            "match_mode": m_mode, "stop_kw": stop_kw, "filter": final_flt, "logic": "None", "fallback": fb_val
        }
        
    st.session_state["master_rules_template"] = updated_masters
    st.write("---")

    # =========================================================================
    # 🛡️ GLOBAL SECTION: COLUMN V AUTO-DETECTION CONFIGURATOR
    # =========================================================================
    st.subheader("🛡️ Global Column V Auto-Detection Configurator (LUT vs Paid 'P')")
    st.caption("ग्लोबल लेवल पर LUT और Paid ढूँढने के डिफ़ॉल्ट कीवर्ड्स यहाँ तय करें:")
    
    global_igst = st.session_state.setdefault("global_igst_config", {
        "lut_keywords": "LUT ARN NO., w/o payment of integrated tax, under bond",
        "paid_keywords": "on payment of integrated tax, with payment of integrated tax, Supply meant for export with payment of integrated tax"
    })
    
    g_lut, g_paid = st.columns(2)
    with g_lut:
        g_lut_val = st.text_area("📌 Global LUT Detection Keywords:", value=global_igst.get("lut_keywords", ""), key="global_lut_kw")
    with g_paid:
        g_paid_val = st.text_area("📌 Global Paid (P) Detection Keywords:", value=global_igst.get("paid_keywords", ""), key="global_paid_kw")
        
    st.session_state["global_igst_config"] = {"lut_keywords": g_lut_val, "paid_keywords": g_paid_val}
    st.write("---")

    # =========================================================================
    # 📦 GLOBAL SECTION: DYNAMIC ITEM TABLE COLUMN BUILDER
    # =========================================================================
    st.subheader("📦 Global Dynamic Item Table Column Builder")
    st.caption("ग्लोबल आइटम टेबल कॉलम रूल्स यहाँ सेट करें:")
    
    global_item_rules = st.session_state.setdefault("global_item_rules", {})
    updated_global_item_rules = {}
    
    gic1, gic2, gic3, gic4, gic5 = st.columns([3, 2, 3, 3, 1])
    with gic1: st.markdown("**Item Field Name**")
    with gic2: st.markdown("**Excel Column**")
    with gic3: st.markdown("**Rule Type**")
    with gic4: st.markdown("**Rule Detail / Value**")
    with gic5: st.markdown("**Act**")
    
    rule_type_options = ["PDF Row Item", "Table Row Item", "Constant Text", "Excel Cell Reference", "Smart Detection", "Header Field Mapping"]
    available_header_fields = list(current_masters.keys())
    
    for g_field in list(global_item_rules.keys()):
        gir = global_item_rules[g_field]
        gic1, gic2, gic3, gic4, gic5 = st.columns([3, 2, 3, 3, 1])
        s_type = gir.get("type", "PDF Row Item")
        s_idx = rule_type_options.index(s_type) if s_type in rule_type_options else 0
        
        with gic1: ge_field = st.text_input(f"g_if_{g_field}", value=g_field, label_visibility="collapsed")
        with gic2: ge_col = st.text_input(f"g_ic_{g_field}", value=gir.get("col", "K"), label_visibility="collapsed").upper()
        with gic3: ge_type = st.selectbox(f"g_it_{g_field}", rule_type_options, index=s_idx, label_visibility="collapsed")
        
        with gic4:
            if ge_type == "Header Field Mapping":
                saved_rule = gir.get("rule", "")
                h_idx = available_header_fields.index(saved_rule) if saved_rule in available_header_fields else 0
                ge_rule = st.selectbox(f"g_ir_{g_field}", available_header_fields if available_header_fields else ["No Headers Found"], index=h_idx if available_header_fields else 0, label_visibility="collapsed")
            else:
                ge_rule = st.text_input(f"g_ir_{g_field}", value=gir.get("rule", ""), label_visibility="collapsed")
                
        with gic5:
            if st.button("🗑️", key=f"g_idel_{g_field}"):
                del global_item_rules[g_field]
                st.rerun()
                
        updated_global_item_rules[ge_field] = {"col": ge_col, "type": ge_type, "rule": ge_rule}
        
    st.session_state["global_item_rules"] = updated_global_item_rules
    
    if st.button("➕ Add Global Item Column", key="add_global_item_col_btn"):
        st.session_state["global_item_rules"]["New Item Field"] = {"col": "K", "type": "PDF Row Item", "rule": ""}
        st.rerun()
        
    st.write("---")
    
    if st.button("💾 Save Entire Master Template to Google Sheet", type="primary", use_container_width=True):
        fields_payload = []
        for f_name, r_info in updated_masters.items():
            fields_payload.append({
                "field": f_name, "keyword": r_info.get("keyword", ""), "position": r_info.get("position", "Right (आगे)"),
                "cell": r_info.get("cell", ""), "match_mode": r_info.get("match_mode", "Exact Word"),
                "stop_kw": r_info.get("stop_kw", ""), "filter": r_info.get("filter", "None"), "logic": r_info.get("logic", "None"),
                "fallback": r_info.get("fallback", "")
            })
            
        payload = {"action": "save_master_fields", "fields": fields_payload}
        try:
            requests.post(WEB_APP_URL, data=json.dumps(payload))
            st.success("🎉 मास्टर टेम्पलेट गूगल शीट में 100% एडवांस फॉर्मेट के साथ लॉक हो गया है!")
        except Exception as e:
            st.error(f"सिंक एरर: {str(e)}")
