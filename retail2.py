import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

def show_retail2_content():
    # Definisi Jalur File UoM Manual
    # PASTIKAN FILE INI ADA DI FOLDER YANG SAMA DENGAN app.py atau ganti jalurnya
    FILE_PATH_UOM_MANUAL = 'ZRW12-UoM.XLSX'

    ## 🎯 Fungsi Utama Pemrosesan Data

    @st.cache_data
    def load_and_process_main_data(uploaded_file):
        """Memuat dan memproses data utama dari file Excel."""
        if uploaded_file is None:
            return None
        try:
            new_column_names = [
                'Product Name', 'Material ID', 'Movement Category Retail', 'Min-Max Recommendation Assessment',
                'Avg Picking (Month-1) in Box', 'Avg Last 14 Days in Box', 'Avg Last 3 Days in Box',
                'Stock in Box', 'Xdays'
            ]
            df = pd.read_excel(uploaded_file, skiprows=3, names=new_column_names)
            quantity_cols = [col for col in new_column_names if 'Box' in col]
            for col in quantity_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        except Exception as e:
            st.error(f"Error saat memuat atau memproses file data utama: {e}")
            return None

    @st.cache_data
    def load_uom_data_manual(file_path):
        """Memuat dan memproses data UoM secara manual dari jalur file yang ditentukan."""
        try:
            df_uom = pd.read_excel(file_path)
            if 'Material' not in df_uom.columns or 'UOM(in BUn)' not in df_uom.columns:
                st.error("File UoM tidak memiliki kolom 'Material' dan/atau 'UOM(in BUn)'.")
                return None
            df_uom_unique = df_uom.drop_duplicates(subset=['Material'], keep='first')
            df_uom_unique['UOM(in BUn)'] = pd.to_numeric(df_uom_unique['UOM(in BUn)'], errors='coerce')
            return df_uom_unique
        except FileNotFoundError:
            st.error(f"File UoM tidak ditemukan di folder: **{file_path}**. Mohon periksa jalurnya.")
            return None
        except Exception as e:
            st.error(f"Error saat memuat file UoM: {e}")
            return None

    def calculate_replenishment(df, chosen_avg_column, max_multiplier=1.5):
        """Menghitung Min/Max Replenishment (dalam Box dan Pcs)."""
        df['Min Replenishment'] = df[chosen_avg_column].fillna(0).round().astype(int)
        df['Max Replenishment'] = (df[chosen_avg_column] * max_multiplier).fillna(0).round().astype(int)

        df['Min Replenishment (Pcs)'] = (df['Min Replenishment'] * df['Pcs per Box']).fillna(0).round().astype(int)
        df['Max Replenishment (Pcs)'] = (df['Max Replenishment'] * df['Pcs per Box']).fillna(0).round().astype(int)

        return df

    @st.cache_data
    def convert_df_to_excel(df):
        """Mengubah DataFrame menjadi file Excel dalam format Bytes."""
        output = BytesIO()
        # Menggunakan engine openpyxl untuk format .xlsx
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Replenishment_Analysis')
        
        processed_data = output.getvalue()
        return processed_data

    ## 🚀 Streamlit App
    st.title("📦 Retail Replenishment Min Max Planning")

    col1, col2 = st.columns([1, 2])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload File Retail Warehouse Stock Analysis",
            type=['xlsx']
        )

    with col2:
        df_uom = load_uom_data_manual(FILE_PATH_UOM_MANUAL)
        if df_uom is None:
            st.stop()

    if uploaded_file and df_uom is not None:
        df = load_and_process_main_data(uploaded_file)

        if df is not None:
            st.success("Data Retail Warehouse Stock Analysis berhasil dimuat!")

            # 1. Penggabungan Data (Merge)
            try:
                df = pd.merge(
                    df,
                    df_uom[['Material', 'UOM(in BUn)']],
                    left_on='Material ID',
                    right_on='Material',
                    how='left'
                )
                df.rename(columns={'UOM(in BUn)': 'Pcs per Box'}, inplace=True)
                df.drop(columns=['Material'], inplace=True)
            except Exception as e:
                st.error(f"Gagal saat menggabungkan data UoM: {e}")
                st.stop()

            # --- (Pengaturan Kalkulasi) ---
            st.subheader("⚙️ Pengaturan Kalkulasi")
            
            avg_cols = [col for col in df.columns if 'Avg' in col and 'Box' in col]
            default_index = avg_cols.index('Avg Picking (Month-1) in Box') if 'Avg Picking (Month-1) in Box' in avg_cols else 0
            
            col_calc, col_mult = st.columns(2)
            
            with col_calc:
                chosen_avg_column = st.selectbox(
                    "Pilih Kolom Rata-Rata untuk Basis Kalkulasi Min Replenishment (Box):",
                    avg_cols,
                    index=default_index
                )
            with col_mult:
                max_multiplier = st.slider(
                    "Pengali untuk Max Replenishment:",
                    min_value=1.0,
                    max_value=3.0,
                    value=1.5,
                    step=0.1
                )

            # 2. Kalkulasi Min/Max Replenishment
            # Lakukan kalkulasi sekali dan simpan hasilnya
            df_full_result = calculate_replenishment(df.copy(), chosen_avg_column, max_multiplier)

            # --- FITUR PENCARIAN BARU ---
            st.subheader("🔍 Filter Data Hasil")
            search_query = st.text_input(
                "Cari berdasarkan Material ID atau Product Name:",
                placeholder="Masukkan ID Material atau Nama Produk",
            )

            # Menerapkan Filter
            df_filtered = df_full_result.copy()
            if search_query:
                # Menggunakan .str.contains() untuk pencarian fleksibel (case-insensitive)
                # Material ID diubah ke string untuk pencarian yang konsisten
                mask = (
                    df_filtered['Material ID'].astype(str).str.contains(search_query, case=False, na=False) |
                    df_filtered['Product Name'].str.contains(search_query, case=False, na=False)
                )
                df_filtered = df_filtered[mask]

            # --- Hasil dan Download ---
            st.subheader("✅ Hasil Kalkulasi Replenishment")
            
            # Kolom yang ditampilkan
            # Definisikan kolom yang benar-benar ingin Anda lihat dan unduh
            display_cols = [
                'Product Name', 'Material ID', chosen_avg_column, 'Pcs per Box',
                'Min Replenishment', 'Max Replenishment',
                'Min Replenishment (Pcs)', 'Max Replenishment (Pcs)'
            ]

            # Menampilkan data yang SUDAH DIFILTER
            st.dataframe(df_filtered[display_cols], use_container_width=True)

            st.info(f"Ditampilkan **{len(df_filtered)}** dari total **{len(df_full_result)}** item.")
            
            # Tombol Download
            df_to_download = df_filtered.copy() # Ambil data yang ditampilkan (filtered baris)

            # HANYA AMBIL KOLOM YANG DITAMPILKAN SEBELUM KONVERSI KE EXCEL
            df_to_download = df_to_download[display_cols] 

            excel_data = convert_df_to_excel(df_to_download)

            st.download_button(
                label="📥 Download Hasil Analisis (Excel XLSX)",
                data=excel_data,
                file_name='retail_stock_replenishment_filtered_analysis.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

        else:
            st.warning("Silakan periksa kembali file Data Stok Utama yang diunggah.")

    else:
        st.info("Silakan unggah file Data Retail Warehouse Stock Analysis.")


# Panggil fungsi utama
show_retail2_content()