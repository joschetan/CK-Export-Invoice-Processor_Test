import streamlit as st

def render_manage_buttons():
    st.header("⚙️ Manage Specific Upload Buttons")
    st.caption("यहाँ बनाए गए ऑप्शन्स पर्टिकुलर शिपर प्रोफाइल में फ़ाइल अपलोड बटन्स के रूप में दिखाई देंगे।")
    
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        new_type = st.text_input("नया डॉक्यूमेंट बटन का नाम लिखें:", placeholder="जैसे: Extra Annexure, License Copy")
    with col_btn:
        st.write("##")
        if st.button("➕ Add Type"):
            if new_type.strip() != "" and new_type not in st.session_state["master_types"]:
                st.session_state["master_types"].append(new_type.strip())
                st.success(f"'{new_type}' लिस्ट में जुड़ गया है!")
                st.rerun()

    st.write("#### वर्तमान में उपलब्ध ऑप्शंस:")
    for t in st.session_state["master_types"]:
        c1, c2 = st.columns([4, 1])
        c1.text(f"🔹 {t}")
        if c2.button(f"❌ Remove", key=f"del_{t}"):
            st.session_state["master_types"].remove(t)
            st.rerun()
