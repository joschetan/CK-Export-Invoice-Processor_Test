import pdfplumber
import pandas as pd
import openpyxl
from io import BytesIO

def extract_data_from_supporting_file(file_obj):
    """
    सपोर्टिंग फाइल (PDF या Excel) को पढ़कर उसका सारा टेक्स्ट या रो-डेटा डिक्शनरी/स्ट्रिंग रूप में लौटाता है
    """
    if not file_obj:
        return "", None
        
    file_name = file_obj.name.lower()
    extracted_text = ""
    excel_df = None
    
    try:
        if file_name.endswith(".pdf"):
            with pdfplumber.open(file_obj) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        extracted_text += t + "\n"
        elif file_name.endswith((".xlsx", ".xls")):
            excel_df = pd.read_excel(file_obj, sheet_name=0)
            # एक्सेल के सारे डेटा को टेक्स्ट फॉर्मेट में भी जोड़ लेते हैं ताकि कीवर्ड सर्च काम आ सके
            extracted_text = excel_df.to_string()
    except Exception as e:
        extracted_text = f"Error reading file: {str(e)}"
        
    return extracted_text, excel_df

def extract_value_using_rule(file_obj, keyword, mode="Exact Word", stop_kw=""):
    """
    सपोर्टिंग फाइल से कीवर्ड के आधार पर पर्टिकुलर वैल्यू ढूंढकर निकालता है
    """
    text, df = extract_data_from_supporting_file(file_obj)
    if not text:
        return ""
        
    lines = text.split("\n")
    raw_t = ""
    
    for line in lines:
        if keyword and keyword.lower() in line.lower():
            start_idx = line.lower().find(keyword.lower()) + len(keyword)
            raw_t = line[start_idx:].strip()
            if raw_t.startswith(":"):
                raw_t = raw_t[1:].strip()
            break
            
    # अगर डायरेक्ट लाइन में नहीं मिला और यह एक्सेल है, तो DF में भी खोज सकते हैं
    if not raw_t and df is not None:
        try:
            for col in df.columns:
                match = df[df[col].astype(str).str.contains(keyword, case=False, na=False)]
                if not match.empty:
                    raw_t = str(match.iloc[0].values[1]) if len(match.columns) > 1 else str(match.iloc[0].values[0])
                    break
        except Exception:
            pass
            
    return raw_t.strip()
