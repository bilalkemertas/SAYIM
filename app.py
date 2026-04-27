import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Ayarları
st.set_page_config(page_title="BRN Depo Sayım v1.7", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Veri Temizliği: Stoktaki boş satırları uçur
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod", "İsim"])
    
    # Eşleşme Sözlüğü (Kod -> İsim)
    kod_isim_dict = pd.Series(df_Stok_ana.İsim.values, index=df_Stok_ana.Kod.astype(str)).to_dict()
    kod_listesi = sorted(list(kod_isim_dict.keys()))
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Hata: {e}")
    st.stop()

# --- 2. GİRİŞ VE CACHE SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'gecici_sayim_listesi' not in st.session_state:
    st.session_state['gecici_sayim_listesi'] = []

if not st.session_state['logged_in']:
    st.title("🔐 BRN Depo Sistemi")
    user_id = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    if st.button("Giriş Yap"):
        if user_id in st.secrets["users"] and st.secrets["users"][user_id] == password:
            st.session_state['logged_in'] = True
            st.session_state['user_name'] = user_id
            st.rerun()
        else:
            st.error("Hatalı Giriş!")
    st.stop()

# --- 3. ANA UYGULAMA ---
st.sidebar.info(f"👤 Personel: {st.session_state['user_name']}")
if st.sidebar.button("Güvenli Çıkış"):
    st.session_state.clear()
    st.rerun()

st.title("🚀 Akıllı Depo Sayım Modülü")

tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Fark Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI (FORM DIŞI - ANLIK GÜNCEL) ---
with tab1:
    st.subheader("📍 Sayım Verisi Ekle")
    
    # Formu kaldırdık, container içinde anlık tepki veriyoruz
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            s_adres = st.text_input("📍 Adres", key="adr_in").upper()
        with c2:
            # Selectbox yerine barkod okuyucuyla uyumlu olması için text_input da olabilir
            # Ama selectbox istersen:
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi, key="kod_sel")
            
            # --- ÜRÜN ADINI GETİRME (BU KISIM ARTIK ANLIK ÇALIŞIR) ---
            s_isim = kod_isim_dict.get(str(s_Kod), "")
            if s_Kod != "":
                st.markdown(f"**Ürün Adı:** :blue[{s_isim}]") # Mavi kalın yazı
        with c3:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0, key="mik_in")
        
        # Butona basınca listeye ekle
        if st.button("➕ Listeye Ekle", use_container_width=True):
            if s_adres and s_Kod and s_miktar >= 0:
                yeni_kayit = {
                    "Tarih": datetime.now().strftime("%d.%m.%Y"), # Saat dakika saniye YOK
                    "Personel": st.session_state['user_name'],
                    "Adres": s_adres,
                    "Kod": s_Kod,
                    "Ürün Adı": s_isim,
                    "Miktar": s_miktar
                }
                st.session_state['gecici_sayim_listesi'].append(yeni_kayit)
                st.toast(f"{s_Kod} sepete eklendi.")
            else:
                st.warning("Lütfen Adres ve Kod alanlarını doldurunuz!")

    # Onay Bekleyen Liste
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        st.markdown("### 📥 Onay Bekleyen Liste")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.dataframe(df_gecici, use_container_width=True)
        
        col_onay, col_iptal = st.columns(2)
        if col_onay.button("📤 DRIVE'A GÖNDER VE KAYDET", type="primary", use_container_width=True):
            try:
                df_db = conn.read(worksheet="sayim", ttl=0)
                df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                conn.update(worksheet="sayim", data=df_son)
                st.session_state['gecici_sayim_listesi'] = []
                st.success("✅ Veriler Drive'a aktarıldı!")
                st.rerun() # Sayfayı yenileyerek listeyi temizle
            except Exception as e:
                st.error(f"Aktarım hatası: {e}")
        
        if col_iptal.button("🗑️ Listeyi Temizle", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: TEMİZ TARİH FİLTRELİ RAPOR ---
with tab2:
    st.subheader("🔍 Stok Karşılaştırma")
    try:
        # Sayım verilerini Drive'dan oku
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        # --- SAAT DAKİKA TEMİZLEME OPERASYONU ---
        if not df_sayim_db.empty:
            # Tarih sütununu stringe çevir ve sadece ilk 10 karakteri al (GG.AA.YYYY)
            df_sayim_db["Tarih"] = df_sayim_db["Tarih"].astype(str).str[:10]
        
        # Sistem Stoğu Hazırla
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        with st.expander("🛠️ Rapor Filtreleri", expanded=True):
            f1, f2 = st.columns(2)
            with f1:
                # Tarih opsiyonlarını temizlenmiş veriden al
                tarih_list = ["Hepsi"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Hepsi"]
                f_tarih = st.selectbox("📅 Sayım Tarihi (GG.AA.YYYY)", tarih_list)
            with f2:
                f_kod = st.multiselect("📦 Kod Filtresi", kod_listesi)

        # Filtreleme Başlıyor
        active_sayim = df_sayim_db.copy()
        if f_tarih != "Hepsi":
            active_sayim = active_sayim[active_sayim["Tarih"] == f_tarih]

        if not active_sayim.empty:
            active_sayim['Miktar'] = pd.to_numeric(active_sayim['Miktar'], errors='coerce').fillna(0)
            sayim_ozet = active_sayim.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            sayim_ozet.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            sayim_ozet = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        # Join ve Karşılaştırma
        final_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Kod'], how='outer').fillna(0)
        final_df['FARK'] = final_df['Sayılan_Miktar'] - final_df['Sistem_Miktarı']

        if f_kod:
            final_df = final_df[final_df["Kod"].isin(f_kod)]

        # Tabloyu Göster
        def style_f(v):
            if v < 0: return 'background-color: #ffcccc; color: red'
            if v > 0: return 'background-color: #ccffcc; color: green'
            return ''

        st.dataframe(final_df.style.map(style_f, subset=['FARK']), use_container_width=True)

        # Alt Toplamlar
        m1, m2, m3 = st.columns(3)
        m1.metric("Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
