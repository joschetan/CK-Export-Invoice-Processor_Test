import re
import io
import pdfplumber

def apply_value_replacement(extracted_text, mapping_str):
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
    if flt == "Exact Keyword Paste (If Found)":
        target_check = stop_kw.strip() if stop_kw and str(stop_kw).strip() else keyword.strip()
        if target_check and target_check.lower() in str(raw_text).lower():
            return target_check
        return target_check if target_check else ""
    if not raw_text: return ""
    text = raw_text.strip()
    if text.startswith(":"): text = text[1:].strip()
    
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
            if text.startswith(":"): text = text[1:].strip()
    elif mode == "Between Keywords" and stop_kw:
        if "=" not in stop_kw and stop_kw.lower() in text.lower():
            text = text.lower().split(stop_kw.lower())[0].strip()
    elif mode == "Exact Word":
        parts = text.split()
        text = parts[0].strip() if parts else ""
    elif mode == "Full Line":
        text = text.split("\n")[0].strip()

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

    if stop_kw and "=" in stop_kw: text = apply_value_replacement(text, stop_kw)
    if flt and "=" in flt: text = apply_value_replacement(text, flt)
    return text.strip()

def extract_header_value(pdf_lines, pdf_text, keyword, position, mode, stop_kw, filter_type, field_label="", pdf_bytes=None):
    raw_t = ""
    
    # 📦 SMART BOX EXTRACTION ENGINE (डब्बे के अंदर की सटीक सीमा)
    if position == "📦 Extract Inside Box (डब्बे के अंदर का टेक्स्ट)" and pdf_bytes and keyword:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                page = pdf.pages[0]
                words = page.extract_words()
                
                # 1. कीवर्ड की पोजीशन ढूँढना
                kw_word = None
                for w in words:
                    if keyword.lower() in w['text'].lower():
                        kw_word = w
                        break
                
                if kw_word:
                    kw_x0 = kw_word['x0']
                    kw_y0 = kw_word['top']
                    
                    # 2. उस डिब्बे की हदों (Box Boundaries) का अनुमान लगाना 
                    box_x0 = kw_x0 - 5
                    box_x1 = kw_x0 + 260  # एक मानक डिब्बे की चौड़ाई सीमा
                    box_y0 = kw_y0 - 2
                    box_y1 = kw_y0 + 130  # डिब्बे की अधिकतम ऊँचाई नीचे की तरफ
                    
                    # 3. सिर्फ उसी डिब्बे की बाउंड्री के अंदर आने वाले शब्दों को चुनना
                    block_words = []
                    for w in words:
                        if box_x0 <= w['x0'] <= box_x1 and box_y0 <= w['top'] <= box_y1:
                            block_words.append(w)
                    
                    # 4. लाइनों को Y-Axis के हिसाब से जोड़ना
                    lines_dict = {}
                    for w in block_words:
                        line_y = round(w['top'] / 4) * 4
                        lines_dict.setdefault(line_y, []).append(w)
                        
                    sorted_y = sorted(lines_dict.keys())
                    result_lines = []
                    stop_markers = ["notify:", "pre-carriage", "vessel", "port of", "place of", "terms of", "buyer's order"]
                    
                    for y in sorted_y:
                        line_words = sorted(lines_dict[y], key=lambda x: x['x0'])
                        line_text = " ".join([w['text'] for w in line_words]).strip()
                        if not line_text: continue
                        
                        lower_lt = line_text.lower()
                        if any(marker in lower_lt for marker in stop_markers if marker not in keyword.lower()):
                            break
                        result_lines.append(line_text)
                        
                    if result_lines:
                        return "\n".join(result_lines).strip()
        except Exception:
            pass

    # --- सामान्य बैकअप लॉजिक ---
    if filter_type == "Exact Keyword Paste (If Found)":
        raw_t = pdf_text
    elif keyword:
        for line_i, line in enumerate(pdf_lines):
            if keyword.lower() in line.lower():
                if position == "Right (आगे)":
                    start_idx = line.lower().find(keyword.lower()) + len(keyword)
                    raw_t = line[start_idx:].strip()
                    if raw_t.startswith(":"): raw_t = raw_t[1:].strip()
                    if raw_t: break
                elif position == "Below (नीचे)":
                    if line_i + 1 < len(pdf_lines):
                        raw_t = pdf_lines[line_i + 1].strip()
                        if raw_t: break
                elif position == "2 Lines Below":
                    if line_i + 2 < len(pdf_lines):
                        raw_t = pdf_lines[line_i + 2].strip()
                        if raw_t: break
    else:
        raw_t = pdf_text

    if position == "📦 Extract Inside Box (डब्बे के अंदर का टेक्स्ट)":
        return raw_t.strip()
        
    return apply_rule_filter(raw_t, mode, stop_kw, filter_type, keyword)

def detect_igst_status(pdf_text, lut_keywords="", paid_keywords=""):
    if not pdf_text: return "UNKNOWN"
    text_lower = pdf_text.lower()
    custom_lut_kws = [k.strip().lower() for k in lut_keywords.split(",") if k.strip()]
    for kw in custom_lut_kws:
        if kw in text_lower: return "LUT"
    custom_paid_kws = [k.strip().lower() for k in paid_keywords.split(",") if k.strip()]
    for kw in custom_paid_kws:
        if kw in text_lower: return "P" 
    return "UNKNOWN"
