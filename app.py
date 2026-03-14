import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from scipy.spatial.distance import cdist

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Konoha Navigation System", layout="wide")

# ID Spreadsheet Google Sheets
SHEET_ID = '1Ov3nggLzpDQPkMyfoJtT8i4Goe1MLJ2t6AFRFspi_X8'

# --- 2. FUNGSI LOAD DATA DENGAN CACHE ---
# ttl=3600 bermaksud data disimpan dalam cache selama 1 jam untuk mempercepat loading
@st.cache_data(ttl=3600)
def load_gsheet_data(sheet_name):
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}'
    return pd.read_csv(url)

@st.cache_data(ttl=3600)
def load_and_process():
    try:
        # Load data dari tab Google Sheets
        df_data = load_gsheet_data('Data')
        df_master = load_gsheet_data('Master_Lokasi')
        df_peta = load_gsheet_data('Peta_Lantai')
        
        # Pastikan kolom koordinat bersih
        df_master['X'] = pd.to_numeric(df_master['X'], errors='coerce')
        df_master['Y'] = pd.to_numeric(df_master['Y'], errors='coerce')
        df_master = df_master.dropna(subset=['X', 'Y'])
        
        # Merge Data Barang dengan Koordinat
        merged = pd.merge(df_data, df_master, left_on='Kode_Lokasi', right_on='Lokasi', how='inner')
        
        # --- LOGIK TERBALIK (Atas jadi Bawah) ---
        # Kita gunakan 1000 sebagai had maksimum paksi Y (sesuaikan jika skala anda berbeza)
        MAX_Y = 1000
        merged['Y_Visual'] = MAX_Y - merged['Y']
        
        # Pembersihan nilai negatif untuk saiz marker
        merged['QtyStok_Visual'] = merged['QtyStok'].clip(lower=0)
        
        return merged, df_peta
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
        return None, None

# Load data menggunakan sistem cache
df, df_peta = load_and_process()

if df is not None:
    # --- 3. SIDEBAR ---
    st.sidebar.title("🥷 Konoha Ops System")
    
    # Butang manual untuk refresh cache jika ada perubahan di Google Sheets
    if st.sidebar.button("🔄 Refresh Data Baru"):
        st.cache_data.clear()
        st.rerun()

    menu = st.sidebar.radio("Menu", ["Peta Interaktif", "Optimasi Rute", "Analisis Heatmap"])
    
    st.sidebar.divider()
    sel_lantai = st.sidebar.selectbox("Pilih Lantai", df_peta['Lantai'].unique())
    floor_df = df[df['Lantai'] == sel_lantai].copy()

    # --- 4. MENU: PETA INTERAKTIF ---
    if menu == "Peta Interaktif":
        st.header(f"📍 Digital Map (Y-Inverted): {sel_lantai}")
        
        map_row = df_peta[df_peta['Lantai'] == sel_lantai]
        if not map_row.empty:
            map_id = map_row['URL'].values[0]
            direct_map_url = f"https://lh3.googleusercontent.com/d/{map_id}"

            fig = px.scatter(
                floor_df, x="X", y="Y_Visual", # Menggunakan Y_Visual yang sudah terbalik
                hover_name="Nama_Barang",
                color="Kategori",
                size="QtyStok_Visual",
                hover_data={
                    "X": True, 
                    "Y_Visual": False, 
                    "Y": True, # Menunjukkan Y asli di hover
                    "QtyStok": True,
                    "Harga": ":,.0f"
                },
                template="plotly_white"
            )

            fig.update_layout(
                images=[dict(
                    source=direct_map_url,
                    xref="x", yref="y", x=0, y=1000,
                    sizex=1000, sizey=1000,
                    sizing="stretch", opacity=0.6, layer="below"
                )],
                xaxis={"range": [0, 1000], "visible": False},
                yaxis={"range": [0, 1000], "visible": False},
                height=750
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- 5. MENU: OPTIMASI RUTE ---
    elif menu == "Optimasi Rute":
        st.header("🚚 Picking Route Optimizer")
        items_to_pick = st.multiselect("Pilih Barang:", floor_df['Nama_Barang'].unique())
        
        if len(items_to_pick) > 1:
            pick_df = floor_df[floor_df['Nama_Barang'].isin(items_to_pick)].copy()
            coords = pick_df[['X', 'Y_Visual']].values
            
            # Algoritma Greedy TSP
            current_idx = 0
            route_indices = [0]
            remaining = list(range(1, len(coords)))
            
            while remaining:
                last_coord = [coords[current_idx]]
                distances = cdist(last_coord, coords[remaining])
                nearest_in_rem = np.argmin(distances)
                current_idx = remaining.pop(nearest_in_rem)
                route_indices.append(current_idx)
            
            ordered_df = pick_df.iloc[route_indices]
            
            fig_route = go.Figure()
            fig_route.add_trace(go.Scatter(
                x=ordered_df['X'], y=ordered_df['Y_Visual'],
                mode='lines+markers+text',
                text=list(range(1, len(ordered_df)+1)),
                textposition="top center",
                line=dict(color='red', width=3),
                marker=dict(size=12, color='black')
            ))
            fig_route.update_layout(xaxis={"range":[0,1000]}, yaxis={"range":[0,1000]}, height=600)
            st.plotly_chart(fig_route)
            st.table(ordered_df[['Nama_Barang', 'Kode_Lokasi']])

    # --- 6. MENU: HEATMAP ---
    elif menu == "Analisis Heatmap":
        st.header("🔥 Density Heatmap")
        fig_h = px.density_heatmap(
            floor_df, x="X", y="Y_Visual", z="QtyStok_Visual",
            nbinsx=25, nbinsy=25, color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_h, use_container_width=True)
