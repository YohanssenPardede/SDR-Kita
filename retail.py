import streamlit as st
import pandas as pd
import io
import numpy as np
import os 

# Tentukan nama file statis
PROCESSED_DATA_FILE = '2025-11-02T15-57_export.xlsx'
UOM_DATA_FILE = 'ZRW12-UoM.XLSX'

# Fungsi untuk memuat file CSV hasil proses secara otomatis (di-cache agar cepat)
@st.cache_data
def load_processed_data(file_path):
    """Memuat data hasil proses dari file."""
    if not os.path.exists(file_path):
        st.error(f"File dataset tidak ditemukan: **{file_path}**")
        return pd.DataFrame()
    try:
        df = pd.read_excel(file_path)
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
        # Menggunakan dummy data UoM jika file tidak ada
        return pd.DataFrame({
             'Material': [1010513.0, 1010514.0, 1010515.0, 1010516.0], 
             'UOM(in BUn)': [12.0, 1.0, 12.0, 12.0]
           })
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
        if 7 <= hour < 9: return '07:00-09:00'
        elif 9 <= hour < 11: return '09:00-11:00'
        elif 11 <= hour < 13: return '11:00-13:00'
        elif 13 <= hour < 15: return '13:00-15:00'
        elif 15 <= hour < 17: return '15:00-17:00'
        elif 17 <= hour < 19: return '17:00-19:00'
        elif 19 <= hour < 21: return '19:00-21:00'
        else: return 'Other'

    @st.cache_data
    def convert_to_box_final(row):
        """Mengkonversi kuantitas Min, Max, dan Avg ke unit BOX."""
        avg_qty = row['Average Total Quantity']
        min_qty = row['Min Total Quantity']
        max_qty = row['Max Total Quantity']
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
        """Fungsi utama untuk memproses data mentah (df_uom diambil dari database)."""
        st.info("Memproses data mentah. Ini mungkin memakan waktu beberapa detik...")
        
        # 1. Filter Data Awal
        # Tambahkan 'Movement Type' ke dalam proses data jika ada di kolom mentah
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
        
        # Kolom yang akan digabungkan ke hasil akhir
        merge_cols = ['Material ID', 'Material Desc']
        if 'Movement Type' in df_filtered.columns:
            merge_cols.append('Movement Type')
        
        # **Ekstrak Material ID, Material Desc, dan Movement Type (jika ada)**
        material_info = df_filtered[merge_cols].copy().drop_duplicates(subset=['Material ID', 'Movement Type'] if 'Movement Type' in df_filtered.columns else ['Material ID'])
        
        # 3. Hitung Kuantitas Total Harian per Interval
        group_keys = ['Material ID', 'Created Date', 'Time Interval']
        if 'Movement Type' in df_filtered.columns:
            group_keys.append('Movement Type')
            
        daily_quantity_by_interval = df_filtered.groupby(group_keys)['TO Dummy Quantity'].sum().reset_index()

        # 4. Hitung Min, Max, dan Rata-rata Total Harian per Material dan Interval
        group_keys_agg = ['Material ID', 'Time Interval']
        if 'Movement Type' in daily_quantity_by_interval.columns:
            group_keys_agg.append('Movement Type')
            
        quantity_by_interval = daily_quantity_by_interval.groupby(group_keys_agg)['TO Dummy Quantity'].agg(['min', 'max', 'mean']).reset_index()
        quantity_by_interval.columns = group_keys_agg + ['Average Total Quantity', 'Min Total Quantity', 'Max Total Quantity']

        # 5. Gabungkan Material Desc & Movement Type ke Data Kuantitas
        quantity_by_interval = pd.merge(quantity_by_interval, material_info, on=['Material ID', 'Movement Type'] if 'Movement Type' in material_info.columns else ['Material ID'], how='left')

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
        
        # Tentukan kunci unik untuk groupby
        unique_keys = ['Material ID', 'Time Interval']
        if 'Movement Type' in quantity_by_interval_merged.columns:
            unique_keys.append('Movement Type')
            
        quantity_by_interval_unique = quantity_by_interval_merged.groupby(unique_keys).first().reset_index()

        # 8. Konversi ke BOX
        quantity_by_interval_unique[[ 'Min Total Quantity (BOX)', 'Max Total Quantity (BOX)', 'Average Total Quantity (BOX)']] = quantity_by_interval_unique.apply(
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
                    'Pilihan Dataset (Oktober 2025)',
                    'Unggah File Mentah (ZRW70)'
                ),
                key='upload_mode'
            )
        
        df_final = pd.DataFrame()
        
        # --- LOGIKA UNGGAH FILE MENTAH (ZRW70) ---
        if upload_option == 'Unggah File Mentah (ZRW70)': 
            with col_file1:
                uploaded_file_data = st.file_uploader(
                    "2. Unggah File Excel Data (ZRW70)", 
                    type=['xlsx']
                )

            df_uom = load_uom_data(UOM_DATA_FILE) 
            
            if uploaded_file_data and not df_uom.empty:
                try:
                    df = pd.read_excel(uploaded_file_data)
                    with col_file2:
                        st.success(f"File UoM (**{UOM_DATA_FILE}**) berhasil dimuat dari data statis.")
                    df_final = process_raw_data(df, df_uom)
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat membaca atau memproses file mentah: {e}")
            elif uploaded_file_data and df_uom.empty:
                 st.warning(f"File UoM ({UOM_DATA_FILE}) tidak dapat dimuat. Unggah data mentah dibatalkan.")

        # --- LOGIKA PILIHAN DATASET (HASIL PROSES) ---
        elif upload_option == 'Pilihan Dataset (Oktober 2025)':

            df_final = load_processed_data(PROCESSED_DATA_FILE)
            
            if not df_final.empty:
                # Perlu memastikan 'Movement Type' ada jika Anda menggunakan dataset statis
                # Jika dataset statis tidak memiliki kolom 'Movement Type', filter tidak akan muncul.
                if 'Movement Type' not in df_final.columns:
                    # Tambahkan kolom dummy jika tidak ada, agar filter tidak error jika digunakan
                    df_final['Movement Type'] = '999' # Nilai dummy
                    
                st.session_state.df_final = df_final.copy()
                with col_file1:
                    st.success(f"Dataset **Oktober 2025** berhasil dimuat! ({len(df_final)} baris)")


    # --- Tampilan Utama dan Filter ---

    if not df_final.empty:
        
        st.header("📊 Replenishment Planning")
        st.markdown("---")

        # --- Aplikasikan Filter ---
        df_display = df_final.copy()

        # Kolom untuk menempatkan Filter di atas tabel
        col_interval, col_movement = st.columns(2)
        col_material, col_empty = st.columns(2) # Tambah baris baru untuk filter material

        with col_interval:
            # 1. Filter Interval Waktu (Multiple Select) - Tanpa Default
            unique_intervals = sorted(df_final['Time Interval'].unique())
            selected_intervals = st.multiselect(
                "1. Filter berdasarkan **Interval Waktu**:",
                unique_intervals,
                default=None, # Mengubah default menjadi None/[] agar tidak ada yang terpilih
                help="Pilih satu atau lebih interval waktu. Tidak ada nilai default yang terpilih."
            )
        
        with col_movement:
            # 2. Filter Movement Type (Multiple Select)
            if 'Movement Type' in df_final.columns:
                
                # --- PERBAIKAN: Konversi ke String dan isi NaN/None ---
                # Mengubah semua tipe data ke string, dan mengisi NaN/None dengan 'N/A' sebelum mengambil nilai unik
                movement_series = df_final['Movement Type'].astype(str).replace({'nan': 'N/A', 'None': 'N/A'})
                
                unique_movement_types = sorted(movement_series.unique()) 
                # --- AKHIR PERBAIKAN ---

                selected_movement_types = st.multiselect(
                    "2. Filter berdasarkan **Movement Type**:",
                    unique_movement_types,
                    default=unique_movement_types, # Default memilih semua
                    help="Pilih satu atau lebih jenis Movement Type."
                )
                
                # Filter harus menggunakan nilai yang sudah dikonversi ke string
                if selected_movement_types:
                    df_display = df_display[movement_series.isin(selected_movement_types)]
                    
            else:
                selected_movement_types = None
                st.info("Kolom 'Movement Type' tidak ada dalam dataset ini.")


        with col_material:
            # 3. Pencarian Material ID/Description (Multiple Search - Dipisah Spasi)
            search_materials_raw = st.text_input(
                "3. Cari **Material ID/Description**:",
                help="Masukkan ID atau Deskripsi, pisahkan dengan spasi (contoh: 10105 BOX KARTON GANTUNGAN)"
            )

        
        # Filter 1: Interval Waktu
        # Hanya filter jika ada interval yang dipilih
        if selected_intervals:
            df_display = df_display[df_display['Time Interval'].isin(selected_intervals)]
            
        # Filter 2: Movement Type
        if selected_movement_types and 'Movement Type' in df_display.columns:
            df_display = df_display[df_display['Movement Type'].isin(selected_movement_types)]
        
        # Filter 3: Material ID/Description (Multiple Search - DIPISAH SPASI)
        if search_materials_raw:
            # Pisahkan input berdasarkan SPASI dan hilangkan string kosong
            search_terms = [term.strip().lower() for term in search_materials_raw.split() if term.strip()]
            
            # Buat mask pencarian (OR logic)
            search_mask = pd.Series(False, index=df_display.index)
            
            if search_terms:
                for term in search_terms:
                    # Mencari di kolom Material ID (setelah diubah jadi string) ATAU Material Desc
                    current_mask = (df_display['Material ID'].astype(str).str.contains(term, case=False, na=False)) | \
                                   (df_display['Material Desc'].astype(str).str.contains(term, case=False, na=False))
                    search_mask = search_mask | current_mask
                
                df_display = df_display[search_mask]
        
        # --- Tampilan DataFrame Hasil ---
        
        st.write(f"""
            Tabel menampilkan data yang telah difilter. Klik header kolom di tabel untuk mengurutkan data.
        """)
        
        cols_to_display = [
            'Material ID', 
            'Material Desc', 
            'Movement Type', # Kolom baru
            'Time Interval', 
            # 'UOM',
            'Average Total Quantity (BOX)',
            'Min Total Quantity (BOX)', 
            'Max Total Quantity (BOX)',
        ]
        
        # Filter kolom yang benar-benar ada di DataFrame untuk menghindari error
        cols_to_display = [col for col in cols_to_display if col in df_display.columns]

        st.dataframe(df_display[cols_to_display], use_container_width=True)

        
        st.info(f"**Total Baris Hasil (Setelah Filter):** {len(df_display)} | **Material ID Ditampilkan:** {df_display['Material ID'].nunique()}")

        # --- Download Hasil Proses ---
        st.subheader("Unduh Hasil Proses")

        @st.cache_data
        def convert_df_to_excel(df):
            """Konversi DataFrame ke format Excel dalam memori (BytesIO)."""
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='ReplenishmentData')
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

# Panggil fungsi utama
show_retail_content()
