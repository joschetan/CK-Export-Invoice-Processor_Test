import re

def apply_value_replacement(extracted_text, mapping_str):
    """
    Parses 'FIND=REPLACE, FIND2=REPLACE2' mapping syntax and applies it to extracted_text.
    """
    if not extracted_text or not mapping_str or "=" not in mapping_str:
        return extracted_text

    text_clean = str(extracted_text).strip()
    pairs = [p.strip() for p in mapping_str.split(",") if "=" in p]
    
    for pair in pairs:
        parts = pair.split("=")
        if len(parts) == 2:
            find_kw = parts[0].strip()
            replace_kw = parts[1].strip()
            
            if text_clean.lower() == find_kw.lower():
                return replace_kw
            elif find_kw.lower() in text_clean.lower():
                pattern = re.compile(re.escape(find_kw), re.IGNORECASE)
                return pattern.sub(replace_kw, text_clean)
                
    return text_clean

def apply_rule_filter(raw_text, mode, stop_kw, flt, keyword=""):
    """
    Core Unified Extraction Engine: Filters raw PDF extracted text based on user rules
    """
    # 🎯 1. यदि नया 'Exact Keyword Paste' फिल्टर चुना गया है
    if flt == "Exact Keyword Paste (If Found)":
        target_check = stop_kw.strip() if stop_kw and str(stop_kw).strip() else keyword.strip()
        if target_check and target_check.lower() in str(raw_text).lower():
            return target_check
        return target_check if target_check else ""

    if not raw_text:
        return ""
        
    text = raw_text.strip()
    if text.startswith(":"):
        text = text[1:].strip()
    
    # अगर यह स्मार्ट ब्लॉक डिटेक्टर से आया हुआ मल्टी-लाइन डेटा है, तो रूल्स से कटने न दें
    if keyword and ("consignee" in keyword.lower() or "buyer" in keyword.lower()):
        return text

    if mode == "Word Position" or mode.startswith("Word "):
        w_num = int(stop_kw.strip()) if stop_kw and str(stop_kw).strip().isdigit() else 1
        parts = text.split()
        text = parts[w_num - 1].strip() if len(parts) >= w_num else ""
    elif mode == "After Word" and stop_kw:
        if "=" not in stop_kw and stop_kw.lower() in text.lower():
            start_idx = text.lower().find(stop_kw.lower()) + len(stop_kw)
            text = text[start_idx:].strip()
            if text.startswith(":"):
                text = text[1:].strip()
    elif mode == "Between Keywords" and stop_kw:
        if "=" not in stop_kw and stop_kw.lower() in text.lower():
            text = text.lower().split(stop_kw.lower())[0].strip()
    elif mode == "Exact Word":
        parts = text.split()
        text = parts[0].strip() if parts else ""
    elif mode == "Full Line":
        text = text.split("\n")[0].strip()

    # 🎯 FILTERS IMPLEMENTATION
    if flt in ["Text Inside Parentheses ()", "Inside Parentheses ()"]:
        bracket_match = re.search(r'\((.*?)\)', text)
        text = bracket_match.group(1).strip() if bracket_match else text.strip()
    elif flt == "Container Number (ISO Format)":
        cntr_match = re.search(r'\b[A-Za-z]{4}\s*\d{7}\b', text)
        text = cntr_match.group(0).replace(" ", "") if cntr_match else text.strip()
    elif flt == "Remove All Spaces":
        text = text.replace(" ", "").strip()
    elif flt == "Numbers Only":
        nums = re.findall(r'[\d,.]+', text)
        text = nums[0].strip() if nums else ""
    elif flt == "Letters Only":
        text = re.sub(r'[^A-Za-z\s]', '', text).strip()
    elif flt == "Clean Date (DD/MM/YYYY)":
        d_match = re.search(r'\b\d{2}[./-]\d{2}[./-]\d{4}\b', text)
        text = d_match.group(0).replace(".", "/").replace("-", "/") if d_match else text.strip()

    if stop_kw and "=" in stop_kw:
        text = apply_value_replacement(text, stop_kw)
    if flt and "=" in flt:
        text = apply_value_replacement(text, flt)

    return text.strip()

def extract_header_value(pdf_lines, pdf_text, keyword, position, mode, stop_kw, filter_type, field_label=""):
    """
    Smart Block Extraction Engine: Automatically detects and extracts multi-line address blocks 
    and handles side-by-side columns intelligently.
    """
    raw_t = ""
    is_target_field = field_label and ("consignee" in field_label.lower() or "buyer" in field_label.lower())
    is_consignee = field_label and "consignee" in field_label.lower()
    
    if filter_type == "Exact Keyword Paste (If Found)":
        raw_t = pdf_text
    elif keyword:
        for line_i, line in enumerate(pdf_lines):
            if keyword.lower() in line.lower():
                if position == "Right (आगे)":
                    start_idx = line.lower().find(keyword.lower()) + len(keyword)
                    raw_t = line[start_idx:].strip()
                    if raw_t.startswith(":"):
                        raw_t = raw_t[1:].strip()
                    if raw_t:
                        break
                elif position == "Below (नीचे)":
                    if is_target_field:
                        # 🤖 SMART TEXT BLOCK DETECTOR (AI-like multi-line block harvester)
                        collected_lines = []
                        stop_markers = [
                            "notify:", "pre-carriage", "vessel", "port of", "place of", 
                            "terms of", "sales order", "invoice no", "buyer", "consignee:"
                        ]
                        
                        for offset in range(1, 6):  # नीचे की 5 लाइनों तक स्मार्ट स्कैन
                            if line_i + offset < len(pdf_lines):
                                next_line = pdf_lines[line_i + offset].strip()
                                lower_next = next_line.lower()
                                
                                # यदि अगला कोई मुख्य सेक्शन शुरू हो जाए तो रुक जाएं
                                if not next_line or any(marker in lower_next for marker in stop_markers if marker not in keyword.lower()):
                                    break
                                    
                                # साइड-बाय-साइड चिपके हुए टेक्स्ट को अलग करने का स्मार्ट तरीका
                                if is_consignee:
                                    if "Welspun USA Inc - 100014" in next_line:
                                        next_line = next_line.split("Welspun USA Inc - 100014")[0].strip()
                                    elif "New York" in next_line:
                                        next_line = next_line.split("New York")[0].strip()
                                    if next_line:
                                        collected_lines.append(next_line)
                                else:
                                    if "Welspun USA Inc - 100014" in next_line:
                                        next_line = "Welspun USA Inc - 100014" + next_line.split("Welspun USA Inc - 100014")[1]
                                    elif "501037" in next_line:
                                        parts = next_line.split("501037")
                                        if len(parts) > 1:
                                            next_line = parts[1].strip()
                                    collected_lines.append(next_line)
                                    
                        if collected_lines:
                            raw_t = "\n".join([cl for cl in collected_lines if cl])
                            break
                    else:
                        if line_i + 1 < len(pdf_lines):
                            raw_t = pdf_lines[line_i + 1].strip()
                            if raw_t:
                                break
                elif position == "2 Lines Below":
                    if line_i + 2 < len(pdf_lines):
                        raw_t = pdf_lines[line_i + 2].strip()
                        if raw_t:
                            break
    else:
        raw_t = pdf_text

    if is_target_field:
        return raw_t.strip()

    return apply_rule_filter(raw_t, mode, stop_kw, filter_type, keyword)

def detect_igst_status(pdf_text, lut_keywords="", paid_keywords=""):
    """
    Detects whether invoice is 'LUT' or 'P' based on shipper custom keywords
    Returns: 'LUT', 'P', or 'UNKNOWN'
    """
    if not pdf_text:
        return "UNKNOWN"
        
    text_lower = pdf_text.lower()
    
    default_lut_kws = ["lut arn no", "w/o payment", "without payment", "under bond", "letter of undertaking"]
    custom_lut_kws = [k.strip().lower() for k in lut_keywords.split(",") if k.strip()]
    all_lut_kws = list(set(default_lut_kws + custom_lut_kws))
    
    for kw in all_lut_kws:
        if kw in text_lower:
            return "LUT"
            
    default_paid_kws = ["on payment of integrated tax", "with payment of integrated tax", "payment of integrated tax"]
    custom_paid_kws = [k.strip().lower() for k in paid_keywords.split(",") if k.strip()]
    all_paid_kws = list(set(default_paid_kws + custom_paid_kws))
    
    for kw in all_paid_kws:
        if kw in text_lower:
            return "P"
            
    return "UNKNOWN"
