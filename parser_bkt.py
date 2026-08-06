import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic (100% Duplicate Free, Exact 5 Rows, Text Format for License).
    """
    parsed_items = []
    seen_identifiers = set()
    
    for line in pdf_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        # ❌ सब-टोटल, टोटल या टेयर वेट वाली लाइनों को छोड़ दें
        if "sub total" in lower_line or "sub_total" in lower_line or lower_line.startswith("total") or "tare weight" in lower_line:
            continue
            
        # ✅ केवल वही लाइन उठाओ जिसमें असली HS Code मौजूद हो
        hs_match = re.search(r'\b(401[12]\d{4})\b', line_str)
        if hs_match:
            if "sub total" in lower_line:
                continue
                
            parts = [p.strip() for p in line_str.split() if p.strip()]
            
            # 1. HS Code
            hs_code = hs_match.group(1)
            
            # 2. License No & Date (Column AD के लिए आगे का जीरो बचाने हेतु टेक्स्ट/स्ट्रिंग फॉर्मेट)
            lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
            if lic_match:
                # '\t' या स्ट्रिंग फॉर्मेट से एक्सेल में आगे का जीरो गायब नहीं होगा
                license_no = "\t" + lic_match.group(1).strip()
                license_date = lic_match.group(2).strip().replace(".", "/")
            else:
                license_no = ""
                license_date = ""
            
            # 3. नंबर्स निकालना (Qty, Value, Gross Wt, Net Wt)
            clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
            nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
            
            filtered_nums = []
            for n in nums:
                if n != hs_code and len(n) < 10:
                    filtered_nums.append(n)
            
            qty = filtered_nums[0] if len(filtered_nums) > 0 else ""
            val = filtered_nums[1] if len(filtered_nums) > 1 else ""
            
            # 🔍 डुप्लीकेट 10 आइटम्स रोकने के लिए यूनिक चेक (HS Code + Qty + Value)
            unique_key = f"{hs_code}_{qty}_{val}"
            if unique_key in seen_identifiers:
                continue
            seen_identifiers.add(unique_key)
            
            item_dict = {
                "raw_parts": parts,
                "line_text": line_str,
                "hs_code": hs_code,
                "license_no": license_no,
                "license_date": license_date,
                "quantity": qty,
                "value": val,
                "gross_wt": filtered_nums[2] if len(filtered_nums) > 2 else "",
                "net_wt": filtered_nums[3] if len(filtered_nums) > 3 else "",
                "nums": filtered_nums,
                "material_grp": "Tyres"
            }
            
            parsed_items.append(item_dict)
            
            # चूंकि BKT की इस टेबल में सिर्फ 5 ही मुख्य आइटम्स होती हैं, जैसे ही 5 पूरी हों लूप रोक दें
            if len(parsed_items) >= 5:
                break
                
    return parsed_items
