# ==========================================
# Aplikasi Simulasi Pajak Emisi Kendaraan Bermotor
# Berdasarkan Permendagri No. 7 Tahun 2025
# ==========================================
import streamlit as st

# -------------------------------
# Data Baku Mutu Emisi
# -------------------------------
baku_mutu = {
    "Diesel": {
        "<2010": 65,
        "2010–2021": 40,
        ">2021": 30
    },
    "Bensin": {
        "<2010": {"CO": 4, "HC": 1000},
        "2010–2021": {"CO": 1, "HC": 150},
        ">2021": {"CO": 0.5, "HC": 100}
    },
    "Roda Dua": {
        "<2010": {"CO": 5.5, "HC": 2200},
        "2010–2021": {"CO": 4, "HC": 1800},
        ">2021": {"CO": 3, "HC": 1000}
    }
}

# -------------------------------
# Default Nilai Alfa (editable)
# -------------------------------
default_alfa = {
    "Motor 2-tak": 0.3,
    "Motor 4-tak": 0.1,
    "Sedan/MPV Euro 2": 0.2,
    "Sedan/MPV Euro 4": 0.1,
    "SUV/Jeep": 0.25,
    "Truk/Bis Euro 2": 0.4,
    "Truk/Bis Euro 4": 0.2,
    "Niaga Ringan": 0.3,
    "CNG": 0.1
}

# -------------------------------
# Nilai KD (Koefisien Dasar)
# -------------------------------
nilai_KD = {
    "Motor 2-tak": 1.0,
    "Motor 4-tak": 1.0,
    "Sedan/MPV Euro 2": 1.025,
    "Sedan/MPV Euro 4": 1.025,
    "SUV/Jeep": 1.05,
    "Truk/Bis Euro 2": 1.1,
    "Truk/Bis Euro 4": 1.1,
    "Niaga Ringan": 1.085,
    "CNG": 1.025
}

# -------------------------------
# Fungsi bantu
# -------------------------------
def kategori_emisi(jenis):
    if jenis in ["Truk/Bis Euro 2", "Truk/Bis Euro 4", "Niaga Ringan"]:
        return "Diesel"
    elif jenis in ["Motor 2-tak", "Motor 4-tak"]:
        return "Roda Dua"
    else:
        return "Bensin"

# -------------------------------
# Streamlit UI
# -------------------------------
st.title("🚗 Simulasi Pajak Emisi Kendaraan Bermotor")
st.caption("Berdasarkan **Permendagri No. 7 Tahun 2025** dan **PERMEN LHK no 8 tahun 2023**")

# 1. Jenis Kendaraan
jenis = st.selectbox(
    "Pilih Jenis Kendaraan:",
    list(default_alfa.keys())
)

# 2. Tahun Kendaraan
tahun = st.number_input("Masukkan Tahun Kendaraan:", min_value=1980, max_value=2025, value=2020)

# Tentukan periode baku mutu
if tahun < 2010:
    periode = "<2010"
elif tahun <= 2021:
    periode = "2010–2021"
else:
    periode = ">2021"

# 3. Hasil Uji Emisi
kategori = kategori_emisi(jenis)
st.subheader("Hasil Nilai Ukur Emisi")

if kategori == "Diesel":
    opasitas = st.number_input("Opasitas (%)", min_value=0.0, value=40.0)
    hasil_emisi = {"Opasitas": opasitas}
else:
    co = st.number_input("CO (%)", min_value=0.0, value=1.0)
    hc = st.number_input("HC (ppm)", min_value=0.0, value=150.0)
    hasil_emisi = {"CO": co, "HC": hc}

# 4. Nilai Alfa (dapat diedit user)
st.markdown("### ⚙️ Pengaturan Lanjutan")
alfa = st.number_input(
    f"Nilai Alfa (α) untuk {jenis}:",
    min_value=0.0,
    max_value=1.0,
    value=default_alfa[jenis],
    step=0.01,
    help="Nilai alfa dapat diubah sesuai kebijakan atau hasil kajian emisi."
)

# 5. Nilai Jual Kendaraan
# njkb = st.number_input("Nilai Jual Kendaraan Bermotor (Rp):", min_value=0.0, value=150_000_000.0, step=1_000_000.0)
st.markdown("### 💰 Nilai Jual Kendaraan Bermotor (NJKB)")
njkb_str = st.text_input(
    "Masukkan Nilai Jual Kendaraan (Rp):",
    value="15,000,000",
    help="Masukkan nilai jual kendaraan, contoh: 150,000,000"
)

# Hapus karakter non-angka dan ubah ke float
try:
    njkb = float(njkb_str.replace(",", "").replace(".", ""))
except ValueError:
    st.error("⚠️ Format angka tidak valid! Gunakan koma atau titik untuk pemisah ribuan.")
    st.stop()
    
# 6. Tarif Pajak Daerah
tarif_pajak = st.number_input("Tarif Pajak Daerah (%):", min_value=0.0, value=2.0)

# Tombol Simulasi
if st.button("🔍 Simulasikan PKB Emisi"):

    # 1. DP PKB
    dp_pkb = njkb * (tarif_pajak / 100)

    # 2. KD
    kd = nilai_KD[jenis]

    # 3. Rasio Emisi
    if kategori == "Diesel":
        baku = baku_mutu["Diesel"][periode]
        rasio_emisi = hasil_emisi["Opasitas"] / baku
    else:
        baku = baku_mutu[kategori][periode]
        rasio_co = hasil_emisi["CO"] / baku["CO"]
        rasio_hc = hasil_emisi["HC"] / baku["HC"]
        rasio_emisi = max(rasio_co, rasio_hc)

    # 4. KE
    ke = alfa * (rasio_emisi - 1)

    # 5. PKB Dasar
    pkb_dasar = dp_pkb * kd

    # 6. PKB Emisi
    pkb_emisi = dp_pkb * (kd + ke)

    # 7. Selisih
    selisih = pkb_emisi - pkb_dasar
    persen_kenaikan = (selisih / pkb_dasar * 100) if pkb_dasar > 0 else 0

    # -------------------------------
    # Hasil Simulasi
    # -------------------------------
    st.subheader("📊 Hasil Simulasi PKB")
    st.write(f"**Rasio Emisi:** {rasio_emisi:.3f}")
    st.write(f"**Koefisien Emisi (KE):** {ke:.4f}")
    st.write("---")

    col1, col2, col3 = st.columns(3)
    col1.metric("PKB Dasar (Rp)", f"{pkb_dasar:,.0f}")
    col2.metric("PKB Emisi (Rp)", f"{pkb_emisi:,.0f}")
    col3.metric("Selisih (Rp)", f"{selisih:,.0f}", f"{persen_kenaikan:.2f}%")

    st.write("---")
    st.caption("DP PKB = NJKB × Tarif Pajak Daerah\nPKB Emisi = DP PKB × (KD + KE)\nNilai Alfa (α) dapat diubah sesuai hasil riset atau kebijakan.")






