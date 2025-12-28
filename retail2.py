import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# Konfigurasi Halaman
st.set_page_config(
    page_title="Retail Replenishment Min Max Planning",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Definisi Jalur File Manual
FILE_PATH_UOM_MANUAL = 'ZRW12-UoM.XLSX'
FILE_PATH_TEMPLATE_MANUAL = 'NZTW65PA Template.xlsx'

def show_retail2_content():
    
    ## 🎯 Fungsi Utama Pemrosesan Data

    @st.cache_data
    def load_and_process_main_data(uploaded_file):
        """Memuat dan memproses data utama dari file Excel."""
        if uploaded_file is None:
            return None
        try:
            new_column_names = [
                'Product Name', 
                'Material ID', 
                'Movement Category Retail', 
                'Avg Picking (Month-1) in Box', 
                'Avg Last 14 Days in Box', 
                'Avg Last 3 Days in Box',
                'Stock in Box', 
                'Xdays'
            ]
            
            df = pd.read_excel(
                uploaded_file, 
                skiprows=3, 
                names=new_column_names, 
                usecols='A:H'
            ) 
            
            quantity_cols = [col for col in new_column_names if 'Box' in col]
            for col in quantity_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception as e:
            st.error(f"Error saat memuat atau memproses file data utama: {e}.")
            return None

    @st.cache_data
    def load_uom_data_manual(file_path):
        """Memuat dan memproses data UoM secara manual."""
        try:
            df_uom = pd.read_excel(file_path)
            if 'Material' not in df_uom.columns or 'UOM(in BUn)' not in df_uom.columns:
                st.error("File UoM tidak memiliki kolom 'Material' dan/atau 'UOM(in BUn)'.")
                return None
            df_uom_unique = df_uom.drop_duplicates(subset=['Material'], keep='first')
            df_uom_unique['UOM(in BUn)'] = pd.to_numeric(df_uom_unique['UOM(in BUn)'], errors='coerce')
            return df_uom_unique
        except Exception as e:
            st.error(f"Error saat memuat file UoM: {e}")
            return None

    @st.cache_data
    def load_replenishment_template_upload(uploaded_file):
        """Memuat template dari upload."""
        if uploaded_file is None:
            return None
        try:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            if file_extension == 'xls':
                df_template = pd.read_excel(uploaded_file, header=0, engine='xlrd')
            else:
                df_template = pd.read_excel(uploaded_file, header=0) 
            
            if not all(col in df_template.columns for col in ['Material', 'Min', 'Max']):
                st.error("Template harus memiliki kolom: Material, Min, Max")
                return None
            return df_template
        except Exception as e:
            st.error(f"Error template upload: {e}")
            return None

    @st.cache_data
    def load_replenishment_template_manual(file_path):
        """Memuat template secara manual."""
        try:
            df_template = pd.read_excel(file_path, header=0) 
            return df_template
        except Exception as e:
            st.error(f"Error template manual: {e}")
            return None

    def calculate_replenishment(df, chosen_avg_column, min_multiplier=1.0, max_multiplier=1.5):
        """Menghitung Min/Max Replenishment."""
        df['Min Replenishment'] = (df[chosen_avg_column] * min_multiplier).fillna(0).round().astype(int)
        df['Max Replenishment'] = (df[chosen_avg_column] * max_multiplier).fillna(0).round().astype(int)
        df['Min Replenishment (Pcs)'] = (df['Min Replenishment'] * df['Pcs per Box']).fillna(0).round().astype(int)
        df['Max Replenishment (Pcs)'] = (df['Max Replenishment'] * df['Pcs per Box']).fillna(0).round().astype(int)
        return df

    @st.cache_data
    def convert_df_to_excel(df):
        """Konversi DF ke bytes Excel."""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Replenishment_Update')
        return output.getvalue()

    ## 🚀 Streamlit App
    st.title("📦 Retail Replenishment Min Max Planning")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        uploaded_file = st.file_uploader("1. Upload Data Stok Utama (.xlsx)", type=['xlsx'])
    with col2:
        df_uom = load_uom_data_manual(FILE_PATH_UOM_MANUAL)
    with col3:
        st.subheader("Template Min/Max (Opsional)")
        template_mode = st.radio("Pilih Mode Input Template:", ('Upload File', 'Template'), index=0)
        df_template = None
        if template_mode == 'Upload File':
            uploaded_template = st.file_uploader("Upload Template (.xlsx, .xls, .csv)", type=['xlsx', 'xls', 'csv'])
            df_template = load_replenishment_template_upload(uploaded_template)
        else:
            st.info(f"Membaca dari: {FILE_PATH_TEMPLATE_MANUAL}")
            df_template = load_replenishment_template_manual(FILE_PATH_TEMPLATE_MANUAL)

    if uploaded_file and df_uom is not None:
        df_main = load_and_process_main_data(uploaded_file)

        if df_main is not None:
            st.success("Data berhasil dimuat!")

            # 1. Merge UoM
            try:
                df_merged = pd.merge(
                    df_main,
                    df_uom[['Material', 'UOM(in BUn)']],
                    left_on='Material ID',
                    right_on='Material',
                    how='left'
                )
                df_merged.rename(columns={'UOM(in BUn)': 'Pcs per Box'}, inplace=True)
                df_merged.drop(columns=['Material'], inplace=True)
            except Exception as e:
                st.error(f"Gagal Merge UoM: {e}")
                st.stop()

            # --- Pengaturan Kalkulasi ---
            st.subheader("⚙️ Pengaturan Kalkulasi")
            avg_cols = [col for col in df_merged.columns if 'Avg' in col and 'Box' in col]
            default_index = avg_cols.index('Avg Picking (Month-1) in Box') if 'Avg Picking (Month-1) in Box' in avg_cols else 0
            
            c1, c2, c3 = st.columns(3)
            with c1:
                chosen_avg_column = st.selectbox("Basis Rata-Rata:", avg_cols, index=default_index)
            with c2:
                min_mult = st.slider("Pengali Min:", 0.5, 2.0, 1.0, 0.1)
            with c3:
                max_mult = st.slider("Pengali Max:", 1.0, 3.0, 1.5, 0.1)

            # 2. Kalkulasi
            df_full_result = calculate_replenishment(df_merged.copy(), chosen_avg_column, min_mult, max_mult)

            # --- Filter Pencarian ---
            st.subheader("🔍 Filter Data Hasil")
            search_query = st.text_input("Cari Material ID atau Product Name:")
            df_filtered = df_full_result.copy()
            if search_query:
                mask = (df_filtered['Material ID'].astype(str).str.contains(search_query, case=False, na=False) |
                        df_filtered['Product Name'].str.contains(search_query, case=False, na=False))
                df_filtered = df_filtered[mask]

            # --- Tampilan Hasil ---
            st.subheader("✅ Hasil Kalkulasi Replenishment")
            display_cols = ['Product Name', 'Material ID', chosen_avg_column, 'Pcs per Box',
                            'Min Replenishment', 'Max Replenishment', 'Min Replenishment (Pcs)', 'Max Replenishment (Pcs)']
            st.dataframe(df_filtered[display_cols], use_container_width=True)

            # --- Download Logic ---
            if df_template is not None:
                st.subheader("🔄 Pembaruan Template (Filtering Match)")
                
                # Menyiapkan data untuk update
                update_data = df_full_result[['Material ID', 'Min Replenishment (Pcs)', 'Max Replenishment']].copy()
                
                # Konversi kunci ke string untuk memastikan kecocokan 100%
                df_template['Material'] = df_template['Material'].astype(str)
                update_data['Material ID'] = update_data['Material ID'].astype(str)
                
                # 🔥 LOGIKA UTAMA: INNER JOIN (Hanya menyimpan baris yang ada di kedua file)
                # Ini otomatis menghapus baris di template yang tidak ada di data Stok Utama
                df_template_updated = pd.merge(
                    df_template, 
                    update_data, 
                    left_on='Material', 
                    right_on='Material ID', 
                    how='inner' 
                )

                # Update nilai Min dan Max dari hasil kalkulasi
                df_template_updated['Min'] = df_template_updated['Min Replenishment (Pcs)']
                df_template_updated['Max'] = df_template_updated['Max Replenishment']
                
                # Buang kolom bantu hasil join
                df_template_updated = df_template_updated.drop(columns=['Material ID', 'Min Replenishment (Pcs)', 'Max Replenishment'], errors='ignore')
                
                st.write(f"Baris Template setelah difilter: {len(df_template_updated)} baris.")
                st.dataframe(df_template_updated.head(10), use_container_width=True)
                
                df_download = df_template_updated
                file_name = 'retail_replenishment_TEMPLATE_MATCHED.xlsx'
            else:
                df_download = df_filtered[display_cols]
                file_name = 'analysis_result.xlsx'

            st.download_button(
                label="📥 Download Excel",
                data=convert_df_to_excel(df_download),
                file_name=file_name,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
    else:
        st.info("Silakan unggah file Data Retail Warehouse Stock Analysis.")

show_retail2_content()
