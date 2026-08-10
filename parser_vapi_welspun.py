import re
import streamlit as st
import pdfplumber
from io import BytesIO
from pdf_engine import apply_value_replacement, extract_header_value

def extract_vapi_welspun_items(pdf_lines, pdf_text=""):
    """
    Vapi Welspun Pattern-Based Auto-Detection Parser Logic:
    यह कॉलम इंडेक्स की झंझट खत्म करके सीधे डेटा के पक्के पैटर्न (8-digit HSN, 3-decimal Weight, 5-decimal Rate) से वैल्यू उठाता है।
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
                            if row and len(row) >= 5:
                                # रो के सभी नॉन-एम्प्टी सेल्स की एक साफ़ लिस्ट बनाना
                                clean_cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != ""]
                                
                                if not clean_cells:
                                    continue
                                    
                                # 1. HS Code ढूंढना: 8 अंकों का शुद्ध नंबर (बिना डेसिमल या कॉमा के)
                                hs_code = ""
                                hs_index = -1
                                for idx, cell in enumerate(clean_cells):
                                    if re.fullmatch(r'\d{8}', cell.replace(",", "")):
                                        hs_code = cell
                                        hs_index = idx
                                        break
                                        
                                if not hs_code:
                                    continue # अगर 8-digit HSN नहीं मिला तो यह आइटम रो नहीं है
                                    
                                # DBK Sr (आम तौर पर HS Code से ठीक पहले वाला सेल होता है)
                                dbk_sr = clean_cells[hs_index - 1] if hs_index > 0 else ""
                                
                                # Description (DBK Sr और HS Code के बीच या उनके आस-पास का टेक्स्ट)
                                desc_parts = []
                                for idx in range(0, hs_index):
                                    if idx != (hs_index - 1) or not dbk_sr.isdigit():
                                        desc_parts.append(clean_cells[idx])
                                description_text = " ".join(desc_parts) if desc_parts else "COTTON TEXTILE ARTICLE"

                                # बाकी बचे सेल्स से पैटर्न्स ढूंढना
                                net_wt, qty, rate, amount_usd, taxable_inr, igst_per, igst_amt = "", "", "", "", "", "", ""
                                
                                rate_index = -1
                                for idx, cell in enumerate(clean_cells):
                                    clean_c = cell.replace(",", "")
                                    
                                    # Net Weight: डेसिमल के बाद ठीक 3 अंक (जैसे 700.876)
                                    if re.fullmatch(r'\d+\.\d{3}', clean_c):
                                        if not net_wt:
                                            net_wt = cell
                                            
                                    # Rate: डेसिमल के बाद हमेशा 5 अंक (जैसे 2.41000)
                                    elif re.fullmatch(r'\d+\.\d{5}', clean_c):
                                        rate = cell
                                        rate_index = idx
                                        
                                    # Quantity: जो बड़ा पूर्णांक या संख्या हो (जिसमें डेसिमल न हो या मात्रा हो)
                                    elif clean_c.isdigit() and int(clean_c) > 99 and cell != hs_code:
                                        if not qty:
                                            qty = cell

                                # आपके नियम के अनुसार: Rate के बाद के कॉलम सीक्वेंस से उठाना
                                if rate_index != -1:
                                    # Rate के बाद वाला अगला सेल Amount USD हो सकता है
                                    if rate_index + 1 < len(clean_cells):
                                        amount_usd = clean_cells[rate_index + 1]
                                    # 2nd column after Rate = Amount in INR (Taxable Value)
                                    if rate_index + 2 < len(clean_cells):
                                        taxable_inr = clean_cells[rate_index + 2]
                                    # 3rd column after Rate = IGST%
                                    if rate_index + 3 < len(clean_cells):
                                        igst_per = clean_cells[rate_index + 3]
                                    # 4th column after Rate = IGST Amount
                                    if rate_index + 4 < len(clean_cells):
                                        igst_amt = clean_cells[rate_index + 4]

                                item_dict = {
                                    "dbk_sr": dbk_sr,
                                    "hs_code": hs_code,
                                    "description_text": description_text,
                                    "net_wt": net_wt,
                                    "qty": qty,
                                    "rate": rate,
                                    "amount_usd": amount_usd,
                                    "amount_inr": taxable_inr,
                                    "igst_per": igst_per if igst_per else "5.00",
                                    "igst_amt": igst_amt
                                }
                                parsed_items.append(item_dict)
        except Exception as e:
            st.error(f"Pattern Parser Error: {str(e)}")

    if not parsed_items:
        parsed_items.append({"dbk_sr": "", "hs_code": "", "description_text": "", "net_wt": "", "qty": "", "rate": "", "amount_usd": "", "amount_inr": "", "igst_per": "5.00", "igst_amt": ""})

    return parsed_items


def map_vapi_welspun_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule=""):
    """
    Dynamic Excel mapping function using Pattern-Detected item dictionary keys.
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

        # 1. Header fields mapping
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

        # 2. Pattern-Driven Item Table Mapping (UI rule ke anusaar key mapping)
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
            
            # UI में यूजर जो भी लिखेगा, उसे डिटेक्टेड पैटर्न कीज़ से मैच करना
            if "hs" in rule_val or "ritc" in rule_val or col_letter == "K":
                raw_val = item.get("hs_code", "")
            elif "desc" in rule_val or col_letter == "M":
                raw_val = item.get("description_text", "")
            elif "dbk" in rule_val or col_letter == "S":
                dbk = item.get("dbk_sr", "")
                raw_val = f"{dbk}B" if dbk and not dbk.upper().endswith("B") else dbk
            elif "wt" in rule_val or "weight" in rule_val or col_letter == "AB":
                raw_val = item.get("net_wt", "")
            elif "qty" in rule_val or "quantity" in rule_val or col_letter == "N":
                raw_val = item.get("qty", "")
            elif "rate" in rule_val or col_letter == "P":
                raw_val = item.get("rate", "")
            elif "amount" in rule_val and "usd" in rule_val or col_letter == "Q":
                raw_val = item.get("amount_usd", "")
            elif "taxable" in rule_val or "inr" in rule_val or col_letter == "W":
                raw_val = item.get("amount_inr", "")
            elif "igst%" in rule_val or "igst per" in rule_val or col_letter == "X":
                raw_val = item.get("igst_per", "5.00")
            elif "igst amount" in rule_val or col_letter == "Y":
                raw_val = item.get("igst_amt", "")
            else:
                raw_val = item.get("qty", "")

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
