import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic (Strictly skips header/empty match lines, 
    forces Text format for 10-digit License number to preserve leading zeros).
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
            
        # ✅ HS Code कंडीशन
        hs_match = re.search(r'\b(401[1236]\d{4}|843[123]\d{4})\b', line_str)
        if hs_match:
            if "sub total" in lower_line:
                continue
                
            parts = [p.strip() for p in line_str.split() if p.strip()]
            
            # 1. HS Code
            hs_code = hs_match.group(1)
            
            # 2. License No & Date (प्रारंभिक शून्य/Leading Zero बचाने के लिए सिंगल कोट के साथ टेक्स्ट फॉर्मेट)
            lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
            if lic_match:
                raw_lic = lic_match.group(1).strip()
                # एक्सेल में टेक्स्ट के रूप में रखने के लिए एपोस्ट्रोफी का प्रयोग ताकि आगे का जीरो न गायब हो
                license_no = f"'{raw_lic}" if not raw_lic.startswith("'") else raw_lic
                license_date = lic_match.group(2).strip().replace(".", "/")
            else:
                license_no = ""
                license_date = ""
            
            # 3. सटीक नंबर्स निकालना (Qty, Value, Gross Wt, Net Wt)
            clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
            nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
            
            filtered_nums = []
            for n in nums:
                if n != hs_code and len(n) < 10:
                    filtered_nums.append(n)
            
            qty = filtered_nums[0] if len(filtered_nums) > 0 else ""
            val = filtered_nums[1] if len(filtered_nums) > 1 else ""
            
            # 🛑 सबसे ज़रूरी बदलाव: यदि क्वांटिटी या वैल्यू ही गायब है (यानी ऊपर की हेडर लाइन है), तो उसे सीधे छोड़ दो!
            if not qty or not val:
                continue
            
            # डुप्लीकेट रोकने के लिए यूनिक चेक
            unique_key = f"{hs_code}_{qty}_{val}"
            if unique_key in seen_identifiers:
                continue
            seen_identifiers.add(unique_key)
            
            # 4. मटीरियल ग्रुप
            mat_grp = "Tyres"
            if "tube" in lower_line:
                mat_grp = "Tubes"
            elif "flap" in lower_line:
                mat_grp = "Flaps"
            elif parts:
                mat_grp = parts[0]
            
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
                "material_grp": mat_grp
            }
            
            parsed_items.append(item_dict)
                
    return parsed_items
