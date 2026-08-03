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
    """गूगल शीट के 'Shipper_JSON_Database' से JSON डेटा और टेम्पलेट्स फेच करता है"""
    try:
        response = requests.get(f"{WEB_APP_URL}?action=get_data", timeout=20)
        if response.status_code == 200:
            res_text = response.text.strip()
            if res_text.startswith("<"):
                return None
            return response.json()
    except Exception:
        pass
    return None

def clear_sheet_cache():
    fetch_all_from_sheet.clear()

def push_all_to_sheet(shippers_json_payload):
    """बड़ी फाइलों को 50 KB के टुकड़ों (Chunks) में बांटकर गूगल शीट पर भेजता है"""
    try:
        # 1. पहले बड़ी फाइल Base64 को चंक्स में भेजें ताकि Apps Script का CHUNK_STORE उसे पकड़ सके
        for shipper_name, shipper_obj in shippers_json_payload.items():
            b64_str = shipper_obj.get("file_base64", "")
            if b64_str and len(b64_str) > 50000:  # अगर फाइल 50KB से बड़ी है तो चंकिंग करें
                init_payload = {"action": "init_chunk", "shipper": shipper_name}
                requests.post(WEB_APP_URL, data=json.dumps(init_payload), timeout=30)
                
                chunk_size = 50000
                for i in range(0, len(b64_str), chunk_size):
                    chunk_piece = b64_str[i:i + chunk_size]
                    chunk_payload = {
                        "action": "append_chunk",
                        "shipper": shipper_name,
                        "chunk": chunk_piece
                    }
                    requests.post(WEB_APP_URL, data=json.dumps(chunk_payload), timeout=30)
                
                # पाइथन साइड से temporary base_64 खाली कर दें क्योंकि वह चंक के जरिए सर्वर पर जुड़ चुका है
                shipper_obj["file_base64"] = ""

        # 2. अंत में सारे JSON रूल्स और सेव करने की फाइनल कमांड भेजें
        payload = {
            "action": "save_shipper_json",
            "shippers_data": shippers_json_payload
        }
        response = requests.post(WEB_APP_URL, data=json.dumps(payload), timeout=120)
        if response.status_code == 200:
            clear_sheet_cache()
            return True
        return False
    except Exception:
        return False

def load_template_bytes_from_sheet(shipper_name):
    """गूगल शीट के कॉलम C से शिपर की Base64 फाइल को डिकोड करके बाइट्स लौटाता है"""
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
