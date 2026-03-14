import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from scipy.spatial.distance import cdist

# --- 1. KONFIGURASI ---
st.set_page_config(page_title="Konoha Navigation System", layout="wide")

# ID Google Sheets Anda
SHEET_ID = '1Ov3nggLzpDQPkMyfoJtT8i4Goe1MLJ2t6AFRFspi_X8'

@st.cache_data(ttl=600) # Data di-refresh setiap 10 menit
def load_gsheet_data(sheet_name):
    # Mengubah ID menjadi format ekspor CSV
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}'
    return pd.read_csv(url)

@st.cache_data
def load_and_process():
    try:
        # Load masing-masing tab
        df_data = load_gsheet_data('Data')
        df_master = load_gsheet_data('Master_Lokasi')
        df_peta = load_gsheet_data('Peta_Lantai')
        
        # Konversi koordinat ke angka
        df_master['X'] = pd.to_numeric(df_master['X'], errors='coerce')
        df_master['Y'] = pd.to_numeric(df_master['Y'], errors='coerce')
        df_master = df_master.dropna(subset=['X', 'Y'])
        
        # Gabungkan Data Barang dengan Koordinat
        merged = pd.merge(df_data, df_master, left_on='Kode_Lokasi', right_on='Lokasi', how='inner')
        return merged, df_peta
    except Exception as e:
        st.error(f"Error Koneksi Data: {e}")
        return None, None

# Load Data
df, df_peta = load_and_process()

if df is not None:
    # --- 2. SIDEBAR ---
    st.sidebar.title("🥷 Konoha System")
    menu = st.sidebar.radio("Navigasi", ["Peta Interaktif", "Optimasi Jalur", "Analisis Heatmap"])
    
    st.sidebar.divider()
    sel_lantai = st.sidebar.selectbox("Lantai", df_peta['Lantai'].unique())
    
    # Filter data berdasarkan lantai
    floor_df = df[df['Lantai'] == sel_lantai]

    # --- 3. MENU: PETA INTERAKTIF ---
    if menu == "Peta Interaktif":
        st.header(f"📍 Posisi Barang - {sel_lantai}")
        
        # Ambil URL Peta
        peta_row = df_peta[df_peta['Lantai'] == sel_lantai]
        map_id = peta_row['URL'].values[0]
        # Mengubah ID Google Drive menjadi Direct Link
        direct_map_url = f"https://lh3.googleusercontent.com/d/{map_id}"

        fig = px.scatter(
            floor_df, x="X", y="Y",
            hover_name="Nama_Barang",
            color="Kategori",
            size="QtyStok",
            hover_data={"X":False, "Y":False, "QtyStok":True, "Harga":True},
            template="plotly_white"
        )

        fig.update_layout(
            images=[dict(
                source=direct_map_url,
                xref="x", yref="y", x=0, y=1000,
                sizex=1000, sizey=1000,
                sizing="stretch", opacity=0.7, layer="below"
            )],
            xaxis=dict(range=[0, 1000], visible=False),
            yaxis=dict(range=[0, 1000], visible=False),
            height=700
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- 4. MENU: OPTIMASI JALUR ---
    elif menu == "Optimasi Jalur":
        st.header("🚚 Picking Path Optimization")
        st.info("Pilih barang yang akan diambil, sistem akan menentukan jalur tercepat.")
        
        selected_items = st.multiselect("Daftar Belanja/Picking", floor_df['Nama_Barang'].unique())
        
        if len(selected_items) > 1:
            pick_df = floor_df[floor_df['Nama_Barang'].isin(selected_items)].copy()
            
            # Algoritma Jalur Terdekat (Greedy)
            coords = pick_df[['X', 'Y']].values
            current_idx = 0
            route = [0]
            unvisited = list(range(1, len(coords)))
            
            while unvisited:
                dists = cdist([coords[current_idx]], coords[unvisited])
                closest_idx = unvisited[np.argmin(dists)]
                route.append(closest_idx)
                unvisited.remove(closest_idx)
                current_idx = closest_idx
            
            final_route = pick_df.iloc[route]
            
            # Gambar Jalur
            fig_route = go.Figure()
            fig_route.add_trace(go.Scatter(
                x=final_route['X'], y=final_route['Y'],
                mode='lines+markers+text',
                text=final_route['Nama_Barang'],
                line=dict(color='red', width=3),
                marker=dict(size=15, color='black')
            ))
            fig_route.update_layout(xaxis=dict(range=[0,1000]), yaxis=dict(range=[0,1000]), height=600)
            st.plotly_chart(fig_route)
            st.dataframe(final_route[['Nama_Barang', 'Kode_Lokasi']])

    # --- 5. MENU: ANALISIS HEATMAP ---
    elif menu == "Analisis Heatmap":
        st.header("🔥 Product Density Heatmap")
        fig_h = px.density_heatmap(
            floor_df, x="X", y="Y", z="QtyStok",
            nbinsx=20, nbinsy=20, 
            color_continuous_scale="Hot",
            title="Kepadatan Stok per Koordinat"
        )
        st.plotly_chart(fig_h, use_container_width=True)

else:
    st.warning("Data tidak tersedia. Cek konfigurasi Google Sheets Anda.")
