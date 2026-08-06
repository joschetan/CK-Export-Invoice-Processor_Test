import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic (Fixed & Perfect).
    Extracts Quantity, Value, Gross Weight, Net Weight, and License details accurately 
    by ignoring HS Code prefix numbers.
    """
    parsed_items = []
    
    for line in pdf_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        # 'sub total', 'total', 'tare weight' आदि पंक्तियों को पूरी तरह छोड़ दें
        if "sub total" in lower_line or lower_line.startswith("total") or "tare weight" in lower_line:
            continue
            
        # BKT टेबल की लाइन में 'HS CODE' या उसका पैटर्न होना अनिवार्य है
        if "hs code" in lower_line or re.search(r'\b401[12]\d{4}\b', line_str):
            parts = [p.strip() for p in line_str.split() if p.strip()]
            
            if "sub total" not in lower_line:
                item_dict = {
                    "raw_parts": parts,
                    "line_text": line_str
                }
                
                # 1. HS Code सही से एक्सट्रैक्ट करना (जैसे 40117000)
                hs_match = re.search(r'\b(401[12]\d{4})\b', line_str)
                item_dict["hs_code"] = hs_match.group(1) if hs_match else ""
                
                # 2. लाइसेंस नंबर और तारीख ढूँढना (जैसे 0311048108 Dtd. 13.10.2025)
                lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
                if lic_match:
                    item_dict["license_no"] = lic_match.group(1).strip()
                    item_dict["license_date"] = lic_match.group(2).strip().replace(".", "/")
                else:
                    item_dict["license_no"] = ""
                    item_dict["license_date"] = ""
                
                # 3. सटीक नंबर्स निकालना (Qty, Value, Gross Wt, Net Wt)
                # यहाँ हम HS Code के साथ आने वाले '#3', '#4' जैसे नंबरों को इग्नोर कर रहे हैं
                clean_line_for_nums = re.sub(r'HS\s*CODE#?\d*', '', line_str, flags=re.IGNORECASE)
                
                # दशमलव और पूर्ण संख्याएं ढूँढना जो टेबल के कॉलम की हैं
                nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', clean_line_for_nums)
                
                # यदि गलती से शिपर का नंबर आ गया हो तो उसे हटाकर सही सूची बनाना
                filtered_nums = []
                for n in nums:
                    # यदि यह नंबर 8-अंकों का RITC कोड या लाइसेंस नंबर नहीं है, तभी इसे आइटम डेटा मानेंगे
                    if n != item_dict["hs_code"] and len(n) < 10:
                        filtered_nums.append(n)
                        
                item_dict["nums"] = filtered_nums
                
                # डिस्क्रिप्शन या मटेरियल ग्रुप सेट करना
                item_dict["material_grp"] = "Tyres" if "tyres" in lower_line else parts[0] if parts else "Tyres"
                
                parsed_items.append(item_dict)
                
    return parsed_items
