import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import AgglomerativeClustering
from collections import defaultdict
import io
import os

def show_layouting_content():
    # --- KONSTANTA ---
    # Pastikan file ini ada di direktori yang sama dengan app.py
    MASTER_FILE_PATH = 'Material Group.xlsx' 

    # Judul Utama
    st.header("📦 Warehouse Layout Optimization")

    # --- Bagian Unggah File & Pilihan Zona & Pengaturan Layout ---
    st.header("1. Konfigurasi Analisis")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Data ZRW70")
        # File ZRW70 masih di-upload
        uploaded_file_df = st.file_uploader("Unggah File Data (*.xlsx)", type=["xlsx"], key="file1")
        
        # --- KODE BARU UNTUK PENGATURAN LAYOUT ---
        st.subheader("Pengaturan Layout Visualisasi")
        
        # Input untuk jumlah Baris (Racks Deep)
        default_rows = 2
        num_rows_input = st.number_input(
            'Jumlah Baris Layout (Depth of Racks)',
            min_value=1,
            max_value=10, # Batasan maksimal yang wajar
            value=default_rows,
            step=1,
            key="num_rows_input"
        )
        
        # Input untuk jumlah Kolom (Aisles Wide) - dihitung berdasarkan Baris secara default,
        # tapi biarkan pengguna mengatur batas max-nya jika mau, atau kita bisa hitung otomatis.
        # Untuk kasus ini, kita hitung kolom secara OTOMATIS di dalam fungsi
        # agar semua material group bisa terakomodasi di row yang dipilih.
        st.info(f"Jumlah Kolom akan **dihitung otomatis** agar semua Material Group terakomodasi di {num_rows_input} baris.")


    with col2:
        st.subheader("Pilihan Zona Analisis")
        # Pilihan zona analisis (bisa 1 atau 2 zona)
        selected_zones = st.multiselect(
            'Pilih Zona Gudang yang akan dianalisis:',
            options=['ZAA', 'ZAB', 'ZAC', 'ZAD', 'ZAE', 'ZAF', 'ZAG', 'ZAH', 'ZAI', 'ZAJ', 'ZAK', 'ZAL', 'ZAM'],
            default=['ZAK', 'ZAL'],
            max_selections=2
        )
        # Menampilkan setting layout yang dipilih pengguna
        st.metric(label="Baris Layout (Racks Deep)", value=num_rows_input)

    # Tombol untuk menjalankan analisis
    if uploaded_file_df and selected_zones:
        if st.button("Jalankan Analisis dan Optimasi"):
            if not os.path.exists(MASTER_FILE_PATH):
                st.error(f"❌ **Error:** File Data Master tidak ditemukan pada path: `{MASTER_FILE_PATH}`. Pastikan file berada di direktori yang sama dengan `app.py`.")
                st.stop()
                
            st.info("Memulai pemrosesan data...")
            
            # Mendapatkan nilai Baris yang sudah diatur pengguna
            # Tidak perlu hitung Kolom di sini, kita hitung di fungsi visualisasi
            num_rows = num_rows_input 
            
            try:
                # ... (Bagian Pemrosesan Data Awal tetap sama) ...
                # --- Bagian Pemrosesan Data Awal ---
                st.header("2. Pemrosesan Data dan Penggabungan")

                # Load Data dari file yang diunggah
                df = pd.read_excel(uploaded_file_df)
                
                # Load Data Master dari file lokal (perubahan di sini)
                excel_df = pd.read_excel(MASTER_FILE_PATH) 

                st.success("Data berhasil dimuat. Melakukan penggabungan data...")

                # Select and copy relevant columns from the Excel DataFrame
                excel_data_to_merge = excel_df[['Material ID', 'Product lvl 1-Category', 'Product lvl 2-Type', 'Product lvl 3-Group', 'Material Group 2']].copy()

                # Clean and prepare 'Material ID' for merging
                df['Material ID'] = df['Material ID'].astype(str).str.replace(r'\.0$', '', regex=True)
                excel_data_to_merge.loc[:, 'Material ID'] = excel_data_to_merge['Material ID'].astype(str)

                # Merge the two DataFrames
                merged_df = pd.merge(df, excel_data_to_merge, on='Material ID', how='left')
                
                # 💡 KODE BARU UNTUK MENGHAPUS BARIS DENGAN NILAI KOSONG DI 'TO Dummy'
                initial_rows = merged_df.shape[0]
                merged_df.dropna(subset=['TO Dummy'], inplace=True)
                rows_dropped = initial_rows - merged_df.shape[0]
                
                st.success(f"Data berhasil digabungkan! ({rows_dropped} baris dengan 'TO Dummy' kosong telah dihapus).")
                st.dataframe(merged_df.head(), use_container_width=True)

                # Filter data berdasarkan Zona yang dipilih oleh pengguna
                df_filtered = merged_df[merged_df['Storage Type Suggestion'].isin(selected_zones)].copy()
                
                if df_filtered.empty:
                    st.warning(f"Tidak ada data ditemukan untuk Zona yang dipilih ({', '.join(selected_zones)}). Cek kolom 'Storage Type Suggestion' pada data ZRW70 Anda.")
                    st.stop()


                # ... (Bagian Co-occurrence dan Clustering tetap sama) ...
                # --- Bagian Co-occurrence dan Clustering ---
                st.header("3. Analisis Co-occurrence dan Material Group Clustering")
                st.info("Menghitung co-occurrence dan menjalankan Agglomerative Clustering (3 Cluster)...")

                # ... (kode selanjutnya tetap sama) ...
                
                # Group the filtered data by 'Reference Document'
                grouped_material_groups = df_filtered.groupby('Reference Document')['Material Group 2'].unique().tolist()
                material_group_ids = sorted(list(df_filtered['Material Group 2'].dropna().unique()))
                
                if len(material_group_ids) < 3:
                    n_clusters = max(1, len(material_group_ids))
                else:
                    n_clusters = 3
                    
                id_to_index = {material_group_id: i for i, material_group_id in enumerate(material_group_ids)}
                n_material_groups = len(material_group_ids)

                # Initialize co-occurrence matrix
                co_occurrence_matrix_groups = np.zeros((n_material_groups, n_material_groups), dtype=int)

                # Fill co-occurrence matrix
                for doc_material_groups in grouped_material_groups:
                    doc_material_group_ids = [mgid for mgid in doc_material_groups if mgid in id_to_index]
                    for i in range(len(doc_material_group_ids)):
                        for j in range(i + 1, len(doc_material_group_ids)):
                            idx1 = id_to_index[doc_material_group_ids[i]]
                            idx2 = id_to_index[doc_material_group_ids[j]]
                            co_occurrence_matrix_groups[idx1, idx2] += 1
                            co_occurrence_matrix_groups[idx2, idx1] += 1

                # Clustering
                distance_matrix_groups = 1 / (co_occurrence_matrix_groups + 1)
                agg_clustering_groups = AgglomerativeClustering(n_clusters=n_clusters, metric='precomputed', linkage='average')
                cluster_labels_groups = agg_clustering_groups.fit_predict(distance_matrix_groups)

                clustering_results_groups = pd.DataFrame({'Material Group 2': material_group_ids, 'Cluster Label': cluster_labels_groups})

                st.subheader(f"Hasil Material Group Clustering ({n_clusters} Cluster)")
                grouped_clusters_groups = clustering_results_groups.groupby('Cluster Label')['Material Group 2'].apply(list).reset_index()
                grouped_clusters_groups.columns = ['Cluster Label', 'Material Group 2 IDs']
                st.dataframe(grouped_clusters_groups, use_container_width=True)

                # --- Bagian Picking Priority Calculation ---
                st.header("4. Perhitungan Prioritas Picking")

                df_filtered['Confirm 1 Time'] = pd.to_datetime(df_filtered['Confirm 1 Time'], errors='coerce')
                df_sorted_picking = df_filtered.sort_values(by=['Reference Document', 'Confirm 1 Time'])
                df_sorted_picking['Picking Order'] = df_sorted_picking.groupby('Reference Document').cumcount() + 1
                df_sorted_picking['Total Items in Document'] = df_sorted_picking.groupby('Reference Document')['TO Dummy'].transform('count')
                df_sorted_picking['Picking Sequence Score'] = df_sorted_picking['Picking Order'] / df_sorted_picking['Total Items in Document']

                # Material Group Picking Score (lower is better)
                material_group_picking_score = df_sorted_picking.groupby('Material Group 2')['Picking Sequence Score'].mean().reset_index()

                # First Pick Frequency (higher is better)
                first_picked_items = df_filtered.groupby('Reference Document').head(1)
                first_picked_material_group_frequency = first_picked_items['Material Group 2'].value_counts().reset_index()
                first_picked_material_group_frequency.columns = ['Material Group 2', 'First Pick Frequency']

                # Merge all results
                clustering_results_groups_with_priority = pd.merge(clustering_results_groups, first_picked_material_group_frequency, on='Material Group 2', how='left')
                clustering_results_groups_with_priority = pd.merge(clustering_results_groups_with_priority, material_group_picking_score, on='Material Group 2', how='left')
                clustering_results_groups_with_priority['First Pick Frequency'] = clustering_results_groups_with_priority['First Pick Frequency'].fillna(0).astype(int)
                max_score = clustering_results_groups_with_priority['Picking Sequence Score'].max() if not clustering_results_groups_with_priority['Picking Sequence Score'].empty else 1
                clustering_results_groups_with_priority['Picking Sequence Score'] = clustering_results_groups_with_priority['Picking Sequence Score'].fillna(max_score)

                # --- FUNGSI visualize_zone_layout diubah untuk menerima num_rows ---
                def visualize_zone_layout(zone_df, zone_name, clustering_results_groups, all_material_groups_priority, **layout_params):
                    material_group_ids_zone = sorted(list(zone_df['Material Group 2'].dropna().unique()))
                    
                    # Ambil parameter layout
                    num_rows = layout_params.get('num_rows', 2) # Default 2 jika tidak ada

                    # Gunakan dataframe priority global yang sudah dihitung sebelumnya, cukup difilter
                    clustering_results_zone = all_material_groups_priority[
                        all_material_groups_priority['Material Group 2'].isin(material_group_ids_zone)
                    ].copy()

                    # Sort 'Material Group 2' IDs based on 'First Pick Frequency' (desc) and then 'Average Picking Sequence Score' (asc)
                    sorted_material_group_ids_zone = clustering_results_zone.sort_values(
                        by=['First Pick Frequency', 'Picking Sequence Score'],
                        ascending=[False, True]
                    )['Material Group 2'].tolist()

                    # Define layout parameters (Racks are num_rows deep, columns adjusted based on material group count)
                    # HITUNG JUMLAH KOLOM OTOMATIS
                    num_cols = max(1, (len(material_group_ids_zone) + num_rows - 1) // num_rows)
                    
                    # Tambahkan informasi layout ke Streamlit
                    st.metric(label="Kolom Layout (Auto-Calculated)", value=num_cols)
                    
                    available_locations = []
                    for r in range(num_rows):
                        for c in range(num_cols):
                            # Hitung jarak (misalnya, Manhattan distance dari (0,0))
                            available_locations.append({'Row': r, 'Column': c, 'Picking Distance': r + c}) 
                    available_locations.sort(key=lambda x: x['Picking Distance'])

                    warehouse_layout_list_zone = []
                    for material_group_id in sorted_material_group_ids_zone:
                        if available_locations:
                            best_location = available_locations.pop(0)
                            cluster_label = clustering_results_zone[clustering_results_zone['Material Group 2'] == material_group_id]['Cluster Label'].iloc[0]
                            warehouse_layout_list_zone.append({
                                'Material Group 2': material_group_id,
                                'Cluster Label': cluster_label,
                                'Row': best_location['Row'],
                                'Column': best_location['Column'],
                                'Picking Distance': best_location['Picking Distance']
                            })
                    warehouse_layout_df_zone = pd.DataFrame(warehouse_layout_list_zone)

                    # Visualize the layout
                    layout_matrix_zone = np.full((num_rows, num_cols), np.nan) 
                    for index, row in warehouse_layout_df_zone.iterrows():
                        r, c = int(row['Row']), int(row['Column'])
                        if 0 <= r < num_rows and 0 <= c < num_cols:
                            layout_matrix_zone[r, c] = row['Cluster Label']

                    fig, ax = plt.subplots(figsize=(num_cols * 1.5, num_rows * 2))
                    sns.heatmap(layout_matrix_zone, annot=False, cmap='viridis', cbar_kws={'label': 'Cluster Label'}, linewidths=.5, linecolor='lightgray', ax=ax)

                    # Annotate cells dengan Material Group 2 ID dan Kata Pertama dari Material Desc yang paling sering
                    for index, row in warehouse_layout_df_zone.iterrows():
                        r, c = int(row['Row']), int(row['Column'])
                        if 0 <= r < num_rows and 0 <= c < num_cols:
                            material_group = row['Material Group 2']
                            
                            # Dapatkan Material ID yang paling sering muncul di Material Group ini di zona ini
                            material_id_counts = zone_df[zone_df['Material Group 2'] == material_group]['Material ID'].value_counts().nlargest(1).index.tolist()

                            annotation_text = f"{material_group}"
                            
                            if material_id_counts:
                                mid = material_id_counts[0]
                                # Ambil deskripsi material dari data zona yang difilter
                                material_desc_series = zone_df[(zone_df['Material Group 2'] == material_group) & (zone_df['Material ID'] == mid)]['Material Desc']
                                
                                if not material_desc_series.empty:
                                    material_desc = material_desc_series.iloc[0]
                                    first_word_desc = material_desc.split()[0] if isinstance(material_desc, str) and material_desc.strip() else ""
                                    
                                    if first_word_desc:
                                        annotation_text += f"\n{first_word_desc}"

                            ax.text(c + 0.5, r + 0.5, annotation_text,
                                    ha='center', va='center', color='white', fontsize=8)

                    ax.set_title(f'Warehouse Layout Rekomendasi ({zone_name}) - {num_rows}x{num_cols}', fontsize=14)
                    ax.set_xlabel('Column', fontsize=12)
                    ax.set_ylabel('Row', fontsize=12)
                    ax.set_yticks(np.arange(num_rows) + 0.5, range(num_rows))
                    ax.set_xticks(np.arange(num_cols) + 0.5, range(num_cols))
                    ax.invert_yaxis()

                    return fig, warehouse_layout_df_zone

                # --- Visualisasi Hasil berdasarkan Pilihan Zona ---
                st.header("5. Visualisasi Rekomendasi Warehouse Layout")

                # Kolom untuk visualisasi hasil zona
                zone_columns = st.columns(len(selected_zones))
                
                zone_data = {zone: df_filtered[df_filtered['Storage Type Suggestion'] == zone].copy() for zone in selected_zones}
                
                for i, zone in enumerate(selected_zones):
                    df_zone = zone_data[zone]
                    
                    with zone_columns[i]:
                        st.subheader(f"Rekomendasi {zone}")
                        
                        if not df_zone.empty:
                            # Panggil fungsi visualize_zone_layout dengan parameter yang tepat
                            fig_zone, layout_df_zone = visualize_zone_layout(
                                df_zone, 
                                zone, 
                                clustering_results_groups, 
                                clustering_results_groups_with_priority, # Kirim dataframe prioritas
                                num_rows=num_rows # Kirim nilai Baris dari input pengguna
                            )
                            st.pyplot(fig_zone)
                            st.caption(f"Tabel Layout {zone}")
                            st.dataframe(layout_df_zone, use_container_width=True)
                        else:
                            st.warning(f"Data filter untuk zona **{zone}** kosong. Tidak ada layout yang dibuat.")

                st.success("Analisis selesai! Rekomendasi layout telah ditampilkan.")

            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses data: {e}")
                st.warning("Pastikan file Excel yang diunggah memiliki struktur kolom yang benar, dan file master ada di lokasi yang benar.")
    else:
        st.info("Silakan unggah file ZRW70, atur Layout, dan pilih minimal satu Zona untuk memulai")