import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic.
    Extracts item rows from the summary table on the last page of BKT invoices,
    extracts HS Code, HS Code Prefix Number (e.g., #3 -> 3), Quantity, Values, Weights, and Licenses.
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
            
        # BKT टेबल की लाइन जिसमें HS CODE या 8-डिजिट का टायर कोड मौजूद हो
        if "hs code" in lower_line or re.search(r'\b401[12]\d{4}\b', line_str):
            parts = [p.strip() for p in line_str.split() if p.strip()]
            
            if "sub total" not in lower_line:
                item_dict = {
                    "raw_parts": parts,
                    "line_text": line_str
                }
                
                # 1. HS Code के बाद का सिंगल डिजिट नंबर निकालना (जैसे HS CODE#3: से '3')
                prefix_match = re.search(r'hs\s*code\s*#?\s*(\d+)', line_str, re.IGNORECASE)
                if prefix_match:
                    item_dict["hs_prefix_no"] = prefix_match.group(1)
                else:
                    item_dict["hs_prefix_no"] = ""

                # 2. असली 8-डिजिट HS Code एक्सट्रैक्ट करना (जैसे 40117000)
                hs_match = re.search(r'\b(401[12]\d{4})\b', line_str)
                item_dict["hs_code"] = hs_match.group(1) if hs_match else ""
                
                # 3. लाइसेंस नंबर और तारीख ढूँढना (जैसे 0311048108 Dtd. 13.10.2025)
                lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
                if lic_match:
                    item_dict["license_no"] = lic_match.group(1).strip()
                    item_dict["license_date"] = lic_match.group(2).strip().replace(".", "/")
                else:
                    item_dict["license_no"] = ""
                    item_dict["license_date"] = ""
                
                # 4. वजन और मात्रा (Numbers - डेसिमल 2 या 3 अंक वाले और साधारण अंक)
                nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', line_str)
                item_dict["nums"] = nums
                
                # डिस्क्रिप्शन या मटेरियल ग्रुप सेट करना
                item_dict["material_grp"] = "Tyres" if "tyres" in lower_line else parts[0] if parts else "Tyres"
                
                parsed_items.append(item_dict)
                
    return parsed_items
