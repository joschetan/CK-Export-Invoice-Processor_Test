import streamlit as st
import pdfplumber
import re
from pdf_engine import extract_header_value, apply_value_replacement

def render_universal_test_suite(selected_shipper):
    st.markdown("---")
    st.header("🧪 Universal Interactive Debugger & Test Suite")
    st.caption("बिना एक्सेल जनरेट किए सीधे लाइव चेक करें कि किस कॉलम में exact क्या डेटा जाएगा।")

    if "cached_pdf_lines" not in st.session_state or not st.session_state["cached_pdf_lines"]:
        st.info("💡 कृपया पहले Section 2 में अपनी इनवॉइस PDF अपलोड करें, फिर यहाँ टेस्ट रन करें।")
        return

    pdf_lines = st.session_state.get("cached_pdf_lines", [])
    pdf_text = st.session_state.get("cached_pdf_text", "")
    
    shipper_info = st.session_state["shipper_database"].get(selected_shipper, {})
    header_rules = shipper_info.get("mapping_rules", {})
    item_rules = shipper_info.get("item_table_rules", {})

    col_category, col_field = st.columns([1, 2])

    with col_category:
        test_category = st.radio("टेस्ट कैटेगरी चुनें:", ["Header Fields Rules", "Item Table Columns (G to AB)"])

    with col_field:
        if test_category == "Header Fields Rules":
            field_options = list(header_rules.keys())
            if not field_options:
                st.warning("कोई Header Field उपलब्ध नहीं है।")
                return
            target_field = st.selectbox("जाँचने के लिए Header Field चुनें:", field_options)
        else:
            field_options = list(item_rules.keys())
            if not field_options:
                st.warning("कोई Item Table Column उपलब्ध नहीं है।")
                return
            target_field = st.selectbox("जाँचने के लिए Item Field चुनिए:", field_options)

    if st.button("🚀 Run Live Single Field Inspection", type="primary", use_container_width=True):
        st.write("---")
        st.subheader(f"🔍 Inspection Result: `{target_field}`")

        if test_category == "Header Fields Rules":
            rule_data = header_rules[target_field]
            ky = rule_data.get("keyword", "")
            pos = rule_data.get("position", "Right (आगे)")
            cl = rule_data.get("cell", "").strip()
            m_mode = rule_data.get("match_mode", "Exact Word")
            stop_kw = rule_data.get("stop_kw", "")
            final_flt = rule_data.get("filter", "None")

            final_val = extract_header_value(pdf_lines, pdf_text, ky, pos, m_mode, stop_kw, final_flt)

            # 🎯 DYNAMIC ROW DISPLAY SUPPORT FOR HEADER FIELDS
            display_cell = cl if cl else 'Not Set'
            if cl and cl.isalpha():
                display_cell = f"{cl.upper()}2 (Dynamic Auto-Increment Row)"

            res_col1, res_col2 = st.columns(2)
            with res_col1:
                st.markdown("#### 📋 Field Parameters")
                st.write(f"* **Target Excel Cell:** `{display_cell}`")
                st.write(f"* **Keyword:** `{ky if ky else 'N/A'}`")
                st.write(f"* **Match Mode:** `{m_mode}`")
                st.write(f"* **Filter:** `{final_flt}`")

            with res_col2:
                st.markdown("#### 🎯 Extracted Excel Value")
                if final_val:
                    st.success(f"✅ **Value to Excel:** `{final_val}`")
                else:
                    st.error("⚠️ **Result:** BLANK / NOT FOUND")

        else:
            # Item Table Inspection Logic
            rule_info = item_rules[target_field]
            col_letter = rule_info.get("col", "").upper()
            rule_type = rule_info.get("type", "PDF Row Item")
            rule_val = rule_info.get("rule", "")

            st.markdown("#### 📋 Item Rule Configuration")
            st.write(f"* **Target Column:** `{col_letter}`")
            st.write(f"* **Rule Type:** `{rule_type}`")
            st.write(f"* **Rule Value / Index:** `{rule_val}`")

            st.markdown("#### 🎯 First Row Simulated Data")
            # PDF ki pehli HS Code wali line pe simulated run
            first_item_found = None
            for line in pdf_lines:
                if re.match(r'^\d{8}\b', line.strip()):
                    nums = re.findall(r'[\d,]+\.\d{2,3}', line)
                    first_item_found = {"line": line.strip(), "nums": nums}
                    break

            if first_item_found:
                st.code(f"Raw Line: {first_item_found['line']}", language="text")
                st.write(f"Detected Numbers in Row: `{first_item_found['nums']}`")
                
                # Sample Extraction logic display
                if rule_type == "Constant Text":
                    sample_res = apply_value_replacement(rule_val, rule_val)
                elif rule_type == "Excel Cell Reference":
                    sample_res = f"={rule_val}"
                elif rule_type == "Smart Detection":
                    if ":" in rule_val:
                        smart_parts = [p.strip() for p in rule_val.split(":")]
                        if len(smart_parts) == 3:
                            search_kw = smart_parts[0].upper()
                            match_val = smart_parts[1]
                            fallback_val = smart_parts[2]
                            
                            if search_kw in str(pdf_text).upper():
                                sample_res = match_val
                            else:
                                sample_res = fallback_val
                        else:
                            sample_res = rule_val
                    else:
                        line_upper = first_item_found['line'].upper()
                        if "PCS" in line_upper or "PC" in line_upper:
                            sample_res = "PCS"
                        else:
                            sample_res = rule_val if rule_val else "SET"
                else:
                    sample_res = f"Mapped via {rule_type} ({rule_val})"
                    if "=" in rule_val:
                        sample_res = apply_value_replacement(sample_res, rule_val)

                st.success(f"✅ **Simulated First Cell Output ({col_letter}2):** `{sample_res}`")
            else:
                st.warning("⚠️ PDF में कोई 8-digit HS Code वाली रो नहीं मिली।")
