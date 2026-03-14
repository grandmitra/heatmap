import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Konoha Ops - Enterprise", layout="wide")

SHEET_ID_MASTER = '1Ov3nggLzpDQPkMyfoJtT8i4Goe1MLJ2t6AFRFspi_X8'
SHEET_ID_SO = '1mjjDF1ETjOB_eTI6ChI6dqvg0wf9aCa7cJwx0x2K3No'

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=30) # Cache singkat untuk monitoring live
def load_all_sync():
    try:
        # Load Master
        df_master = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Master_Lokasi')
        df_peta = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Peta_Lantai')
        df_data = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_MASTER}/gviz/tq?tqx=out:csv&sheet=Data')
        
        # Load Stok Opname (Ralat: Sheet stat_lok)
        df_so = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID_SO}/gviz/tq?tqx=out:csv&sheet=stat_lok')

        # Cleaning Master
        df_master['X'] = pd.to_numeric(df_master['X'], errors='coerce')
        df_master['Y'] = pd.to_numeric(df_master['Y'], errors='coerce')
        df_master = df_master.dropna(subset=['X', 'Y'])
        
        # Speed Score for Heatmap
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
        st.error(f"Gagal Load Data: {e}")
        return None, None, None

df_main, df_peta, df_so = load_all_sync()

# --- 3. SIDEBAR ---
st.sidebar.title("Konoha Systems")
menu = st.sidebar.radio("Navigation", ["📦 Live Stok Opname", "🔥 Warehouse Heatmap", "🎯 Coordinate Picker"])
sel_lantai = st.sidebar.selectbox("Pilih Lantai", ["Lantai 1", "Lantai 2", "Lantai 3"])

if df_main is not None:
    floor_df = df_main[df_main['Lantai'] == sel_lantai].copy()
    map_row = df_peta[df_peta['Lantai'] == sel_lantai]
    bg_map = f"https://lh3.googleusercontent.com/d/{map_row['URL'].values[0]}" if not map_row.empty else ""

    # --- 4. MODULE: STOK OPNAME ---
    if menu == "📦 Live Stok Opname":
        st.title(f"Monitoring Live Stok Opname ({sel_lantai})")
        
        # Merge dengan sheet stat_lok (Join berdasarkan Lokasi)
        so_map = pd.merge(floor_df, df_so, left_on='Lokasi', right_on='Lokasi', how='left')
        
        # Penanganan Status (Mapping warna sesuai data Anda)
        so_map['STATUS'] = so_map['STATUS'].fillna('BELUM ADA DATA')
        
        # Map warna berdasarkan status di data Anda
        color_so = {
            'DONE': '#28a745',           # Hijau
            'ON PROGRESS': '#ffc107',    # Kuning
            'PENDING': '#dc3545',        # Merah
            'BELUM ADA DATA': '#6c757d'  # Abu-abu
        }
        
        fig = px.scatter(
            so_map, x="X", y="Y_Visual",
            color="STATUS", 
            text="Lokasi",
            hover_data={
                "TARGET SKU": True, 
                "P1": True, "P2": True, "P3": True,
                "X": False, "Y_Visual": False
            },
            color_discrete_map=color_so
        )
        
        fig.update_traces(marker=dict(size=22, line=dict(width=2, color='white')), textposition='top center')

    # --- 5. MODULE: HEATMAP ---
    elif menu == "🔥 Warehouse Heatmap":
        st.title("Heatmap Dominasi Rak")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=floor_df['X'], y=floor_df['Y_Visual'],
            mode='markers+text', text=floor_df['Lokasi'],
            marker=dict(
                size=floor_df['Total_Barang'].fillna(0) * 10,
                sizemode='area', sizeref=0.8,
                color=floor_df['Speed_Score'].fillna(0),
                colorscale='RdBu_r', showscale=True,
                line=dict(width=2, color='white')
            )
        ))

    # --- 6. MODULE: PICKER ---
    else:
        st.title("Coordinate Picker")
        fig = px.scatter(x=[0, 1000], y=[0, 1000], opacity=0)

    # Global Layout
    fig.update_layout(
        images=[dict(source=bg_map, xref="x", yref="y", x=0, y=1000, sizex=1000, sizey=1000, sizing="stretch", opacity=0.7, layer="below")],
        xaxis=dict(range=[0, 1000], visible=False),
        yaxis=dict(range=[0, 1000], visible=False),
        height=850, margin=dict(l=0, r=0, t=30, b=0),
        clickmode='event+select'
    )

    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

    # Picker Logic
    if menu == "🎯 Coordinate Picker" and selected and "selection" in selected:
        pts = selected["selection"]["points"]
        if pts:
            st.success(f"📍 X: {int(pts[-1]['x'])}, Y: {1000 - int(pts[-1]['y'])}")

    # --- 7. SUMMARY ---
    if menu == "📦 Live Stok Opname":
        st.markdown("---")
        done_count = len(so_map[so_map['STATUS'] == 'DONE'])
        total_rak = len(so_map)
        prog = int((done_count/total_rak)*100) if total_rak > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Lokasi", total_rak)
        c2.metric("Selesai (DONE)", done_count)
        c3.write(f"**Total Progress: {prog}%**")
        st.progress(prog/100)
