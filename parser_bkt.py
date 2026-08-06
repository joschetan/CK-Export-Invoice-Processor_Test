import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic.
    Extracts exact item rows based on table structure, accurately capturing Quantity,
    Value, Gross Wt, Net Wt, and License details without hardcoding HS Code prefixes.
    """
    parsed_items = []
    
    for line in pdf_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        # ❌ केवल ग्रांड टोटल या टेयर वेट को छोड़ना है, 'SUB TOTAL' हमारी असली आइटम लाइन है!
        if lower_line.startswith("total") or "tare weight" in lower_line or "freight terms" in lower_line:
            continue
            
        # ✅ पहचान: जिस लाइन में मात्रा, वैल्यू या वजन (डेसिमल नंबर) मौजूद हों और वह टेबल का हिस्सा हो
        if "hs code" in lower_line or "hs code#" in lower_line or "sub total" in lower_line or re.search(r'\d+\.\d{3}', line_str):
            
            parts = [p.strip() for p in line_str.split() if p.strip()]
            if not parts:
                continue
                
            item_dict = {
                "raw_parts": parts,
                "line_text": line_str
            }
            
            # 1. HS Code निकालना (किसी भी अंक से शुरू हो सकता है, जैसे 8 या 10 डिजिट का कोड)
            hs_match = re.search(r'\b(\d{8,10})\b', line_str)
            item_dict["hs_code"] = hs_match.group(1) if hs_match else ""
            
            # 2. License No & Date निकालना (अगर मौजूद हो)
            lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
            if lic_match:
                item_dict["license_no"] = lic_match.group(1).strip()
                item_dict["license_date"] = lic_match.group(2).strip().replace(".", "/")
            else:
                item_dict["license_no"] = ""
                item_dict["license_date"] = ""
            
            # 3. सटीक नंबर्स निकालना (Quantity, Value, Gross Wt, Net Wt)
            clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
            nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
            
            filtered_nums = []
            for n in nums:
                if n != item_dict["hs_code"] and len(n) < 10 and n not in item_dict["license_no"]:
                    filtered_nums.append(n)
            
            # कॉलम मैपिंग
            item_dict["quantity"] = filtered_nums[0] if len(filtered_nums) > 0 else ""
            item_dict["value"] = filtered_nums[1] if len(filtered_nums) > 1 else ""
            item_dict["gross_wt"] = filtered_nums[2] if len(filtered_nums) > 2 else ""
            item_dict["net_wt"] = filtered_nums[3] if len(filtered_nums) > 3 else ""
            
            item_dict["nums"] = filtered_nums
            item_dict["material_grp"] = "Tyres"
            
            parsed_items.append(item_dict)
            
    return parsed_items
