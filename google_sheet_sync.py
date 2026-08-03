import streamlit as st
import requests
import json
import base64
from io import BytesIO
import openpyxl

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbwYVVWbqNZbzTOujVmip41KlID-rf9zEQLy_JM04ZEhUL-kixwRMD9nbPnOrZ46Fmz3/exec"

def get_val_case_insensitive(d, *keys, default=""):
    if not isinstance(d, dict):
        return default
    d_lower = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        if str(k).lower() in d_lower:
            val = d_lower[str(k).lower()]
            if val is not None:
                return str(val).strip()
    return default

@st.cache_data(show_spinner=False)
def fetch_all_from_sheet():
    """गूगल शीट से डेटा फेच करता है और एरर होने पर डीबग जानकारी देता है"""
    try:
        response = requests.get(f"{WEB_APP_URL}?action=get_data", timeout=20)
        st.write("HTTP STATUS CODE:", response.status_code) # यह देखेगा कि गूगल ने 200 दिया या 404/500
        res_text = response.text.strip()
        st.write("RAW RESPONSE TEXT:", res_text[:200]) # रिस्पांस की पहली 200 लाइनें दिखाएगा
        
        if response.status_code == 200:
            if res_text.startswith("<"):
                st.error("⚠️ गूगल स्क्रिप्ट से HTML पेज आ रहा है, JSON नहीं! URL या डिप्लॉयमेंट चेक करें।")
                return None
            return response.json()
    except Exception as e:
        st.error(f"Request Exception: {str(e)}")
    return None

def clear_sheet_cache():
    fetch_all_from_sheet.clear()

def push_all_to_sheet(shippers_json_payload):
    try:
        payload = {
            "action": "save_shipper_json",
            "shippers_data": shippers_json_payload
        }
        response = requests.post(WEB_APP_URL, data=json.dumps(payload), timeout=30)
        if response.status_code == 200:
            clear_sheet_cache()
            return True
        return False
    except Exception:
        return False

def load_template_bytes_from_sheet(shipper_name):
    data = fetch_all_from_sheet()
    if not data:
        return None
    
    shippers_dict = data.get("shippers", {})
    if shipper_name in shippers_dict:
        s_data = shippers_dict[shipper_name]
        b64_str = s_data.get("file_base64", "")
        if b64_str and len(b64_str.strip()) > 0:
            try:
                clean_b64 = b64_str.lstrip("'").strip().replace(" ", "+")
                missing_padding = len(clean_b64) % 4
                if missing_padding:
                    clean_b64 += '=' * (4 - missing_padding)
                
                decoded_bytes = base64.b64decode(clean_b64)
                if decoded_bytes.startswith(b'PK'):
                    return decoded_bytes
            except Exception:
                pass
    return None

def load_template_from_sheet(shipper_name):
    raw_bytes = load_template_bytes_from_sheet(shipper_name)
    if raw_bytes:
        try:
            return openpyxl.load_workbook(BytesIO(raw_bytes))
        except Exception:
            pass
    return None
