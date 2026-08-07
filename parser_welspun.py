import re

def extract_welspun_items(pdf_lines, pdf_text=""):
    """
    Welspun Dedicated Item Table Parser Logic (Merged with Commodity & HS Code Extraction).
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
                
                # 🚀 Ensure 'B' is appended at the end of DBK code if found
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
    Dynamic Excel mapping function for Welspun with DBK 'B' suffix enforcement.
    """
    curr_row = start_excel_row
    overall_sr = start_overall_sr
    
    pdf_text_upper = str(pdf_text).upper()
    
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

        # Commodity, Sr. & Description mapping based on UI rules
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            f_lower = field_name.lower()
            rule_val_lower = str(r_info.get("rule", "")).lower()
            
            if not col_letter or col_letter == "V":
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            
            if "commodity" in f_lower or "commodity" in rule_val_lower:
                if col_letter:
                    ws[cell_ref] = item.get("commodity_desc", "")
            elif "sr" in f_lower or f_lower == "sr." or rule_val_lower in ["(1)", "sr", "serial"]:
                if col_letter:
                    ws[cell_ref] = item.get("commodity_sr", "")
            elif "description" in f_lower or "description" in rule_val_lower:
                if col_letter:
                    ws[cell_ref] = item.get("description_text", "")

        # Standard PDF Row Item Numeric & Other columns mapping
        for field_name, r_info in item_rules.items():
            col_letter = r_info.get("col", "").strip().upper()
            rule_type_raw = str(r_info.get("type", "PDF Row Item")).strip()
            rule_val = str(r_info.get("rule", "")).strip()
            
            if not col_letter or col_letter in ["V", "I", "J", "G", "H"]:
                continue
            
            skip_cols = [r.get("col","").upper() for f, r in item_rules.items() if "commodity" in f.lower() or "sr" in f.lower() or "description" in f.lower()]
            if col_letter in skip_cols:
                continue
                
            cell_ref = f"{col_letter}{curr_row}"
            
            if "pdf" in rule_type_raw.lower():
                r_val_lower = rule_val.lower().strip()
                raw_val = ""
                
                if "hs" in r_val_lower or "hs code" in r_val_lower:
                    raw_val = item.get("hs_code", "")
                elif "dbk" in r_val_lower or col_letter == "S":
                    raw_val = item.get("dbk_found", "") # Already ends with 'B'
                elif "weight" in r_val_lower:
                    raw_val = nums[0] if len(nums) > 0 else ""
                elif "qty" in r_val_lower:
                    raw_val = nums[1] if len(nums) > 1 else ""
                elif "rate" in r_val_lower:
                    raw_val = nums[2] if len(nums) > 2 else ""
                elif "amount" in r_val_lower:
                    raw_val = nums[3] if len(nums) > 3 else ""

                try:
                    if col_letter == "S":
                        ws[cell_ref] = raw_val # DBK should remain string (e.g. 630201B)
                    else:
                        ws[cell_ref] = float(str(raw_val).replace(",", ""))
                except:
                    ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
