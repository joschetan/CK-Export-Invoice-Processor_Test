import re
import streamlit as st
import pdfplumber
from io import BytesIO
from pdf_engine import apply_value_replacement, extract_header_value

def extract_vapi_welspun_items(pdf_lines, pdf_text=""):
    """
    Vapi Welspun Dedicated Item Table Parser Logic with Live Index Debugging:
    यह PDF की टेबल से कॉलम्स को इंडेक्स के रूप में कैप्चर करेगा और टर्मिनल पर प्रिंट भी करेगा।
    """
    parsed_items = []
    
    cached_bytes = st.session_state.get("cached_pdf_bytes", None)
    if cached_bytes:
        try:
            with pdfplumber.open(BytesIO(cached_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for row_idx, row in enumerate(table):
                            if row and len(row) >= 5:
                                # 🔍 डिबगिंग के लिए कंसोल पर हर रो और उसका इंडेक्स प्रिंट करना
                                print(f"--- ROW {row_idx} (Total Cols: {len(row)}) ---")
                                for col_i, val in enumerate(row):
                                    print(f"  Index [{col_i}] = {repr(val)}")

                                # चेक करें कि क्या यह वैलिड आइटम रो है (दूसरा कॉलम 8-digit HSN हो)
                                col2_text = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                                if re.search(r'^\d{8}$', col2_text):
                                    item_dict = {f"col_{i}": (str(row[i]).strip() if i < len(row) and row[i] else "") for i in range(len(row))}
                                    parsed_items.append(item_dict)
        except Exception as e:
            st.error(f"Table Extraction Error: {str(e)}")

    # यदि नेटिव टेबल से न मिले तो खाली डिक्शनरी ताकि ऐप क्रैश न हो
    if not parsed_items:
        parsed_items.append({f"col_{i}": "" for i in range(20)})

    return parsed_items


def map_vapi_welspun_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule=""):
    """
    Dynamic Excel mapping function:
    1. अगर यूजर UI में नंबर (0, 1, 2...) डालेगा -> Left to Right (A to Z) काउंट होगा।
    2. अगर यूजर UI में लेटर (A, B, C... या a, b, c) डालेगा -> Right to Left (Z to A) उल्टा काउंट होगा।
    """
    curr_row = start_excel_row
    overall_sr = start_overall_sr
    
    pdf_text_upper = str(pdf_text).upper()
    pdf_lines = str(pdf_text).split("\n")
    
    l_keywords = [k.strip().upper() for k in str(lut_kws).split(",") if k.strip()]
    p_keywords = [k.strip().upper() for k in str(paid_kws).split(",") if k.strip()]
    
    matched_lut = any(kw.replace("NO.", "").replace(".", "").strip() in pdf_text_upper for kw in l_keywords if kw.strip())
    matched_paid = any(kw.replace(".", "").strip() in pdf_text_upper for kw in p_keywords if kw.strip())

    v_column_value = "LUT" if matched_lut else ("P" if matched_paid else "LUT")

    max_rows = len(parsed_items)

    for item_idx in range(max_rows):
        item_sr_no = item_idx + 1
        item = parsed_items[item_idx] if item_idx < len(parsed_items) else {}
        
        ws[f"G{curr_row}"] = inv_sr_no                    
        ws[f"H{curr_row}"] = item_sr_no                                      
        ws[f"V{curr_row}"] = v_column_value               
        
        ws[f"I{curr_row}"] = default_invoice_no
        if default_invoice_date and not "ROSC" in str(default_invoice_date):
            ws[f"J{curr_row}"] = default_invoice_date

        # 1. Consignee / Box / Header fields mapping
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip()
            
            if not col_letter or col_letter in ["V", "BR", "BS", "S", "J"]:
                continue
                
            if "extract" in rule_type_raw.lower() or "box" in rule_type_raw.lower() or "header" in rule_type_raw.lower() or col_letter in ["BW", "BY"]:
                cached_bytes = st.session_state.get("cached_pdf_bytes", None)
                extracted_val = extract_header_value(pdf_lines, pdf_text, rule_val, "📦 Extract Inside Box (डब्बे के अंदर का टेक्स्ट)", "Exact Word", "", "None", field_label=field_name, pdf_bytes=cached_bytes)
                if not extracted_val or not extracted_val.strip():
                    extracted_val = extract_header_value(pdf_lines, pdf_text, rule_val, "Right (आगे)", "Exact Word", "", "None", field_label=field_name)
                
                if extracted_val and "\n" in str(extracted_val):
                    lines = [l.strip() for l in str(extracted_val).split("\n") if l.strip()]
                    ws[f"{col_letter}{curr_row}"] = lines[item_idx] if item_idx < len(lines) else ""
                else:
                    ws[f"{col_letter}{curr_row}"] = extracted_val if item_idx == 0 else ""

        # 2. 100% डायनेमिक UI-Driven Item Table Mapping (Dual Mode: A to Z & Z to A)
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip()
            
            if not col_letter or col_letter in ["V", "I", "J", "G", "BR", "BS"]:
                continue
            
            if "extract" in rule_type_raw.lower() or "box" in rule_type_raw.lower() or "header" in rule_type_raw.lower():
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            raw_val = ""
            
            rule_val_lower = rule_val.lower()
            clean_rule_val = rule_val_lower.replace("col_", "").strip()
            
            # 🚀 MODE 1: नंबर दिया गया है (0, 1, 2...) -> Left to Right (A to Z काउंट)
            if clean_rule_val.isdigit():
                col_idx = int(clean_rule_val)
                col_key = f"col_{col_idx}"
                raw_val = item.get(col_key, "")
                
            # 🚀 MODE 2: सिंगल अल्फाबेट दिया गया है (A, B, C... / a, b, c...) -> Right to Left (Z to A उलटा काउंट)
            elif clean_rule_val.isalpha() and len(clean_rule_val) == 1:
                # a/A -> सबसे आखिरी कॉलम, b/B -> सेकंड लास्ट कॉलम, c/C -> थर्ड लास्ट कॉलम
                char_offset = ord(clean_rule_val) - ord('a')
                
                # टेबल में कुल कॉलम्स की गिनती
                total_cols = len([k for k in item.keys() if k.startswith("col_")])
                if total_cols > 0:
                    target_idx = max(0, total_cols - 1 - char_offset)
                    raw_val = item.get(f"col_{target_idx}", "")
                else:
                    raw_val = ""
                    
            # 🚀 MODE 3: टेक्स्ट/कीवर्ड मैपिंग (जैसे hs, qty, rate आदि)
            else:
                if "hs" in rule_val_lower or "ritc" in rule_val_lower:
                    raw_val = item.get("col_1", "")
                elif "desc" in rule_val_lower:
                    raw_val = item.get("col_2", "")
                elif "weight" in rule_val_lower or "wt" in rule_val_lower:
                    raw_val = item.get("col_5", "")
                elif "qty" in rule_val_lower or "quantity" in rule_val_lower:
                    raw_val = item.get("col_6", "")
                elif "rate" in rule_val_lower:
                    raw_val = item.get("col_7", "")
                elif "amount" in rule_val_lower or "goods value" in rule_val_lower:
                    raw_val = item.get("col_8", "")
                else:
                    raw_val = ""

            if "=" in rule_val:
                raw_val = apply_value_replacement(str(raw_val), rule_val)

            try:
                if col_letter in ["S", "K", "M"]:
                    ws[cell_ref] = str(raw_val).replace("\n", " ")
                else:
                    clean_num = str(raw_val).replace(",", "").replace("\n", "").strip()
                    ws[cell_ref] = float(clean_num) if clean_num else 0.0
            except:
                ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
