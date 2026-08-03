import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime

# --- SAYFA AYARLARI (Mobil Uyumlu) ---
st.set_page_config(
    page_title="Satın Alma Görev Takip",
    page_icon="🛋️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- SUPABASE BAĞLANTISI ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Veritabanı bağlantı hatası! Lütfen Streamlit Secrets alanını kontrol edin.")
    st.stop()

# --- VERİ ÇEKME FONKSİYONU ---
def load_tasks():
    response = supabase.table("tasks").select("*").order("created_at", desc=True).execute()
    return pd.DataFrame(response.data)

# --- BAŞLIK ---
st.title("🛋️ Satın Alma Görev Takip")
st.caption("Yatak Üretim Fabrikası · Canlı İş Takibi")

# --- KULLANICI SEÇİMİ ---
PEOPLE = ["Fatih Sarı", "Abdullah Gözbaşı", "Ali Karabörklü"]
selected_user = st.selectbox("Bu cihazı kullanan kişi:", ["Seçiniz..."] + PEOPLE)

if selected_user == "Seçiniz...":
    st.warning("⚠️ İşlem yapabilmek için lütfen yukarıdan kullanıcı seçiniz.")

st.divider()

# --- VERİLERİ YÜKLE ---
df = load_tasks()

# Eğer veritabanı tamamen boşsa ilk varsayılan verileri yükle
if df.empty:
    seed_data = [
        {"id": "seed-1", "tarih": "2025-01-30", "gorev": "400 adet FF keçesi fazla geldi, MTAY ile görüşülecek.", "aciklama": "Yeni siparişte kullanılacak.", "durum": "kapali", "silindi": False},
        {"id": "seed-2", "tarih": "2026-02-19", "gorev": "NEC fermuar numune gönderimi.", "aciklama": "", "durum": "acik", "silindi": False},
        {"id": "seed-3", "tarih": "2026-02-25", "gorev": "Tedarikçi kategorize çalışması.", "aciklama": "", "durum": "acik", "silindi": False},
    ]
    supabase.table("tasks").insert(seed_data).execute()
    st.rerun()

# Silinmemiş görevleri filtrele
df_active = df[df["silindi"] == False] if "silindi" in df.columns else df

# --- İSTATİSTİKLER ---
acik_sayisi = len(df_active[df_active["durum"] == "acik"])
devam_sayisi = len(df_active[df_active["durum"] == "devam"])
kapali_sayisi = len(df_active[df_active["durum"] == "kapali"])

col1, col2, col3 = st.columns(3)
col1.metric("Açık", acik_sayisi)
col2.metric("Devam Eden", devam_sayisi)
col3.metric("Kapalı", kapali_sayisi)

# --- İŞLEM BUTONLARI VE EXCEL IMPORT ---
tab1, tab2, tab3 = st.tabs(["📋 Görev Listesi", "➕ Yeni Görev Ekle", "📊 Excel'den Toplu Yükle"])

# TAB 1: GÖREV LİSTESİ
with tab1:
    search_query = st.text_input("🔍 Görevlerde ara...", "")
    status_filter = st.radio("Filtrele:", ["Açık", "Devam Eden", "Kapalı", "Tümü"], horizontal=True)

    filtered_df = df_active.copy()

    if status_filter == "Açık":
        filtered_df = filtered_df[filtered_df["durum"] == "acik"]
    elif status_filter == "Devam Eden":
        filtered_df = filtered_df[filtered_df["durum"] == "devam"]
    elif status_filter == "Kapalı":
        filtered_df = filtered_df[filtered_df["durum"] == "kapali"]

    if search_query:
        filtered_df = filtered_df[
            filtered_df["gorev"].str.contains(search_query, case=False, na=False) |
            filtered_df["aciklama"].str.contains(search_query, case=False, na=False)
        ]

    st.write(f"**Toplam {len(filtered_df)} görev gösteriliyor:**")

    for idx, row in filtered_df.iterrows():
        with st.expander(f"**{row['gorev']}** ({row.get('sorumlu', 'Atanmadı')})"):
            st.write(f"**Açıklama:** {row.get('aciklama', '-')}")
            st.write(f"**Tarih:** {row.get('tarih', '-')}")
            
            c1, c2, c3 = st.columns(3)
            
            # Durum Değiştirme
            if c1.button("🔄 Durum Değiştir", key=f"status_{row['id']}"):
                next_status = "devam" if row["durum"] == "acik" else ("kapali" if row["durum"] == "devam" else "acik")
                supabase.table("tasks").update({
                    "durum": next_status,
                    "tamamlanma_tarihi": str(datetime.date.today()) if next_status == "kapali" else None
                }).eq("id", row["id"]).execute()
                st.toast(f"Görev durumu '{next_status.upper()}' olarak güncellendi!")
                st.rerun()

            # Silme
            if c2.button("🗑️ Sil", key=f"del_{row['id']}"):
                if selected_user == "Seçiniz...":
                    st.error("Silmek için kullanıcı seçmelisiniz!")
                else:
                    supabase.table("tasks").update({
                        "silindi": True,
                        "silinme_tarihi": str(datetime.date.today()),
                        "silen": selected_user
                    }).eq("id", row["id"]).execute()
                    st.toast("Görev silindi!")
                    st.rerun()

# TAB 2: YENİ GÖREV EKLE
with tab2:
    with st.form("new_task_form"):
        f_gorev = st.text_input("Görev Tanımı*")
        f_aciklama = st.text_area("Açıklama / Detay")
        f_sorumlu = st.selectbox("Sorumlu", [""] + PEOPLE)
        f_tarih = st.date_input("Görev Tarihi", datetime.date.today())
        
        submitted = st.form_submit_button("💾 Kaydet")
        if submitted:
            if not f_gorev.strip():
                st.error("Lütfen görev tanımını boş bırakmayın!")
            else:
                new_data = {
                    "id": f"task-{int(datetime.datetime.now().timestamp())}",
                    "gorev": f_gorev,
                    "aciklama": f_aciklama,
                    "sorumlu": f_sorumlu,
                    "tarih": str(f_tarih),
                    "durum": "acik",
                    "silindi": False
                }
                supabase.table("tasks").insert(new_data).execute()
                st.success("Yeni görev başarıyla eklendi!")
                st.rerun()

# TAB 3: EXCEL IMPORT
with tab3:
    uploaded_file = st.file_uploader("Excel dosyasını yükleyin (.xlsx)", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            excel_df = pd.read_excel(uploaded_file)
            st.write("Yüklenecek Veri Önizlemesi:", excel_df.head())
            
            if st.button("📤 Verileri Veritabanına Aktar"):
                new_records = []
                for idx, row in excel_df.iterrows():
                    gorev = row.get("Görev Tanımı") or row.get("Görev") or row.get("Gorev")
                    if pd.isna(gorev):
                        continue
                    
                    new_records.append({
                        "id": f"excel-{int(datetime.datetime.now().timestamp())}-{idx}",
                        "gorev": str(gorev),
                        "aciklama": str(row.get("Açıklama", "")),
                        "sorumlu": str(row.get("Sorumlu", "")),
                        "tarih": str(datetime.date.today()),
                        "durum": "acik",
                        "silindi": False
                    })
                
                if new_records:
                    supabase.table("tasks").insert(new_records).execute()
                    st.success(f"{len(new_records)} adet yeni görev Excel'den aktarıldı!")
                    st.rerun()
        except Exception as e:
            st.error(f"Excel okunurken hata oluştu: {e}")
