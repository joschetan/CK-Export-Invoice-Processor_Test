import streamlit as st
import pdfplumber
import re
from pdf_engine import extract_header_value, apply_value_replacement
from parser_welspun import extract_welspun_items
from parser_bkt import extract_bkt_items

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
    assigned_parser = shipper_info.get("item_table_rule_name", "parser_welspun").strip().lower()

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
            # 🚀 SMART ROW-BY-ROW ITEM TABLE PREVIEW
            rule_info = item_rules[target_field]
            col_letter = rule_info.get("col", "").upper()
            rule_type = rule_info.get("type", "PDF Row Item")
            rule_val = rule_info.get("rule", "")

            st.markdown("#### 📋 Item Rule Configuration")
            st.write(f"* **Target Excel Column:** `{col_letter}`")
            st.write(f"* **Rule Type:** `{rule_type}`")
            st.write(f"* **Rule Value / Detail:** `{rule_val}`")

            st.markdown("---")
            st.markdown(f"#### 📊 Row-by-Row Preview for Column `{col_letter}`")

            # सही पार्सर कॉल करके सारे आइटम्स निकालें
            if "bkt" in assigned_parser:
                parsed_items = extract_bkt_items(pdf_lines)
            else:
                parsed_items = extract_welspun_items(pdf_lines, pdf_text=pdf_text)

            if parsed_items:
                preview_table_data = []
                for idx, item in enumerate(parsed_items):
                    excel_row_num = 2 + idx  # मान लेते हैं डेटा Row 2 से शुरू होता है
                    cell_target = f"{col_letter}{excel_row_num}"
                    
                    nums = item.get("nums", [])
                    r_val_lower = str(rule_val).lower().strip()
                    f_name_lower = target_field.lower().strip()
                    extracted_cell_val = ""

                    # सिमुलेशन लॉजिक ठीक वैसे ही जैसे प्रोसेसर में चलता है
                    if rule_type == "Constant Text":
                        extracted_cell_val = apply_value_replacement(rule_val, rule_val)
                    elif rule_type == "Excel Cell Reference":
                        extracted_cell_val = f"={rule_val}"
                    elif rule_type == "Smart Detection":
                        desc = item.get("description_text", "").upper()
                        if "PCS" in desc or "PC" in desc:
                            extracted_cell_val = "PCS"
                        else:
                            extracted_cell_val = rule_val if rule_val else "SET"
                    else:
                        # Standard PDF Row Item logic matching
                        if "igst %" in r_val_lower or "igst rate" in f_name_lower:
                            extracted_cell_val = nums[5] if len(nums) > 5 else ""
                        elif "igst amt" in r_val_lower or "igst amount" in f_name_lower:
                            extracted_cell_val = nums[6] if len(nums) > 6 else ""
                        elif "hs" in r_val_lower or "ritc" in f_name_lower or "hs code" in r_val_lower:
                            extracted_cell_val = item.get("hs_code", "")
                        elif "description" in r_val_lower or "description" in f_name_lower:
                            extracted_cell_val = item.get("description_text", "")
                        elif "dbk" in r_val_lower or "drawback" in f_name_lower or col_letter == "S":
                            extracted_cell_val = item.get("dbk_found", "")
                        elif "weight" in r_val_lower or "net wt" in f_name_lower:
                            extracted_cell_val = nums[0] if len(nums) > 0 else ""
                        elif "qty" in r_val_lower or "quantity" in f_name_lower:
                            extracted_cell_val = nums[1] if len(nums) > 1 else ""
                        elif "rate" in r_val_lower:
                            extracted_cell_val = nums[2] if len(nums) > 2 else ""
                        elif "amount" in r_val_lower or "goods value" in f_name_lower:
                            extracted_cell_val = nums[3] if len(nums) > 3 else ""
                        elif "taxable" in r_val_lower:
                            extracted_cell_val = nums[4] if len(nums) > 4 else ""
                        else:
                            extracted_cell_val = rule_val

                        if "=" in str(rule_val):
                            extracted_cell_val = apply_value_replacement(str(extracted_cell_val), str(rule_val))

                    preview_table_data.append({
                        "Item Sr No": idx + 1,
                        "Excel Cell": cell_target,
                        "Extracted Value": str(extracted_cell_val)
                    })

                # Streamlit में खूबसूरत टेबल दिखाना
                st.dataframe(preview_table_data, use_container_width=True)
                st.success(f"🎉 कुल {len(parsed_items)} आइटम्स की रो-बाय-रो रिपोर्ट सफलतापूर्वक जनरेट हो गई है!")
            else:
                st.warning("⚠️ इस PDF में कोई आइटम रो नहीं मिली या पार्सर से डेटा एक्सट्रेक्ट नहीं हुआ।")
