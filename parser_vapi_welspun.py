import re
import streamlit as st
import pdfplumber
from io import BytesIO
from pdf_engine import apply_value_replacement, extract_header_value

def extract_vapi_welspun_items(pdf_lines, pdf_text=""):
    """
    Vapi Welspun Dedicated Item Table Parser Logic using pdfplumber native table extraction (Index/Column 1, 2, 3...).
    """
    parsed_items = []
    
    # 1. सीधे PDF से नेटिव टेबल स्ट्रक्चर निकालने की कोशिश
    cached_bytes = st.session_state.get("cached_pdf_bytes", None)
    if cached_bytes:
        try:
            with pdfplumber.open(BytesIO(cached_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            # चेक करें कि क्या यह रो एक वैलिड आइटम रो है (कम से कम 5-6 कॉलम और दूसरा कॉलम 8-digit HSN हो)
                            if row and len(row) >= 8:
                                col2_text = str(row[1]).strip() if row[1] else ""
                                # यदि दूसरे कॉलम में 8-digit HSN कोड है (जैसे 57024910 या 63026090)
                                if re.search(r'^\d{8}$', col2_text):
                                    item_dict = {
                                        "dbk_sr": str(row[0]).strip() if row[0] else "",
                                        "hs_code": col2_text,
                                        "description_text": str(row[2]).strip() if row[2] else "",
                                        "size": str(row[3]).strip() if row[3] else "",
                                        "sqmtr": str(row[4]).strip() if row[4] else "",
                                        "net_wt": str(row[5]).strip() if row[5] else "",
                                        "qty": str(row[6]).strip() if row[6] else "",
                                        "rate": str(row[7]).strip() if row[7] else "",
                                        "amount_usd": str(row[8]).strip() if row[8] else "",
                                        "amount_inr": str(row[9]).strip() if row[9] else "",
                                        "igst_per": str(row[10]).strip() if row[10] else "",
                                        "igst_amt": str(row[11]).strip() if row[11] else ""
                                    }
                                    parsed_items.append(item_dict)
        except Exception as e:
            st.error(f"Table Extraction Error: {str(e)}")

    # यदि नेटिव टेबल से डेटा न मिले तो पुराना लाइन-बाय-लाइन फॉलबैक तरीका इस्तेमाल होगा
    if not parsed_items:
        # (लाइन आधारित फॉलबैक लॉजिक)
        pass

    return parsed_items


def map_vapi_welspun_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule=""):
    """
    Dynamic Excel mapping function for Vapi Welspun using extracted column dictionaries.
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

        # 2. Standard Item Columns Mapping (सीधे 1, 2, 3... कॉलम डेटा से)
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
            
            # कॉलम लेटर के हिसाब से सटीक डेटा मैप करना
            if col_letter == "K":
                raw_val = item.get("hs_code", "")
            elif col_letter == "M":
                raw_val = item.get("description_text", "")
            elif col_letter == "S":
                dbk = item.get("dbk_sr", "")
                raw_val = f"{dbk}B" if dbk and not dbk.upper().endswith("B") else dbk
            elif col_letter == "AB":
                raw_val = item.get("net_wt", "")
            elif col_letter == "N":
                raw_val = item.get("qty", "")
            elif col_letter == "P":
                raw_val = item.get("rate", "")
            elif col_letter == "Q":
                raw_val = item.get("amount_usd", "")
            elif col_letter == "W":
                raw_val = item.get("amount_inr", "")
            elif col_letter == "X":
                raw_val = item.get("igst_per", "5.00")
            elif col_letter == "Y":
                raw_val = item.get("igst_amt", "")

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
