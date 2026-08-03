def fetch_data_from_google_sheet(show_toast=False):
    """गूगल शीट से आए JSON डेटा को सीधे सेशन स्टेट में लोड करता है"""
    ensure_default_shipper()
    try:
        fetch_cached_sheet_data.clear()
        data = fetch_all_from_sheet()
        
        if not data or not isinstance(data, dict):
            if show_toast: st.error("⚠️ गूगल शीट से डेटा नहीं मिला.")
            return

        shippers_dict = data.get("shippers", {})
        
        for s_name, s_data in shippers_dict.items():
            if not s_name:
                continue
                
            if s_name not in st.session_state["shipper_database"]:
                st.session_state["shipper_database"][s_name] = {
                    "allowed_uploads": ["Full Job Excel Format File"],
                    "uploaded_files": {},
                    "mapping_rules": {},
                    "item_table_rules": {},
                    "item_table_rule_name": "Rule_Welspun",
                    "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                }
            
            shipper_info = st.session_state["shipper_database"][s_name]
            
            if isinstance(s_data, dict):
                shipper_info["mapping_rules"] = s_data.get("mapping_rules", {})
                shipper_info["item_table_rules"] = s_data.get("item_table_rules", {})
                shipper_info["item_table_rule_name"] = s_data.get("item_table_rule_name", "Rule_Welspun")
                shipper_info["igst_config"] = s_data.get("igst_config", {"lut_keywords": "", "paid_keywords": ""})

            # कॉलम C से टेम्पलेट बाइट्स लोड करना
            t_bytes = load_template_bytes_from_sheet(s_name)
            if t_bytes:
                shipper_info.setdefault("uploaded_files", {})["Full Job Excel Format File"] = t_bytes

        if show_toast: st.toast("✅ गूगल शीट से सारे रूल्स सफलतापर्पूर्वक लोड हो गए!")
    except Exception as e:
        if show_toast: st.error(f"फ़ैच एरर: {str(e)}")
