# ==========================================
# Aplikasi Simulasi Pajak Emisi Kendaraan Bermotor
# Berdasarkan Permendagri No. 7 Tahun 2025
# dan PERMEN LHK No. 8 Tahun 2023
# ==========================================

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
from datetime import datetime
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from io import BytesIO

# ===============================
# KONFIGURASI LLM / CHATBOT
# ===============================

MODEL_LLM = "gpt-4.1"

api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("❌ OPENAI_API_KEY belum diset di Streamlit Secrets atau Environment Variable")
    st.stop()

client = OpenAI(api_key=api_key)

# ===============================
# LOAD & CACHE LAPORAN PDF
# ===============================

@st.cache_data(show_spinner=False)
def load_pdf_text(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text


try:
    laporan_text = load_pdf_text("ringkasa_laporan.pdf")
except Exception:
    laporan_text = ""
    st.warning(
        "⚠️ File ringkasa_laporan.pdf tidak ditemukan atau belum dapat dibaca. "
        "Chatbot tetap berjalan, tetapi tanpa konteks laporan PDF."
    )

# ===============================
# DATA BAKU MUTU EMISI
# ===============================

# -------------------------------
# Bensin - Sepeda Motor
# -------------------------------
# Untuk sepeda motor:
# - Tahun < 2010 dibedakan menjadi 2-langkah dan 4-langkah
# - Tahun 2010 ke atas tidak dibedakan lagi 2-langkah/4-langkah

baku_mutu_bensin_motor = {
    "<2010": {
        "2-langkah": {"CO": 4.5, "HC": 6000},
        "4-langkah": {"CO": 5.5, "HC": 2200}
    },
    "2010–2016": {"CO": 4.0, "HC": 1800},
    ">2016": {"CO": 3.0, "HC": 1000}
}

# -------------------------------
# Bensin - Kategori M
# -------------------------------
# Digunakan untuk klasifikasi B dan C

baku_mutu_bensin_m = {
    "<2007": {"CO": 4.0, "HC": 1000},
    "2007–2018": {"CO": 1.0, "HC": 150},
    ">2018": {"CO": 0.5, "HC": 100}
}

# -------------------------------
# Bensin - Kategori N dan O
# -------------------------------
# Digunakan untuk klasifikasi D

baku_mutu_bensin_no = {
    "<2007": {"CO": 4.0, "HC": 1100},
    "2007–2018": {"CO": 1.0, "HC": 200},
    ">2018": {"CO": 0.5, "HC": 150}
}

# -------------------------------
# Diesel - Berdasarkan JBB
# -------------------------------

baku_mutu_diesel = {
    "<= 3.5 ton": {
        "<2010": 65,
        "2010–2021": 40,
        ">2021": 30
    },
    "> 3.5 ton": {
        "<2010": 65,
        "2010–2021": 40,
        ">2021": 35
    }
}

# ===============================
# BATAS KE MAKSIMUM DAN DEFAULT ALFA
# ===============================
# Data mengikuti file Excel "nilai alfa dan rasio emisi.xlsx"
# (kolom: Bahan Bakar, Klasifikasi, Segmen Tahun, Alpha, KE maksimal).
#
# Jika kombinasi bahan bakar + klasifikasi + periode tahun ada di tabel ini:
# - Nilai alfa otomatis terisi default sesuai tabel
# - Nilai KE hasil perhitungan dibatasi maksimum sesuai "KE maksimal"
#
# Jika kombinasi tidak ada:
# - Nilai alfa diisi manual oleh user
# - Nilai KE tidak dibatasi

ke_alfa_rules = {
    # BENSIN - KLASIFIKASI A
    ("Bensin", "A", "<2010"): {
        "alfa": 0.054,
        "ke_max": 0.11558577273659994
    },
    ("Bensin", "A", "2010–2016"): {
        "alfa": 0.054,
        "ke_max": 0.1269
    },
    ("Bensin", "A", ">2016"): {
        "alfa": 0.064,
        "ke_max": 0.215466666688
    },

    # BENSIN - KLASIFIKASI B
    ("Bensin", "B", "<2007"): {
        "alfa": 0.047,
        "ke_max": 0.07890908334430001
    },
    ("Bensin", "B", "2007–2018"): {
        "alfa": 0.052,
        "ke_max": 0.15343466665279976
    },
    ("Bensin", "B", ">2018"): {
        "alfa": 0.111,
        "ke_max": 0.12549105000000005
    },

    # BENSIN - KLASIFIKASI C
    ("Bensin", "C", "<2007"): {
        "alfa": 0.043,
        "ke_max": 0.08620066667669984
    },
    ("Bensin", "C", "2007–2018"): {
        "alfa": 0.21,
        "ke_max": 0.9458399999999999
    },
    ("Bensin", "C", ">2018"): {
        "alfa": 0.053,
        "ke_max": 0.15880566665695
    },

    # BENSIN - KLASIFIKASI D
    ("Bensin", "D", "<2007"): {
        "alfa": 0.043,
        "ke_max": 0.09126570832114997
    },
    ("Bensin", "D", "2007–2018"): {
        "alfa": 0.21,
        "ke_max": 1.031519999999999
    },
    ("Bensin", "D", ">2018"): {
        "alfa": 0.053,
        "ke_max": 0.07033099999999999
    },

    # DIESEL / SOLAR - KLASIFIKASI C
    ("Diesel", "C", "<2010"): {
        "alfa": 0.84,
        "ke_max": 0.4504984616159999
    },
    ("Diesel", "C", "2010–2021"): {
        "alfa": 0.84,
        "ke_max": 1.2264
    },
    ("Diesel", "C", ">2021"): {
        "alfa": 0.056,
        "ke_max": 0.04097333332399999
    },

    # DIESEL / SOLAR - KLASIFIKASI D
    ("Diesel", "D", "<2010"): {
        "alfa": 0.84,
        "ke_max": 0.5868046153200001
    },
    ("Diesel", "D", "2010–2021"): {
        "alfa": 0.84,
        "ke_max": 1.1988899999999998
    },
    ("Diesel", "D", ">2021"): {
        "alfa": 0.056,
        "ke_max": 0.0993066666592
    },

    # DIESEL / SOLAR - KLASIFIKASI E
    ("Diesel", "E", "<2010"): {
        "alfa": 0.84,
        "ke_max": 0.18200000027999994
    },
    ("Diesel", "E", "2010–2021"): {
        "alfa": 0.84,
        "ke_max": 0.58632
    },
    ("Diesel", "E", ">2021"): {
        "alfa": 0.056,
        "ke_max": 0.039088
    },

    # DIESEL / SOLAR - KLASIFIKASI F
    ("Diesel", "F", "<2010"): {
        "alfa": 0.84,
        "ke_max": 0.6821640000839997
    },
    ("Diesel", "F", "2010–2021"): {
        "alfa": 0.84,
        "ke_max": 0.9970799999999991
    },
    ("Diesel", "F", ">2021"): {
        "alfa": 0.056,
        "ke_max": 0.05651333333800001
    },

    # DIESEL / SOLAR - KLASIFIKASI G
    ("Diesel", "G", "<2010"): {
        "alfa": 0.84,
        "ke_max": 0.4392553845960001
    },
    ("Diesel", "G", "2010–2021"): {
        "alfa": 0.84,
        "ke_max": 1.12182
    },
    ("Diesel", "G", ">2021"): {
        "alfa": 0.056,
        "ke_max": 0.0018666666480000042
    }
}

# ===============================
# NILAI KD BERDASARKAN KLASIFIKASI
# ===============================

nilai_KD = {
    "A": 1.000,
    "B": 1.025,
    "C": 1.050,
    "D": 1.085,
    "E": 1.100,
    "F": 1.300,
    "G": 1.400
}

# ===============================
# KETERANGAN KLASIFIKASI
# ===============================

keterangan_bensin = """
**Keterangan Klasifikasi Kendaraan Bensin:**

- **A**: Motor, scooter, bajaj roda tiga penumpang  
- **B**: Sedan / 4–5 penumpang, city car  
- **C**: SUV, MPV 7 penumpang, jeep, minibus  
- **D**: Blind van, pick-up, pick-up box, mikrobus  
"""

keterangan_diesel = """
**Keterangan Klasifikasi Kendaraan Diesel:**

- **C**: SUV, MPV 7 penumpang, jeep, minibus  
- **D**: Blind van, pick-up, pick-up box, mikrobus  
- **E**: Bus sedang dan besar, angkutan umum  
- **F**: Truk kecil, light truck, engkel  
- **G**: Truk besar, tronton, trailer  
"""

# ===============================
# FUNGSI BANTU
# ===============================

def tentukan_periode_motor(tahun):
    if tahun < 2010:
        return "<2010"
    elif tahun <= 2016:
        return "2010–2016"
    else:
        return ">2016"


def tentukan_periode_bensin_non_motor(tahun):
    if tahun < 2007:
        return "<2007"
    elif tahun <= 2018:
        return "2007–2018"
    else:
        return ">2018"


def tentukan_periode_diesel(tahun):
    if tahun < 2010:
        return "<2010"
    elif tahun <= 2021:
        return "2010–2021"
    else:
        return ">2021"


def tentukan_periode_ke_alfa(bahan_bakar, klasifikasi, tahun):
    """
    Menentukan segmen tahun khusus untuk tabel nilai alfa dan KE maksimum.

    Bensin klasifikasi A:
    - <2010
    - 2010–2016
    - >2016

    Bensin klasifikasi B, C, D:
    - <2007
    - 2007–2018
    - >2018

    Diesel klasifikasi C, D, E, F, G:
    - <2010
    - 2010–2021
    - >2021
    """
    if bahan_bakar == "Bensin":
        if klasifikasi == "A":
            if tahun < 2010:
                return "<2010"
            elif tahun <= 2016:
                return "2010–2016"
            else:
                return ">2016"

        elif klasifikasi in ["B", "C", "D"]:
            if tahun < 2007:
                return "<2007"
            elif tahun <= 2018:
                return "2007–2018"
            else:
                return ">2018"

    elif bahan_bakar == "Diesel":
        if tahun < 2010:
            return "<2010"
        elif tahun <= 2021:
            return "2010–2021"
        else:
            return ">2021"

    return None


def ambil_rule_ke_alfa(bahan_bakar, klasifikasi, tahun):
    periode_rule = tentukan_periode_ke_alfa(
        bahan_bakar=bahan_bakar,
        klasifikasi=klasifikasi,
        tahun=tahun
    )

    rule = ke_alfa_rules.get(
        (bahan_bakar, klasifikasi, periode_rule)
    )

    return rule, periode_rule


def ambil_baku_mutu(bahan_bakar, klasifikasi, tahun, tipe_motor=None, jbb=None):
    """
    Fungsi untuk mengambil nilai baku mutu emisi berdasarkan:
    - bahan bakar / jenis mesin
    - klasifikasi kendaraan
    - tahun pembuatan
    - tipe motor khusus sepeda motor <2010
    - JBB khusus diesel

    Return:
    - baku mutu
    - periode baku mutu
    - kategori baku mutu
    - metode uji
    """

    if bahan_bakar == "Bensin":
        metode_uji = "Kondisi diam (Idle)"

        # Klasifikasi A = sepeda motor
        if klasifikasi == "A":
            periode = tentukan_periode_motor(tahun)

            if periode == "<2010":
                if tipe_motor is None:
                    return None, None, None, None

                baku = baku_mutu_bensin_motor["<2010"][tipe_motor]
                kategori_baku = f"Sepeda motor {tipe_motor}"

            else:
                baku = baku_mutu_bensin_motor[periode]
                kategori_baku = "Sepeda motor"

            return baku, periode, kategori_baku, metode_uji

        # Klasifikasi B dan C = Kategori M
        elif klasifikasi in ["B", "C"]:
            periode = tentukan_periode_bensin_non_motor(tahun)
            baku = baku_mutu_bensin_m[periode]
            kategori_baku = "Kategori M"
            return baku, periode, kategori_baku, metode_uji

        # Klasifikasi D = Kategori N dan O
        elif klasifikasi == "D":
            periode = tentukan_periode_bensin_non_motor(tahun)
            baku = baku_mutu_bensin_no[periode]
            kategori_baku = "Kategori N dan O"
            return baku, periode, kategori_baku, metode_uji

    elif bahan_bakar == "Diesel":
        metode_uji = "Percepatan bebas"

        if jbb is None:
            return None, None, None, None

        periode = tentukan_periode_diesel(tahun)
        baku = baku_mutu_diesel[jbb][periode]
        kategori_baku = f"Diesel dengan JBB {jbb}"
        return baku, periode, kategori_baku, metode_uji

    return None, None, None, None


def parse_rupiah(nilai_str):
    """
    Mengubah input rupiah seperti:
    15,000,000 atau 15.000.000 menjadi float 15000000
    """
    return float(nilai_str.replace(",", "").replace(".", "").strip())


def parse_float(nilai_str):
    """
    Mengubah angka desimal user.
    Mendukung input 0.2 atau 0,2
    """
    return float(nilai_str.replace(",", ".").strip())


def generate_pdf_bytes(data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 2 * cm

    def draw(text):
        nonlocal y
        c.drawString(2 * cm, y, text)
        y -= 14

    c.setFont("Helvetica-Bold", 14)
    draw("HASIL SIMULASI PAJAK EMISI KENDARAAN BERMOTOR")
    y -= 10

    c.setFont("Helvetica", 10)
    draw(f"Tanggal Simulasi              : {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    draw(f"Bahan Bakar/Jenis Mesin       : {data['bahan_bakar']}")
    draw(f"Klasifikasi Kendaraan         : {data['klasifikasi']}")
    draw(f"Merk Kendaraan                : {data.get('merk', '-')}")
    draw(f"Tipe/Model Kendaraan          : {data.get('tipe', '-')}")
    draw(f"Tahun Kendaraan               : {data['tahun']}")
    draw(f"Usia Kendaraan                : {data['usia']} tahun")

    if data.get("tipe_motor"):
        draw(f"Tipe Sepeda Motor             : {data['tipe_motor']}")

    if data.get("jbb"):
        draw(f"JBB                           : {data['jbb']}")

    draw(f"Periode Baku Mutu             : {data['periode_baku']}")
    draw(f"Kategori Baku Mutu            : {data['kategori_baku']}")
    draw(f"Metode Uji                    : {data['metode_uji']}")
    y -= 10

    c.setFont("Helvetica-Bold", 11)
    draw("Hasil Uji Emisi Kendaraan")
    c.setFont("Helvetica", 10)

    hasil_emisi = data.get("hasil_emisi", {})

    if data["bahan_bakar"] == "Diesel":
        draw(f"Opasitas                      : {hasil_emisi.get('Opasitas', '-')} %")
        draw(f"Baku Mutu Opasitas            : {data.get('baku_opasitas', '-')} % HSU")
    else:
        draw(f"CO                            : {hasil_emisi.get('CO', '-')} %")
        draw(f"HC                            : {hasil_emisi.get('HC', '-')} ppm")
        draw(f"Baku Mutu CO                  : {data.get('baku_co', '-')} %")
        draw(f"Baku Mutu HC                  : {data.get('baku_hc', '-')} ppm")

    y -= 10
    draw(f"NJKB                          : Rp {data['njkb']:,.0f}")
    draw(f"Tarif Pajak Daerah            : {data['tarif']} %")
    draw(f"KD                            : {data['kd']}")
    draw(f"Nilai Alfa (α)                : {data['alfa']}")
    draw(f"Sumber Alfa                   : {data['sumber_alfa']}")
    draw(f"Faktor Usia                   : {data['faktor_usia']}")
    y -= 10

    draw(f"Rasio Emisi                   : {data['rasio']:.3f}")
    draw(f"KE Hasil Perhitungan          : {data['ke_awal']:.6f}")

    if data.get("ke_max") is not None:
        draw(f"KE Maksimum                   : {data['ke_max']:.6f}")
        draw(f"KE Dipakai untuk PKB          : {data['ke']:.6f}")
    else:
        draw("KE Maksimum                   : Tidak dibatasi")
        draw(f"KE Dipakai untuk PKB          : {data['ke']:.6f}")

    draw(f"Status Emisi                  : {data['status_plain']}")
    y -= 10

    c.setFont("Helvetica-Bold", 11)
    draw(f"PKB Dasar                     : Rp {data['pkb_dasar']:,.0f}")
    draw(f"PKB Emisi                     : Rp {data['pkb_emisi']:,.0f}")
    draw(f"Selisih PKB                   : Rp {data['selisih']:,.0f}")
    draw(f"Kenaikan PKB                  : {data['persen_kenaikan']:.2f} %")

    y -= 20
    c.setFont("Helvetica", 9)
    draw("Rumus:")
    draw("DP PKB = NJKB x Tarif Pajak Daerah")
    draw("PKB Dasar = DP PKB x KD")
    draw("PKB Emisi = DP PKB x (KD + KE)")
    draw("KE = α x (Rasio Emisi - 1) x Faktor Usia")
    draw("Jika tersedia dalam daftar usulan, nilai KE dibatasi sampai KE Maksimum.")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer

# ===============================
# STREAMLIT UI
# ===============================

st.title("🚗 Aplikasi Pajak Emisi Kendaraan Bermotor")
st.caption("Berdasarkan **Permendagri No. 7 Tahun 2025** dan **PERMEN LHK No. 8 Tahun 2023**")

# -------------------------------
# 1. Pemilihan Bahan Bakar / Jenis Mesin
# -------------------------------

bahan_bakar = st.selectbox(
    "Pemilihan Bahan Bakar/Jenis Mesin :",
    ["Bensin", "Diesel"]
)

# -------------------------------
# 2. Jenis Klasifikasi Kendaraan
# -------------------------------

if bahan_bakar == "Bensin":
    klasifikasi = st.selectbox(
        "Jenis Klasifikasi Kendaraan :",
        ["A", "B", "C", "D"]
    )

    st.markdown(keterangan_bensin)

    jbb = None

else:
    klasifikasi = st.selectbox(
        "Jenis Klasifikasi Kendaraan :",
        ["C", "D", "E", "F", "G"]
    )

    st.markdown(keterangan_diesel)

    jbb = st.selectbox(
        "Jumlah Berat yang diperbolehkan/JBB :",
        ["<= 3.5 ton", "> 3.5 ton"]
    )

# -------------------------------
# 3. Identitas Kendaraan
# -------------------------------

st.markdown("### 🏷️ Identitas Kendaraan")

merk_kendaraan = st.text_input(
    "Merk Kendaraan:",
    placeholder="Contoh: Toyota, Honda, Yamaha, Mitsubishi"
)

tipe_kendaraan = st.text_input(
    "Tipe / Model Kendaraan:",
    placeholder="Contoh: Avanza 1.5, CRF 150L, Pajero Sport"
)

# -------------------------------
# 4. Tahun Kendaraan
# -------------------------------

tahun_sekarang = datetime.now().year

tahun = st.number_input(
    "Masukkan Tahun Kendaraan:",
    min_value=1980,
    max_value=tahun_sekarang,
    value=min(2020, tahun_sekarang)
)

# -------------------------------
# 5. Tipe Sepeda Motor
# -------------------------------
# Hanya muncul untuk:
# Bensin + Klasifikasi A + Tahun < 2010

tipe_motor = None

if bahan_bakar == "Bensin" and klasifikasi == "A":
    if tahun < 2010:
        tipe_motor = st.selectbox(
            "Tipe Sepeda Motor :",
            ["2-langkah", "4-langkah"]
        )
        st.caption("Untuk sepeda motor dengan tahun pembuatan < 2010, baku mutu dibedakan menjadi 2-langkah dan 4-langkah.")
    else:
        st.info("Sepeda motor tahun 2010 ke atas tidak dibedakan menjadi 2-langkah atau 4-langkah dalam baku mutu emisi.")

# -------------------------------
# 6. Hasil Uji Emisi
# -------------------------------

st.subheader("Hasil Nilai Ukur Emisi")

if bahan_bakar == "Diesel":
    opasitas = st.number_input(
        "Opasitas (%)",
        min_value=0.0,
        value=40.0
    )

    hasil_emisi = {
        "Opasitas": opasitas
    }

else:
    co = st.number_input(
        "CO (%)",
        min_value=0.0,
        value=1.0
    )

    hc = st.number_input(
        "HC (ppm)",
        min_value=0.0,
        value=150.0
    )

    hasil_emisi = {
        "CO": co,
        "HC": hc
    }

# -------------------------------
# 7. Nilai Alfa dan Batas KE Maksimum
# -------------------------------

st.markdown("### ⚙️ Pengaturan Lanjutan")

rule_ke_alfa, periode_rule = ambil_rule_ke_alfa(
    bahan_bakar=bahan_bakar,
    klasifikasi=klasifikasi,
    tahun=tahun
)

if rule_ke_alfa is not None:
    ke_max_default = rule_ke_alfa["ke_max"]
    alfa_default = rule_ke_alfa["alfa"]

    st.info(
        f"Kombinasi **{bahan_bakar} - Klasifikasi {klasifikasi} - Tahun {periode_rule}** "
        f"tersedia dalam daftar usulan. Nilai KE maksimum = **{ke_max_default:.6f}**, "
        f"dan nilai alfa default = **{alfa_default}**."
    )

    alfa_input = st.text_input(
        "Nilai Alfa (α):",
        value=str(alfa_default),
        key=f"alfa_{bahan_bakar}_{klasifikasi}_{periode_rule}"
    )

else:
    ke_max_default = None
    alfa_default = None

    st.warning(
        f"Kombinasi **{bahan_bakar} - Klasifikasi {klasifikasi} - Tahun {periode_rule}** "
        "belum tersedia dalam daftar usulan nilai alfa dan KE maksimum. "
        "Nilai KE tidak dibatasi dan nilai alfa harus diisi manual."
    )

    alfa_input = st.text_input(
        "Nilai Alfa (α):",
        placeholder="Contoh: 0.2",
        key=f"alfa_manual_{bahan_bakar}_{klasifikasi}_{periode_rule}"
    )

use_fusia = st.radio(
    "Gunakan Faktor Usia dalam Perhitungan KE?",
    ("Ya, gunakan faktor usia", "Tidak, tanpa faktor usia"),
    index=1
)

# -------------------------------
# 8. NJKB
# -------------------------------

st.markdown("### 💰 Nilai Jual Kendaraan Bermotor (NJKB)")

njkb_str = st.text_input(
    "Masukkan Nilai Jual Kendaraan (Rp):",
    value="15,000,000"
)

# -------------------------------
# 9. Tarif Pajak Daerah
# -------------------------------

tarif_pajak = st.number_input(
    "Tarif Pajak Daerah (%):",
    min_value=0.0,
    value=2.0
)

# ===============================
# SIMULASI
# ===============================

if st.button("🔍 Simulasikan PKB Emisi"):

    # Validasi alfa
    if not alfa_input.strip():
        st.error("⚠️ Nilai Alfa (α) wajib diisi.")
        st.stop()

    try:
        alfa = parse_float(alfa_input)
    except ValueError:
        st.error("⚠️ Nilai Alfa (α) tidak valid. Contoh input yang benar: 0.2 atau 0,2")
        st.stop()

    if alfa < 0:
        st.error("⚠️ Nilai Alfa (α) tidak boleh negatif.")
        st.stop()

    # Validasi NJKB
    try:
        njkb = parse_rupiah(njkb_str)
    except ValueError:
        st.error("⚠️ Format angka NJKB tidak valid. Contoh: 15,000,000 atau 15.000.000")
        st.stop()

    if njkb <= 0:
        st.error("⚠️ Nilai NJKB harus lebih besar dari 0.")
        st.stop()

    if tarif_pajak < 0:
        st.error("⚠️ Tarif pajak tidak boleh negatif.")
        st.stop()

    if not merk_kendaraan or not tipe_kendaraan:
        st.warning("⚠️ Merk dan tipe kendaraan sebaiknya diisi untuk identifikasi laporan.")

    # -------------------------------
    # Hitung usia kendaraan
    # -------------------------------

    usia = tahun_sekarang - tahun

    # -------------------------------
    # Faktor usia
    # -------------------------------

    if use_fusia == "Ya, gunakan faktor usia":
        if usia < 10:
            faktor_usia = 1
        elif 10 <= usia <= 20:
            faktor_usia = 1.5
        else:
            faktor_usia = 2
    else:
        faktor_usia = 1

    # -------------------------------
    # DP PKB
    # -------------------------------

    dp_pkb = njkb * (tarif_pajak / 100)

    # -------------------------------
    # KD berdasarkan klasifikasi
    # -------------------------------

    kd = nilai_KD[klasifikasi]

    # -------------------------------
    # Ambil baku mutu
    # -------------------------------

    baku, periode_baku, kategori_baku, metode_uji = ambil_baku_mutu(
        bahan_bakar=bahan_bakar,
        klasifikasi=klasifikasi,
        tahun=tahun,
        tipe_motor=tipe_motor,
        jbb=jbb
    )

    if baku is None:
        st.error("⚠️ Baku mutu tidak ditemukan untuk kombinasi input ini.")
        st.stop()

    # -------------------------------
    # Ambil rule KE maksimum dan alfa
    # -------------------------------

    rule_ke_alfa, periode_rule = ambil_rule_ke_alfa(
        bahan_bakar=bahan_bakar,
        klasifikasi=klasifikasi,
        tahun=tahun
    )

    if rule_ke_alfa is not None:
        ke_max = rule_ke_alfa["ke_max"]
        sumber_alfa = "Default daftar usulan nilai alfa dan KE maksimum"
    else:
        ke_max = None
        sumber_alfa = "Input manual user"

    # -------------------------------
    # Hitung rasio emisi
    # -------------------------------

    if bahan_bakar == "Diesel":
        baku_opasitas = baku
        baku_co = None
        baku_hc = None

        rasio_emisi = hasil_emisi["Opasitas"] / baku_opasitas
        parameter_dominan = "Opasitas"

    else:
        baku_co = baku["CO"]
        baku_hc = baku["HC"]
        baku_opasitas = None

        rasio_co = hasil_emisi["CO"] / baku_co
        rasio_hc = hasil_emisi["HC"] / baku_hc

        rasio_emisi = max(rasio_co, rasio_hc)

        if rasio_co >= rasio_hc:
            parameter_dominan = "CO"
        else:
            parameter_dominan = "HC"

    # -------------------------------
    # Hitung KE dan terapkan batas KE maksimum
    # -------------------------------
    # Rasio emisi TIDAK dibatasi.
    # Jika kombinasi tersedia dalam daftar usulan,
    # hasil KE akhir dibatasi sampai nilai KE maksimum.

    if rasio_emisi <= 1:
        ke_awal = 0
        ke = 0
        ke_dibatasi = False

        status_emisi = "✅ LULUS — Emisi di bawah atau sama dengan baku mutu"
        status_plain = "LULUS - Emisi di bawah atau sama dengan baku mutu"

    else:
        ke_awal = alfa * (rasio_emisi - 1) * faktor_usia

        if ke_max is not None:
            ke = min(ke_awal, ke_max)
            ke_dibatasi = ke_awal > ke_max
        else:
            ke = ke_awal
            ke_dibatasi = False

        status_emisi = "⚠️ TIDAK LULUS — Emisi melebihi ambang batas"
        status_plain = "TIDAK LULUS - Emisi melebihi ambang batas"

    # -------------------------------
    # Hitung PKB
    # -------------------------------

    pkb_dasar = dp_pkb * kd
    pkb_emisi = dp_pkb * (kd + ke)
    selisih = pkb_emisi - pkb_dasar
    persen_kenaikan = (selisih / pkb_dasar * 100) if pkb_dasar > 0 else 0

    # ===============================
    # HASIL SIMULASI
    # ===============================

    st.subheader("📊 Hasil Simulasi PKB")

    st.write(f"**Bahan Bakar/Jenis Mesin:** {bahan_bakar}")
    st.write(f"**Klasifikasi Kendaraan:** {klasifikasi}")

    if tipe_motor:
        st.write(f"**Tipe Sepeda Motor:** {tipe_motor}")

    if jbb:
        st.write(f"**JBB:** {jbb}")

    st.write(f"**Periode Baku Mutu:** {periode_baku}")
    st.write(f"**Kategori Baku Mutu:** {kategori_baku}")
    st.write(f"**Periode Usulan Alfa-KE:** {periode_rule}")
    st.write(f"**Metode Uji:** {metode_uji}")
    st.write(f"**Usia Kendaraan:** {usia} tahun")
    st.write(f"**Faktor Usia Dipakai?** {'Ya' if use_fusia == 'Ya, gunakan faktor usia' else 'Tidak'}")
    st.write(f"**Nilai Faktor Usia:** {faktor_usia}")

    if bahan_bakar == "Diesel":
        st.write(f"**Baku Mutu Opasitas:** {baku_opasitas} % HSU")
        st.write(f"**Rasio Opasitas:** {rasio_emisi:.3f}")
    else:
        st.write(f"**Baku Mutu CO:** {baku_co} %")
        st.write(f"**Baku Mutu HC:** {baku_hc} ppm")
        st.write(f"**Rasio CO:** {rasio_co:.3f}")
        st.write(f"**Rasio HC:** {rasio_hc:.3f}")

    st.write(f"**Parameter Dominan:** {parameter_dominan}")
    st.write(f"**Rasio Emisi:** {rasio_emisi:.3f}")
    st.write(f"**Nilai Alfa (α):** {alfa}")
    st.write(f"**Sumber Alfa:** {sumber_alfa}")

    if ke_max is not None:
        st.write(f"**KE Hasil Perhitungan:** {ke_awal:.6f}")
        st.write(f"**Batas KE Maksimum:** {ke_max:.6f}")
        st.write(f"**Koefisien Emisi (KE) yang Dipakai:** {ke:.6f}")

        if ke_dibatasi:
            st.warning(
                "⚠️ Nilai KE hasil perhitungan melebihi batas KE maksimum daftar usulan, "
                "sehingga nilai KE yang dipakai dalam perhitungan PKB dibatasi."
            )
    else:
        st.write("**Batas KE Maksimum:** Tidak ada / tidak dibatasi")
        st.write(f"**Koefisien Emisi (KE):** {ke:.6f}")

    # Tampilkan status dengan warna sesuai hasil emisi
    if rasio_emisi <= 1:
        st.success(status_emisi)
    else:
        st.error(status_emisi)

    st.write("---")

    warna = "normal" if rasio_emisi <= 1 else "inverse"

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "PKB Dasar (Rp)",
        f"{pkb_dasar:,.0f}"
    )

    col2.metric(
        "PKB Emisi (Rp)",
        f"{pkb_emisi:,.0f}",
        f"{persen_kenaikan:.2f}%",
        delta_color=warna
    )

    col3.metric(
        "Selisih (Rp)",
        f"{selisih:,.0f}"
    )

    st.write("---")

    st.caption("""
    🧮 Rumus:
    - DP PKB = NJKB × Tarif Pajak Daerah  
    - PKB Dasar = DP PKB × KD  
    - PKB Emisi = DP PKB × (KD + KE)  
    - KE = α × (Rasio Emisi − 1) × Faktor Usia  
    - Jika tersedia dalam daftar usulan, nilai KE hasil perhitungan dibatasi sampai KE Maksimum  
    """)

    # Simpan hasil ke session state untuk PDF
    st.session_state.hasil_simulasi = {
        "bahan_bakar": bahan_bakar,
        "klasifikasi": klasifikasi,
        "merk": merk_kendaraan,
        "tipe": tipe_kendaraan,
        "tahun": tahun,
        "usia": usia,
        "tipe_motor": tipe_motor,
        "jbb": jbb,
        "hasil_emisi": hasil_emisi,
        "njkb": njkb,
        "tarif": tarif_pajak,
        "kd": kd,
        "alfa": alfa,
        "sumber_alfa": sumber_alfa,
        "faktor_usia": faktor_usia,
        "periode_baku": periode_baku,
        "kategori_baku": kategori_baku,
        "metode_uji": metode_uji,
        "baku_co": baku_co,
        "baku_hc": baku_hc,
        "baku_opasitas": baku_opasitas,
        "rasio": rasio_emisi,
        "ke_awal": ke_awal,
        "ke_max": ke_max,
        "ke_dibatasi": ke_dibatasi,
        "ke": ke,
        "status": status_emisi,
        "status_plain": status_plain,
        "pkb_dasar": pkb_dasar,
        "pkb_emisi": pkb_emisi,
        "selisih": selisih,
        "persen_kenaikan": persen_kenaikan
    }

# ===============================
# DOWNLOAD PDF
# ===============================

if "hasil_simulasi" in st.session_state:
    pdf_bytes = generate_pdf_bytes(st.session_state.hasil_simulasi)

    st.download_button(
        label="📄 Download Hasil Simulasi (PDF)",
        data=pdf_bytes,
        file_name=f"Simulasi_PKB_Emisi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf"
    )

# ===============================
# CHATBOT CHATGPT
# ===============================

st.markdown("---")
st.subheader("💬 Asisten Pajak Emisi")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# tampilkan histori chat
for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

# Gunakan form biasa, bukan st.chat_input
with st.form("chatbot_form", clear_on_submit=True):
    user_msg = st.text_area(
        "Tanyakan seputar pajak emisi, baku mutu, atau regulasi kendaraan:",
        placeholder="Contoh: Bagaimana cara menghitung PKB emisi?",
        height=100
    )

    submit_chat = st.form_submit_button("Kirim Pertanyaan")

if submit_chat and user_msg.strip():
    st.session_state.chat_history.append(("user", user_msg))

    with st.chat_message("assistant"):
        with st.spinner("🤖 Menganalisis regulasi dan laporan..."):
            try:
                system_prompt = (
                    "Anda adalah asisten ahli pajak emisi kendaraan bermotor Indonesia. "
                    "Gunakan bahasa formal kebijakan publik. "
                    "Jawaban harus relevan dengan regulasi Indonesia, baku mutu emisi, "
                    "dan simulasi pajak emisi kendaraan bermotor."
                )

                if laporan_text:
                    system_prompt += (
                        "\n\nGunakan juga konteks laporan berikut sebagai dasar jawaban:\n\n"
                        f"{laporan_text[:30000]}"
                    )

                response = client.chat.completions.create(
                    model=MODEL_LLM,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        }
                    ] + [
                        {"role": r, "content": m}
                        for r, m in st.session_state.chat_history[-6:]
                    ],
                    max_tokens=700,
                    temperature=0.1
                )

                answer = response.choices[0].message.content.strip()
                st.markdown(answer)
                st.session_state.chat_history.append(("assistant", answer))

            except Exception as e:
                st.error(f"⚠️ Terjadi error ChatGPT: {e}")
