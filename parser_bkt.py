import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic.
    Extracts item rows from the summary table usually found on the last page of BKT invoices,
    ignoring SUB TOTAL and Total rows, and ensuring Material Grp has valid text.
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
            
        # BKT टेबल की लाइन आमतौर पर 'Tyres' या इसी तरह के मटेरियल ग्रुप से शुरू होती है
        # साथ ही उसमें HS CODE और मात्रा/वजन मौजूद होना चाहिए
        if "hs code" in lower_line or re.search(r'\b401[12]\d{4}\b', line_str):
            parts = [p.strip() for p in line_str.split() if p.strip()]
            
            # यदि लाइन में 'SUB TOTAL' या 'Total' नहीं है और यह वैलिड आइटम रो है
            if "sub total" not in lower_line:
                item_dict = {
                    "raw_parts": parts,
                    "line_text": line_str
                }
                
                # 1. HS Code एक्सट्रैक्ट करना (जैसे 40117000 या HS CODE#3: 40117000)
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
                
                # 3. वजन और मात्रा (Numbers) निकालना
                nums = re.findall(r'[\d,]+\.\d{3}|\b\d+\b', line_str)
                item_dict["nums"] = nums
                
                # डिस्क्रिप्शन या मटेरियल ग्रुप सेट करना
                item_dict["material_grp"] = "Tyres" if "tyres" in lower_line else parts[0] if parts else "Tyres"
                
                parsed_items.append(item_dict)
                
    return parsed_items
