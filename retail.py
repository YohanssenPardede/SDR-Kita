import streamlit as st
import pandas as pd
import io
import numpy as np
import os # Tambahkan modul os untuk pengecekan file

# Tentukan nama file statis
PROCESSED_DATA_FILE = '2025-11-02T15-57_export (1).csv'
UOM_DATA_FILE = 'ZRW12-UoM.XLSX'

# Fungsi untuk memuat file CSV hasil proses secara otomatis (di-cache agar cepat)
@st.cache_data
def load_processed_data(file_path):
    """Memuat data hasil proses dari file."""
    if not os.path.exists(file_path):
        st.error(f"File dataset tidak ditemukan: **{file_path}**")
        return pd.DataFrame()
    try:
        df = pd.read_csv(file_path)
        # Konversi ulang tipe data yang mungkin berubah setelah disimpan/dibaca
        if 'Material ID' in df.columns:
            df['Material ID'] = df['Material ID'].astype('Int64', errors='ignore')
        return df
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memuat file dataset: {e}")
        return pd.DataFrame()

# Fungsi untuk memuat file UoM secara otomatis (di-cache agar cepat)
@st.cache_data
def load_uom_data(file_path):
    """Memuat data UoM dari file XLSX statis."""
    if not os.path.exists(file_path):
        st.error(f"File UoM statis tidak ditemukan: **{file_path}**")
        return pd.DataFrame()
    try:
        return pd.read_excel(file_path)
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memuat file UoM statis: {e}")
        return pd.DataFrame()


def show_retail_content():
    st.title("📦 Replenishment Retail")
    st.markdown("Aplikasi untuk menganalisis kuantitas replenishment retail berdasarkan interval waktu.")
    
    @st.cache_data
    def get_time_interval(hour):
        """Menentukan interval waktu berdasarkan jam pembuatan."""
        if 7 <= hour < 9:
            return '07:00-09:00'
        elif 9 <= hour < 11:
            return '09:00-11:00'
        elif 11 <= hour < 13:
            return '11:00-13:00'
        elif 13 <= hour < 15:
            return '13:00-15:00'
        elif 15 <= hour < 17:
            return '15:00-17:00'
        elif 17 <= hour < 19:
            return '17:00-19:00'
        elif 19 <= hour < 21:
            return '19:00-21:00'
        else:
            return 'Other'

    @st.cache_data
    def convert_to_box_final(row):
        """Mengkonversi kuantitas Min, Max, dan Avg ke unit BOX."""
        min_qty = row['Min Total Quantity']
        max_qty = row['Max Total Quantity']
        avg_qty = row['Average Total Quantity']
        original_uom = row['UOM']
        conversion_to_pcs = row['Conversion_to_PCS']
        
        if pd.isna(original_uom) or pd.isna(conversion_to_pcs) or conversion_to_pcs <= 0:
            return np.nan, np.nan, np.nan 
        elif original_uom == 'BOX':
            return min_qty, max_qty, avg_qty
        elif original_uom == 'PCS':
            min_qty_box = min_qty / conversion_to_pcs
            max_qty_box = max_qty / conversion_to_pcs
            avg_qty_box = avg_qty / conversion_to_pcs
            return min_qty_box, max_qty_box, avg_qty_box
        else:
            return np.nan, np.nan, np.nan

    @st.cache_data
    def process_raw_data(df, df_uom):
        """Fungsi utama untuk memproses data mentah (di-cache agar cepat)."""
        st.info("Memproses data mentah. Ini mungkin memakan waktu beberapa detik...")
        
        # 1. Filter Data Awal
        df_filtered = df[df['Storage Type Suggestion'] == 'ZYY'].copy()

        if df_filtered.empty:
            st.warning("Tidak ada data ditemukan untuk 'Storage Type Suggestion' = 'ZYY'.")
            return pd.DataFrame()

        # 2. Pembersihan & Pembuatan Kolom Waktu
        df_filtered['Confirm 1 Time'] = pd.to_datetime(df_filtered['Confirm 1 Time'], errors='coerce')
        df_filtered['Created Time'] = pd.to_datetime(df_filtered['Created Time'], format='%H:%M:%S', errors='coerce')
        df_filtered['Created Hour'] = df_filtered['Created Time'].dt.hour
        df_filtered['Time Interval'] = df_filtered['Created Hour'].apply(get_time_interval)
        excel_epoch = pd.to_datetime('1899-12-30')
        df_filtered['Created Date'] = pd.to_datetime(df_filtered['Created Date'], unit='D', origin=excel_epoch, errors='coerce')
        df_filtered['Material ID'] = df_filtered['Material ID'].astype(float)

        # **Ekstrak Material ID dan Material Desc**
        material_desc_info = df_filtered[['Material ID', 'Material Desc']].copy().drop_duplicates(subset=['Material ID'])
        
        # 3. Hitung Kuantitas Total Harian per Interval
        daily_quantity_by_interval = df_filtered.groupby(['Material ID', 'Created Date', 'Time Interval'])['TO Dummy Quantity'].sum().reset_index()

        # 4. Hitung Min, Max, dan Rata-rata Total Harian per Material dan Interval
        quantity_by_interval = daily_quantity_by_interval.groupby(['Material ID', 'Time Interval'])['TO Dummy Quantity'].agg(['min', 'max', 'mean']).reset_index()
        quantity_by_interval.columns = ['Material ID', 'Time Interval', 'Min Total Quantity', 'Max Total Quantity', 'Average Total Quantity']

        # 5. Gabungkan Material Desc ke Data Kuantitas
        quantity_by_interval = pd.merge(quantity_by_interval, material_desc_info, on='Material ID', how='left')

        # 6. Pembersihan dan Persiapan Data UoM
        df_uom_cleaned = df_uom[['Material', 'UOM(in BUn)']].copy()
        df_uom_cleaned.columns = ['Material ID', 'Conversion_to_PCS']
        df_uom_cleaned.dropna(subset=['Material ID', 'Conversion_to_PCS'], inplace=True)
        df_uom_cleaned['Material ID'] = df_uom_cleaned['Material ID'].astype(float)
        uom_info_from_df = df_filtered[['Material ID', 'UOM Actual']].copy().drop_duplicates()
        uom_info_from_df.columns = ['Material ID', 'UOM']
        df_uom_cleaned = pd.merge(df_uom_cleaned, uom_info_from_df, on='Material ID', how='left').drop_duplicates(subset=['Material ID', 'UOM', 'Conversion_to_PCS'])

        # 7. Gabungkan Data Kuantitas dan UoM
        quantity_by_interval_merged = pd.merge(
            quantity_by_interval, 
            df_uom_cleaned[['Material ID', 'Conversion_to_PCS', 'UOM']], 
            on='Material ID', 
            how='left'
        )
        quantity_by_interval_unique = quantity_by_interval_merged.groupby(['Material ID', 'Time Interval']).first().reset_index()

        # 8. Konversi ke BOX
        quantity_by_interval_unique[['Min Total Quantity (BOX)', 'Max Total Quantity (BOX)', 'Average Total Quantity (BOX)']] = quantity_by_interval_unique.apply(
            lambda row: pd.Series(convert_to_box_final(row)), axis=1
        )
        
        # Pembersihan akhir
        quantity_by_interval_unique['Material ID'] = quantity_by_interval_unique['Material ID'].astype('Int64')
        result_df = quantity_by_interval_unique.sort_values(by='Average Total Quantity (BOX)', ascending=False).round(2)
        
        st.success("Pemrosesan data selesai!")
        return result_df

    # --- Pilihan Unggah (Dipindahkan ke Menu Utama) ---
    st.header("⬆️ Unggah Data")

    with st.expander("Pilih Mode Unggah dan Masukkan File", expanded=True):
        col_mode, col_file1, col_file2 = st.columns(3)
        
        with col_mode:
            upload_option = st.radio(
                "1. Mode Unggah:",
                (
                    'Pilihan Dataset (Oktober 2025)', # Diubah dari 'Unggah File Hasil Proses (.csv/.xlsx)'
                    'Unggah File Mentah (ZRW70)' # Diubah dan ZRW12 dihapus
                ),
                key='upload_mode'
            )
        
        df_final = pd.DataFrame()
        
        # --- LOGIKA UNGGAH FILE MENTAH (ZRW70) ---
        if upload_option == 'Unggah File Mentah (ZRW70)': 
            with col_file1:
                uploaded_file_data = st.file_uploader(
                    "2. Unggah File Excel Data (ZRW70 Oktober.xlsx)", 
                    type=['xlsx']
                )
            # col_file2 tidak digunakan karena file UoM dimuat statis

            # Memuat file UoM secara statis
            df_uom = load_uom_data(UOM_DATA_FILE) 

            if uploaded_file_data and not df_uom.empty:
                try:
                    df = pd.read_excel(uploaded_file_data)
                    st.success(f"File UoM (**{UOM_DATA_FILE}**) berhasil dimuat dari data statis.")
                    df_final = process_raw_data(df, df_uom)
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat membaca atau memproses file mentah: {e}")
            elif uploaded_file_data and df_uom.empty:
                 st.warning(f"File UoM ({UOM_DATA_FILE}) tidak dapat dimuat. Unggah data mentah dibatalkan.")

        # --- LOGIKA PILIHAN DATASET (HASIL PROSES) ---
        elif upload_option == 'Pilihan Dataset (Oktober 2025)': # Logika memuat statis

            df_final = load_processed_data(PROCESSED_DATA_FILE)
            
            if not df_final.empty:
                # Menggunakan st.session_state untuk menyimpan df_final
                st.session_state.df_final = df_final.copy()
                st.success(f"Dataset **Oktober 2025** berhasil dimuat! ({len(df_final)} baris)")


    # --- Tampilan Utama dan Filter ---

    if not df_final.empty:
        
        st.header("📊 Replenishment Planning")
        st.markdown("---")

        # Kolom untuk menempatkan Filter di atas tabel
        col_interval, col_material = st.columns(2)

        with col_interval:
            # 1. Filter Interval Waktu
            unique_intervals = sorted(df_final['Time Interval'].unique())
            time_filter_options = ['Semua Interval'] + unique_intervals
            selected_interval = st.selectbox(
                "Filter berdasarkan Interval Waktu:",
                time_filter_options
            )
        
        with col_material:
            # 2. Pencarian Material ID/Description (Pencarian dilakukan pada kedua kolom)
            search_material = st.text_input(
                "Cari Material ID/Description:",
                help="Masukkan ID (contoh: 10105) atau Deskripsi (contoh: BOX KARTON)"
            )

        # Aplikasikan Filter
        df_display = df_final.copy()

        # Filter Interval Waktu
        if selected_interval != 'Semua Interval':
            df_display = df_display[df_display['Time Interval'] == selected_interval]
        
        # Filter Material ID/Description
        if search_material:
            # Cari di kolom Material ID (setelah diubah jadi string) ATAU Material Desc
            search_mask = (df_display['Material ID'].astype(str).str.contains(search_material, case=False, na=False)) | \
                        (df_display['Material Desc'].astype(str).str.contains(search_material, case=False, na=False))
            df_display = df_display[search_mask]
            
        
        # --- Tampilan DataFrame Hasil ---
        
        st.write(f"""
            Tabel menampilkan data yang telah difilter. Klik header kolom di tabel untuk mengurutkan data.
        """)
        
        cols_to_display = [
            'Material ID', 
            'Material Desc', 
            'Time Interval', 
            'UOM',
            'Min Total Quantity (BOX)', 
            'Max Total Quantity (BOX)', 
            'Average Total Quantity (BOX)'
        ]
        
        # Pastikan semua kolom yang akan ditampilkan ada di df_display
        cols_to_display = [col for col in cols_to_display if col in df_display.columns]

        st.dataframe(df_display[cols_to_display], use_container_width=True)

        
        st.info(f"**Total Baris Hasil:** {len(df_final)} | **Material ID Ditampilkan:** {df_display['Material ID'].nunique()}")

        # --- Download Hasil Proses ---
        st.subheader("Unduh Hasil Proses")

        @st.cache_data
        def convert_df_to_excel(df):
            """Konversi DataFrame ke format Excel dalam memori (BytesIO)."""
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='ReplenishmentData')
            # Dapatkan bytes dari buffer
            processed_data = output.getvalue()
            return processed_data

        excel_data = convert_df_to_excel(df_final)

        st.download_button(
            label="📥 Unduh Data Hasil Proses Lengkap (Excel)",
            data=excel_data,
            file_name='Analisis_Material_Interval_ZYY_Hasil_Lengkap.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            help="Data hasil lengkap (sebelum difilter) termasuk Material Desc dalam format Excel (.xlsx)."
        )

    else:
        st.info("👆 Silakan pilih mode unggah dan masukkan file di bagian **Unggah Data** di atas.")