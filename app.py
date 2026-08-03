import streamlit as st
import pandas as pd
import datetime
import io
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
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
           "silindi", "tamamlanma_tarihi", "silinme_tarihi", "silen",
           "created_at", "olusturan", "tamamlayan"]

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
            df[col] = ""

    df = df.dropna(how="all")

    df["silindi"] = df["silindi"].fillna(False).astype(bool)
    for col in ["gorev", "aciklama", "sorumlu", "durum", "tarih", "id",
                "tamamlanma_tarihi", "silinme_tarihi", "silen", "created_at",
                "olusturan", "tamamlayan"]:
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

# --- SEKMELER ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Görev Listesi", "➕ Yeni Görev Ekle", "📊 Excel'den Toplu Yükle",
    "📈 Rapor", "📄 Haftalık Rapor (Word)"
])

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
            if row.get("tamamlayan"):
                st.write(f"**Tamamlayan:** {row.get('tamamlayan')} · {row.get('tamamlanma_tarihi', '-')}")

            c1, c2 = st.columns(2)

            if c1.button("🔄 Durum Değiştir", key=f"status_{row['id']}"):
                next_status = "devam" if row["durum"] == "acik" else ("kapali" if row["durum"] == "devam" else "acik")
                df.loc[df["id"] == row["id"], "durum"] = next_status
                if next_status == "kapali":
                    df.loc[df["id"] == row["id"], "tamamlanma_tarihi"] = str(datetime.date.today())
                    df.loc[df["id"] == row["id"], "tamamlayan"] = selected_user
                else:
                    df.loc[df["id"] == row["id"], "tamamlanma_tarihi"] = ""
                    df.loc[df["id"] == row["id"], "tamamlayan"] = ""
                save_tasks(df)
                st.toast(f"Görev durumu '{next_status.upper()}' olarak güncellendi!")
                st.rerun()

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
                    "olusturan": selected_user,
                    "tamamlayan": "",
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
                        "olusturan": selected_user,
                        "tamamlayan": "",
                    })

                if new_records:
                    df = pd.concat([df, pd.DataFrame(new_records)], ignore_index=True)
                    save_tasks(df)
                    st.success(f"{len(new_records)} adet yeni görev Excel'den aktarıldı!")
                    st.rerun()
        except Exception as e:
            st.error(f"Excel okunurken hata oluştu: {e}")

# TAB 4: RAPOR
with tab4:
    st.subheader("📈 Görev Raporu")

    r1, r2 = st.columns(2)
    durum_secim = r1.multiselect("Durum", ["acik", "devam", "kapali"], default=["acik", "devam", "kapali"],
                                  format_func=lambda x: {"acik": "Açık", "devam": "Devam Eden", "kapali": "Kapalı"}[x])
    sorumlu_listesi = sorted([s for s in df_active["sorumlu"].unique() if s])
    sorumlu_secim = r2.multiselect("Sorumlu", sorumlu_listesi, default=sorumlu_listesi)

    r3, r4 = st.columns(2)
    tamamlayan_listesi = sorted([s for s in df_active["tamamlayan"].unique() if s])
    tamamlayan_secim = r3.multiselect("Tamamlayan", tamamlayan_listesi, default=tamamlayan_listesi)

    tarih_araligi = r4.date_input(
        "Görev tarihi aralığı",
        value=(datetime.date.today() - datetime.timedelta(days=30), datetime.date.today())
    )

    rapor_df = df_active.copy()
    rapor_df = rapor_df[rapor_df["durum"].isin(durum_secim)]
    if sorumlu_secim:
        rapor_df = rapor_df[rapor_df["sorumlu"].isin(sorumlu_secim) | (rapor_df["sorumlu"] == "")]
    if tamamlayan_secim:
        rapor_df = rapor_df[rapor_df["tamamlayan"].isin(tamamlayan_secim) | (rapor_df["tamamlayan"] == "")]

    if len(tarih_araligi) == 2:
        try:
            rapor_df["_tarih_dt"] = pd.to_datetime(rapor_df["tarih"], errors="coerce")
            baslangic, bitis = tarih_araligi
            rapor_df = rapor_df[
                (rapor_df["_tarih_dt"].dt.date >= baslangic) & (rapor_df["_tarih_dt"].dt.date <= bitis)
                | (rapor_df["_tarih_dt"].isna())
            ]
            rapor_df = rapor_df.drop(columns=["_tarih_dt"])
        except Exception:
            pass

    st.write(f"**{len(rapor_df)} görev bulundu**")
    st.dataframe(
        rapor_df[["gorev", "sorumlu", "durum", "tarih", "tamamlanma_tarihi", "tamamlayan", "olusturan"]],
        use_container_width=True,
        hide_index=True
    )

    csv_data = rapor_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ CSV olarak indir", csv_data, file_name="gorev_raporu.csv", mime="text/csv")

# TAB 5: HAFTALIK RAPOR (WORD)
def add_report_table(doc, dataframe, columns, headers, empty_text="Bu dönemde kayıt yok."):
    if dataframe.empty:
        p = doc.add_paragraph(empty_text)
        p.italic = True
        return

    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Light Grid Accent 1"
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        for p in hdr_cells[i].paragraphs:
            for r in p.runs:
                r.bold = True

    for _, row in dataframe.iterrows():
        cells = table.add_row().cells
        for i, col in enumerate(columns):
            cells[i].text = str(row.get(col, "") or "-")


def generate_weekly_report_docx(donem_baslangic, donem_bitis, tamamlanan_donem, yeni_donem,
                                 acik_sayisi, devam_sayisi, kapali_sayisi, hazirlayan):
    doc = Document()

    title = doc.add_heading("Haftalık Faaliyet Raporu", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    meta = doc.add_paragraph()
    meta.add_run(f"Dönem: ").bold = True
    meta.add_run(f"{donem_baslangic.strftime('%d.%m.%Y')} — {donem_bitis.strftime('%d.%m.%Y')}\n")
    meta.add_run("Hazırlayan: ").bold = True
    meta.add_run(f"{hazirlayan}\n")
    meta.add_run("Oluşturma Tarihi: ").bold = True
    meta.add_run(datetime.date.today().strftime('%d.%m.%Y'))

    doc.add_heading("Genel Durum (Anlık)", level=2)
    ozet = doc.add_paragraph()
    ozet.add_run(f"Açık görev sayısı: ").bold = True
    ozet.add_run(f"{acik_sayisi}\n")
    ozet.add_run(f"Devam eden görev sayısı: ").bold = True
    ozet.add_run(f"{devam_sayisi}\n")
    ozet.add_run(f"Kapalı görev sayısı: ").bold = True
    ozet.add_run(f"{kapali_sayisi}")

    doc.add_heading(f"Bu Dönemde Tamamlanan Görevler ({len(tamamlanan_donem)})", level=2)
    add_report_table(
        doc, tamamlanan_donem,
        columns=["gorev", "sorumlu", "tamamlanma_tarihi", "tamamlayan"],
        headers=["Görev", "Sorumlu", "Tamamlanma Tarihi", "Tamamlayan"]
    )

    doc.add_heading(f"Bu Dönemde Eklenen Yeni Görevler ({len(yeni_donem)})", level=2)
    add_report_table(
        doc, yeni_donem,
        columns=["gorev", "sorumlu", "durum", "tarih", "olusturan"],
        headers=["Görev", "Sorumlu", "Durum", "Tarih", "Ekleyen"]
    )

    footer = doc.add_paragraph()
    footer_run = footer.add_run(
        f"Bu rapor Satın Alma Görev Takip sisteminden {hazirlayan} tarafından oluşturulmuştur."
    )
    footer_run.italic = True
    footer_run.font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


with tab5:
    st.subheader("📄 Haftalık Faaliyet Raporu (Word)")
    st.caption("Raporu oluşturup Word (.docx) olarak indirin, dilediğiniz gibi düzenleyip kendi e-posta istemcinizden gönderin.")

    donem_col1, donem_col2 = st.columns(2)
    varsayilan_baslangic = datetime.date.today() - datetime.timedelta(days=7)
    donem_baslangic = donem_col1.date_input("Dönem başlangıcı", varsayilan_baslangic, key="donem_baslangic")
    donem_bitis = donem_col2.date_input("Dönem bitişi", datetime.date.today(), key="donem_bitis")

    if st.button("📝 Raporu Oluştur"):
        if donem_baslangic > donem_bitis:
            st.error("Dönem başlangıcı, bitiş tarihinden sonra olamaz.")
        else:
            df_all = df_active.copy()
            df_all["_tarih_dt"] = pd.to_datetime(df_all["tarih"], errors="coerce")
            df_all["_tamamlanma_dt"] = pd.to_datetime(df_all["tamamlanma_tarihi"], errors="coerce")

            tamamlanan_donem = df_all[
                (df_all["_tamamlanma_dt"].dt.date >= donem_baslangic) &
                (df_all["_tamamlanma_dt"].dt.date <= donem_bitis)
            ]
            yeni_donem = df_all[
                (df_all["_tarih_dt"].dt.date >= donem_baslangic) &
                (df_all["_tarih_dt"].dt.date <= donem_bitis)
            ]

            docx_buf = generate_weekly_report_docx(
                donem_baslangic, donem_bitis, tamamlanan_donem, yeni_donem,
                acik_sayisi, devam_sayisi, kapali_sayisi, selected_user
            )

            st.session_state["rapor_docx"] = docx_buf.getvalue()
            st.session_state["rapor_dosya_adi"] = f"haftalik_rapor_{donem_baslangic}_{donem_bitis}.docx"
            st.success("Rapor oluşturuldu, aşağıdan indirebilirsiniz.")

    if "rapor_docx" in st.session_state:
        st.download_button(
            "⬇️ Word Raporunu İndir",
            data=st.session_state["rapor_docx"],
            file_name=st.session_state["rapor_dosya_adi"],
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

# --- İMZA ---
st.markdown(
    """
    <style>
    .imza {
        position: fixed;
        bottom: 8px;
        right: 14px;
        font-size: 11px;
        color: #9a9a9a;
        opacity: 0.7;
        z-index: 100;
    }
    </style>
    <div class="imza">created by Bilal KEMERTAŞ 🛠️</div>
    """,
    unsafe_allow_html=True
)
