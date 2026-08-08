import re
import streamlit as st
import pdfplumber
from io import BytesIO
from pdf_engine import apply_value_replacement, extract_header_value

def extract_vapi_welspun_items(pdf_lines, pdf_text=""):
    """
    Vapi Welspun Dedicated Item Table Parser Logic:
    यह PDF की टेबल से 12 कॉलम को सीधे इंडेक्स (0 से 11) के रूप में कैप्चर करता है, 
    ताकि आप UI में कॉलम नंबर डालकर डेटा को सही जगह भेज सकें।
    """
    parsed_items = []
    
    cached_bytes = st.session_state.get("cached_pdf_bytes", None)
    if cached_bytes:
        try:
            with pdfplumber.open(BytesIO(cached_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            # चेक करें कि रो में कम से कम 12 कॉलम हैं और दूसरा कॉलम 8-digit HSN कोड है
                            if row and len(row) >= 12:
                                col2_text = str(row[1]).strip() if row[1] else ""
                                if re.search(r'^\d{8}$', col2_text):
                                    # सीधे 0 से 11 तक के 12 कॉलम को इंडेक्स के रूप में सेव करना
                                    item_dict = {
                                        "col_0": str(row[0]).strip() if row[0] else "",   # DBK Sr
                                        "col_1": str(row[1]).strip() if row[1] else "",   # HS Code
                                        "col_2": str(row[2]).strip() if row[2] else "",   # Description
                                        "col_3": str(row[3]).strip() if row[3] else "",   # Size (CM)
                                        "col_4": str(row[4]).strip() if row[4] else "",   # SQMTR
                                        "col_5": str(row[5]).strip() if row[5] else "",   # Nt.Wt (KGS)
                                        "col_6": str(row[6]).strip() if row[6] else "",   # Quantity PC
                                        "col_7": str(row[7]).strip() if row[7] else "",   # Rate in USDN
                                        "col_8": str(row[8]).strip() if row[8] else "",   # Amount USDN
                                        "col_9": str(row[9]).strip() if row[9] else "",   # Amount in INR
                                        "col_10": str(row[10]).strip() if row[10] else "", # IGST %
                                        "col_11": str(row[11]).strip() if row[11] else ""  # IGST Amount
                                    }
                                    parsed_items.append(item_dict)
        except Exception as e:
            st.error(f"Table Extraction Error: {str(e)}")

    # यदि नेटिव टेबल से न मिले तो खाली डिक्शनरी ताकि ऐप क्रैश न हो
    if not parsed_items:
        parsed_items.append({f"col_{i}": "" for i in range(12)})

    return parsed_items


def map_vapi_welspun_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule=""):
    """
    Dynamic Excel mapping function: 
    यह पूरी तरह UI के भरोसे है। UI में यूजर जो कॉलम नंबर (0 से 11) रूल में डालेगा, 
    डेटा बिना किसी हार्ड-कोडिंग के सीधे उस एक्सेल कॉलम में चला जाएगा।
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

        # 2. 100% डायनेमिक UI-Driven Item Table Mapping
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip().lower()
            
            if not col_letter or col_letter in ["V", "I", "J", "G", "BR", "BS"]:
                continue
            
            if "extract" in rule_type_raw.lower() or "box" in rule_type_raw.lower() or "header" in rule_type_raw.lower():
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            raw_val = ""
            
            # 🚀 यहाँ यूजर UI में जो रूल वैल्यू (जैसे 0, 1, 2... या col_0, col_1) डालेगा, 
            # पार्सर बिल्कुल उसी के हिसाब से डेटा उठा कर एक्सेल कॉलम में भर देगा।
            clean_rule_val = rule_val.replace("col_", "").strip()
            if clean_rule_val.isdigit():
                col_key = f"col_{clean_rule_val}"
                raw_val = item.get(col_key, "")
            else:
                # यदि यूजर ने टेक्स्ट लिखा हो (जैसे hs, qty, rate आदि) तो उससे मैच करना
                if "hs" in rule_val or "ritc" in rule_val:
                    raw_val = item.get("col_1", "")
                elif "desc" in rule_val:
                    raw_val = item.get("col_2", "")
                elif "weight" in rule_val or "wt" in rule_val:
                    raw_val = item.get("col_5", "")
                elif "qty" in rule_val or "quantity" in rule_val:
                    raw_val = item.get("col_6", "")
                elif "rate" in rule_val:
                    raw_val = item.get("col_7", "")
                elif "amount" in rule_val or "goods value" in rule_val:
                    raw_val = item.get("col_8", "")
                else:
                    raw_val = item.get("col_0", "")

            if "=" in rule_val:
                raw_val = apply_value_replacement(str(raw_val), rule_val)

            try:
                # यदि टेक्स्ट कॉलम हो (जैसे Description या HS Code) तो स्ट्रिंग रखें, वरना नंबर बनाएं
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
