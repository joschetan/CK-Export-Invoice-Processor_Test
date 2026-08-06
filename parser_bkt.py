import re

def extract_bkt_items(pdf_lines):
    """
    BKT Dedicated Item Table Parser Logic (Strictly processes 'ORIGINAL FOR RECIPIENT' page,
    extracts Taxable Value & IGST from Sub-total lines, forces Text format for 10-digit License, 
    and converts text to UPPERCASE).
    """
    parsed_items = []
    seen_identifiers = set()
    
    port_destination = ""
    country_destination = ""
    
    # 🛑 1. ट्विस्ट का समाधान: केवल "ORIGINAL FOR RECIPIENT" वाले पेज/हिस्से को ही प्रोसेस करें
    # इसके लिए हम पूरी लाइनों को चेक करेंगे कि क्या ओरिजिनल पेज शुरू हुआ है
    is_original_page = True  # डिफ़ॉल्ट रूप से चालू रखेंगे, और डुप्लीकेट/एक्स्ट्रा कॉपी मिलते ही रोक देंगे
    
    # एक अस्थायी लिस्ट बनाएंगे जो हर आइटम के ब्लॉक और उसके Sub-total को ट्रैक करेगी
    current_hs_code = ""
    current_license_no = ""
    current_license_date = ""
    current_mat_grp = "TYRES"
    
    for idx, line in enumerate(pdf_lines):
        line_str = line.strip()
        if not line_str:
            continue
            
        lower_line = line_str.lower()
        
        # यदि पेज पर Duplicate, Triplicate या Extra copy आ जाए, तो ओरिजिनल सेक्शन समाप्त मान लें
        if "duplicate for" in lower_line or "triplicate for" in lower_line or "extra copy" in lower_line or "account ho" in lower_line:
            if "original for recipient" not in lower_line:
                is_original_page = False
                
        if "original for recipient" in lower_line:
            is_original_page = True
            
        # अगर यह ओरिजिनल पेज नहीं है, तो आगे बढ़ जाएं
        if not is_original_page:
            # लेकिन अगर गलती से फ्लैग मिस हो और 'ORIGINAL FOR RECIPIENT' टेक्स्ट मिल जाए तो फिर से ऑन कर लें
            if "original for recipient" in lower_line:
                is_original_page = True
            else:
                continue

        # 🌍 पोर्ट और कंट्री डेस्टिनेशन लॉजिक (Capital 'Final' vs Small 'final')
        if "Final destination" in line_str:
            parts_dest = line_str.split(":")
            val_part = parts_dest[-1].strip() if len(parts_dest) > 1 else line_str.replace("Final destination", "").strip()
            port_destination = val_part.upper()
            
        elif "final destination" in lower_line and "country of final destination" not in lower_line:
            parts_dest = line_str.split(":")
            val_part = parts_dest[-1].strip() if len(parts_dest) > 1 else line_str.replace("final destination", "").strip()
            if len(val_part) > 0:
                country_destination = val_part.upper()
                
        elif "country of final destination" in lower_line:
            parts_dest = line_str.split(":")
            val_part = parts_dest[-1].strip() if len(parts_dest) > 1 else ""
            if val_part:
                country_destination = val_part.upper()

        # ✅ HS Code वाली मुख्य लाइन को पकड़ना
        hs_match = re.search(r'\b(401[1236]\d{4}|843[123]\d{4})\b', line_str)
        if hs_match:
            current_hs_code = hs_match.group(1)
            
            # मटीरियल ग्रुप तय करना
            current_mat_grp = "TYRES"
            if "tube" in lower_line:
                current_mat_grp = "TUBES"
            elif "flap" in lower_line:
                current_mat_grp = "FLAPS"
                
            # लाइसेंस नंबर और डेट ढूंढना
            lic_match = re.search(r'(\d{10})\s*(?:dtd\.?|date)?\s*([\d./-]+)', line_str, re.IGNORECASE)
            if lic_match:
                raw_lic = lic_match.group(1).strip()
                current_license_no = f"'{raw_lic}" if not raw_lic.startswith("'") else raw_lic
                current_license_date = lic_match.group(2).strip().replace(".", "/")
            continue

        # ✅ सबसे महत्वपूर्ण सुधार: जैसे ही ब्लॉक के अंत में "Sub-total" मिले, वहाँ से सटीक Taxable Value और IGST उठा लो
        if "sub-total" in lower_line or "sub total" in lower_line:
            # Sub-total वाली लाइन से सभी आंकड़े निकालना
            nums = re.findall(r'[\d,]+\.\d{2,3}|\b\d+\b', line_str)
            
            if nums and current_hs_code:
                # Sub-total लाइन के नंबर्स का क्रम: [0]=Qty (या कुछ और), [आगे]=Taxable Value, IGST Amt आदि[cite: 8, 9]
                qty = nums[0] if len(nums) > 0 else ""
                
                # आमतौर पर Sub-total लाइन में आखिरी से पहले वाली वैल्यू Taxable Value होती है और अंतिम IGST(Rs) होती है[cite: 8, 9]
                taxable_val = nums[-3] if len(nums) >= 3 else (nums[1] if len(nums) > 1 else "")
                igst_amt = nums[-2] if len(nums) >= 2 else ""
                
                # यदि ऊपर की लाइन से Qty या वैल्यू मिल चुकी है तो यूनिक चेक करें
                unique_key = f"{current_hs_code}_{qty}_{taxable_val}"
                if unique_key in seen_identifiers:
                    continue
                seen_identifiers.add(unique_key)
                
                item_dict = {
                    "raw_parts": line_str.split(),
                    "line_text": line_str.upper(),
                    "hs_code": current_hs_code,
                    "license_no": current_license_no,
                    "license_date": current_license_date,
                    "quantity": qty,
                    "value": taxable_val,
                    "taxable_value": taxable_val, # सीधी Taxable Value (जैसे 333,097.92)[cite: 8, 9]
                    "igst_rate": "18.00",         # स्टैंडर्ड IGST रेट[cite: 8, 9]
                    "igst_amt": igst_amt,         # IGST (Rs)[cite: 8, 9]
                    "gross_wt": "",
                    "net_wt": "",
                    "nums": nums,
                    "material_grp": current_mat_grp,
                    "port_destination": port_destination,
                    "country_destination": country_destination
                }
                
                parsed_items.append(item_dict)
                
                # डेटा कैप्चर होने के बाद HS Code खाली कर दें ताकि अगली आइटम के लिए फ्रेश रहे
                current_hs_code = ""

    return parsed_items
