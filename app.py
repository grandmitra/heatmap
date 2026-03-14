import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Konoha Ops Pro Mobile", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .main { padding: 0rem 0rem; }
    .stRadio [data-testid="stWidgetLabel"] p { font-size: 16px; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 10px; background-color: #007bff; color: white; font-weight: bold; }
    
    .map-container { display: grid; grid-template-columns: 3.5fr 1fr; gap: 10px; padding: 10px; }
    
    @media (max-width: 768px) {
        .map-container { grid-template-columns: 1fr; }
        .legend-col { display: none !important; }
        .map-col { grid-column: 1 / -1; }
    }
    
    .legend-col { 
        background-color: #f8f9fa; 
        padding: 15px; 
        border-radius: 12px; 
        border: 1px solid #ddd;
    }
    </style>
    """, unsafe_allow_html=True)

# IDs
SHEET_ID_MASTER = '1Ov3nggLzpDQPkMyfoJtT8i4Goe1MLJ2t6AFRFspi_X8'
SHEET_ID_SO = '1mjjDF1ETjOB_eTI6ChI6dqvg0wf9aCa7cJwx0x2K3No'

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=300)
def load_data_pro():
    try:
        df_master = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Master_Lokasi')
        df_peta = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Peta_Lantai')
        df_items = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Data')
        df_so = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_SO}/gviz/tq?tqx=out:csv&sheet=stat_lok')

        df_master['X'] = pd.to_numeric(df_master['X'], errors='coerce')
        df_master['Y'] = pd.to_numeric(df_master['Y'], errors='coerce')
        df_master = df_master.dropna(subset=['X', 'Y'])
        
        # Merge Items
        df_full = pd.merge(df_items, df_master, left_on='Kode_Lokasi', right_on='Lokasi', how='inner')
        df_full['Y_Visual'] = 1000 - df_full['Y']
        
        # Pastikan kolom Kategori adalah string dan isi yang kosong dengan "Tanpa Kategori"
        df_full['Kategori'] = df_full['Kategori'].astype(str).replace('nan', 'TANPA KATEGORI')
        
        return df_full, df_peta, df_so, df_master
    except Exception as e:
        st.error(f"Gagal Sinkronisasi: {e}")
        return None, None, None, None

if st.sidebar.button("🔄 Paksa Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df_full, df_peta, df_so, df_m = load_data_pro()

# --- 3. FILTER & SEARCH ---
if df_full is not None:
    st.sidebar.header("⚙️ Filter Global")
    sel_lantai = st.sidebar.selectbox("Pilih Lantai", ["Lantai 1", "Lantai 2", "Lantai 3"])
    
    # PERBAIKAN DI SINI: Mengonversi ke list string sebelum di-sort untuk menghindari TypeError
    raw_cats = df_full['Kategori'].unique().tolist()
    sorted_cats = sorted([str(c) for c in raw_cats])
    all_cats = ["SEMUA KATEGORI"] + sorted_cats
    
    sel_kategori = st.sidebar.selectbox("Filter Kategori Barang", all_cats)
    search_q = st.text_input("🔍 Cari Nama Barang atau Kode Rak", placeholder="Ketik di sini...").upper()
    menu = st.radio("Mode Tampilan:", ["📦 STOK OPNAME", "🔥 HEATMAP ANALYTICS", "🎯 COORDINATE PICKER"], horizontal=True)

    # --- 4. PROCESSING ---
    floor_data = df_full[df_full['Lantai'] == sel_lantai].copy()
    if sel_kategori != "SEMUA KATEGORI":
        floor_data = floor_data[floor_data['Kategori'] == sel_kategori]

    map_row = df_peta[df_peta['Lantai'] == sel_lantai]
    bg_map = f"https://lh3.googleusercontent.com/d/{map_row['URL'].values[0]}" if not map_row.empty else ""

    viz_df = pd.merge(df_m[df_m['Lantai'] == sel_lantai], df_so, on='Lokasi', how='left')
    viz_df['Y_Visual'] = 1000 - viz_df['Y']
    viz_df['STATUS'] = viz_df['STATUS'].fillna('BELUM')

    h_locations = []
    if search_q:
        match = floor_data[
            (floor_data['Nama_Barang'].str.contains(search_q, na=False, case=False)) | 
            (floor_data['Lokasi'].str.contains(search_q, na=False, case=False))
        ]
        h_locations = match['Lokasi'].unique().tolist()

    # --- 5. VISUALIZATION ---
    fig = go.Figure()

    if "STOK OPNAME" in menu:
        colors = {'DONE': '#28a745', 'ON PROGRESS': '#ffc107', 'PENDING': '#dc3545', 'BELUM': '#6c757d'}
        for status, color in colors.items():
            sub = viz_df[viz_df['STATUS'] == status]
            if sel_kategori != "SEMUA KATEGORI":
                sub = sub[sub['Lokasi'].isin(floor_data['Lokasi'].unique())]
                
            fig.add_trace(go.Scatter(
                x=sub['X'], y=sub['Y_Visual'], mode='markers+text',
                name=status, text=sub['Lokasi'] if not search_q else "",
                marker=dict(size=25, color=color, line=dict(width=2, color='white')),
                textposition="top center", customdata=sub['Lokasi'],
                hovertemplate="<b>Rak: %{customdata}</b>"
            ))

    elif "HEATMAP" in menu:
        heatmap_data = floor_data.groupby(['Lokasi', 'X', 'Y_Visual']).size().reset_index(name='Count')
        fig.add_trace(go.Scatter(
            x=heatmap_data['X'], y=heatmap_data['Y_Visual'], mode='markers',
            marker=dict(size=heatmap_data['Count']*15, color=heatmap_data['Count'], 
                        colorscale='Viridis', showscale=True, sizemode='area', sizeref=0.5)
        ))

    if h_locations:
        h_df = viz_df[viz_df['Lokasi'].isin(h_locations)]
        fig.add_trace(go.Scatter(
            x=h_df['X'], y=h_df['Y_Visual'], mode='markers+text',
            text=h_df['Lokasi'], textposition="top center",
            marker=dict(size=45, color="rgba(0,0,0,0)", line=dict(width=4, color="#00ffff")),
            name="Target"
        ))

    fig.update_layout(
        images=[dict(source=bg_map, xref="x", yref="y", x=0, y=1000, sizex=1000, sizey=1000, sizing="stretch", opacity=0.7, layer="below")],
        xaxis=dict(range=[0, 1000], visible=False), yaxis=dict(range=[0, 1000], visible=False),
        height=650, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, dragmode=False
    )

    # --- 6. RENDER ---
    st.markdown('<div class="map-container">', unsafe_allow_html=True)
    st.markdown('<div class="map-col">', unsafe_allow_html=True)
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun", config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="legend-col">', unsafe_allow_html=True)
    st.write("### 🏷️ Status")
    for s, c in {'DONE': '#28a745', 'ON PROGRESS': '#ffc107', 'PENDING': '#dc3545', 'BELUM': '#6c757d'}.items():
        st.markdown(f'<div style="display:flex; align-items:center; margin-bottom:8px;"><div style="width:18px; height:18px; background:{c}; border-radius:50%; margin-right:10px;"></div><b>{s}</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Progress Info
    done_m = len(viz_df[viz_df['STATUS'] == 'DONE'])
    total_m = len(viz_df)
    prog_m = int((done_m/total_m)*100) if total_m > 0 else 0
    st.write(f"**Progress SO: {prog_m}%** ({done_m}/{total_m} Rak)")
    st.progress(prog_m/100)

    if menu == "🎯 COORDINATE PICKER" and selected and "selection" in selected:
        pts = selected["selection"]["points"]
        if pts:
            st.info(f"📍 X: {int(pts[-1]['x'])} | Y: {1000 - int(pts[-1]['y'])}")
