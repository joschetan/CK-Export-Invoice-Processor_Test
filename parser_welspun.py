import re

def extract_welspun_items(pdf_lines, pdf_text=""):
    """
    Welspun Dedicated Item Table Parser Logic (Merged with Commodity & HS Code Extraction).
    """
    parsed_items = []
    
    # 1. Pehle PDF text se commodities (jaise (1), (2) etc.) extract karne ka logic yahan add kar diya hai
    extracted_commodities = []
    if pdf_text:
        comm_matches = re.findall(r'\((\d+)\)(.*?)(?=\(\d+\)|Freight Terms|$)', pdf_text, re.DOTALL)
        if comm_matches:
            seen_srs = set()
            for c_no, c_desc in comm_matches:
                sr_clean = c_no.strip()
                if sr_clean not in seen_srs:
                    seen_srs.add(sr_clean)
                    clean_desc = re.sub(r'\s+', ' ', c_desc).strip()
                    extracted_commodities.append({
                        "sr": sr_clean,
                        "desc": clean_desc
                    })

    # 2. Standard row item parsing (HS Code, nums, DBK, description)
    for idx, line in enumerate(pdf_lines):
        line_str = line.strip()
        if re.match(r'^\d{8}\b', line_str):
            parts = [p.strip() for p in line_str.split() if p.strip()]
            if len(parts) >= 3:
                item_dict = {
                    "raw_parts": parts,
                    "hs_code": parts[0]
                }
                
                nums = re.findall(r'[\d,]+\.\d{2,3}', line_str)
                item_dict["nums"] = nums
                
                dbk_match = re.search(r'\b\d{6}[A-Za-z]?\b|\b\d{10}[A-Za-z]?\b', line_str)
                item_dict["dbk_found"] = dbk_match.group(0) if dbk_match else ""

                if len(nums) > 0:
                    first_num = nums[0]
                    start_pos = len(parts[0])
                    end_pos = line_str.find(first_num)
                    if end_pos > start_pos:
                        desc_text = line_str[start_pos:end_pos].strip()
                        if item_dict["dbk_found"]:
                            desc_text = desc_text.replace(item_dict["dbk_found"], "").strip()
                        item_dict["description_text"] = desc_text
                else:
                    item_dict["description_text"] = " ".join(parts[1:]) if len(parts) > 1 else ""
                
                # Agar extracted commodities available hain toh is item ke sath map kar do
                item_idx = len(parsed_items)
                if extracted_commodities and item_idx < len(extracted_commodities):
                    item_dict["commodity_sr"] = extracted_commodities[item_idx]["sr"]
                    item_dict["commodity_desc"] = extracted_commodities[item_idx]["desc"]
                else:
                    item_dict["commodity_sr"] = str(item_idx + 1)
                    item_dict["commodity_desc"] = item_dict.get("description_text", "")
                        
                parsed_items.append(item_dict)
                
    return parsed_items
