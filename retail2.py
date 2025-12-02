import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# Konfigurasi Halaman (Dipindahkan ke luar fungsi untuk dijalankan sekali)
st.set_page_config(
    page_title="Retail Replenishment Min Max Planning",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Definisi Jalur File UoM Manual (tetap sama)
FILE_PATH_UOM_MANUAL = 'ZRW12-UoM.XLSX'

# 🔥 Definisi Jalur File Template Manual (BARU)
FILE_PATH_TEMPLATE_MANUAL = 'NZTW65PA Template.xlsx'


def show_retail2_content():
    
    ## 🎯 Fungsi Utama Pemrosesan Data

    @st.cache_data
    def load_and_process_main_data(uploaded_file):
        """Memuat dan memproses data utama dari file Excel."""
        if uploaded_file is None:
            return None
        try:
            # DAFTAR 8 KOLOM YANG DIPERBARUI
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
            
            # usecols='A:H' digunakan untuk memastikan hanya 8 kolom (A hingga H) yang dibaca
            df = pd.read_excel(
                uploaded_file, 
                skiprows=3, 
                names=new_column_names, 
                usecols='A:H'
            ) 
            
            # Konversi tipe data untuk kolom kuantitas
            quantity_cols = [col for col in new_column_names if 'Box' in col]
            for col in quantity_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception as e:
            st.error(f"Error saat memuat atau memproses file data utama: {e}. Pastikan file memiliki 8 kolom yang dimulai dari baris ke-4.")
            return None

    @st.cache_data
    def load_uom_data_manual(file_path):
        """Memuat dan memproses data UoM secara manual dari file yang ditentukan."""
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

    # Fungsi untuk memuat template dari UPLOAD
    @st.cache_data
    def load_replenishment_template_upload(uploaded_file):
        """Memuat dan memproses data template replenishment dari file Excel/CSV yang diunggah."""
        if uploaded_file is None:
            return None
        try:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            # 🔥 Perbaikan: Tentukan engine secara eksplisit
            if file_extension == 'xls':
                try:
                    # Menggunakan engine xlrd untuk format Excel lama (.xls).
                    df_template = pd.read_excel(uploaded_file, header=0, engine='xlrd')
                except ImportError:
                    # Jika xlrd tidak ada, lemparkan Exception custom yang akan ditangkap di luar
                    raise Exception("Missing optional dependency 'xlrd'. Untuk membaca file .xls, Anda harus menginstalnya atau mengubah format file menjadi .xlsx.")
                except ValueError as ve:
                    # Tangani error file bukan zip/format tidak terbaca oleh xlrd
                    raise Exception(f"File .xls tidak dapat dibaca: {ve}. Coba simpan ulang file sebagai .xlsx.")

            elif file_extension == 'xlsx':
                # Menggunakan engine openpyxl untuk format Excel baru (.xlsx).
                df_template = pd.read_excel(uploaded_file, header=0, engine='openpyxl')
            else:
                # Untuk CSV atau format lain, biarkan Pandas menentukan
                df_template = pd.read_excel(uploaded_file, header=0, engine=None) 

            
            required_cols = ['Material', 'Min', 'Max']
            if not all(col in df_template.columns for col in required_cols):
                st.error(f"Template harus memiliki kolom: {', '.join(required_cols)}")
                return None
            return df_template
        except Exception as e:
            st.error(f"Error saat memuat file template dari upload: {e}")
            return None

    # Fungsi baru untuk memuat template secara MANUAL
    @st.cache_data
    def load_replenishment_template_manual(file_path):
        """Memuat dan memproses data template replenishment dari jalur file yang ditentukan."""
        try:
            # Tetapkan engine openpyxl untuk kompatibilitas yang lebih baik
            df_template = pd.read_excel(file_path, header=0, engine='openpyxl') 
            
            required_cols = ['Material', 'Min', 'Max']
            if not all(col in df_template.columns for col in required_cols):
                st.error(f"Template manual harus memiliki kolom: {', '.join(required_cols)}")
                return None
            return df_template
        except FileNotFoundError:
            st.error(f"File template manual tidak ditemukan di jalur: **{file_path}**. Harap letakkan file tersebut di direktori yang sama atau ganti jalurnya.")
            return None
        except Exception as e:
            st.error(f"Error saat memuat file template manual: {e}")
            return None


    # 🔥 PERUBAHAN FUNGSI: Menambahkan min_multiplier
    def calculate_replenishment(df, chosen_avg_column, min_multiplier=1.0, max_multiplier=1.5):
        """Menghitung Min/Max Replenishment (dalam Box dan Pcs)."""
        # Min Replenishment sekarang menggunakan slider
        df['Min Replenishment'] = (df[chosen_avg_column] * min_multiplier).fillna(0).round().astype(int)
        df['Max Replenishment'] = (df[chosen_avg_column] * max_multiplier).fillna(0).round().astype(int)

        df['Min Replenishment (Pcs)'] = (df['Min Replenishment'] * df['Pcs per Box']).fillna(0).round().astype(int)
        df['Max Replenishment (Pcs)'] = (df['Max Replenishment'] * df['Pcs per Box']).fillna(0).round().astype(int)

        return df

    @st.cache_data
    def convert_df_to_excel(df):
        """Mengubah DataFrame menjadi file Excel dalam format Bytes."""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Penulisan ke Excel: Headers akan mempertahankan nama kolom DataFrame (yaitu header template)
            df.to_excel(writer, index=False, sheet_name='Replenishment_Update')
        
        processed_data = output.getvalue()
        return processed_data

    ## 🚀 Streamlit App
    st.title("📦 Retail Replenishment Min Max Planning")

    # --- Uploader Layout ---
    col1, col2, col3 = st.columns([1, 1, 1])

    # KOLOM 1: Data Stok Utama
    with col1:
        uploaded_file = st.file_uploader(
            "1. Upload Data Retail Warehouse Stock Analysis (.xlsx)",
            type=['xlsx']
        )
    # KOLOM 2: Data UoM (Manual)
    with col2:
        # st.info(f"2. Data UoM dibaca otomatis dari: \n`{FILE_PATH_UOM_MANUAL}`")
        df_uom = load_uom_data_manual(FILE_PATH_UOM_MANUAL)
        if df_uom is None:
            st.stop()
    # KOLOM 3: Template (Pilihan Upload atau Manual)
    with col3:
        st.subheader("Template Min/Max (Opsional)")
        template_mode = st.radio(
            "Pilih Mode Input Template:",
            ('Upload File', 'Template'),
            index=0
        )
        
        df_template = None
        
        if template_mode == 'Upload File':
            uploaded_template = st.file_uploader(
                "Upload Template Min/Max (.xlsx, .xls, .csv)",
                type=['xlsx', 'xls', 'csv']
            )
            df_template = load_replenishment_template_upload(uploaded_template)
        
        elif template_mode == 'Template':
            st.info(f"Membaca dari: \n`{FILE_PATH_TEMPLATE_MANUAL}`")
            df_template = load_replenishment_template_manual(FILE_PATH_TEMPLATE_MANUAL)

    # --- Logika Utama ---
    if uploaded_file and df_uom is not None:
        df = load_and_process_main_data(uploaded_file)

        if df is not None:
            st.success("Data berhasil dimuat!")

            # 1. Penggabungan Data (Merge UoM)
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
                # st.info("Data UoM telah berhasil digabungkan (Merged).")
            except Exception as e:
                st.error(f"Gagal saat menggabungkan data UoM: {e}")
                st.stop()

            # --- (Pengaturan Kalkulasi) ---
            st.subheader("⚙️ Pengaturan Kalkulasi")
            
            avg_cols = [col for col in df.columns if 'Avg' in col and 'Box' in col]
            default_index = avg_cols.index('Avg Picking (Month-1) in Box') if 'Avg Picking (Month-1) in Box' in avg_cols else 0
            
            col_calc, col_mult_min, col_mult_max = st.columns(3)

            with col_calc:
                chosen_avg_column = st.selectbox(
                    "Basis Rata-Rata Replenishment (Box):",
                    avg_cols,
                    index=default_index
                )
            
            with col_mult_min:
                min_multiplier = st.slider(
                    "Pengali untuk Min Replenishment:",
                    min_value=0.5,
                    max_value=2.0,
                    value=1.0,
                    step=0.1,
                    help="Min Replenishment = Basis Rata-Rata * Pengali ini"
                )

            with col_mult_max:
                max_multiplier = st.slider(
                    "Pengali untuk Max Replenishment:",
                    min_value=1.0,
                    max_value=3.0,
                    value=1.5,
                    step=0.1
                )

            # 2. Kalkulasi Min/Max Replenishment
            df_full_result = calculate_replenishment(df.copy(), chosen_avg_column, min_multiplier, max_multiplier)

            # --- FITUR PENCARIAN ---
            st.subheader("🔍 Filter Data Hasil")
            search_query = st.text_input(
                "Cari berdasarkan Material ID atau Product Name:",
                placeholder="Masukkan ID Material atau Nama Produk",
            )

            # Menerapkan Filter Baris
            df_filtered = df_full_result.copy()
            if search_query:
                mask = (
                    df_filtered['Material ID'].astype(str).str.contains(search_query, case=False, na=False) |
                    df_filtered['Product Name'].str.contains(search_query, case=False, na=False)
                )
                df_filtered = df_filtered[mask]

            # --- Hasil & Download ---
            st.subheader("✅ Hasil Kalkulasi Replenishment")
            
            # Kolom yang ditampilkan
            display_cols = [
                'Product Name', 'Material ID', chosen_avg_column, 'Pcs per Box',
                'Min Replenishment', 'Max Replenishment',
                'Min Replenishment (Pcs)', 'Max Replenishment (Pcs)'
            ]

            # Menampilkan data yang SUDAH DIFILTER BARIS
            st.dataframe(df_filtered[display_cols], use_container_width=True)

            st.info(f"Ditampilkan **{len(df_filtered)}** dari total **{len(df_full_result)}** item.")
            
            # Tombol Download Logic
            df_to_download = df_filtered.copy()
            file_name = 'retail_stock_replenishment_filtered_analysis.xlsx'
            download_label = "📥 Download Hasil Analisis (Excel XLSX)"

            # LOGIKA PEMBARUAN TEMPLATE (Jika template berhasil dimuat)
            if df_template is not None:
                st.subheader("🔄 Template Diperbarui Siap Diunduh")
                
                # 1. Pilih kolom yang dibutuhkan dari hasil analisis
                update_data = df_full_result[['Material ID', 'Min Replenishment (Pcs)', 'Max Replenishment']].copy()
                
                # 2. Gabungkan template dengan hasil analisis (menggunakan Material ID = Material)
                df_template_merged = pd.merge(
                    df_template, 
                    update_data, 
                    left_on='Material', 
                    right_on='Material ID', 
                    how='left'
                )

                # 3. Timpa kolom Min dan Max jika ada nilai baru (non-NaN)
                df_template_merged['Min'] = df_template_merged['Min Replenishment (Pcs)'].combine_first(df_template_merged['Min'])
                df_template_merged['Max'] = df_template_merged['Max Replenishment'].combine_first(df_template_merged['Max'])
                
                # 4. Bersihkan kolom bantu dan siapkan untuk download
                df_template_updated = df_template_merged.drop(columns=['Material ID', 'Min Replenishment (Pcs)', 'Max Replenishment'], errors='ignore')
                
                st.write("Preview Template yang Diperbarui (10 baris pertama):")
                st.dataframe(df_template_updated.head(10), use_container_width=True) 
                
                # Set data yang akan diunduh sebagai template yang diperbarui
                df_to_download = df_template_updated.copy()
                file_name = 'retail_replenishment_TEMPLATE_UPDATED.xlsx'
                download_label = "📥 Download Template Excel yang Diperbarui"
            else:
                # Filter kolom untuk hasil analisis jika tidak ada template
                df_to_download = df_to_download[display_cols]
            
            # Button Download
            excel_data = convert_df_to_excel(df_to_download)

            st.download_button(
                label=download_label,
                data=excel_data,
                file_name=file_name,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

        else:
            st.warning("Silakan periksa kembali file Data Stok Utama yang diunggah.")

    else:
        st.info("Silakan unggah file Data Retail Warehouse Stock Analysis.")


# Panggil fungsi utama
show_retail2_content()



