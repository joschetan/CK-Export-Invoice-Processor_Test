import re
import streamlit as st
from pdf_engine import apply_value_replacement, extract_header_value

def extract_welspun_items(pdf_lines, pdf_text=""):
    """
    Welspun Dedicated Item Table Parser Logic (Merged with Commodity, HS Code & DBK 'B' Suffix).
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
                found_dbk = dbk_match.group(0) if dbk_match else ""
                
                if found_dbk:
                    if not found_dbk.upper().endswith("B"):
                        found_dbk = f"{found_dbk}B"
                item_dict["dbk_found"] = found_dbk

                if len(nums) > 0:
                    first_num = nums[0]
                    start_pos = len(parts[0])
                    end_pos = line_str.find(first_num)
                    if end_pos > start_pos:
                        desc_text = line_str[start_pos:end_pos].strip()
                        if dbk_match and dbk_match.group(0) in desc_text:
                            desc_text = desc_text.replace(dbk_match.group(0), "").strip()
                        item_dict["description_text"] = desc_text
                else:
                    item_dict["description_text"] = " ".join(parts[1:]) if len(parts) > 1 else ""
                
                item_idx = len(parsed_items)
                if extracted_commodities:
                    comm_target = extracted_commodities[item_idx] if item_idx < len(extracted_commodities) else extracted_commodities[-1]
                    item_dict["commodity_sr"] = comm_target["sr"]
                    item_dict["commodity_desc"] = comm_target["desc"]
                else:
                    item_dict["commodity_sr"] = ""
                    item_dict["commodity_desc"] = ""
                        
                parsed_items.append(item_dict)
                
    return parsed_items


def map_items_to_excel_dynamic(ws, parsed_items, item_rules, inv_sr_no=1, start_overall_sr=1, start_excel_row=2, default_invoice_no="", default_invoice_date="", pdf_text="", lut_kws="", paid_kws="", parser_rule=""):
    """
    Dynamic Excel mapping function for Welspun with multi-line Consignee/Buyer address split handling.
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

        # 🚀 1. Handle Consignee / Buyer Box / Extract fields (BW, BY etc. multi-line mapping)[cite: 16]
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

        # 🚀 2. Commodity Sr (BR) & Name of Commodity (BS) mapping[cite: 16]
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

        # 🚀 3. Standard PDF Row Item Numeric & Other columns mapping (Including Column S for DBK)[cite: 16]
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
            elif "pdf" in rule_type_raw.lower() or col_letter == "S":
                r_val_lower = rule_val.lower().strip()
                f_name_lower = field_name.lower().strip()
                raw_val = ""
                
                if "igst %" in r_val_lower or "igst rate" in f_name_lower:
                    raw_val = nums[5] if len(nums) > 5 else ""
                elif "igst amt" in r_val_lower or "igst amount" in f_name_lower:
                    raw_val = nums[6] if len(nums) > 6 else ""
                elif "hs" in r_val_lower or "ritc" in f_name_lower or "hs code" in r_val_lower:
                    raw_val = item.get("hs_code", "")
                elif "description" in r_val_lower or "description" in f_name_lower:
                    raw_val = item.get("description_text", "")
                elif "dbk" in r_val_lower or "drawback" in f_name_lower or col_letter == "S":
                    raw_val = item.get("dbk_found", "") 
                elif "weight" in r_val_lower or "net wt" in f_name_lower:
                    raw_val = nums[0] if len(nums) > 0 else ""
                elif "qty" in r_val_lower or "quantity" in f_name_lower:
                    raw_val = nums[1] if len(nums) > 1 else ""
                elif "rate" in r_val_lower:
                    raw_val = nums[2] if len(nums) > 2 else ""
                elif "amount usd" in r_val_lower or "goods value" in f_name_lower or "amount" in r_val_lower:
                    raw_val = nums[3] if len(nums) > 3 else ""
                elif "taxable" in r_val_lower:
                    raw_val = nums[4] if len(nums) > 4 else ""

                if "=" in rule_val:
                    raw_val = apply_value_replacement(raw_val, rule_val)

                try:
                    if col_letter == "S":
                        ws[cell_ref] = raw_val 
                    else:
                        ws[cell_ref] = float(str(raw_val).replace(",", ""))
                except:
                    ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
