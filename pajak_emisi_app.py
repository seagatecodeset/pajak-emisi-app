# ==========================================
# Aplikasi Simulasi Pajak Emisi Kendaraan Bermotor
# Berdasarkan Permendagri No. 7 Tahun 2025
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
# KONFIGURASI LLM (CHATGPT)
# ===============================
MODEL_LLM = "gpt-4.1"  # 🔒 Stabil untuk chatbot UI (selalu keluar teks)

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
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text

laporan_text = load_pdf_text("ringkasa_laporan.pdf")

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
    draw("HASIL PAJAK EMISI KENDARAAN BERMOTOR")
    y -= 10

    c.setFont("Helvetica", 10)
    draw(f"Tanggal Simulasi : {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    draw(f"Jenis Kendaraan  : {data['jenis']}")
    draw(f"Merk Kendaraan  : {data.get('merk', '-')}")
    draw(f"Tipe Kendaraan  : {data.get('tipe', '-')}")
    draw(f"Tahun Kendaraan  : {data['tahun']}")
    draw(f"Usia Kendaraan   : {data['usia']} tahun")
    draw(f"Kategori Emisi   : {data['kategori']}")
    y -= 10
    # ===============================
    # HASIL UJI EMISI
    # ===============================
    c.setFont("Helvetica-Bold", 11)
    draw("Hasil Uji Emisi Kendaraan")
    c.setFont("Helvetica", 10)

    hasil_emisi = data.get("hasil_emisi", {})  # ✅ AMAN

    if data.get("kategori") == "Diesel":
        draw(f"Opasitas        : {hasil_emisi.get('Opasitas', '-')} %")
    else:
        draw(f"CO              : {hasil_emisi.get('CO', '-')} %")
        draw(f"HC              : {hasil_emisi.get('HC', '-')} ppm")

    y -= 10
    draw(f"NJKB             : Rp {data['njkb']:,.0f}")
    draw(f"Tarif Pajak      : {data['tarif']} %")
    draw(f"KD               : {data['kd']}")
    draw(f"Nilai Alfa (α)   : {data['alfa']}")
    draw(f"Faktor Usia      : {data['faktor_usia']}")
    y -= 10

    draw(f"Rasio Emisi      : {data['rasio']:.3f}")
    draw(f"Koefisien Emisi  : {data['ke']:.4f}")
    draw(f"Status Emisi    : {data['status']}")
    y -= 10

    c.setFont("Helvetica-Bold", 11)
    draw(f"PKB Dasar        : Rp {data['pkb_dasar']:,.0f}")
    draw(f"PKB Emisi        : Rp {data['pkb_emisi']:,.0f}")
    draw(f"Selisih PKB      : Rp {data['selisih']:,.0f}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer

# -------------------------------
# Streamlit UI
# -------------------------------
st.title("🚗 Aplikasi Pajak Emisi Kendaraan Bermotor")
st.caption("Berdasarkan **Permendagri No. 7 Tahun 2025** dan **PERMEN LHK No. 8 Tahun 2023**")

# 1. Jenis Kendaraan
jenis = st.selectbox(
    "Pilih Jenis Kendaraan:",
    list(default_alfa.keys())
)

# 1a. Identitas Kendaraan (input bebas)
st.markdown("### 🏷️ Identitas Kendaraan")

merk_kendaraan = st.text_input(
    "Merk Kendaraan:",
    placeholder="Contoh: Toyota, Honda, Yamaha, Mitsubishi"
)

tipe_kendaraan = st.text_input(
    "Tipe / Model Kendaraan:",
    placeholder="Contoh: Avanza 1.5, CRF 150L, Pajero Sport"
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
    step=0.01
)

# Tambahkan Opsi: Menggunakan Faktor Usia atau Tidak
use_fusia = st.radio(
    "Gunakan Faktor Usia dalam Perhitungan KE?",
    ("Ya, gunakan faktor usia", "Tidak, tanpa faktor usia")
)

# 5. Nilai Jual Kendaraan
st.markdown("### 💰 Nilai Jual Kendaraan Bermotor (NJKB)")
njkb_str = st.text_input(
    "Masukkan Nilai Jual Kendaraan (Rp):",
    value="15,000,000"
)

try:
    njkb = float(njkb_str.replace(",", "").replace(".", ""))
except ValueError:
    st.error("⚠️ Format angka tidak valid! Gunakan koma atau titik untuk pemisah ribuan.")
    st.stop()

# 6. Tarif Pajak Daerah
tarif_pajak = st.number_input("Tarif Pajak Daerah (%):", min_value=0.0, value=2.0)

# -------------------------------
# SIMULASI
# -------------------------------
if st.button("🔍 Simulasikan PKB Emisi"):
    if not merk_kendaraan or not tipe_kendaraan:
        st.warning("⚠️ Merk dan tipe kendaraan sebaiknya diisi untuk identifikasi laporan.")
    # Hitung usia kendaraan
    from datetime import datetime
    tahun_now = datetime.now().year
    usia = tahun_now - tahun
    #usia = 2025 - tahun

    # Faktor usia jika dipilih
    if use_fusia == "Ya, gunakan faktor usia":
        if usia < 10:
            faktor_usia = 1
        elif 10 <= usia <= 20:
            faktor_usia = 1.5
        else:  # usia > 20
            faktor_usia = 2
    else:
        faktor_usia = 1  # dianggap tidak mempengaruhi

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

    # 4. Tentukan KE dan status
    if rasio_emisi <= 1:
        ke = 0
        status_emisi = "✅ LULUS — Emisi di bawah atau sama dengan baku mutu"
    else:
        ke = alfa * (rasio_emisi - 1) * faktor_usia
        status_emisi = "⚠️ TIDAK LULUS — Emisi melebihi ambang batas"

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
    st.write(f"**Usia Kendaraan:** {usia} tahun")
    st.write(f"**Faktor Usia Dipakai?** {'Ya' if use_fusia=='Ya, gunakan faktor usia' else 'Tidak'}")
    st.write(f"**Nilai Faktor Usia:** {faktor_usia}")
    st.write(f"**Rasio Emisi:** {rasio_emisi:.3f}")
    st.write(f"**Koefisien Emisi (KE):** {ke:.4f}")
    st.info(status_emisi)
    st.write("---")

    warna = "normal" if rasio_emisi <= 1 else "inverse"

    col1, col2, col3 = st.columns(3)
    col1.metric("PKB Dasar (Rp)", f"{pkb_dasar:,.0f}")
    col2.metric("PKB Emisi (Rp)", f"{pkb_emisi:,.0f}", f"{persen_kenaikan:.2f}%", delta_color=warna)
    col3.metric("Selisih (Rp)", f"{selisih:,.0f}")

    st.write("---")
    st.caption("""
    🧮 Rumus:
    - DP PKB = NJKB × Tarif Pajak Daerah  
    - PKB Dasar = DP PKB × KD  
    - PKB Emisi = DP PKB × (KD + KE)  
    - KE = α × (Rasio Emisi − 1) × Faktor Usia  
    """)

    st.session_state.hasil_simulasi = {
    "jenis": jenis,
    "merk": merk_kendaraan,
    "tipe": tipe_kendaraan,
    "tahun": tahun,
    "usia": usia,
    "kategori": kategori,
    "hasil_emisi": hasil_emisi,
    "njkb": njkb,
    "tarif": tarif_pajak,
    "kd": kd,
    "alfa": alfa,
    "faktor_usia": faktor_usia,
    "rasio": rasio_emisi,
    "ke": ke,
    "status": status_emisi,
    "pkb_dasar": pkb_dasar,
    "pkb_emisi": pkb_emisi,
    "selisih": selisih
    }
if "hasil_simulasi" in st.session_state:
    pdf_bytes = generate_pdf_bytes(st.session_state.hasil_simulasi)

    st.download_button(
        label="📄 Download Hasil Simulasi (PDF)",
        data=pdf_bytes,
        file_name=f"Simulasi_PKB_Emisi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf"
    )
# ===============================
# CHATBOT CHATGPT (GPT-4.1-mini)
# ===============================
st.markdown("---")
st.subheader("💬 Asisten Pajak Emisi")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# tampilkan histori chat
for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

user_msg = st.chat_input(
    "Tanyakan seputar pajak emisi, baku mutu, atau regulasi kendaraan"
)

if user_msg:
    st.session_state.chat_history.append(("user", user_msg))

    with st.chat_message("assistant"):
        with st.spinner("🤖 Menganalisis regulasi dan laporan..."):
            try:
                response = client.chat.completions.create(
                    model=MODEL_LLM,  # "gpt-4.1-mini"
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Anda adalah asisten ahli pajak emisi kendaraan bermotor Indonesia. "
                                "Gunakan bahasa formal kebijakan publik. "
                                "Jawaban HARUS berdasarkan regulasi Indonesia dan laporan berikut.\n\n"
                                f"{laporan_text[:30000]}"
                            )
                        }
                    ] + [
                        {"role": r, "content": m}
                        for r, m in st.session_state.chat_history[-6:]  # history aman diperpanjang
                    ],
                    max_tokens=700,      # ✅ PARAMETER GPT-4
                    temperature=0.1     # ✅ BOLEH di GPT-4
                )

                answer = response.choices[0].message.content.strip()
                st.markdown(answer)
                st.session_state.chat_history.append(("assistant", answer))

            except Exception as e:
                st.error(f"⚠️ Terjadi error ChatGPT: {e}")












































