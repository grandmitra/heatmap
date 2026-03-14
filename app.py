import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIG & DATA LOAD ---
st.set_page_config(page_title="Konoha Ops - Heatmap & Picker", layout="wide")

SHEET_ID = '1Ov3nggLzpDQPkMyfoJtT8i4Goe1MLJ2t6AFRFspi_X8'

def fix_google_url(url):
    if pd.isna(url) or str(url).strip() == "": return None
    try:
        if "googleusercontent.com" in str(url): return url
        file_id = url.split('d/')[1].split('/')[0] if 'd/' in url else url.split('/')[-1]
        return f"https://lh3.googleusercontent.com/d/1mtODhk7uOT_x1_rf53PIBtTT94r53I60{file_id}"
    except: return None

@st.cache_data(ttl=300)
def load_and_sync():
    try:
        df_data = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Data')
        df_master = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Master_Lokasi')
        df_peta = pd.read_csv(f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Peta_Lantai')

        # Bersihkan data koordinat
        df_master['X'] = pd.to_numeric(df_master['X'], errors='coerce')
        df_master['Y'] = pd.to_numeric(df_master['Y'], errors='coerce')
        
        # --- LOGIKA ANALYTICS PER RAK ---
        # Beri bobot: FAST=1, SLOW=-1 untuk rata-rata status
        df_data['Weight'] = df_data['Kategori'].apply(lambda x: 1 if x == 'FASTSLOW' else -1)
        
        rak_resume = df_data.groupby('Kode_Lokasi').agg(
            Total_Barang=('Nama_Barang', 'count'),
            Speed_Score=('Weight', 'mean'), # Nilai antara -1 sampai 1
            List_Barang=('Nama_Barang', lambda x: '<br>'.join(list(x)[:5])) # Ambil 5 contoh
        ).reset_index()

        merged = pd.merge(rak_resume, df_master, left_on='Kode_Lokasi', right_on='Lokasi', how='right')
        merged['Y_Visual'] = 1000 - merged['Y']
        merged['Status'] = merged['Speed_Score'].apply(lambda x: '🔥 Fast' if x > 0 else ('❄️ Slow' if x < 0 else '⚖️ Balanced'))
        
        return merged, df_peta, df_data
    except Exception as e:
        st.error(f"Error Sync: {e}")
        return None, None, None

df_rak, df_peta, df_raw = load_and_sync()

# --- 2. SIDEBAR ---
st.sidebar.image("https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjOSYdAHgNypARS4Hgo0dIYjUDv9dqrEKxp20CPHJ2WE_VMJ2mNu9gEdMUbrZl6OX8dKk8rw-6J1jl4qBtggKHCpRcz6oTlXFdQbCGG3JmeoRYNDRV32VcGj4xUlFbPTuQ1NwnvQ7lK6jY/s1600/Sharingan.gif", width=80)
st.sidebar.title("Konoha Analytics")

sel_lantai = st.sidebar.selectbox("Pilih Lantai", ["Lantai 1", "Lantai 2", "Lantai 3"])
mode = st.sidebar.radio("Mode Visual", ["Heatmap Resume", "Detail Barang", "Coordinate Picker"])

# Filter Data Berdasarkan Lantai
floor_df = df_rak[df_rak['Lantai'] == sel_lantai].copy()

# --- 3. MAIN INTERFACE ---
st.header(f"📊 {mode} - {sel_lantai}")

# Background Map Logic
map_row = df_peta[df_peta['Lantai'] == sel_lantai]
bg_map = f"https://lh3.googleusercontent.com/d/{map_row['URL'].values[0]}" if not map_row.empty else ""

if mode == "Heatmap Resume":
    # Membuat Chart Heatmap
    fig = go.Figure()
    
    # Tambahkan titik agregat
    fig.add_trace(go.Scatter(
        x=floor_df['X'], y=floor_df['Y_Visual'],
        mode='markers+text',
        text=floor_df['Lokasi'],
        textposition="top center",
        marker=dict(
            size=floor_df['Total_Barang'].fillna(0) * 8, # Ukuran berdasarkan densitas
            sizemode='area', sizeref=0.5,
            color=floor_df['Speed_Score'].fillna(0), # Warna berdasarkan speed
            colorscale='RdBu_r', # Red (Fast) to Blue (Slow)
            showscale=True,
            colorbar=dict(title="Speed Index", tickvals=[-1, 0, 1], ticktext=["Slow", "Mix", "Fast"]),
            line=dict(width=2, color='white')
        ),
        hovertemplate=(
            "<b>Rak: %{text}</b><br>" +
            "Status: %{customdata[0]}<br>" +
            "Total Item: %{customdata[1]}<br>" +
            "Isi Rak:<br>%{customdata[2]}<extra></extra>"
        ),
        customdata=np.stack((floor_df['Status'], floor_df['Total_Barang'].fillna(0), floor_df['List_Barang'].fillna("-")), axis=-1)
    ))

elif mode == "Detail Barang":
    # Join ulang untuk mendapatkan titik per barang secara spesifik
    detail_df = pd.merge(df_raw, df_rak[['Lokasi', 'X', 'Y_Visual', 'Lantai']], left_on='Kode_Lokasi', right_on='Lokasi')
    detail_df = detail_df[detail_df['Lantai'] == sel_lantai]
    
    fig = px.scatter(detail_df, x="X", y="Y_Visual", color="Kategori", 
                     hover_name="Nama_Barang", text="Kode_Lokasi",
                     color_discrete_map={"FASTSLOW": "#ff4b4b", "SLOWDEAD": "#1c83e1"})
    fig.update_traces(marker=dict(size=12, line=dict(width=1, color='white')))

else: # Coordinate Picker
    st.info("Klik pada peta untuk mendapatkan nilai X dan Y.")
    # Canvas kosong untuk picker
    fig = px.scatter(x=[0, 1000], y=[0, 1000], opacity=0)

# Final Layouting
fig.update_layout(
    images=[dict(source=bg_map, xref="x", yref="y", x=0, y=1000, sizex=1000, sizey=1000, sizing="stretch", opacity=0.7, layer="below")],
    xaxis=dict(range=[0, 1000], visible=False),
    yaxis=dict(range=[0, 1000], visible=False),
    height=800, margin=dict(l=0, r=0, t=30, b=0),
    clickmode='event+select'
)

# Output Chart
selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

# Handle Picker Output
if mode == "Coordinate Picker" and selected and "selection" in selected:
    points = selected["selection"]["points"]
    if points:
        px_val, py_val = int(points[-1]['x']), 1000 - int(points[-1]['y'])
        st.success(f"📍 Koordinat Terdeteksi: X={px_val}, Y={py_val}")
        st.code(f"{px_val}\t{py_val}", language="text")
        st.caption("Salin angka di atas ke Google Sheets Anda.")

# --- 4. ANALYTICS CARD ---
if mode == "Heatmap Resume":
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rak", len(floor_df))
    c2.metric("Rak Prioritas (Fast)", len(floor_df[floor_df['Speed_Score'] > 0]))
    c3.metric("Rak Butuh Evaluasi (Slow)", len(floor_df[floor_df['Speed_Score'] < 0]))
