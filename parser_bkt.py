import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic.
    Strictly skips Sub Totals to maintain exact item count (5 items),
    and correctly maps quantity, value, weights, and license details.
    """
    parsed_items = []
    
    for line in pdf_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        # ❌ 'SUB TOTAL', 'Total' या 'Tare Weight' वाली लाइनों को पूरी तरह ब्लॉक/स्किप करें
        if "sub total" in lower_line or lower_line.startswith("total") or "tare weight" in lower_line or "freight terms" in lower_line:
            continue
            
        # ✅ केवल मुख्य आइटम लाइन को पकड़ें जिसमें HS Code (या रme कोड पैटर्न) मौजूद हो
        hs_match = re.search(r'\b(\d{8,10})\b', line_str)
        if hs_match or "hs code" in lower_line or "hs code#" in lower_line:
            
            parts = [p.strip() for p in line_str.split() if p.strip()]
            if not parts:
                continue
                
            item_dict = {
                "raw_parts": parts,
                "line_text": line_str
            }
            
            # 1. HS Code
            item_dict["hs_code"] = hs_match.group(1) if hs_match else ""
            
            # 2. License No & Date
            lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
            if lic_match:
                item_dict["license_no"] = lic_match.group(1).strip()
                item_dict["license_date"] = lic_match.group(2).strip().replace(".", "/")
            else:
                item_dict["license_no"] = ""
                item_dict["license_date"] = ""
            
            # 3. Clean numbers extraction
            clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
            nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
            
            filtered_nums = []
            for n in nums:
                if n != item_dict["hs_code"] and len(n) < 10 and n not in item_dict["license_no"]:
                    filtered_nums.append(n)
            
            # स्पष्ट मैपिंग
            item_dict["quantity"] = filtered_nums[0] if len(filtered_nums) > 0 else ""
            item_dict["value"] = filtered_nums[1] if len(filtered_nums) > 1 else ""
            item_dict["gross_wt"] = filtered_nums[2] if len(filtered_nums) > 2 else ""
            item_dict["net_wt"] = filtered_nums[3] if len(filtered_nums) > 3 else ""
            
            item_dict["nums"] = filtered_nums
            item_dict["material_grp"] = "Tyres" if "tyres" in lower_line else parts[0] if parts else "Tyres"
            
            parsed_items.append(item_dict)
            
    return parsed_items
