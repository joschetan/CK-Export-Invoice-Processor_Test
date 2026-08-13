import streamlit as st
import base64
import pdfplumber
import os
import re
import io
from io import BytesIO

from pdf_engine import extract_header_value, detect_igst_status
from test_suite import render_universal_test_suite
from google_sheet_sync import fetch_all_from_sheet, push_rules_to_sheet, push_template_file_to_sheet, get_val_case_insensitive, load_template_bytes_from_sheet
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
            "item_table_rule_name": "parser_welspun",
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

        shippers_dict = data.get("shippers", {})
        if not shippers_dict and isinstance(data, dict):
            shippers_dict = data
        
        for s_name, s_data in shippers_dict.items():
            if not s_name or s_name == "error":
                continue
                
            if s_name not in st.session_state["shipper_database"]:
                st.session_state["shipper_database"][s_name] = {
                    "allowed_uploads": ["Full Job Excel Format File"],
                    "uploaded_files": {},
                    "mapping_rules": {},
                    "item_table_rules": {},
                    "item_table_rule_name": "parser_welspun",
                    "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                }
            
            shipper_info = st.session_state["shipper_database"][s_name]
            
            if isinstance(s_data, dict):
                shipper_info["mapping_rules"] = s_data.get("mapping_rules", {})
                shipper_info["item_table_rules"] = s_data.get("item_table_rules", {})
                shipper_info["item_table_rule_name"] = s_data.get("item_table_rule_name", "parser_welspun")
                shipper_info["igst_config"] = s_data.get("igst_config", {"lut_keywords": "", "paid_keywords": ""})

            t_bytes = load_template_bytes_from_sheet(s_name)
            if t_bytes:
                shipper_info.setdefault("uploaded_files", {})["Full Job Excel Format File"] = t_bytes

        for s_key in st.session_state["shipper_database"].keys():
            igst_fetched = fetch_igst_config_from_sheet(s_key)
            if igst_fetched and isinstance(igst_fetched, dict):
                current_igst = st.session_state["shipper_database"][s_key].get("igst_config", {})
                if not current_igst.get("lut_keywords"):
                    current_igst["lut_keywords"] = igst_fetched.get("lut_keywords", "")
                if not current_igst.get("paid_keywords"):
                    current_igst["paid_keywords"] = igst_fetched.get("paid_keywords", "")
                st.session_state["shipper_database"][s_key]["igst_config"] = current_igst

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
    
    doc_source_item = st.selectbox(
        "यह आइटम डेटा किस डॉक्यूमेंट से लिया जाएगा?",
        ["Main Invoice", "GST Invoice (PDF/Excel)", "DEEC Declaration (PDF/Excel)"],
        key="add_item_doc_source"
    )
    
    if st.button("Confirm & Add Item Column", type="primary"):
        if not c_name or not c_col:
            st.error("Heading Name और Column Letter अनिवार्य हैं!")
        else:
            item_rules = st.session_state["shipper_database"][selected_shipper].setdefault("item_table_rules", {})
            item_rules[c_name] = {
                "col": c_col, 
                "type": c_type, 
                "rule": c_rule,
                "logic": doc_source_item
            }
            st.success(f"🎉 कॉलम '{c_name}' ({doc_source_item}) जुड़ गया!")
            st.rerun()

def render_shipper_data():
    if "sheet_data_loaded" not in st.session_state:
        fetch_data_from_google_sheet(show_toast=False)
        st.session_state["sheet_data_loaded"] = True
    
    st.header("🏢 Add Shipper Name & Live-Test AI Mapping Builder")
    st.caption("सटीक डेटा एक्सट्रैक्शन और रो-बाय-रो लाइव टेस्ट इंजन.")
    
    with st.expander("➕ Add New Shipper (नया शिपर जोड़ें)", expanded=False):
        new_shipper_name = st.text_input("नया शिपर कंपनी का नाम दर्ज करें:", key="input_new_shipper_name")
        
        available_parsers = ["parser_welspun", "parser_bkt", "parser_polycab", "parser_vapi_welspun"]
        selected_parser_rule = st.selectbox("इस शिपर के लिए पार्सर रूल (Parser File) चुनें:", available_parsers, key="input_new_shipper_parser")
        
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
                        "item_table_rule_name": selected_parser_rule,
                        "igst_config": {"lut_keywords": "", "paid_keywords": ""}
                    }
                    st.success(f"🎉 नया शिपर '{s_clean}' और पार्सर '{selected_parser_rule}' सफलतापूर्वक जुड़ गया है! अब नीचे से कॉन्फ़िगर करें.")
                    st.rerun()
                else:
                    st.warning("⚠️ यह शिपर पहले से मौजूद है!")

    shippers_list = sorted(list(st.session_state["shipper_database"].keys()))
    
    if shippers_list:
        selected_shipper = st.selectbox(
            "कॉन्फ़िगर करने के लिए शिपर चुनें:", 
            shippers_list, 
            index=None, 
            placeholder="शिपर का नाम टाइप करें या चुनें..."
        )
        
        if selected_shipper:
            st.write(f"### ⚙️ प्रोफाइल सेटअप और रूल्स: **{selected_shipper}**")
            shipper_info = st.session_state["shipper_database"][selected_shipper]
            
            current_assigned_parser = shipper_info.get("item_table_rule_name", "parser_welspun")
            available_parsers = ["parser_welspun", "parser_bkt", "parser_polycab", "parser_vapi_welspun"]
            p_idx = available_parsers.index(current_assigned_parser) if current_assigned_parser in available_parsers else 0
            
            updated_parser_choice = st.selectbox("📌 इस शिपर के लिए एक्टिव पार्सर रूल (Parser File):", available_parsers, index=p_idx, key=f"sel_parser_{selected_shipper}")
            shipper_info["item_table_rule_name"] = updated_parser_choice

            st.write("---")
            st.subheader("📁 1. टेम्पलेट फ़ाइल अपलोड (अलग बटन)")
            
            has_file = "Full Job Excel Format File" in shipper_info.get("uploaded_files", {}) and len(shipper_info["uploaded_files"]["Full Job Excel Format File"]) > 0
            
            if has_file:
                st.success("✅ Blank Full Job Excel Format File अपलोडेड एवं सुरक्षित है.")
                col_del, col_rep = st.columns([2, 8])
                with col_del:
                    if st.button("🗑️ Delete Template", key=f"del_tpl_{selected_shipper}"):
                        shipper_info["uploaded_files"]["Full Job Excel Format File"] = b""
                        push_template_file_to_sheet(selected_shipper, b"")
                        st.rerun()
                with col_rep:
                    if "show_uploader" not in st.session_state:
                        st.session_state["show_uploader"] = False
                    if not st.session_state["show_uploader"]:
                        if st.button("🔄 Replace Template", key=f"btn_rep_toggle_{selected_shipper}"):
                            st.session_state["show_uploader"] = True
                            st.rerun()
            
            if not has_file or st.session_state.get("show_uploader", False):
                if has_file:
                    st.info("ℹ️ नई फाइल चुनकर नीचे दिए गए बटन से पुरानी फाइल को बदलें:")
                
                f_upload = st.file_uploader("➡️ नई Blank Full Job Excel Format File (Template) चुनें", type=["xlsx", "xls"], key=f"tpl_{selected_shipper}")
                
                if f_upload is not None:
                    file_bytes = f_upload.getvalue()
                    if st.button("🚀 Upload & Overwrite Template in Google Sheet", type="primary", use_container_width=True, key=f"btn_upload_tpl_{selected_shipper}"):
                        shipper_info.setdefault("uploaded_files", {})["Full Job Excel Format File"] = file_bytes
                        with st.spinner("⏳ बड़ी टेम्पलेट फाइल टुकड़ों में गूगल शीट पर अपलोड हो रही है..."):
                            success = push_template_file_to_sheet(selected_shipper, file_bytes)
                            if success:
                                st.session_state["show_uploader"] = False
                                fetch_cached_sheet_data.clear()
                                st.success("🎉 टेम्पलेट फाइल सफलतापर्वक अपडेट हो गई!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("❌ टेम्पलेट अपलोड करने में एरर आया!")
                    
            st.write("---")
            
            st.subheader("🧪 2. Instant PDF Upload & Live Data Test Engine")
            st.caption("यहाँ टेस्ट इनवॉइस PDF अपलोड करें, फिर रूल्स के सामने ⚡ Test दबाकर पॉप-अप में लाइव डेटा देखें.")
            
            test_pdf = st.file_uploader("➡️ टेस्ट करने के लिए इनवॉइस PDF अपलोड करें", type=["pdf"], key=f"test_pdf_{selected_shipper}")
            
            pdf_lines = []
            pdf_text = ""
            if test_pdf:
                st.session_state["cached_pdf_bytes"] = test_pdf.getvalue()
                
                with pdfplumber.open(test_pdf) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            pdf_text += t + "\n"
                            pdf_lines.extend(t.split("\n"))
                st.session_state["cached_pdf_lines"] = pdf_lines
                st.session_state["cached_pdf_text"] = pdf_text
                st.success(f"📄 PDF अपलोड है ({len(pdf_lines)} पंक्तियाँ)। अब नीचे ⚡ Test बटन दबाएँ!")

                # 🔍 PDFPlumber Raw Structure Debugger (Previous Project Feature Added)
                with st.expander("🔍 PDFPlumber Raw Structure Debugger (शब्द और कोऑर्डिनेट्स देखें)"):
                    if st.button("📊 Inspect PDF Raw Words & Layout", key=f"inspect_pdf_{selected_shipper}"):
                        try:
                            with pdfplumber.open(io.BytesIO(st.session_state["cached_pdf_bytes"])) as pdf:
                                page = pdf.pages[0]
                                words = page.extract_words()
                                
                                st.write(f"कुल मिले शब्द (Total Words): {len(words)}")
                                
                                debug_data = []
                                for w in words:
                                    debug_data.append({
                                        "Text": w['text'],
                                        "X0 (Left)": round(w['x0'], 2),
                                        "Top (Height)": round(w['top'], 2),
                                        "X1 (Right)": round(w['x1'], 2)
                                    })
                                
                                st.dataframe(debug_data, use_container_width=True)
                        except Exception as e:
                            st.error(f"एरर: {str(e)}")

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
            
            pos_options = [
                "Right (आगे)", 
                "Below (नीचे)", 
                "2 Lines Below", 
                "📦 Extract Inside Box (डब्बे के अंदर का टेक्स्ट)", 
                "Table Row Item", 
                "Table Row Index"
            ]
            
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
            
            doc_source_options = ["Main Invoice", "GST Invoice (PDF/Excel)", "DEEC Declaration (PDF/Excel)"]
            
            c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11 = st.columns([1.6, 2.0, 1.2, 0.6, 1.3, 1.1, 1.3, 1.3, 1.5, 0.6, 0.9])
            with c1: st.markdown("**Field Name**")
            with c2: st.markdown("**Keyword**")
            with c3: st.markdown("**Position**")
            with c4: st.markdown("**Cell**")
            with c5: st.markdown("**Match Mode**")
            with c6: st.markdown("**Stop / Word**")
            with c7: st.markdown("**Filter**")
            with c8: st.markdown("**Source Doc**")  
            with c9: st.markdown("**Fallback**")
            with c10: st.markdown("**Del**")
            with c11: st.markdown("**⚡ Test**")
            st.write("---")
            
            curr_pdf_lines = st.session_state.get("cached_pdf_lines", [])
            curr_pdf_text = st.session_state.get("cached_pdf_text", "")

            for field in list(current_rules.keys()):
                if field.lower() in ["igst status", "igst mode"] or current_rules[field].get("cell", "").strip().upper() in ["V", "B19"]:
                    continue

                s_val = current_rules[field]
                c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11 = st.columns([1.6, 2.0, 1.2, 0.6, 1.3, 1.1, 1.3, 1.3, 1.5, 0.6, 0.9])
                
                saved_pos = s_val.get("position", "Right (आगे)")
                pos_idx = pos_options.index(saved_pos) if saved_pos in pos_options else 0
                
                saved_mode = s_val.get("match_mode", "Exact Word")
                mode_idx = mode_options.index(saved_mode) if saved_mode in mode_options else 0
                
                saved_flt = s_val.get("filter", "None")
                if saved_flt in ["Inside Parentheses ()", "Text Inside ()"]:
                    saved_flt = "Text Inside Parentheses ()"
                flt_idx = filter_options.index(saved_flt) if saved_flt in filter_options else 0
                
                saved_logic = s_val.get("logic", "Main Invoice")
                logic_idx = doc_source_options.index(saved_logic) if saved_logic in doc_source_options else 0

                with c1: edited_name = st.text_input(f"f_{field}", value=field, label_visibility="collapsed")
                with c2: ky = st.text_input(f"k_{field}", value=s_val.get("keyword", ""), label_visibility="collapsed")
                with c3: pos = st.selectbox(f"p_{field}", pos_options, index=pos_idx, label_visibility="collapsed")
                with c4: cl = st.text_input(f"c_{field}", value=s_val.get("cell", ""), label_visibility="collapsed")
                with c5: m_mode = st.selectbox(f"mm_{field}", mode_options, index=mode_idx, label_visibility="collapsed")
                with c6: stop_kw = st.text_input(f"sk_{field}", value=s_val.get("stop_kw", ""), label_visibility="collapsed")
                with c7: final_flt = st.selectbox(f"flt_{field}", filter_options, index=flt_idx, label_visibility="collapsed")
                with c8: final_logic = st.selectbox(f"logic_{field}", doc_source_options, index=logic_idx, label_visibility="collapsed") 
                with c9: fb_val = st.text_input(f"fb_{field}", value=s_val.get("fallback", ""), label_visibility="collapsed", placeholder="अगर ब्लैंक हो")
                with c10:
                    if st.button("🗑️", key=f"del_h_{field}"):
                        del st.session_state["shipper_database"][selected_shipper]["mapping_rules"][field]
                        st.rerun()
                with c11:
                    if st.button("⚡ Test", key=f"test_btn_{field}"):
                        if not curr_pdf_lines:
                            st.toast("⚠️ पहले Section 2 में PDF अपलोड करें!")
                        else:
                            pdf_bytes = st.session_state.get("cached_pdf_bytes", None)
                            res_val = extract_header_value(
                                curr_pdf_lines, curr_pdf_text, ky, pos, m_mode, 
                                stop_kw, final_flt, field_label=edited_name, pdf_bytes=pdf_bytes
                            )
                            
                            if not res_val or not res_val.strip():
                                res_val = fb_val
                            
                            rule_summary = {
                                "keyword": ky, "position": pos, "cell": cl,
                                "match_mode": m_mode, "stop_kw": stop_kw, "filter": final_flt, "logic": final_logic
                            }
                            show_field_test_dialog(edited_name, rule_summary, res_val if res_val else "❌ (Not Found)")
                
                updated_rules[edited_name] = {"keyword": ky, "position": pos, "cell": cl, "match_mode": m_mode, "stop_kw": stop_kw, "filter": final_flt, "logic": final_logic, "fallback": fb_val}
                
            shipper_info["mapping_rules"] = updated_rules

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
            
            ic1, ic2, ic3, ic4, ic5, ic6 = st.columns([2.5, 1.5, 2.5, 2.5, 2.0, 0.8])
            with ic1: st.markdown("**Item Field Name**")
            with ic2: st.markdown("**Excel Col**")
            with ic3: st.markdown("**Rule Type**")
            with ic4: st.markdown("**Rule Detail**")
            with ic5: st.markdown("**Source Doc**")     
            with ic6: st.markdown("**Del**")
            st.write("---")
            
            rule_type_options = ["PDF Row Item", "Table Row Item", "Constant Text", "Excel Cell Reference", "Smart Detection", "Header Field Mapping"]
            available_header_fields = list(current_rules.keys())
            
            for item_field in list(item_rules.keys()):
                if item_field.lower() in ["igst status", "igst mode"] or item_rules[item_field].get("col", "").strip().upper() in ["V", "B19"]:
                    continue

                ir = item_rules[item_field]
                ic1, ic2, ic3, ic4, ic5, ic6 = st.columns([2.5, 1.5, 2.5, 2.5, 2.0, 0.8])
                
                saved_type = ir.get("type", "PDF Row Item")
                type_idx = rule_type_options.index(saved_type) if saved_type in rule_type_options else 0
                
                saved_item_logic = ir.get("logic", "Main Invoice")
                item_logic_idx = doc_source_options.index(saved_item_logic) if saved_item_logic in doc_source_options else 0
                
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
                
                with ic5: e_ilogic = st.selectbox(f"ilogic_{item_field}", doc_source_options, index=item_logic_idx, label_visibility="collapsed") 
                
                with ic6:
                    if st.button("🗑️", key=f"idel_{item_field}"):
                        del item_rules[item_field]
                        st.rerun()
                        
                updated_item_rules[e_ifield] = {
                    "col": e_icol, 
                    "type": e_itype, 
                    "rule": e_irule,
                    "logic": e_ilogic
                }
                
            shipper_info["item_table_rules"] = updated_item_rules
            st.write("---")
            
            if st.button("💾 Save Rules Only to Google Sheet", type="primary", use_container_width=True, key="btn_save_rules_sheet"):
                shippers_payload = {}
                for s_name, s_data in st.session_state["shipper_database"].items():
                    shippers_payload[s_name] = {
                        "mapping_rules": s_data.get("mapping_rules", {}),
                        "item_table_rules": s_data.get("item_table_rules", {}),
                        "item_table_rule_name": s_data.get("item_table_rule_name", "parser_welspun"),
                        "igst_config": s_data.get("igst_config", {})
                    }
                
                with st.spinner("⏳ गूगल शीट में केवल रूल्स सेव हो रहे हैं..."):
                    success = push_rules_to_sheet(shippers_payload)
                    if success:
                        fetch_cached_sheet_data.clear()
                        st.session_state["sheet_data_loaded"] = False
                        st.success("🎉 सफलता! आपके सारे रूल्स 'Shipper_JSON_Database' में सुरक्षित सेव हो गए हैं!")
                        st.balloons()
                    else:
                        st.error("❌ रूल्स सेव करते समय एरर आया!")

            render_universal_test_suite(selected_shipper)
