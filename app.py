import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- SAYFA AYARLARI (Mobil Uyumlu) ---
st.set_page_config(
    page_title="Satın Alma Görev Takip",
    page_icon="🛋️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

WORKSHEET = "tasks"
COLUMNS = ["id", "tarih", "gorev", "aciklama", "sorumlu", "durum",
           "silindi", "tamamlanma_tarihi", "silinme_tarihi", "silen", "created_at"]

# --- GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource
def init_connection():
    return st.connection("gsheets", type=GSheetsConnection)

try:
    conn = init_connection()
except Exception as e:
    st.error(f"Google Sheets bağlantı hatası: {e}")
    st.stop()


def load_tasks() -> pd.DataFrame:
    try:
        df = conn.read(worksheet=WORKSHEET, ttl=0)
    except Exception as e:
        st.error(f"Veri okunurken hata oluştu: {e}")
        st.stop()

    if df is None or df.empty:
        df = pd.DataFrame(columns=COLUMNS)

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Boş satırları temizle (Google Sheets bazen tamamen boş satırlar döndürebilir)
    df = df.dropna(how="all")

    # Tip düzeltmeleri
    df["silindi"] = df["silindi"].fillna(False).astype(bool)
    for col in ["gorev", "aciklama", "sorumlu", "durum", "tarih", "id"]:
        df[col] = df[col].fillna("").astype(str)

    return df.reset_index(drop=True)


def save_tasks(df: pd.DataFrame):
    conn.update(worksheet=WORKSHEET, data=df[COLUMNS])
    st.cache_data.clear()


# --- KULLANICI GİRİŞİ (Şifreli) ---
def check_login():
    if st.session_state.get("logged_in"):
        return True

    st.title("🔒 Giriş Yap")
    users = dict(st.secrets.get("users", {}))
    username = st.selectbox("Kullanıcı adı:", ["Seçiniz..."] + list(users.keys()))
    password = st.text_input("Şifre:", type="password")

    if st.button("Giriş Yap"):
        if username == "Seçiniz...":
            st.error("Lütfen kullanıcı adı seçiniz.")
        elif username in users and password == users[username]:
            st.session_state["logged_in"] = True
            st.session_state["current_user"] = username
            st.rerun()
        else:
            st.error("Kullanıcı adı veya şifre hatalı.")

    return False


if not check_login():
    st.stop()

selected_user = st.session_state["current_user"]

# --- ÇIKIŞ BUTONU ---
top_col1, top_col2 = st.columns([4, 1])
with top_col1:
    st.title("🛋️ Satın Alma Görev Takip")
    st.caption(f"Yatak Üretim Fabrikası · Canlı İş Takibi · Giriş yapan: **{selected_user}**")
with top_col2:
    if st.button("Çıkış"):
        st.session_state["logged_in"] = False
        st.rerun()

st.divider()

# --- VERİLERİ YÜKLE ---
df = load_tasks()

# Sheet tamamen boşsa ilk varsayılan verileri yükle
if df.empty:
    seed_data = pd.DataFrame([
        {"id": "seed-1", "tarih": "2025-01-30", "gorev": "400 adet FF keçesi fazla geldi, MTAY ile görüşülecek.",
         "aciklama": "Yeni siparişte kullanılacak.", "sorumlu": "", "durum": "kapali", "silindi": False,
         "tamamlanma_tarihi": "", "silinme_tarihi": "", "silen": "", "created_at": str(datetime.datetime.now())},
        {"id": "seed-2", "tarih": "2026-02-19", "gorev": "NEC fermuar numune gönderimi.",
         "aciklama": "", "sorumlu": "", "durum": "acik", "silindi": False,
         "tamamlanma_tarihi": "", "silinme_tarihi": "", "silen": "", "created_at": str(datetime.datetime.now())},
        {"id": "seed-3", "tarih": "2026-02-25", "gorev": "Tedarikçi kategorize çalışması.",
         "aciklama": "", "sorumlu": "", "durum": "acik", "silindi": False,
         "tamamlanma_tarihi": "", "silinme_tarihi": "", "silen": "", "created_at": str(datetime.datetime.now())},
    ])
    save_tasks(seed_data)
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
        with st.expander(f"**{row['gorev']}** ({row.get('sorumlu') or 'Atanmadı'})"):
            st.write(f"**Açıklama:** {row.get('aciklama', '-') or '-'}")
            st.write(f"**Tarih:** {row.get('tarih', '-') or '-'}")

            c1, c2 = st.columns(2)

            # Durum Değiştirme
            if c1.button("🔄 Durum Değiştir", key=f"status_{row['id']}"):
                next_status = "devam" if row["durum"] == "acik" else ("kapali" if row["durum"] == "devam" else "acik")
                df.loc[df["id"] == row["id"], "durum"] = next_status
                df.loc[df["id"] == row["id"], "tamamlanma_tarihi"] = str(datetime.date.today()) if next_status == "kapali" else ""
                save_tasks(df)
                st.toast(f"Görev durumu '{next_status.upper()}' olarak güncellendi!")
                st.rerun()

            # Silme
            if c2.button("🗑️ Sil", key=f"del_{row['id']}"):
                df.loc[df["id"] == row["id"], "silindi"] = True
                df.loc[df["id"] == row["id"], "silinme_tarihi"] = str(datetime.date.today())
                df.loc[df["id"] == row["id"], "silen"] = selected_user
                save_tasks(df)
                st.toast("Görev silindi!")
                st.rerun()

# TAB 2: YENİ GÖREV EKLE
with tab2:
    with st.form("new_task_form"):
        f_gorev = st.text_input("Görev Tanımı*")
        f_aciklama = st.text_area("Açıklama / Detay")
        f_sorumlu = st.selectbox("Sorumlu", [""] + list(dict(st.secrets.get("users", {})).keys()))
        f_tarih = st.date_input("Görev Tarihi", datetime.date.today())

        submitted = st.form_submit_button("💾 Kaydet")
        if submitted:
            if not f_gorev.strip():
                st.error("Lütfen görev tanımını boş bırakmayın!")
            else:
                new_row = pd.DataFrame([{
                    "id": f"task-{int(datetime.datetime.now().timestamp())}",
                    "gorev": f_gorev,
                    "aciklama": f_aciklama,
                    "sorumlu": f_sorumlu,
                    "tarih": str(f_tarih),
                    "durum": "acik",
                    "silindi": False,
                    "tamamlanma_tarihi": "",
                    "silinme_tarihi": "",
                    "silen": "",
                    "created_at": str(datetime.datetime.now()),
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_tasks(df)
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
                        "silindi": False,
                        "tamamlanma_tarihi": "",
                        "silinme_tarihi": "",
                        "silen": "",
                        "created_at": str(datetime.datetime.now()),
                    })

                if new_records:
                    df = pd.concat([df, pd.DataFrame(new_records)], ignore_index=True)
                    save_tasks(df)
                    st.success(f"{len(new_records)} adet yeni görev Excel'den aktarıldı!")
                    st.rerun()
        except Exception as e:
            st.error(f"Excel okunurken hata oluştu: {e}")
