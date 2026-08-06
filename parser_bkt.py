import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic (Strictly skips header/empty match lines, 
    forces Text format for 10-digit License number, handles Port vs Country destination, 
    and converts all extracted text to UPPERCASE).
    """
    parsed_items = []
    seen_identifiers = set()
    
    # अतिरिक्त फील्ड्स (पोर्ट और कंट्री) रखने के लिए वेरिएबल्स
    port_destination = ""
    country_destination = ""
    
    for line in pdf_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        # 🌍 पोर्ट और कंट्री डेस्टिनेशन को अलग-अलग पकड़ने का सटीक लॉजिक (Capital 'Final' vs Small 'final')
        if "Final destination" in line_str:
            # अगर 'Final' कैपिटल F से है, तो यह पोर्ट है (जैसे BREMERHAVEN)
            parts_dest = line_str.split(":")
            val_part = parts_dest[-1].strip() if len(parts_dest) > 1 else line_str.replace("Final destination", "").strip()
            port_destination = val_part.upper()
            
        elif "final destination" in lower_line and "country of final destination" not in lower_line:
            # अगर स्मॉल f वाला 'final' है
            parts_dest = line_str.split(":")
            val_part = parts_dest[-1].strip() if len(parts_dest) > 1 else line_str.replace("final destination", "").strip()
            if "GERMANY" in line_str.upper() or len(val_part) > 0:
                country_destination = val_part.upper()
                
        elif "country of final destination" in lower_line:
            # कंट्री ऑफ फाइनल डेस्टिनेशन के लिए
            parts_dest = line_str.split(":")
            val_part = parts_dest[-1].strip() if len(parts_dest) > 1 else ""
            if val_part:
                country_destination = val_part.upper()
        
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
            
            # 2. License No & Date (प्रारंभिक शून्य बचाने के लिए टेक्स्ट फॉर्मेट)
            lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
            if lic_match:
                raw_lic = lic_match.group(1).strip()
                license_no = f"'{raw_lic}" if not raw_lic.startswith("'") else raw_lic
                license_date = lic_match.group(2).strip().replace(".", "/")
            else:
                license_no = ""
                license_date = ""
            
            # 3. सटीक नंबर्स निकालना
            clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
            nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
            
            filtered_nums = []
            for n in nums:
                if n != hs_code and len(n) < 10:
                    filtered_nums.append(n)
            
            qty = filtered_nums[0] if len(filtered_nums) > 0 else ""
            val = filtered_nums[1] if len(filtered_nums) > 1 else ""
            
            if not qty or not val:
                continue
            
            # डुप्लीकेट रोकने के लिए यूनिक चेक
            unique_key = f"{hs_code}_{qty}_{val}"
            if unique_key in seen_identifiers:
                continue
            seen_identifiers.add(unique_key)
            
            # 4. मटीरियल ग्रुप (इसे भी कैपिटल कर दिया है)
            mat_grp = "TYRES"
            if "tube" in lower_line:
                mat_grp = "TUBES"
            elif "flap" in lower_line:
                mat_grp = "FLAPS"
            elif parts:
                mat_grp = parts[0].upper()
            
            item_dict = {
                "raw_parts": parts,
                "line_text": line_str.upper(),
                "hs_code": hs_code,
                "license_no": license_no,
                "license_date": license_date,
                "quantity": qty,
                "value": val,
                "gross_wt": filtered_nums[2] if len(filtered_nums) > 2 else "",
                "net_wt": filtered_nums[3] if len(filtered_nums) > 3 else "",
                "nums": filtered_nums,
                "material_grp": mat_grp,
                # यहाँ पोर्ट और कंट्री दोनों को कैपिटल फॉर्मेट में जोड़ दिया गया है
                "port_destination": port_destination,
                "country_destination": country_destination
            }
            
            parsed_items.append(item_dict)
                
    return parsed_items
