import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIGURATION (MOBILE OPTIMIZED) ---
st.set_page_config(
    page_title="Konoha Ops Mobile", 
    layout="wide", 
    initial_sidebar_state="collapsed" # Tutup sidebar otomatis di HP agar lega
)

# Custom CSS untuk mempercantik tampilan di HP
st.markdown("""
    <style>
    .main {
        padding: 0rem 0rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    div[data-testid="stExpander"] {
        border: none !important;
        box-shadow: none !important;
    }
    /* Memperbesar tombol radio di HP */
    .stRadio [data-testid="stWidgetLabel"] p {
        font-size: 18px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# Google Sheets IDs
SHEET_ID_MASTER = '1Ov3nggLzpDQPkMyfoJtT8i4Goe1MLJ2t6AFRFspi_X8'
SHEET_ID_SO = '1mjjDF1ETjOB_eTI6ChI6dqvg0wf9aCa7cJwx0x2K3No'

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=30)
def load_all_sync():
    try:
        # Load Master & Peta
        df_master = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Master_Lokasi')
        df_peta = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Peta_Lantai')
        df_data = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Data')
        
        # Load Stok Opname (Sheet: stat_lok)
        df_so = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_SO}/gviz/tq?tqx=out:csv&sheet=stat_lok')

        # Cleaning Master
        df_master['X'] = pd.to_numeric(df_master['X'], errors='coerce')
        df_master['Y'] = pd.to_numeric(df_master['Y'], errors='coerce')
        df_master = df_master.dropna(subset=['X', 'Y'])
        
        # Heatmap Processing
        df_data['Weight'] = df_data['Kategori'].apply(lambda x: 1 if x == 'FASTSLOW' else -1)
        rak_resume = df_data.groupby('Kode_Lokasi').agg(
            Total_Barang=('Nama_Barang', 'count'),
            Speed_Score=('Weight', 'mean'),
            List_Barang=('Nama_Barang', lambda x: '<br>'.join(list(x)[:5]))
        ).reset_index()

        merged = pd.merge(df_master, rak_resume, left_on='Lokasi', right_on='Kode_Lokasi', how='left')
        merged['Y_Visual'] = 1000 - merged['Y']
        
        return merged, df_peta, df_so
    except Exception as e:
        st.error(f"Gagal Load: {e}")
        return None, None, None

df_main, df_peta, df_so = load_all_sync()

# --- 3. MOBILE MENU ---
# Menggunakan sidebar untuk filter, tapi main menu di atas untuk akses cepat
st.sidebar.title("⚙️ Pengaturan")
sel_lantai = st.sidebar.selectbox("Pilih Lantai", ["Lantai 1", "Lantai 2", "Lantai 3"])

menu = st.radio(
    "Pilih Menu Utama:",
    ["📦 STOK OPNAME", "🔥 HEATMAP", "🎯 PICKER"],
    horizontal=True # Membuat menu berjejer ke samping (cocok untuk jempol)
)

if df_main is not None:
    floor_df = df_main[df_main['Lantai'] == sel_lantai].copy()
    map_row = df_peta[df_peta['Lantai'] == sel_lantai]
    bg_map = f"https://lh3.googleusercontent.com/d/{map_row['URL'].values[0]}" if not map_row.empty else ""

    # --- 4. MODULE: STOK OPNAME ---
    if "STOK OPNAME" in menu:
        # Merge dengan data asli stat_lok
        so_map = pd.merge(floor_df, df_so, on='Lokasi', how='left')
        so_map['STATUS'] = so_map['STATUS'].fillna('BELUM ADA DATA')
        
        color_so = {
            'DONE': '#28a745', 
            'ON PROGRESS': '#ffc107', 
            'PENDING': '#dc3545', 
            'BELUM ADA DATA': '#6c757d'
        }
        
        fig = px.scatter(
            so_map, x="X", y="Y_Visual",
            color="STATUS", 
            text="Lokasi",
            hover_data=["TARGET SKU", "P1", "P2", "P3"],
            color_discrete_map=color_so
        )
        # Marker lebih besar agar mudah diklik di HP
        fig.update_traces(marker=dict(size=25, line=dict(width=2, color='white')), textposition='top center')

    # --- 5. MODULE: HEATMAP ---
    elif "HEATMAP" in menu:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=floor_df['X'], y=floor_df['Y_Visual'],
            mode='markers+text', text=floor_df['Lokasi'],
            marker=dict(
                size=floor_df['Total_Barang'].fillna(0) * 12,
                sizemode='area', sizeref=0.8,
                color=floor_df['Speed_Score'].fillna(0),
                colorscale='RdBu_r', showscale=True,
                line=dict(width=2, color='white')
            )
        ))

    # --- 6. MODULE: PICKER ---
    else:
        st.write("Klik pada gambar untuk ambil koordinat:")
        fig = px.scatter(x=[0, 1000], y=[0, 1000], opacity=0)

    # Global Layout Optimized for Mobile Aspect Ratio
    fig.update_layout(
        images=[dict(source=bg_map, xref="x", yref="y", x=0, y=1000, sizex=1000, sizey=1000, sizing="stretch", opacity=0.8, layer="below")],
        xaxis=dict(range=[0, 1000], visible=False),
        yaxis=dict(range=[0, 1000], visible=False),
        height=600, # Tinggi disesuaikan untuk layar HP
        margin=dict(l=5, r=5, t=10, b=10),
        clickmode='event+select',
        dragmode=False # Nonaktifkan drag agar scroll layar HP lebih mudah
    )

    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun", config={'displayModeBar': False})

    # Hasil Picker
    if "PICKER" in menu and selected and "selection" in selected:
        pts = selected["selection"]["points"]
        if pts:
            x_res, y_res = int(pts[-1]['x']), 1000 - int(pts[-1]['y'])
            st.success(f"📍 X: {x_res} | Y: {y_res}")
            st.button("Salin Koordinat") # Memudahkan tim di HP

    # --- 7. MOBILE SUMMARY CARD ---
    if "STOK OPNAME" in menu:
        done = len(so_map[so_map['STATUS'] == 'DONE'])
        total = len(so_map)
        prog = int((done/total)*100) if total > 0 else 0
        
        st.markdown(f"### 📊 Progress: {prog}%")
        st.progress(prog/100)
        
        col1, col2 = st.columns(2)
        col1.metric("Done", done)
        col2.metric("Pending", len(so_map[so_map['STATUS'] == 'PENDING']))
