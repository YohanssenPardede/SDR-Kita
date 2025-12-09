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
    
    # Unpack the list returned by st.tabs() into a single variable
    tab1_container, = st.tabs(["Retail by Min-Max"])

    with tab1_container: # Use the unpacked container variable
        # Memanggil fungsi dari file retail.py
        show_retail2_content()

if __name__ == "__main__":
    main()



