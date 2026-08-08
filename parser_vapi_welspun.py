import re
import streamlit as st
from pdf_engine import apply_value_replacement, extract_header_value

def extract_vapi_welspun_items(pdf_lines, pdf_text=""):
    """
    Vapi Welspun Dedicated Item Table Parser Logic (Strictly filtered by 8-digit HSN code).
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
        
        # 🚀 सख्त शर्त: लाइन में कम से कम एक 8-digit HSN कोड (जैसे 57024910 या 63026090) होना अनिवार्य है
        hs_match = re.search(r'\b\d{8}\b', line_str)
        
        if hs_match:
            # फुटर या टोटल लाइनों को छोड़ दें
            if "SUM TOTAL" in line_str.upper() or "GROSS WEIGHT" in line_str.upper() or "TOTAL FOB" in line_str.upper():
                continue
                
            hs_code = hs_match.group(0)
            
            # लाइन से सभी नंबर्स (डेसिमल और कॉमा वाले) निकालें
            nums = re.findall(r'[\d,]+\.\d{2,5}', line_str)
            if not nums:
                nums = re.findall(r'\b[\d,]+\b', line_str)
            
            # DBK Sr निकालना (लाइन का सबसे पहला शब्द या कोड)
            parts = [p.strip() for p in line_str.split() if p.strip()]
            dbk_found = parts[0] if parts else ""
            if dbk_found and not dbk_found.upper().endswith("B") and dbk_found.isdigit():
                dbk_found = f"{dbk_found}B"

            # डिस्क्रिप्शन टेक्स्ट निकालना (HS Code और नंबर्स को हटाकर जो बचे)
            desc_text = line_str
            for n in nums:
                desc_text = desc_text.replace(n, "")
            desc_text = desc_text.replace(hs_code, "")
            if dbk_found:
                desc_text = desc_text.replace(dbk_found, "")
            
            # फालतू शब्द या साइज हटाकर क्लीन डिस्क्रिप्शन बनाना
            desc_text = re.sub(r'\b(52\s*X\s*80|86\s*X\s*160|70\s*X\s*140|40\s*X\s*76|33\s*X\s*33|70X140)\b', '', desc_text)
            desc_text = re.sub(r'\s+', ' ', desc_text).strip()
            
            if not desc_text:
                desc_text = "COTTON TEXTILE ARTICLE"

            item_dict = {
                "hs_code": hs_code,
                "description_text": desc_text,
                "nums": nums,
                "dbk_found": dbk_found
            }

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

        # 3. Standard Item Columns Mapping (सही कॉलम इंडेक्स के साथ)
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
                ws[cell_ref] = "PCS"
            elif "pdf" in rule_type_raw.lower() or col_letter in ["K", "M", "N", "P", "Q", "S", "W", "X", "Y", "AB"]:
                r_val_lower = rule_val.lower().strip()
                f_name_lower = field_name.lower().strip()
                raw_val = ""
                
                # 🎯 सटीक नंबर पोजीशन मैपिंग (इनवॉइस के कॉलम ऑर्डर के अनुसार)
                if col_letter == "K" or "hs" in r_val_lower or "ritc" in f_name_lower:
                    raw_val = item.get("hs_code", "")
                elif col_letter == "M" or "description" in r_val_lower:
                    raw_val = item.get("description_text", "")
                elif col_letter == "S" or "dbk" in r_val_lower or "drawback" in f_name_lower:
                    raw_val = item.get("dbk_found", "")
                elif col_letter == "AB" or "weight" in r_val_lower or "nt.wt" in f_name_lower:
                    raw_val = nums[0] if len(nums) > 0 else ""      # Net Weight (जैसे 700.876)
                elif col_letter == "N" or "quantity" in r_val_lower or "qty" in r_val_lower:
                    raw_val = nums[1] if len(nums) > 1 else (nums[0] if len(nums) > 0 else "") # Qty (जैसे 1,872)
                elif col_letter == "P" or "rate" in r_val_lower:
                    raw_val = nums[2] if len(nums) > 2 else ""      # Rate (जैसे 2.41000)
                elif col_letter == "Q" or "amount usd" in r_val_lower or "goods value" in f_name_lower:
                    raw_val = nums[3] if len(nums) > 3 else ""      # Amount USD (जैसे 4,511.52)
                elif col_letter == "W" or "taxable" in r_val_lower:
                    raw_val = nums[4] if len(nums) > 4 else (nums[3] if len(nums) > 3 else "") # Amount INR
                elif col_letter == "X" or "igst%" in r_val_lower:
                    raw_val = "5.00"
                elif col_letter == "Y" or "igst amount" in r_val_lower:
                    raw_val = nums[-1] if len(nums) > 0 else ""
                else:
                    raw_val = nums[0] if nums else ""

                if "=" in rule_val:
                    raw_val = apply_value_replacement(str(raw_val), rule_val)

                try:
                    if col_letter in ["S", "K", "M"]:
                        ws[cell_ref] = str(raw_val)
                    else:
                        ws[cell_ref] = float(str(raw_val).replace(",", ""))
                except:
                    ws[cell_ref] = raw_val
                    
        curr_row += 1
        overall_sr += 1
        
    return ws, overall_sr, curr_row
