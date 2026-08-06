import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic.
    Extracts and maps each field directly so no external mapping confusion remains.
    """
    parsed_items = []
    
    for line in pdf_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        if "sub total" in lower_line or lower_line.startswith("total") or "tare weight" in lower_line:
            continue
            
        if "hs code" in lower_line or re.search(r'\b401[12]\d{4}\b', line_str):
            parts = [p.strip() for p in line_str.split() if p.strip()]
            
            if "sub total" not in lower_line:
                item_dict = {
                    "raw_parts": parts,
                    "line_text": line_str
                }
                
                # 1. HS Code
                hs_match = re.search(r'\b(401[12]\d{4})\b', line_str)
                item_dict["hs_code"] = hs_match.group(1) if hs_match else ""
                
                # 2. License No & Date
                lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
                if lic_match:
                    item_dict["license_no"] = lic_match.group(1).strip()
                    item_dict["license_date"] = lic_match.group(2).strip().replace(".", "/")
                else:
                    item_dict["license_no"] = ""
                    item_dict["license_date"] = ""
                
                # 3. Clean numbers extraction for BKT Table columns:
                # BKT Table format: [Quantity, Value, Gross Weight, Net Weight]
                clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
                nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
                
                filtered_nums = []
                for n in nums:
                    if n != item_dict["hs_code"] and len(n) < 10:
                        filtered_nums.append(n)
                
                # सीधे स्पष्ट नाम देना ताकि गड़बड़ी की 0% गुंजाइश रहे
                item_dict["quantity"] = filtered_nums[0] if len(filtered_nums) > 0 else ""
                item_dict["value"] = filtered_nums[1] if len(filtered_nums) > 1 else ""
                item_dict["gross_wt"] = filtered_nums[2] if len(filtered_nums) > 2 else ""
                item_dict["net_wt"] = filtered_nums[3] if len(filtered_nums) > 3 else ""
                
                item_dict["nums"] = filtered_nums # बैकअप के लिए
                item_dict["material_grp"] = "Tyres" if "tyres" in lower_line else parts[0] if parts else "Tyres"
                
                parsed_items.append(item_dict)
                
    return parsed_items
