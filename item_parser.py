import re
import streamlit as st
from pdf_engine import apply_value_replacement
from parser_welspun import extract_welspun_items
from parser_bkt import extract_bkt_items

def extract_item_table_rows(pdf_lines, parser_rule="Rule_Welspun"):
    rule_name = str(parser_rule).strip().lower()
    
    # 🟢 1. यदि शिपर के नाम में 'balkrishna' है, तो Balkrishna Industries Limited (BKT) का पार्सर चलेगा
    if "balkrishna" in rule_name:
        return extract_bkt_items(pdf_lines)
    
    # 🟢 2. बाकी सभी (जैसे Welspun या कोई नया शिपर) डिफ़ॉल्ट रूप से Welspun वाले वर्किंग पार्सर पर चलेंगे
    else:
        return extract_welspun_items(pdf_lines)

@st.dialog("⚠️ Urgent: Manual IGST Status Required")
def get_manual_igst_choice(invoice_identifier):
    st.warning(f"⚠️ इन्वॉइस **`{invoice_identifier}`** में स्पष्ट रूप से LUT या Paid (P) का टेक्स्ट नहीं मिला!")
    st.write("कस्टम्स पेनाल्टी से बचने के लिए कृपया सही विकल्प चुनें:")
    
    selected_choice = st.selectbox("Column V के लिए सही स्टेटस चुनें:", ["LUT", "P"], index=0)
    
    if st.button("Confirm & Apply", type="primary"):
        st.session_state[f"resolved_igst_{invoice_identifier}"] = selected_choice
        st.rerun()

def map_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule="Rule_Welspun"):
    curr_row = start_excel_row
    overall_sr = start_overall_sr
    
    pdf_text_upper = str(pdf_text).upper()
    rule_name_lower = str(parser_rule).strip().lower()
    
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

    max_rows = len(parsed_items)

    for item_idx in range(max_rows):
        item_sr_no = item_idx + 1
        item = parsed_items[item_idx] if item_idx < len(parsed_items) else {}
        
        ws[f"G{curr_row}"] = inv_sr_no                    
        ws[f"H{curr_row}"] = item_sr_no                                      
        ws[f"V{curr_row}"] = v_column_value               
        
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip().lower()
            
            if not col_letter or col_letter == "V":
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            raw_val = ""
            
            if rule_type_raw.lower() == "constant text":
                raw_val = apply_value_replacement(rule_val, rule_val)
            elif rule_type_raw.lower() == "excel cell reference":
                if rule_val and len(rule_val) >= 2 and rule_val[1].isdigit():
                    ws[cell_ref] = f"={rule_val}"
                    continue
                else:
                    raw_val = rule_val
            else:
                # 🟢 1. BALKRISHNA INDUSTRIES LIMITED के लिए स्पेसिफिक कीज़
                if "balkrishna" in rule_name_lower:
                    if "quantity" in rule_val or "qty" in rule_val:
                        raw_val = item.get("quantity", "")
                    elif "taxable" in rule_val or "value" in rule_val:
                        raw_val = item.get("taxable_value", item.get("value", ""))
                    elif "igst amt" in rule_val or "igst rs" in rule_val:
                        raw_val = item.get("igst_amt", "")
                    elif "gross" in rule_val:
                        raw_val = item.get("gross_wt", "")
                    elif "net" in rule_val:
                        raw_val = item.get("net_wt", "")
                    elif "hs" in rule_val or "ritc" in rule_val:
                        raw_val = item.get("hs_code", "")
                    elif "license_no" in rule_val:
                        raw_val = item.get("license_no", "")
                    elif "license_date" in rule_val:
                        raw_val = item.get("license_date", "")
                    else:
                        raw_val = item.get("hs_code", "")
                
                # 🟢 2. WELSPUN और अन्य सभी के लिए पुराना मक्खन जैसा वर्किंग लॉजिक
                else:
                    nums_list = item.get("nums", [])
                    if "hs" in rule_val or "ritc" in rule_val:
                        raw_val = item.get("hs_code", "")
                    elif "qty" in rule_val or "quantity" in rule_val:
                        raw_val = nums_list[0] if len(nums_list) > 0 else ""
                    elif "rate" in rule_val:
                        raw_val = nums_list[1] if len(nums_list) > 1 else ""
                    elif "value" in rule_val:
                        raw_val = nums_list[2] if len(nums_list) > 2 else (nums_list[0] if nums_list else "")
                    elif "desc" in rule_val:
                        raw_val = item.get("description_text", "")
                    elif "dbk" in rule_val:
                        raw_val = item.get("dbk_found", "")
                    else:
                        raw_val = item.get("hs_code", "")

            try:
                if str(raw_val).strip() and not str(raw_val).startswith("'"):
                    if "." in str(raw_val):
                        ws[cell_ref] = float(str(raw_val).replace(",", ""))
                    else:
                        ws[cell_ref] = int(str(raw_val).replace(",", ""))
                else:
                    ws[cell_ref] = raw_val
            except:
                ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
