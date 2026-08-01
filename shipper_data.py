import streamlit as st
import base64
import pdfplumber
import os
import re
from io import BytesIO

from pdf_engine import extract_header_value, detect_igst_status
from test_suite import render_universal_test_suite
from google_sheet_sync import fetch_all_from_sheet, push_all_to_sheet, get_val_case_insensitive, load_template_bytes_from_sheet
from igst_config_sync import fetch_igst_config_from_sheet

def ensure_default_shipper():
    if "shipper_database" not in st.session_state:
        st.session_state["shipper_database"] = {}
        
    s_name = "WELSPUN GLOBAL BRANDS LIMITED"
    if s_name not in st.session_state["shipper_database"]:
        st.session_state["shipper_database"][s_name] = {
            "allowed_uploads": ["Full Job Excel Format File"], 
            "uploaded_files": {},
            "mapping_rules": {},
            "item_table_rules": {},
            "igst_config": {"lut_keywords": "", "paid_keywords": ""}
        }

@st.cache_data(show_spinner=False)
def fetch_cached_sheet_data():
    return fetch_all_from_sheet()

def fetch_data_from_google_sheet(show_toast=False):
    ensure_default_shipper()
    try:
        data = fetch_cached_sheet_data()
        if not data:
            if show_toast: st.error("⚠️ गूगल शीट से डेटा नहीं मिला.")
            return

        rules_list = data.get("rules", [])
        
        if isinstance(rules_list, list) and len(rules_list) > 1:
            for row in rules_list[1:]:
                if not row or len(row) < 11:
                    continue
                
                # A: ShipperName (0), B: FieldName (1), C: Keyword (2), D: Position (3), E: Cell (4), F: MatchMode (5)
                # G: Stop/Word (6), H: Filter/Logic (7), I: Main Invoice (8), J: Fallback (9), K: RuleKind (10)
                s_name = str(row[0]).strip() if row[0] is not None else ""
                f_name = str(row[1]).strip() if row[1] is not None else ""
                kw_val = str(row[2]).strip() if row[2] is not None else ""
                pos_val = str(row[3]).strip() if row[3] is not None else "Right (आगे)"
                cell_val = str(row[4]).strip().upper() if row[4] is not None else ""
                match_val = str(row[5]).strip() if row[5] is not None else "Exact Word"
                stop_val = str(row[6]).strip() if row[6] is not None else ""
                flt_val = str(row[7]).strip() if row[7] is not None else "None"
                logic_val = str(row[8]).strip() if row[8] is not None else "Main Invoice"
                fb_val = str(row[9]).strip() if row[9] is not None else ""
                rule_kind = str(row[10]).strip().lower() if row[10] is not None else "header"
                
                if f_name.lower() in ["igst status", "igst mode"] or cell_val in ["V", "B19"]:
                    continue

                if s_name and f_name:
                    target_key = s_name
                        
                    if target_key not in st.session_state["shipper_database"]:
                        st.session_state["shipper_database"][target_key] = {
                            "allowed_uploads": ["Full Job Excel Format File"],
                            "uploaded_files": {},
                            "mapping_rules": {},
                            "item_table_rules": {},
                            "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                        }
                    
                    if "igst_config" in rule_kind or f_name.lower() in ["lut_keywords", "paid_keywords"]:
                        if f_name.lower() == "lut_keywords":
                            st.session_state["shipper_database"][target_key].setdefault("igst_config", {})["lut_keywords"] = kw_val
                        elif f_name.lower() == "paid_keywords":
                            st.session_state["shipper_database"][target_key].setdefault("igst_config", {})["paid_keywords"] = kw_val
                    elif "item" in rule_kind:
                        st.session_state["shipper_database"][target_key].setdefault("item_table_rules", {})[f_name] = {
                            "col": cell_val,
                            "type": match_val,
                            "rule": kw_val
                        }
                    else:
                        if not flt_val or flt_val == "":
                            flt_val = "None"
                            
                        if "(pdf)" in logic_val.lower():
                            logic_val = "Main Invoice"

                        st.session_state["shipper_database"][target_key].setdefault("mapping_rules", {})[f_name] = {
                            "keyword": kw_val,
                            "position": pos_val,
                            "cell": cell_val,
                            "match_mode": match_val,
                            "stop_kw": stop_val,
                            "filter": flt_val,
                            "logic": logic_val,
                            "fallback": fb_val
                        }

        for s_key in st.session_state["shipper_database"].keys():
            igst_fetched = fetch_igst_config_from_sheet(s_key)
            if igst_fetched and isinstance(igst_fetched, dict):
                current_igst = st.session_state["shipper_database"][s_key].get("igst_config", {})
                if not current_igst.get("lut_keywords"):
                    current_igst["lut_keywords"] = igst_fetched.get("lut_keywords", "")
                if not current_igst.get("paid_keywords"):
                    current_igst["paid_keywords"] = igst_fetched.get("paid_keywords", "")
                st.session_state["shipper_database"][s_key]["igst_config"] = current_igst

            t_bytes = load_template_bytes_from_sheet(s_key)
            if t_bytes:
                st.session_state["shipper_database"][s_key].setdefault("uploaded_files", {})["Full Job Excel Format File"] = t_bytes

        if show_toast: st.toast("✅ गूगल शीट से रूल्स और टेम्पलेट लोड हो गए!")
    except Exception as e:
        if show_toast: st.error(f"फ़ैच एरर: {str(e)}")

@st.dialog("🧪 Live Extraction Field Test Result")
def show_field_test_dialog(field_name, rule_data, result_val):
    st.write(f"### 🔍 Field: **`{field_name}`**")
    st.markdown("#### 📋 Applied Rule Parameters:")
    
    raw_cell = str(rule_data.get('cell', 'Blank')).strip()
    display_cell = f"{raw_cell} (Dynamic Row)" if raw_cell and raw_cell.isalpha() else raw_cell

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"* **Keyword:** `{rule_data.get('keyword', 'N/A')}`")
        st.markdown(f"* **Position:** `{rule_data.get('position', 'Right (आगे)')}`")
        st.markdown(f"* **Target Cell:** `{display_cell}`")
    with col_b:
        st.markdown(f"* **Match Mode:** `{rule_data.get('match_mode', 'Exact Word')}`")
        st.markdown(f"* **Stop / Word No.:** `{rule_data.get('stop_kw', 'N/A')}`")
        st.markdown(f"* **Filter/Logic:** `{rule_data.get('filter', 'None')}`")
        st.markdown(f"* **Source Doc:** `{rule_data.get('logic', 'Main Invoice')}`")
        
    st.write("---")
    st.markdown("#### 🎯 Extracted Result from Uploaded File:")
    if "❌" in result_val or not result_val.strip():
        st.error(f"❌ **Not Found!** Value: `{result_val}`")
    else:
        st.success("🎉 **SUCCESS! Extracted Value:**")
        st.code(result_val, language="text")

@st.dialog("➕ Add New Custom Header Field")
def add_custom_header_field_dialog(selected_shipper):
    st.write("यहाँ नया हेडर फ़ील्ड जोड़ें:")
    new_field = st.text_input("Field Name (उदा: Invoice No, GST Inv No):")
    
    doc_source = st.selectbox(
        "यह डेटा किस डॉक्यूमेंट से लिया जाएगा?",
        ["Main Invoice", "GST Invoice (PDF/Excel)", "DEEC Declaration (PDF/Excel)"]
    )
    
    if st.button("Confirm & Add Field", type="primary"):
        if not new_field.strip():
            st.error("फ़ील्ड नाम खाली नहीं हो सकता!")
        else:
            rules = st.session_state["shipper_database"][selected_shipper].setdefault("mapping_rules", {})
            rules[new_field.strip()] = {
                "keyword": "", 
                "position": "Right (आगे)", 
                "cell": "",
                "match_mode": "Exact Word", 
                "stop_kw": "", 
                "filter": "None", 
                "logic": doc_source,
                "fallback": ""
            }
            st.success(f"🎉 फ़ील्ड '{new_field}' ({doc_source}) जुड़ गया!")
            st.rerun()

@st.dialog("➕ Add Item Column Rule")
def add_item_col_dialog(selected_shipper):
    st.write("यहाँ आइटम टेबल के लिए नया कॉलम हेडिंग और एक्सेल कॉलम जोड़ें:")
    c_name = st.text_input("Heading Name (उदा: Net Weight, Boxes, Size):")
    c_col = st.text_input("Excel Column Letter (उदा: L, M, N, Z):").upper()
    c_type = st.selectbox("Rule Type:", ["PDF Row Item", "Table Row Item", "Constant Text", "Excel Cell Reference", "Smart Detection", "Header Field Mapping"])
    c_rule = st.text_input("Rule Detail / Value (उदा: B19, SET, PCS, Numbers Only):")
    
    if st.button("Confirm & Add Item Column", type="primary"):
        if not c_name or not c_col:
            st.error("Heading Name और Column Letter अनिवार्य हैं!")
        else:
            item_rules = st.session_state["shipper_database"][selected_shipper].setdefault("item_table_rules", {})
            item_rules[c_name] = {"col": c_col, "type": c_type, "rule": c_rule}
            st.success(f"🎉 कॉलम '{c_name}' जुड़ गया!")
            st.rerun()

def render_shipper_data():
    if "sheet_data_loaded" not in st.session_state:
        fetch_data_from_google_sheet(show_toast=False)
        st.session_state["sheet_data_loaded"] = True
    
    st.header("🏢 Add Shipper Name & Live-Test AI Mapping Builder")
    st.caption("सटीक डेटा एक्सट्रैक्शन और रो-बाय-रो लाइव टेस्ट इंजन.")
    
    with st.expander("➕ Add New Shipper (नया शिपर जोड़ें)", expanded=False):
        new_shipper_name = st.text_input("नया शिपर कंपनी का नाम दर्ज करें:", key="input_new_shipper_name")
        if st.button("Create New Shipper Profile", type="primary", key="btn_create_shipper"):
            if not new_shipper_name.strip():
                st.error("शिपर का नाम खाली नहीं हो सकता!")
            else:
                s_clean = new_shipper_name.strip()
                if s_clean not in st.session_state["shipper_database"]:
                    st.session_state["shipper_database"][s_clean] = {
                        "allowed_uploads": ["Full Job Excel Format File"],
                        "uploaded_files": {},
                        "mapping_rules": {},
                        "item_table_rules": {},
                        "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                    }
                    st.success(f"🎉 नया शिपर '{s_clean}' सफलतापूर्वक जुड़ गया है! अब नीचे ड्रॉपडाउन से इसे चुनकर कॉन्फ़िगर करें.")
                    st.rerun()
                else:
                    st.warning("⚠️ यह शिपर पहले से मौजूद है!")

    shippers_list = list(st.session_state["shipper_database"].keys())
    
    if shippers_list:
        selected_shipper = st.selectbox("कॉन्फ़िगर करने के लिए शिपर चुनें:", shippers_list, index=0)
        
        if selected_shipper:
            st.write(f"### ⚙️ प्रोफाइल सेटअप और रूल्स: **{selected_shipper}**")
            shipper_info = st.session_state["shipper_database"][selected_shipper]
            
            st.subheader("📁 1. टेम्पलेट फ़ाइल अपलोड")
            
            has_file = "Full Job Excel Format File" in shipper_info.get("uploaded_files", {})
            if has_file:
                st.success("✅ Blank Full Job Excel Format File अपलोडेड एवं सुरक्षित है.")
                if st.button("🗑️ Delete & Replace Template", key=f"del_tpl_{selected_shipper}"):
                    del shipper_info["uploaded_files"]["Full Job Excel Format File"]
                    st.rerun()
            else:
                f_upload = st.file_uploader("➡️ Blank Full Job Excel Format File (Template) अपलोड करें", type=["xlsx", "xls"], key=f"tpl_{selected_shipper}")
                if f_upload:
                    shipper_info.setdefault("uploaded_files", {})["Full Job Excel Format File"] = f_upload.getvalue()
                    st.success("टेम्पलेट सेव हो गया! अब नीचे 'Save All Rules' दबाकर गूगल शीट में लॉक करें.")
                    st.rerun()
                    
            st.write("---")
            
            st.subheader("🧪 2. Instant PDF Upload & Live Data Test Engine")
            st.caption("यहाँ टेस्ट इनवॉइस PDF अपलोड करें, फिर रूल्स के सामने ⚡ Test दबाकर पॉप-अप में लाइव डेटा देखें.")
            
            test_pdf = st.file_uploader("➡️ टेस्ट करने के लिए इनवॉइस PDF अपलोड करें", type=["pdf"], key=f"test_pdf_{selected_shipper}")
            
            pdf_lines = []
            pdf_text = ""
            if test_pdf:
                with pdfplumber.open(test_pdf) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            pdf_text += t + "\n"
                            pdf_lines.extend(t.split("\n"))
                st.session_state["cached_pdf_lines"] = pdf_lines
                st.session_state["cached_pdf_text"] = pdf_text
                st.success(f"📄 PDF अपलोड है ({len(pdf_lines)} पंक्तियाँ)। अब नीचे ⚡ Test बटन दबाएँ!")

            st.write("---")
            
            col_title, col_sync, col_add_h, col_import = st.columns([3.5, 2.5, 2, 2])
            with col_title:
                st.subheader("🛠️ 3. Header Fields Mapping Rules")
            with col_sync:
                if st.button("🔄 Reload Saved Rules", type="secondary", use_container_width=True):
                    with st.spinner("⏳ गूगल शीट से रूल्स लोड हो रहे हैं..."):
                        fetch_cached_sheet_data.clear()
                        st.session_state["sheet_data_loaded"] = False
                        st.session_state["shipper_database"] = {}
                        fetch_data_from_google_sheet(show_toast=True)
                    st.rerun()
            with col_add_h:
                if st.button("➕ Add Field", type="secondary", use_container_width=True):
                    add_custom_header_field_dialog(selected_shipper)
            with col_import:
                if st.button("📥 Import Master", type="primary", use_container_width=True, help="ग्लोबल मास्टर से डिफ़ॉल्ट रूल्स यहाँ इम्पोर्ट करें"):
                    master_tpl = st.session_state.get("master_rules_template", {})
                    if master_tpl:
                        imported_rules = {}
                        for m_key, m_val in master_tpl.items():
                            imported_rules[m_key] = {
                                "keyword": m_val.get("keyword", ""),
                                "position": m_val.get("position", "Right (आगे)"),
                                "cell": m_val.get("cell", ""),
                                "match_mode": m_val.get("match_mode", "Exact Word"),
                                "stop_kw": m_val.get("stop_kw", ""),
                                "filter": m_val.get("filter", "None"),
                                "logic": "Main Invoice",
                                "fallback": ""
                            }
                        shipper_info["mapping_rules"] = imported_rules
                        
                        g_items = st.session_state.get("global_item_rules", {})
                        if g_items:
                            shipper_info["item_table_rules"] = dict(g_items)
                            
                        g_igst = st.session_state.get("global_igst_config", {})
                        if g_igst:
                            shipper_info["igst_config"] = dict(g_igst)
                            
                        st.success("🎉 ग्लोबल मास्टर से फॉर्मेट सफलतापूर्वक इम्पोर्ट हो गया!")
                        st.rerun()
                    else:
                        st.warning("⚠️ ग्लोबल मास्टर टेम्पलेट खाली है!")
            
            current_rules = shipper_info.get("mapping_rules", {})
            updated_rules = {}
            
            pos_options = ["Right (आगे)", "Below (नीचे)", "2 Lines Below", "Table Row Item", "Table Row Index"]
            mode_options = ["Exact Word", "Word Position", "Full Line", "After Word", "Between Keywords", "Table Row Match"]
            
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
            
            c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([1.8, 2.2, 1.3, 0.7, 1.5, 1.3, 1.5, 1.5, 0.7, 1.0])
            with c1: st.markdown("**Field Name**")
            with c2: st.markdown("**Keyword**")
            with c3: st.markdown("**Position**")
            with c4: st.markdown("**Cell**")
            with c5: st.markdown("**Match Mode**")
            with c6: st.markdown("**Stop / Word**")
            with c7: st.markdown("**Filter/Logic**")
            with c8: st.markdown("**Fallback Value**")
            with c9: st.markdown("**Del**")
            with c10: st.markdown("**⚡ Test**")
            st.write("---")
            
            curr_pdf_lines = st.session_state.get("cached_pdf_lines", [])
            curr_pdf_text = st.session_state.get("cached_pdf_text", "")

            for field in list(current_rules.keys()):
                if field.lower() in ["igst status", "igst mode"] or current_rules[field].get("cell", "").strip().upper() in ["V", "B19"]:
                    continue

                s_val = current_rules[field]
                c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([1.8, 2.2, 1.3, 0.7, 1.5, 1.3, 1.5, 1.5, 0.7, 1.0])
                
                saved_pos = s_val.get("position", "Right (आगे)")
                pos_idx = pos_options.index(saved_pos) if saved_pos in pos_options else 0
                
                saved_mode = s_val.get("match_mode", "Exact Word")
                mode_idx = mode_options.index(saved_mode) if saved_mode in mode_options else 0
                
                saved_flt = s_val.get("filter", "None")
                if saved_flt in ["Inside Parentheses ()", "Text Inside ()"]:
                    saved_flt = "Text Inside Parentheses ()"
                
                flt_idx = filter_options.index(saved_flt) if saved_flt in filter_options else 0
                saved_logic = "Main Invoice"

                with c1: edited_name = st.text_input(f"f_{field}", value=field, label_visibility="collapsed")
                with c2: ky = st.text_input(f"k_{field}", value=s_val.get("keyword", ""), label_visibility="collapsed")
                with c3: pos = st.selectbox(f"p_{field}", pos_options, index=pos_idx, label_visibility="collapsed")
                with c4: cl = st.text_input(f"c_{field}", value=s_val.get("cell", ""), label_visibility="collapsed")
                with c5: m_mode = st.selectbox(f"mm_{field}", mode_options, index=mode_idx, label_visibility="collapsed")
                with c6: stop_kw = st.text_input(f"sk_{field}", value=s_val.get("stop_kw", ""), label_visibility="collapsed")
                with c7: final_flt = st.selectbox(f"flt_{field}", filter_options, index=flt_idx, label_visibility="collapsed")
                with c8: fb_val = st.text_input(f"fb_{field}", value=s_val.get("fallback", ""), label_visibility="collapsed", placeholder="अगर ब्लैंक हो")
                with c9:
                    if st.button("🗑️", key=f"del_h_{field}"):
                        del st.session_state["shipper_database"][selected_shipper]["mapping_rules"][field]
                        st.rerun()
                with c10:
                    if st.button("⚡ Test", key=f"test_btn_{field}"):
                        if not curr_pdf_lines:
                            st.toast("⚠️ पहले Section 2 में PDF अपलोड करें!")
                        else:
                            res_val = extract_header_value(curr_pdf_lines, curr_pdf_text, ky, pos, m_mode, stop_kw, final_flt)
                            if not res_val or not res_val.strip():
                                res_val = fb_val
                            
                            rule_summary = {
                                "keyword": ky, "position": pos, "cell": cl,
                                "match_mode": m_mode, "stop_kw": stop_kw, "filter": final_flt, "logic": saved_logic
                            }
                            show_field_test_dialog(edited_name, rule_summary, res_val if res_val else "❌ (Not Found)")
                
                updated_rules[edited_name] = {"keyword": ky, "position": pos, "cell": cl, "match_mode": m_mode, "stop_kw": stop_kw, "filter": final_flt, "logic": saved_logic, "fallback": fb_val}
                
            st.session_state["shipper_database"][selected_shipper]["mapping_rules"] = updated_rules

            st.write("---")
            st.subheader("🛡️ Column V Auto-Detection Configurator (LUT vs Paid 'P')")
            st.caption("कस्टम्स पेनाल्टी से बचने के लिए शिपर के हिसाब से LUT और Paid ढूँढने के कीवर्ड्स यहाँ तय करें:")
            
            igst_cfg = shipper_info.get("igst_config", {})
            
            col_lut, col_paid = st.columns(2)
            with col_lut:
                updated_lut_kws = st.text_area(
                    "📌 LUT Detection Keywords (कॉमा से अलग करें):",
                    value=igst_cfg.get("lut_keywords", ""),
                    key=f"lut_kw_input_{selected_shipper}",
                    help="अगर इनमें से कोई भी शब्द PDF में मिला तो V कॉलम में सीधे 'LUT' जाएगा।"
                )
            with col_paid:
                updated_paid_kws = st.text_area(
                    "📌 Paid (P) Detection Keywords (कॉमा से अलग करें):",
                    value=igst_cfg.get("paid_keywords", ""),
                    key=f"paid_kw_input_{selected_shipper}",
                    help="अगर LUT नहीं मिला और इनमें से कोई शब्द मिला तो V कॉलम में सीधे 'P' जाएगा।"
                )
                
            shipper_info["igst_config"] = {
                "lut_keywords": updated_lut_kws,
                "paid_keywords": updated_paid_kws
            }

            st.write("---")
            
            c_head, c_add_btn = st.columns([7, 3])
            with c_head:
                st.subheader("📦 4. Dynamic Item Table Column Builder (Shipper-Wise)")
            with c_add_btn:
                if st.button("➕ Add Item Column", use_container_width=True, key="btn_add_item_col_main"):
                    add_item_col_dialog(selected_shipper)
            
            item_rules = shipper_info.get("item_table_rules", {})
            updated_item_rules = {}
            
            ic1, ic2, ic3, ic4, ic5 = st.columns([3, 2, 3, 3, 1])
            with ic1: st.markdown("**Item Field Name**")
            with ic2: st.markdown("**Excel Column**")
            with ic3: st.markdown("**Rule Type**")
            with ic4: st.markdown("**Rule Detail / Value**")
            with ic5: st.markdown("**Del**")
            st.write("---")
            
            rule_type_options = ["PDF Row Item", "Table Row Item", "Constant Text", "Excel Cell Reference", "Smart Detection", "Header Field Mapping"]
            available_header_fields = list(current_rules.keys())
            
            for item_field in list(item_rules.keys()):
                if item_field.lower() in ["igst status", "igst mode"] or item_rules[item_field].get("col", "").strip().upper() in ["V", "B19"]:
                    continue

                ir = item_rules[item_field]
                ic1, ic2, ic3, ic4, ic5 = st.columns([3, 2, 3, 3, 1])
                
                saved_type = ir.get("type", "PDF Row Item")
                type_idx = rule_type_options.index(saved_type) if saved_type in rule_type_options else 0
                
                with ic1: e_ifield = st.text_input(f"if_{item_field}", value=item_field, label_visibility="collapsed")
                with ic2: e_icol = st.text_input(f"ic_{item_field}", value=ir.get("col", "K"), label_visibility="collapsed").upper()
                with ic3: e_itype = st.selectbox(f"it_{item_field}", rule_type_options, index=type_idx, label_visibility="collapsed")
                
                with ic4:
                    if e_itype == "Header Field Mapping":
                        saved_rule = ir.get("rule", "")
                        h_idx = available_header_fields.index(saved_rule) if saved_rule in available_header_fields else 0
                        e_irule = st.selectbox(f"ir_{item_field}", available_header_fields if available_header_fields else ["No Headers Found"], index=h_idx if available_header_fields else 0, label_visibility="collapsed")
                    else:
                        e_irule = st.text_input(f"ir_{item_field}", value=ir.get("rule", ""), label_visibility="collapsed")
                        
                with ic5:
                    if st.button("🗑️", key=f"idel_{item_field}"):
                        del item_rules[item_field]
                        st.rerun()
                        
                updated_item_rules[e_ifield] = {"col": e_icol, "type": e_itype, "rule": e_irule}
                
            st.session_state["shipper_database"][selected_shipper]["item_table_rules"] = updated_item_rules
            st.write("---")
            
            if st.button("💾 Save All AI Mapping Rules to Google Sheet", type="primary", use_container_width=True, key="btn_save_all_sheet"):
                rules_payload = []
                files_payload = []
                
                for s_name, s_data in st.session_state["shipper_database"].items():
                    for f_name, r_info in s_data.get("mapping_rules", {}).items():
                        rules_payload.append({
                            "ShipperName": s_name, "FieldName": f_name, "Keyword": r_info.get("keyword", ""),
                            "Position": r_info.get("position", "Right (आगे)"), "Cell": r_info.get("cell", ""),
                            "MatchMode": r_info.get("match_mode", "Exact Word"), "StopKw": r_info.get("stop_kw", ""),
                            "Filter": r_info.get("filter", "None"), "Logic": "Main Invoice",
                            "Fallback": r_info.get("fallback", ""),
                            "RuleKind": "header"
                        })
                    for i_field, i_info in s_data.get("item_table_rules", {}).items():
                        rules_payload.append({
                            "ShipperName": s_name, "FieldName": i_field, "Keyword": i_info.get("rule", ""),
                            "Position": "Right (आगे)", "Cell": i_info.get("col", "K"),
                            "MatchMode": i_info.get("type", "PDF Row Item"), "StopKw": "",
                            "Filter": "None", "Logic": "None", "Fallback": "",
                            "RuleKind": "item"
                        })
                    
                    igst_data = s_data.get("igst_config", {})
                    rules_payload.append({
                        "ShipperName": s_name, "FieldName": "lut_keywords", "Keyword": igst_data.get("lut_keywords", ""),
                        "Position": "Right (आगे)", "Cell": "", "MatchMode": "Config", "StopKw": "",
                        "Filter": "None", "Logic": "None", "Fallback": "", "RuleKind": "igst_config"
                    })
                    rules_payload.append({
                        "ShipperName": s_name, "FieldName": "paid_keywords", "Keyword": igst_data.get("paid_keywords", ""),
                        "Position": "Right (आगे)", "Cell": "", "MatchMode": "Config", "StopKw": "",
                        "Filter": "None", "Logic": "None", "Fallback": "", "RuleKind": "igst_config"
                    })
                        
                    tpl_bytes = s_data.get("uploaded_files", {}).get("Full Job Excel Format File", b"")
                    if isinstance(tpl_bytes, bytes) and len(tpl_bytes) > 0:
                        b64_str = base64.b64encode(tpl_bytes).decode('utf-8')
                        files_payload.append({
                            "ShipperName": s_name,
                            "FileBase64": b64_str
                        })
                
                with st.spinner("⏳ गूगल शीट में सुरक्षित सेव हो रहा है..."):
                    success = push_all_to_sheet(rules_payload, files_payload)
                    if success:
                        fetch_cached_sheet_data.clear()
                        st.session_state["sheet_data_loaded"] = False
                        st.success("🎉 आपके सभी रूल्स, IGST कॉन्फिग और Excel टेम्पलेट गूगल शीट में 100% परमानेंट सेव हो गए हैं और कैच रीसेट हो गई है!")
                        st.balloons()
                    else:
                        st.error("❌ सेव करते समय एरर आया!")

            render_universal_test_suite(selected_shipper)
