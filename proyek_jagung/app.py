# app.py — Geo-Interactive Agricultural Dashboard v2.0 (Modern Elegant)
import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import plotly.express as px
import folium
from streamlit_folium import st_folium

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="🌾 Geo Dashboard Jagung v2.0", page_icon="🌽", layout="wide")
THEME_COLOR = "#0b7a3f"

st.markdown(f"""
<style>
body {{ background-color: #f6fff7; }}
[data-testid="stMetricValue"] {{ color: {THEME_COLOR}; font-weight: 700; }}
.stButton>button {{ background-color: {THEME_COLOR}; color: white; border-radius:8px; }}
.stDownloadButton>button {{ background-color:#2fbf71; color:white; border-radius:8px; }}
.card {{ background: white; border-radius:12px; padding:18px; box-shadow:0 6px 18px rgba(0,0,0,0.06); margin-bottom:14px; }}
.header-gradient {{ background: linear-gradient(90deg,#e8f8ee,{THEME_COLOR}); padding:14px; border-radius:10px; margin-bottom:10px; }}
.small {{ font-size:12px; color:#666; }}
</style>
""", unsafe_allow_html=True)

# -------------------------
# PATHS
# -------------------------
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
USERS_FILE = "users.csv"

# default users for prototype
if not os.path.exists(USERS_FILE):
    pd.DataFrame([{"username":"admin","password":"admin123","role":"Admin"},
                  {"username":"worker","password":"worker123","role":"Field Worker"}]).to_csv(USERS_FILE, index=False)

# -------------------------
# SCHEMAS
# -------------------------
SCHEMAS = {
    "blok.csv": ["ID Blok","Luas (ha)","Lokasi","Latitude","Longitude","pH","Kelembapan (%)","Kesuburan","Status Tanam","Foto (link)"],
    "tanaman.csv": ["ID Blok","Jenis Jagung","Tanggal Tanam","Estimasi Panen (kg)","Jumlah Bibit","Varietas","Sumber Bibit"],
    "pupuk.csv": ["ID Blok","Jenis Pupuk","Jumlah (kg)","Tanggal Pemakaian","Jenis Pestisida","Jadwal Penyemprotan"],
    "tenaga_kerja.csv": ["Nama Pekerja","ID Blok","Tugas","Jam Kerja","Upah (Rp)"],
    "panen.csv": ["ID Blok","Tanggal Panen","Hasil Panen (kg)","Grade","Harga Jual (Rp/kg)","Pembeli"],
    "keuangan.csv": ["ID Blok","Biaya Produksi (Rp)","Pemasukan (Rp)","Laba Bersih (Rp)"]
}

# -------------------------
# HELPERS: IO & CACHE
# -------------------------
def csv_path(name): return os.path.join(DATA_DIR, name)

@st.cache_data
def load_data_cached(file_name):
    path = csv_path(file_name)
    if not os.path.exists(path):
        if file_name in SCHEMAS:
            pd.DataFrame(columns=SCHEMAS[file_name]).to_csv(path, index=False)
        else:
            pd.DataFrame().to_csv(path, index=False)
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.DataFrame()
    return df

def load_data(file_name):
    return load_data_cached(file_name)

def clear_load_cache():
    load_data_cached.clear()

def save_data(df, file_name):
    df.to_csv(csv_path(file_name), index=False)
    clear_load_cache()

def ensure_table(file_name):
    path = csv_path(file_name)
    if not os.path.exists(path) and file_name in SCHEMAS:
        pd.DataFrame(columns=SCHEMAS[file_name]).to_csv(path, index=False)
        clear_load_cache()

def df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()

def read_uploaded_file(uploaded):
    try:
        if uploaded.name.lower().endswith(".csv"):
            return pd.read_csv(uploaded)
        else:
            return pd.read_excel(uploaded)
    except Exception as e:
        st.error("Gagal membaca file upload: " + str(e))
        return None

# -------------------------
# SAFE RERUN HELPER
# -------------------------
def safe_rerun():
    """Safe rerun for Streamlit 1.27+ without using experimental_rerun"""
    st.session_state["_safe_rerun"] = True

if "_safe_rerun" in st.session_state and st.session_state["_safe_rerun"]:
    st.session_state["_safe_rerun"] = False
    st.rerun()

# -------------------------
# AUTH
# -------------------------
def login_page():
    st.markdown('<div class="header-gradient"><h2>🌿 Dashboard Jagung v2.0 — Login</h2></div>', unsafe_allow_html=True)
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Masuk"):
        try:
            users = pd.read_csv(USERS_FILE)
        except Exception:
            st.error("File users.csv tidak ditemukan atau korup.")
            return
        match = users[(users.username==username)&(users.password==password)]
        if not match.empty:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.session_state['role'] = match.iloc[0]['role']
            st.success(f"Selamat datang, {username} ({st.session_state['role']})")
            safe_rerun()
        else:
            st.error("Username/password salah.")

if 'logged_in' not in st.session_state:
    login_page()
    st.stop()

# -------------------------
# SIDEBAR NAV
# -------------------------
st.sidebar.markdown(f"**👋 {st.session_state.get('username','-')} ({st.session_state.get('role','-')})**")
menu = st.sidebar.selectbox("Menu", ["🏠 Dashboard","🧱 Data Blok Lahan","🌱 Data Tanaman","🧪 Pupuk & Pestisida","👷 Tenaga Kerja","🌾 Produksi & Panen","💰 Keuangan","🗺️ Peta Blok Lahan","⚙️ Pengaturan (Admin)"])

# -------------------------
# UTILS
# -------------------------
# -------------------------
# UTILS
# -------------------------
def align_to_schema(df_up, schema):
    """
    Menyamakan DataFrame dengan schema:
    - Rename kolom sesuai schema (case-insensitive)
    - Tambahkan kolom yang hilang dengan pd.NA
    - Urutkan kolom sesuai schema
    """
    cols_map = {}
    for c in df_up.columns:
        for s in schema:
            if c.strip().lower() == s.strip().lower():
                cols_map[c] = s
                break
    df_up = df_up.rename(columns=cols_map)
    for s in schema:
        if s not in df_up.columns:
            df_up[s] = pd.NA
    df_up = df_up[schema]
    return df_up

def upload_section(file_name, id_col=None):
    st.markdown("**Import data (CSV / XLSX)**")
    uploaded = st.file_uploader(f"Upload file untuk `{file_name}`", type=["csv","xlsx"], key=file_name+"_u")
    if uploaded is None:
        return None
    df_up = read_uploaded_file(uploaded)
    if df_up is None:
        return None
    st.info(f"Terbaca: {uploaded.name} — {df_up.shape[0]} baris")
    mode = st.radio("Mode import", ["Replace (timpa seluruh tabel)","Append (gabung, hindari duplikat jika ID ada)"], key=file_name+"_mode")
    if file_name in SCHEMAS:
        df_up = align_to_schema(df_up, SCHEMAS[file_name])
    if st.button("Proses Import", key=file_name+"_proses"):
        existing = load_data(file_name)
        existing = align_to_schema(existing, SCHEMAS[file_name])  # ✅ pastikan schema sama
        if mode.startswith("Replace"):
            save_data(df_up, file_name)
            st.success("Tabel diganti dengan data baru.")
            safe_rerun()
        else:
            combined = pd.concat([existing, df_up], ignore_index=True)
            if id_col and id_col in combined.columns:
                combined = combined.drop_duplicates(subset=[id_col], keep="last")
            save_data(combined, file_name)
            st.success("Data berhasil digabung (append).")
            safe_rerun()

def manage_table_page(title, file_name, id_col=None):
    st.markdown(f'<div class="header-gradient"><h3>{title}</h3></div>', unsafe_allow_html=True)
    ensure_table(file_name)
    df = load_data(file_name)
    df = align_to_schema(df, SCHEMAS[file_name])  # ✅ pastikan semua kolom schema muncul

    role = st.session_state.get("role", "")

    # -----------------------
    # 📁 Import / Export
    # -----------------------
    with st.expander("📁 Import / Export"):
        if role != "Viewer":  # 🔒 Viewer tidak boleh upload
            upload_section(file_name, id_col=id_col)
        if not df.empty:
            st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8"), file_name, mime="text/csv")
            st.download_button("⬇️ Download Excel", df_to_excel_bytes(df), file_name.replace(".csv", ".xlsx"))

    # -----------------------
    # 📋 Data Tabel
    # -----------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if role == "Viewer":  # 🔒 Mode tampilan saja
        st.subheader("👁️ Tampilan Data (Read-Only)")
        st.dataframe(df, use_container_width=True)
        st.info("Mode Viewer: tidak dapat menambah, mengedit, atau menghapus data.")
    else:
        st.subheader("✏️ Edit tabel (klik sel untuk edit langsung)")
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        if st.button("💾 Simpan Perubahan", key=file_name + "_save"):
            for c in edited.columns:
                if pd.api.types.is_datetime64_any_dtype(edited[c]):
                    edited[c] = edited[c].dt.strftime("%Y-%m-%d")
            save_data(edited, file_name)
            st.success("Perubahan disimpan.")
            safe_rerun()

        if id_col and id_col in df.columns and not df.empty:
            st.markdown("### 🗑️ Hapus baris berdasarkan ID")
            ids = df[id_col].astype(str).tolist()
            to_del = st.multiselect("Pilih ID untuk dihapus", ids)
            if st.button("Hapus Terpilih", key=file_name + "_del"):
                if to_del:
                    df2 = df[~df[id_col].astype(str).isin(to_del)]
                    save_data(df2, file_name)
                    st.success(f"{len(to_del)} baris dihapus.")
                    safe_rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# -------------------------
# DASHBOARD UTAMA
# -------------------------

if menu == "🏠 Dashboard":
    st.markdown("<h1 style='color:#0b7a3f'>🌾 Dashboard Jagung - SmartFarm H.Imis</h1>", unsafe_allow_html=True)
    st.caption("📊 Dashboard berbasis data CSV — dibuat oleh Yori Destrama")

    # Load data dari CSV
    blok = load_data("blok.csv")
    panen = load_data("panen.csv")
    keu = load_data("keuangan.csv")
    tanaman = load_data("tanaman.csv")
    pupuk = load_data("pupuk.csv")
    tenaga = load_data("tenaga_kerja.csv")

# -------------------------
    # KONVERSI NUMERIK (penting supaya .mean() & .sum() tidak nan)
    # -------------------------
    for col in ["pH","Luas (ha)"]:
        if col in blok.columns:
            blok[col] = pd.to_numeric(blok[col], errors='coerce')
    for col in ["Hasil Panen (kg)"]:
        if col in panen.columns:
            panen[col] = pd.to_numeric(panen[col], errors='coerce')
    for col in ["Laba Bersih (Rp)"]:
        if col in keu.columns:
            keu[col] = pd.to_numeric(keu[col], errors='coerce')

    # -------------------------
    # CEK DATA & Fallback
    # -------------------------
    if blok.empty:
        st.warning("⚠️ Data blok kosong. Dashboard menampilkan nilai 0 untuk sebagian metrik.")
        blok = pd.DataFrame([{"ID Blok":"B01","Luas (ha)":0,"pH":0,"Kesuburan":"-","Status Tanam":"-"}])

    if panen.empty:
        st.info("ℹ️ Data panen belum tersedia. Nilai panen ditampilkan 0.")

    if keu.empty:
        st.info("ℹ️ Data keuangan belum tersedia. Nilai laba ditampilkan 0.")

    # -------------------------
    # METRIK UTAMA
    # -------------------------
    total_blok = len(blok)
    avg_ph = round(blok["pH"].mean(), 2) if "pH" in blok.columns else "-"
    total_panen = int(panen["Hasil Panen (kg)"].sum()) if not panen.empty and "Hasil Panen (kg)" in panen.columns else 0
    total_laba = int(keu["Laba Bersih (Rp)"].sum()) if not keu.empty and "Laba Bersih (Rp)" in keu.columns else 0
    avg_luas = round(blok["Luas (ha)"].mean(), 2) if "Luas (ha)" in blok.columns else "-"
    total_jenis_tanaman = tanaman["Jenis Jagung"].nunique() if not tanaman.empty else 0
    total_pekerja = len(tenaga) if not tenaga.empty else 0

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1: st.metric("🌱 Jumlah Blok", total_blok)
    with col2: st.metric("💧 Rata-rata pH", avg_ph)
    with col3: st.metric("🌽 Total Panen (kg)", f"{total_panen:,}")
    with col4: st.metric("💰 Total Laba Bersih (Rp)", f"{total_laba:,}")
    with col5: st.metric("📏 Rata-rata Luas Blok (ha)", avg_luas)
    with col6: st.metric("🌾 Jenis Jagung", total_jenis_tanaman)
    with col7: st.metric("👷 Jumlah Tenaga Kerja", total_pekerja)

    st.divider()

    # -------------------------
    # DISTRIBUSI KESUBURAN
    # -------------------------
    if "Kesuburan" in blok.columns and not blok.empty:
        fig_pie = px.pie(
            blok, 
            names="Kesuburan", 
            title="Distribusi Kesuburan Tanah", 
            color_discrete_sequence=px.colors.sequential.Greens
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # -------------------------
    # STATUS TANAM
    # -------------------------
    if "Status Tanam" in blok.columns and not blok.empty:
        status_count = blok["Status Tanam"].value_counts().reset_index()
        status_count.columns = ["Status", "Jumlah Blok"]
        fig_status = px.bar(
            status_count, x="Status", y="Jumlah Blok", 
            color="Jumlah Blok", color_continuous_scale="Greens", 
            title="Jumlah Blok per Status Tanam"
        )
        st.plotly_chart(fig_status, use_container_width=True)

    # -------------------------
    # TREND PANEN BULANAN
    # -------------------------
    if not panen.empty and "Tanggal Panen" in panen.columns and "Hasil Panen (kg)" in panen.columns:
        panen["Tanggal Panen"] = pd.to_datetime(panen["Tanggal Panen"], errors='coerce')
        panen["Bulan"] = panen["Tanggal Panen"].dt.to_period("M").astype(str)
        panen_bulanan = panen.groupby("Bulan")["Hasil Panen (kg)"].sum().reset_index()
        fig_line = px.line(
            panen_bulanan, x="Bulan", y="Hasil Panen (kg)", markers=True,
            title="Tren Hasil Panen Bulanan", color_discrete_sequence=["#0b7a3f"]
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # -------------------------
    # LABA PER BLOK
    # -------------------------
    if not keu.empty and all(col in keu.columns for col in ["ID Blok", "Pemasukan (Rp)", "Biaya Produksi (Rp)", "Laba Bersih (Rp)"]):
        fig_profit = px.bar(
            keu, x="ID Blok", y=["Pemasukan (Rp)", "Biaya Produksi (Rp)", "Laba Bersih (Rp)"],
            barmode="group", title="Perbandingan Pemasukan, Biaya, dan Laba per Blok",
            color_discrete_sequence=["#a3e4a2", "#0b7a3f", "#ffa500"]
        )
        st.plotly_chart(fig_profit, use_container_width=True)

    # -------------------------
    # RINGKASAN TABEL
    # -------------------------
    st.markdown("### 📋 Ringkasan Blok + Panen + Keuangan")
    df_summary = blok[["ID Blok","Luas (ha)","pH","Kesuburan","Status Tanam"]].copy()
    if not panen.empty and "Hasil Panen (kg)" in panen.columns:
        panen_sum = panen.groupby("ID Blok")["Hasil Panen (kg)"].sum().reset_index()
    else:
        panen_sum = pd.DataFrame(columns=["ID Blok","Hasil Panen (kg)"])
    if not keu.empty and "Laba Bersih (Rp)" in keu.columns:
        keu_sum = keu.groupby("ID Blok")["Laba Bersih (Rp)"].sum().reset_index()
    else:
        keu_sum = pd.DataFrame(columns=["ID Blok","Laba Bersih (Rp)"])
    df_summary = df_summary.merge(panen_sum, on="ID Blok", how="left")
    df_summary = df_summary.merge(keu_sum, on="ID Blok", how="left")
    df_summary.fillna(0, inplace=True)

    # Tampilkan data editor
    edited_summary = st.data_editor(df_summary, num_rows="dynamic", use_container_width=True)

    # Simpan perubahan
    if st.button("💾 Simpan Ringkasan (Update Data Asli)"):
        blok_update = edited_summary[["ID Blok","Luas (ha)","pH","Kesuburan","Status Tanam"]].copy()
        save_data(blok_update, "blok.csv")
        if not panen.empty:
            panen_update = panen.merge(edited_summary[["ID Blok","Hasil Panen (kg)"]], on="ID Blok", how="right")
            panen_update["Hasil Panen (kg)"].fillna(0, inplace=True)
            save_data(panen_update, "panen.csv")
        if not keu.empty:
            keu_update = keu.merge(edited_summary[["ID Blok","Laba Bersih (Rp)"]], on="ID Blok", how="right")
            keu_update["Laba Bersih (Rp)"].fillna(0, inplace=True)
            save_data(keu_update, "keuangan.csv")
        st.success("Ringkasan disimpan ke data asli.")
        safe_rerun()

    # Hapus baris
    st.markdown("### 🗑️ Hapus Baris Ringkasan")
    ids_summary = df_summary["ID Blok"].astype(str).tolist()
    to_del_summary = st.multiselect("Pilih ID Blok untuk dihapus", ids_summary)
    if st.button("Hapus Baris Terpilih dari Ringkasan"):
        if to_del_summary:
            blok2 = blok[~blok["ID Blok"].astype(str).isin(to_del_summary)]
            save_data(blok2, "blok.csv")
            panen2 = panen[~panen["ID Blok"].astype(str).isin(to_del_summary)]
            save_data(panen2, "panen.csv")
            keu2 = keu[~keu["ID Blok"].astype(str).isin(to_del_summary)]
            save_data(keu2, "keuangan.csv")
            st.success(f"{len(to_del_summary)} baris dihapus dari semua data terkait.")
            safe_rerun()


# -------------------------
# CRUD PAGES
# -------------------------
elif menu == "🧱 Data Blok Lahan":
    manage_table_page("🧱 Data Blok Lahan", "blok.csv", id_col="ID Blok")

elif menu == "🌱 Data Tanaman":
    manage_table_page("🌱 Data Tanaman", "tanaman.csv", id_col="ID Blok")

elif menu == "🧪 Pupuk & Pestisida":
    manage_table_page("🧪 Pupuk & Pestisida", "pupuk.csv", id_col="ID Blok")

elif menu == "👷 Tenaga Kerja":
    manage_table_page("👷 Tenaga Kerja", "tenaga_kerja.csv", id_col="Nama Pekerja")

elif menu == "🌾 Produksi & Panen":
    manage_table_page("🌾 Produksi & Panen", "panen.csv", id_col="ID Blok")

elif menu == "💰 Keuangan":
    manage_table_page("💰 Data Keuangan", "keuangan.csv", id_col="ID Blok")

# -------------------------
# -------------------------
# -------------------------
# GEO MAP PAGE
# -------------------------
elif menu == "🗺️ Peta Blok Lahan":
    st.markdown(
        '<div class="header-gradient"><h3>🗺️ Peta Blok Lahan</h3></div>',
        unsafe_allow_html=True
    )

    # Pilihan tipe peta
    map_type = st.radio("Pilih tipe peta", ["🗺️ Geo Map (Marker)", "🖼️ Peta Offline Blok"])

    if map_type == "🗺️ Geo Map (Marker)":
        # ------------------- kode Geo Map lama -------------------
        blok = load_data("blok.csv")

        # Jika data kosong, buat dummy
        if blok.empty:
            st.warning("Belum ada data blok lahan. Menampilkan dummy sementara.")
            blok = pd.DataFrame([
                {
                    "ID Blok": f"B{i+1:02}",
                    "Luas (ha)": round(1.8 + i*0.4,2),
                    "Lokasi": "Tambahrejo, Blora",
                    "pH": 6.7,
                    "Kesuburan": "Tinggi",
                    "Status Tanam": "Tumbuh",
                    "Latitude": -3.316 + i*0.001,
                    "Longitude": 114.602 + i*0.001
                }
                for i in range(6)
            ])

        # Sidebar filter
        statuses = ["Semua"] + sorted(blok["Status Tanam"].dropna().astype(str).unique().tolist()) if "Status Tanam" in blok.columns else ["Semua"]
        kesub = ["Semua"] + sorted(blok["Kesuburan"].dropna().astype(str).unique().tolist()) if "Kesuburan" in blok.columns else ["Semua"]
        sel_status = st.sidebar.selectbox("Status Tanam", statuses, key="map_status")
        sel_kesub = st.sidebar.selectbox("Kesuburan", kesub, key="map_kesub")

        # Pastikan Latitude dan Longitude ada
        if ("Latitude" not in blok.columns) or ("Longitude" not in blok.columns) or blok["Latitude"].isna().any() or blok["Longitude"].isna().any():
            center_lat, center_lon = -3.316, 114.602
            blok["Latitude"] = center_lat + (np.random.rand(len(blok)) - 0.5) * 0.02
            blok["Longitude"] = center_lon + (np.random.rand(len(blok)) - 0.5) * 0.02

        # Filter data
        blok_filtered = blok.copy()
        if sel_status != "Semua":
            blok_filtered = blok_filtered[blok_filtered["Status Tanam"] == sel_status]
        if sel_kesub != "Semua":
            blok_filtered = blok_filtered[blok_filtered["Kesuburan"] == sel_kesub]

        # Jika filter kosong
        if blok_filtered.empty:
            st.warning("Data blok tidak ditemukan untuk filter ini.")
        else:
            # Map
            m = folium.Map(
                location=[blok_filtered["Latitude"].mean(), blok_filtered["Longitude"].mean()],
                zoom_start=15
            )
            folium.TileLayer('OpenStreetMap').add_to(m)
            folium.TileLayer('Esri.WorldImagery', name='Satelit').add_to(m)
            folium.LayerControl().add_to(m)

            # Marker
            for _, row in blok_filtered.iterrows():
                folium.Marker(
                    location=[row["Latitude"], row["Longitude"]],
                    popup=(
                        f"ID: {row['ID Blok']}<br>"
                        f"Luas: {row['Luas (ha)']} ha<br>"
                        f"Status: {row.get('Status Tanam','-')}<br>"
                        f"Kesuburan: {row.get('Kesuburan','-')}"
                    )
                ).add_to(m)

            st_folium(m, width=1024, height=600)

    else:
        # ================= PETA OFFLINE =================
        st.markdown("### 🖼️ Peta Blok Offline")
        st.image(r"C:\Users\LENOVO\Downloads\Peta Offline Blok.png", use_container_width=True)


# -------------------------
# ADMIN PAGE
# -------------------------
elif menu == "⚙️ Pengaturan (Admin)":
    if st.session_state.get("role","") != "Admin":
        st.warning("Hanya Admin yang bisa mengakses halaman ini.")
        st.stop()

    st.markdown('<div class="header-gradient"><h3>⚙️ Pengaturan Pengguna & Data</h3></div>', unsafe_allow_html=True)
    
    # EDIT USER
    users = pd.read_csv(USERS_FILE)
    edited = st.data_editor(users, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Simpan Pengguna"):
        save_data(edited, USERS_FILE)
        st.success("Pengguna disimpan.")
        safe_rerun()

    st.divider()

    # HAPUS SEMUA DATA (Admin Only)
    st.markdown("### ⚠️ Hapus Semua Data (Blok, Tanaman, Pupuk, Tenaga Kerja, Panen, Keuangan)")
    if st.button("🗑️ Hapus Semua Data"):
        for f in SCHEMAS.keys():
            save_data(pd.DataFrame(columns=SCHEMAS[f]), f)
        st.success("Semua data berhasil dihapus.")
        safe_rerun()



