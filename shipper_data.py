st.write("---")
            st.subheader("📁 1. टेम्पलेट फ़ाइल अपलोड")
            
            # सुनिश्चित करें कि डिक्शनरी बनी हुई है
            shipper_info.setdefault("uploaded_files", {})
            has_file = "Full Job Excel Format File" in shipper_info["uploaded_files"] and len(shipper_info["uploaded_files"]["Full Job Excel Format File"]) > 0
            
            if has_file:
                st.success("✅ Blank Full Job Excel Format File अपलोडेड एवं सुरक्षित है.")
                if st.button("🗑️ Delete & Replace Template", key=f"del_tpl_{selected_shipper}"):
                    shipper_info["uploaded_files"]["Full Job Excel Format File"] = b""
                    st.rerun()
            else:
                f_upload = st.file_uploader("➡️ Blank Full Job Excel Format File (Template) अपलोड करें", type=["xlsx", "xls"], key=f"tpl_{selected_shipper}")
                if f_upload:
                    file_bytes = f_upload.getvalue()
                    shipper_info["uploaded_files"]["Full Job Excel Format File"] = file_bytes
                    st.success("टेम्पलेट सफलतापर्पूर्वक लोड हो गया है! अब नीचे 'Save All AI Mapping Rules' बटन दबाएं।")
                    st.rerun()
