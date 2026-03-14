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
    .map-container { display: grid; grid-template-columns: 3.5fr 1fr; gap: 10px; padding: 10px; }
    @media (max-width: 768px) {
        .map-container { grid-template-columns: 1fr; }
        .legend-col { display: none !important; }
        .map-col { grid-column: 1 / -1; }
    }
    .legend-col { background-color: #f8f9fa; padding: 15px; border-radius: 12px; border: 1px solid #ddd; }
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
        
        # Pre-Processing Resume Item untuk Heatmap
        df_items['Kategori'] = df_items['Kategori'].astype(str).replace('nan', 'N/A')
        # Beri bobot: FAST=1, SLOW=-1 untuk rata-rata warna
        df_items['Weight'] = df_items['Kategori'].apply(lambda x: 1 if 'FAST' in x.upper() else (-1 if 'SLOW' in x.upper() else 0))
        
        rak_resume = df_items.groupby('Kode_Lokasi').agg(
            Total_Barang=('Nama_Barang', 'count'),
            Speed_Score=('Weight', 'mean'),
            List_Barang=('Nama_Barang', lambda x: '<br>'.join([f"• {b}" for b in list(x)[:5]]))
        ).reset_index()

        df_full = pd.merge(df_master, rak_resume, left_on='Lokasi', right_on='Kode_Lokasi', how='left')
        df_full['Y_Visual'] = 1000 - df_full['Y']
        
        # Tambahkan data kategori original ke df_items_full untuk filter
        df_items_full = pd.merge(df_items, df_master, left_on='Kode_Lokasi', right_on='Lokasi', how='inner')
        
        return df_full, df_peta, df_so, df_items_full
    except Exception as e:
        st.error(f"Gagal Sinkronisasi: {e}")
        return None, None, None, None

if st.sidebar.button("🔄 Paksa Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df_full, df_peta, df_so, df_items_full = load_data_pro()

# --- 3. FILTER & SEARCH ---
if df_full is not None:
    st.sidebar.header("⚙️ Filter")
    sel_lantai = st.sidebar.selectbox("Pilih Lantai", ["Lantai 1", "Lantai 2", "Lantai 3"])
    
    raw_cats = df_items_full['Kategori'].unique().tolist()
    sorted_cats = ["SEMUA KATEGORI"] + sorted([str(c) for c in raw_cats])
    sel_kategori = st.sidebar.selectbox("Filter Kategori", sorted_cats)
    
    search_q = st.text_input("🔍 Cari Barang / Rak", placeholder="Ketik nama barang...").upper()
    menu = st.radio("Mode:", ["📦 STOK OPNAME", "🔥 HEATMAP ANALYTICS", "🎯 PICKER"], horizontal=True)

    # --- 4. LOGIC ---
    floor_data = df_full[df_full['Lantai'] == sel_lantai].copy()
    
    # Filter per kategori (jika dipilih)
    if sel_kategori != "SEMUA KATEGORI":
        # Cek lokasi mana saja yang punya kategori tersebut
        lokasi_terpilih = df_items_full[df_items_full['Kategori'] == sel_kategori]['Kode_Lokasi'].unique()
        floor_data = floor_data[floor_data['Lokasi'].isin(lokasi_terpilih)]

    map_row = df_peta[df_peta['Lantai'] == sel_lantai]
    bg_map = f"https://lh3.googleusercontent.com/d/{map_row['URL'].values[0]}" if not map_row.empty else ""

    viz_df = pd.merge(floor_data, df_so[['Lokasi', 'STATUS']], on='Lokasi', how='left')
    viz_df['STATUS'] = viz_df['STATUS'].fillna('BELUM')

    h_locations = []
    if search_q:
        match = df_items_full[
            (df_items_full['Nama_Barang'].str.contains(search_q, na=False, case=False)) | 
            (df_items_full['Lokasi'].str.contains(search_q, na=False, case=False))
        ]
        h_locations = match['Lokasi'].unique().tolist()

    # --- 5. VISUALIZATION ---
    fig = go.Figure()

    if "STOK OPNAME" in menu:
        colors = {'DONE': '#28a745', 'ON PROGRESS': '#ffc107', 'PENDING': '#dc3545', 'BELUM': '#6c757d'}
        for status, color in colors.items():
            sub = viz_df[viz_df['STATUS'] == status]
            fig.add_trace(go.Scatter(
                x=sub['X'], y=sub['Y_Visual'], mode='markers+text',
                name=status, text=sub['Lokasi'] if not search_q else "",
                marker=dict(size=25, color=color, line=dict(width=2, color='white')),
                textposition="top center", customdata=sub['Lokasi'],
                hovertemplate="<b>Rak: %{customdata}</b><extra></extra>"
            ))

    elif "HEATMAP" in menu:
        # Tampilan Resume Item Original
        fig.add_trace(go.Scatter(
            x=floor_data['X'], y=floor_data['Y_Visual'],
            mode='markers+text', text=floor_data['Lokasi'],
            textposition="top center",
            marker=dict(
                size=floor_data['Total_Barang'].fillna(0) * 12,
                sizemode='area', sizeref=1.0,
                color=floor_data['Speed_Score'].fillna(0),
                colorscale='RdBu_r', # Merah = Slow, Biru = Fast
                showscale=True,
                line=dict(width=2, color='white')
            ),
            customdata=np.stack((
                floor_data['Total_Barang'].fillna(0),
                floor_data['List_Barang'].fillna("Kosong")
            ), axis=-1),
            hovertemplate=(
                "<b>Rak: %{text}</b><br>" +
                "Total SKU: %{customdata[0]}<br>" +
                "--------------------<br>" +
                "Item:<br>%{customdata[1]}<extra></extra>"
            )
        ))

    if h_locations:
        h_df = viz_df[viz_df['Lokasi'].isin(h_locations)]
        fig.add_trace(go.Scatter(
            x=h_df['X'], y=h_df['Y_Visual'], mode='markers',
            marker=dict(size=45, color="rgba(0,0,0,0)", line=dict(width=4, color="#00ffff")),
            name="Target", hoverinfo='skip'
        ))

    fig.update_layout(
        images=[dict(source=bg_map, xref="x", yref="y", x=0, y=1000, sizex=1000, sizey=1000, sizing="stretch", opacity=0.7, layer="below")],
        xaxis=dict(range=[0, 1000], visible=False), yaxis=dict(range=[0, 1000], visible=False),
        height=700, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, dragmode=False
    )

    # --- 6. RENDER ---
    st.markdown('<div class="map-container">', unsafe_allow_html=True)
    st.markdown('<div class="map-col">', unsafe_allow_html=True)
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun", config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="legend-col">', unsafe_allow_html=True)
    if "HEATMAP" in menu:
        st.write("### 🔥 Heatmap Info")
        st.write("🔵 **Biru:** Cenderung FAST")
        st.write("🔴 **Merah:** Cenderung SLOW")
        st.write("⚪ **Ukuran:** Jumlah SKU")
    else:
        st.write("### 🏷️ Status")
        for s, c in {'DONE': '#28a745', 'ON PROGRESS': '#ffc107', 'PENDING': '#dc3545', 'BELUM': '#6c757d'}.items():
            st.markdown(f'<div style="display:flex; align-items:center; margin-bottom:8px;"><div style="width:18px; height:18px; background:{c}; border-radius:50%; margin-right:10px;"></div><b>{s}</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if menu == "🎯 PICKER" and selected and "selection" in selected:
        pts = selected["selection"]["points"]
        if pts: st.info(f"📍 X: {int(pts[-1]['x'])} | Y: {1000 - int(pts[-1]['y'])}")
