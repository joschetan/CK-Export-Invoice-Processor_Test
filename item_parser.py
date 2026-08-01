import re
import streamlit as st
from pdf_engine import apply_value_replacement

def extract_item_table_rows(pdf_lines):
    parsed_items = []
    
    for line in pdf_lines:
        line_str = line.strip()
        if re.match(r'^\d{8}\b', line_str):
            parts = [p.strip() for p in line_str.split() if p.strip()]
            if len(parts) >= 3:
                item_dict = {
                    "raw_parts": parts,
                    "hs_code": parts[0]
                }
                
                nums = re.findall(r'[\d,]+\.\d{2,3}', line_str)
                item_dict["nums"] = nums
                
                dbk_match = re.search(r'\b\d{6}[A-Za-z]?\b|\b\d{10}[A-Za-z]?\b', line_str)
                item_dict["dbk_found"] = dbk_match.group(0) if dbk_match else ""

                if len(nums) > 0:
                    first_num = nums[0]
                    start_pos = len(parts[0])
                    end_pos = line_str.find(first_num)
                    if end_pos > start_pos:
                        desc_text = line_str[start_pos:end_pos].strip()
                        if item_dict["dbk_found"]:
                            desc_text = desc_text.replace(item_dict["dbk_found"], "").strip()
                        item_dict["description_text"] = desc_text
                else:
                    item_dict["description_text"] = " ".join(parts[1:]) if len(parts) > 1 else ""
                        
                parsed_items.append(item_dict)
                
    return parsed_items

@st.dialog("⚠️ Urgent: Manual IGST Status Required")
def get_manual_igst_choice(invoice_identifier):
    st.warning(f"⚠️ इन्वॉइस **`{invoice_identifier}`** में स्पष्ट रूप से LUT या Paid (P) का टेक्स्ट नहीं मिला!")
    st.write("कस्टम्स पेनाल्टी से बचने के लिए कृपया सही विकल्प चुनें:")
    
    selected_choice = st.selectbox("Column V के लिए सही स्टेटस चुनें:", ["LUT", "P"], index=0)
    
    if st.button("Confirm & Apply", type="primary"):
        st.session_state[f"resolved_igst_{invoice_identifier}"] = selected_choice
        st.rerun()

def map_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws=""):
    curr_row = start_excel_row
    overall_sr = start_overall_sr
    
    pdf_text_upper = str(pdf_text).upper()
    
    l_keywords = [k.strip().upper() for k in str(lut_kws).split(",") if k.strip()]
    p_keywords = [k.strip().upper() for k in str(paid_kws).split(",") if k.strip()]
    
    matched_lut = False
    for kw in l_keywords:
        clean_kw = kw.replace("NO.", "").replace(".", "").strip()
        if clean_kw and clean_kw in pdf_text_upper:
            matched_lut = True
            break
            
    matched_paid = False
    for kw in p_keywords:
        clean_kw = kw.replace(".", "").strip()
        if clean_kw and clean_kw in pdf_text_upper:
            matched_paid = True
            break

    v_column_value = ""
    
    if matched_lut:
        v_column_value = "LUT"
    elif matched_paid:
        v_column_value = "P"
    else:
        inv_key = default_invoice_no if default_invoice_no else f"INV_{inv_sr_no}"
        session_key = f"resolved_igst_{inv_key}"
        
        if session_key in st.session_state:
            v_column_value = st.session_state[session_key]
        else:
            get_manual_igst_choice(inv_key)
            st.stop()

    has_commodity_ui_rule = any(str(r_info.get("col", "")).strip().upper() in ["BR", "BS"] for r_info in item_rules.values())

    extracted_commodities = []
    if has_commodity_ui_rule and pdf_text:
        # 🎯 सुधरा हुआ लॉजिक: अब यह ब्रैकेट के अंदर की वैल्यू (जैसे 1, 2, 3) पकड़ेगा और अगले सीरियल या अंत तक का पूरा टेक्स्ट बिना काटे उठाएगा
        comm_matches = re.findall(r'\((\d+)\)(.*?)(?=\(\d+\)|Freight Terms|$)', pdf_text, re.DOTALL)
        if comm_matches:
            seen_srs = set()
            for c_no, c_desc in comm_matches:
                sr_clean = c_no.strip()
                if sr_clean not in seen_srs:
                    seen_srs.add(sr_clean)
                    # सभी एक्स्ट्रा स्पेसेस और लाइन ब्रेक्स को सिंगल स्पेस में बदलकर पूरा टेक्स्ट साफ़ करना
                    clean_desc = re.sub(r'\s+', ' ', c_desc).strip()
                    extracted_commodities.append({
                        "sr": sr_clean,
                        "desc": clean_desc
                    })

    max_rows = len(parsed_items)

    for item_idx in range(max_rows):
        item_sr_no = item_idx + 1
        item = parsed_items[item_idx] if item_idx < len(parsed_items) else {}
        
        ws[f"G{curr_row}"] = inv_sr_no                    
        ws[f"H{curr_row}"] = item_sr_no                                      
        ws[f"V{curr_row}"] = v_column_value               
        
        nums = item.get("nums", [])
        
        if has_commodity_ui_rule and extracted_commodities and item_idx < len(extracted_commodities):
            comm_data = extracted_commodities[item_idx]
            ws[f"BR{curr_row}"] = comm_data["sr"]
            ws[f"BS{curr_row}"] = comm_data["desc"]

        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip()
            
            if not col_letter or col_letter in ["V", "BR", "BS"]:
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            
            if rule_type_raw.lower() == "constant text":
                ws[cell_ref] = apply_value_replacement(rule_val, rule_val)
            elif rule_type_raw.lower() == "excel cell reference":
                if rule_val and len(rule_val) >= 2 and rule_val[1].isdigit():
                    ws[cell_ref] = f"={rule_val}"
                else:
                    ws[cell_ref] = rule_val
            elif "smart" in rule_type_raw.lower():
                if ":" in rule_val:
                    smart_parts = [p.strip() for p in rule_val.split(":")]
                    if len(smart_parts) == 3:
                        search_kw = smart_parts[0].upper().replace(" ", "")
                        match_val = smart_parts[1]
                        fallback_val = smart_parts[2]
                        
                        clean_pdf_upper = re.sub(r'\s+', '', str(pdf_text).upper())
                        
                        if search_kw in clean_pdf_upper:
                            ws[cell_ref] = match_val
                        else:
                            ws[cell_ref] = fallback_val
                    else:
                        ws[cell_ref] = rule_val
                else:
                    desc = item.get("description_text", "").upper()
                    if "PCS" in desc or "PC" in desc:
                        ws[cell_ref] = "PCS"
                    else:
                        ws[cell_ref] = rule_val if rule_val else "SET"
            elif "pdf" in rule_type_raw.lower():
                r_val_lower = rule_val.lower().strip()
                f_name_lower = field_name.lower().strip()
                
                raw_val = ""
                
                if "igst %" in r_val_lower or "igst rate" in f_name_lower or ("igst" in f_name_lower and "%" in f_name_lower) or ("igst" in f_name_lower and "rate" in f_name_lower):
                    raw_val = nums[5] if len(nums) > 5 else ""
                elif "igst amt" in r_val_lower or "igst amount" in f_name_lower or ("igst" in f_name_lower and "amt" in f_name_lower):
                    raw_val = nums[6] if len(nums) > 6 else ""
                elif "hs" in r_val_lower or "ritc" in f_name_lower or "hs code" in r_val_lower:
                    raw_val = item.get("hs_code", "")
                elif "description" in r_val_lower or "description" in f_name_lower:
                    raw_val = item.get("description_text", "")
                elif "dbk" in r_val_lower or "drawback" in f_name_lower or col_letter == "S":
                    raw_val = item.get("dbk_found", "")
                    if raw_val and not str(raw_val).upper().endswith("B"):
                        raw_val = f"{raw_val}B"
                elif "weight" in r_val_lower or "net wt" in f_name_lower:
                    raw_val = nums[0] if len(nums) > 0 else ""
                elif "qty" in r_val_lower or "quantity" in f_name_lower:
                    raw_val = nums[1] if len(nums) > 1 else ""
                elif "rate" in r_val_lower or "rate" in f_name_lower:
                    raw_val = nums[2] if len(nums) > 2 else ""
                elif "amount usd" in r_val_lower or "goods value" in f_name_lower or "amount" in r_val_lower:
                    raw_val = nums[3] if len(nums) > 3 else ""
                elif "taxable" in r_val_lower or "taxable" in f_name_lower:
                    raw_val = nums[4] if len(nums) > 4 else ""
                
                if "=" in rule_val:
                    raw_val = apply_value_replacement(raw_val, rule_val)

                try:
                    ws[cell_ref] = float(str(raw_val).replace(",", ""))
                except:
                    ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
