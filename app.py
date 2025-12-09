import streamlit as st
# Mengimpor fungsi dari file app.py dan retail.py
from retail import show_retail1_content
from retail2 import show_retail2_content

st.set_page_config(
    page_title="SDR Kita",
    layout="wide"
)

def main():
    st.title("SDR Kita")
    
    # Membuat dua tab
    tab1 = st.tabs(["Retail by Min-Max"])

    # with tab1:
    #     # Memanggil fungsi dari file app.py
    #     show_retail1_content() 

    with tab1:
        # Memanggil fungsi dari file retail.py
        show_retail2_content()

if __name__ == "__main__":
    main()


