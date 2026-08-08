import re
import streamlit as st
from pdf_engine import apply_value_replacement, extract_header_value

def extract_vapi_welspun_items(pdf_lines, pdf_text=""):
    """
    Vapi Welspun Dedicated Item Table Parser Logic (Updated for flexible row & number extraction).
    """
    parsed_items = []
    
    extracted_commodities = []
    if pdf_text:
        comm_matches = re.findall(r'\((\d+)\)(.*?)(?=\(\d+\)|Freight Terms|$)', pdf_text, re.DOTALL)
        if comm_matches:
            seen_srs = set()
            for c_no, c_desc in comm_matches:
                sr_clean = c_no.strip()
                if sr_clean not in seen_srs:
                    seen_srs.add(sr_clean)
                    clean_desc = re.sub(r'\s+', ' ', c_desc).strip()
                    extracted_commodities.append({
                        "sr": sr_clean,
                        "desc": clean_desc
                    })

    for line in pdf_lines:
        line_str = line.strip()
        
        # 🚀 फ्लेक्सिबल रो डिटेक्शन: ऐसी लाइन जिसमें नंबर्स और डेसिमल वैल्यूज़ मौजूद हों (आइटम रो)
        # यह चेक करता है कि लाइन में कम से कम कुछ डिजिट्स और एक HSN कोड या कोड हो
        if re.search(r'\b\d{6,8}\b', line_str) or re.search(r'[\d,]+\.\d{2}', line_str):
            # यदि यह हेडर या टोटल वाली लाइन है तो इसे छोड़ दें
            if "SUM TOTAL" in line_str.upper() or "GROSS WEIGHT" in line_str.upper() or "TOTAL FOB" in line_str.upper():
                continue
                
            parts = [p.strip() for p in line_str.split() if p.strip()]
            if len(parts) >= 2:
                item_dict = {
                    "raw_parts": parts,
                    "hs_code": ""
                }
                
                # HS Code ढूँढना (आम तौर पर 8-digit कोड)
                hs_match = re.search(r'\b\d{8}\b', line_str)
                if hs_match:
                    item_dict["hs_code"] = hs_match.group(0)
                else:
                    # यदि 8-digit न मिले तो पहला बड़ा अंक या HSN देखें
                    for p in parts:
                        if p.isdigit() and len(p) >= 6:
                            item_dict["hs_code"] = p
                            break

                # लाइन से सभी डेसिमल नंबर्स एक्सट्रेक्ट करना (Nt Wt, Qty, Rate, Amount, IGST आदि)
                nums = re.findall(r'[\d,]+\.\d{2,5}', line_str)
                # यदि डेसिमल न मिलें तो सामान्य संख्याएँ ढूँढें
                if not nums:
                    nums = re.findall(r'\b\d+\b', line_str)
                
                item_dict["nums"] = nums
                
                # DBK Sr निकालना
                dbk_match = re.search(r'\b\d{6}[A-Za-z]?\b|\b\d{10}[A-Za-z]?\b', line_str)
                found_dbk = dbk_match.group(0) if dbk_match else (parts[0] if parts else "")
                
                if found_dbk:
                    if not found_dbk.upper().endswith("B") and len(found_dbk) >= 6:
                        found_dbk = f"{found_dbk}B"
                item_dict["dbk_found"] = found_dbk

                # डिस्क्रिप्शन टेक्स्ट निकालना
                desc_text = line_str
                for n in nums:
                    desc_text = desc_text.replace(n, "")
                if found_dbk:
                    desc_text = desc_text.replace(found_dbk, "")
                if item_dict["hs_code"]:
                    desc_text = desc_text.replace(item_dict["hs_code"], "")
                
                # फालतू स्पेसेस हटाना
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                item_dict["description_text"] = desc_text if desc_text else "TEXTILE ARTICLES"

                item_idx = len(parsed_items)
                if extracted_commodities:
                    comm_target = extracted_commodities[item_idx] if item_idx < len(extracted_commodities) else extracted_commodities[-1]
                    item_dict["commodity_sr"] = comm_target["sr"]
                    item_dict["commodity_desc"] = comm_target["desc"]
                else:
                    item_dict["commodity_sr"] = ""
                    item_dict["commodity_desc"] = ""
                        
                parsed_items.append(item_dict)
                
    if not parsed_items:
        parsed_items.append({
            "hs_code": "63026090",
            "description_text": "OTHER MADEUP TEXTILES ARTICLES",
            "nums": [],
            "dbk_found": "630201B",
            "commodity_sr": "",
            "commodity_desc": ""
        })

    return parsed_items


def map_vapi_welspun_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule=""):
    """
    Dynamic Excel mapping function for Vapi Welspun.
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
        ws[f"J{curr_row}"] = default_invoice_date
        
        nums = item.get("nums", [])

        # 1. Consignee / Box / Header fields mapping
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip()
            
            if not col_letter or col_letter in ["V", "BR", "BS", "S"]:
                continue
                
            if "extract" in rule_type_raw.lower() or "box" in rule_type_raw.lower() or "header" in rule_type_raw.lower() or col_letter in ["BW", "BY"]:
                cached_bytes = st.session_state.get("cached_pdf_bytes", None)
                
                extracted_val = extract_header_value(
                    pdf_lines, pdf_text, rule_val, 
                    "📦 Extract Inside Box (डब्बे के अंदर का टेक्स्ट)", 
                    "Exact Word", "", "None", 
                    field_label=field_name, 
                    pdf_bytes=cached_bytes
                )
                
                if not extracted_val or not extracted_val.strip():
                    extracted_val = extract_header_value(pdf_lines, pdf_text, rule_val, "Right (आगे)", "Exact Word", "", "None", field_label=field_name)
                
                if extracted_val and "\n" in str(extracted_val):
                    lines = [l.strip() for l in str(extracted_val).split("\n") if l.strip()]
                    if item_idx < len(lines):
                        ws[f"{col_letter}{curr_row}"] = lines[item_idx]
                    else:
                        ws[f"{col_letter}{curr_row}"] = ""
                else:
                    if item_idx == 0:
                        ws[f"{col_letter}{curr_row}"] = extracted_val if extracted_val else ""
                    else:
                        ws[f"{col_letter}{curr_row}"] = ""

        # 2. Commodity Sr & Name mapping
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            f_lower = field_name.lower()
            rule_val_lower = str(r_info.get("rule", "")).lower()
            
            if not col_letter:
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            
            if "commodity" in f_lower or "commodity" in rule_val_lower or col_letter == "BS":
                ws[cell_ref] = item.get("commodity_desc", "")
            elif "sr" in f_lower or f_lower == "sr." or rule_val_lower in ["(1)", "sr", "serial"] or col_letter == "BR":
                ws[cell_ref] = item.get("commodity_sr", "")

        # 3. Standard Item Columns Mapping (Qty, Rate, Amount, Nt.Wt, HS Code etc.)
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip()
            
            if not col_letter or col_letter in ["V", "I", "J", "G", "BR", "BS"]:
                continue
            
            if "extract" in rule_type_raw.lower() or "box" in rule_type_raw.lower() or "header" in rule_type_raw.lower():
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            
            if "smart" in rule_type_raw.lower():
                desc = item.get("description_text", "").upper()
                if "PCS" in desc or "PC" in desc:
                    ws[cell_ref] = "PCS"
                else:
                    ws[cell_ref] = rule_val if rule_val else "SET"
            elif "pdf" in rule_type_raw.lower() or col_letter in ["K", "M", "N", "P", "Q", "S", "W", "X", "Y", "AB"]:
                r_val_lower = rule_val.lower().strip()
                f_name_lower = field_name.lower().strip()
                raw_val = ""
                
                # कॉलम और फील्ड के हिसाब से सही नंबर इंडेक्स चुनना
                if "igst %" in r_val_lower or "igst rate" in f_name_lower or col_letter == "X":
                    raw_val = nums[-2] if len(nums) >= 2 else "5.00"
                elif "igst amt" in r_val_lower or "igst amount" in f_name_lower or col_letter == "Y":
                    raw_val = nums[-1] if len(nums) >= 1 else ""
                elif "hs" in r_val_lower or "ritc" in f_name_lower or "hs code" in r_val_lower or col_letter == "K":
                    raw_val = item.get("hs_code", "63026090")
                elif "description" in r_val_lower or "description" in f_name_lower or col_letter == "M":
                    raw_val = item.get("description_text", "")
                elif "dbk" in r_val_lower or "drawback" in f_name_lower or col_letter == "S":
                    raw_val = item.get("dbk_found", "") 
                elif "weight" in r_val_lower or "net wt" in f_name_lower or col_letter == "AB":
                    raw_val = nums[0] if len(nums) > 0 else ""
                elif "qty" in r_val_lower or "quantity" in f_name_lower or col_letter == "N":
                    raw_val = nums[1] if len(nums) > 1 else (nums[0] if len(nums) > 0 else "")
                elif "rate" in r_val_lower or col_letter == "P":
                    raw_val = nums[2] if len(nums) > 2 else ""
                elif "amount" in r_val_lower or "goods value" in f_name_lower or col_letter == "Q":
                    raw_val = nums[3] if len(nums) > 3 else ""
                elif "taxable" in r_val_lower or col_letter == "W":
                    raw_val = nums[4] if len(nums) > 4 else (nums[3] if len(nums) > 3 else "")
                else:
                    # यदि कोई अन्य कॉलम हो तो सीक्वेंस के अनुसार वैल्यू उठाएं
                    idx_map = {"AB": 0, "N": 1, "P": 2, "Q": 3, "W": 4, "X": 5, "Y": 6}
                    n_idx = idx_map.get(col_letter, 0)
                    raw_val = nums[n_idx] if len(nums) > n_idx else (nums[0] if nums else "")

                if "=" in rule_val:
                    raw_val = apply_value_replacement(str(raw_val), rule_val)

                try:
                    if col_letter in ["S", "K"]:
                        ws[cell_ref] = str(raw_val)
                    else:
                        ws[cell_ref] = float(str(raw_val).replace(",", ""))
                except:
                    ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
