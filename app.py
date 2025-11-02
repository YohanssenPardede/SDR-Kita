import streamlit as st
# Mengimpor fungsi dari file app.py dan retail.py
from layouting import show_layouting_content
from retail import show_retail_content

st.set_page_config(
    page_title="SDR Kita",
    layout="wide"
)

def main():
    st.title("SDR Kita")
    
    # Membuat dua tab
    tab1, tab2 = st.tabs(["Menu Layouting", "Menu Retail"])

    with tab1:
        # Memanggil fungsi dari file app.py
        show_layouting_content() 

    with tab2:
        # Memanggil fungsi dari file retail.py
        show_retail_content()

if __name__ == "__main__":
    main()