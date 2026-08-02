import re

def extract_welspun_items(pdf_lines):
    """
    Welspun Dedicated Item Table Parser Logic (Working perfectly like butter).
    """
    parsed_items = []
    
    for line in pdf_lines:
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
                        
                parsed_items.append(item_dict)
                
    return parsed_items
