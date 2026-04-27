import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Genişlik Ayarı
st.set_page_config(page_title="BRN Depo Sayım v1.4", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Veri temizleme (Boş satırları atla)
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod"])
    
    # Filtreler ve Eşleşmeler için Sözlük Hazırla
    # Kod girince ismi getirmek için bir sözlük (Mapping) oluşturuyoruz
    kod_isim_dict = pd.Series(df_Stok_ana.İsim.values, index=df_Stok_ana.Kod).to_dict()
    kod_listesi = sorted(list(kod_isim_dict.keys()))
    ad_listesi = sorted(df_Stok_ana["İsim"].unique().tolist())
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Lütfen 'Stok' sekmesini kontrol et. Hata: {e}")
    st.stop()

# --- 2. GİRİŞ VE CACHE SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'gecici_sayim_listesi' not in st.session_state:
    st.session_state['gecici_sayim_listesi'] = []

if not st.session_state['logged_in']:
    st.title("🔐 BRN Depo Sistemi Giriş")
    user_id = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    if st.button("Sisteme Giriş Yap"):
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

st.title("🚀 Akıllı Sayım ve Dinamik Raporlama")

tab1, tab2 = st.tabs(["📝 Hızlı Sayım Girişi", "📊 Stok Karşılaştırma Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI ---
with tab1:
    st.subheader("📍 Yerel Sayım Listesi")
    
    # Sayım Formu
    with st.container(border=True):
        c1, c2, c3 = st.columns([1,2,1])
        with c1:
            s_adres = st.text_input("📍 Adres", key="input_adres").upper()
        with c2:
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi, key="input_kod")
            # --- OTOMATİK İSİM GETİRME ---
            s_isim = kod_isim_dict.get(s_Kod, "")
            if s_isim:
                st.info(f"ℹ️ **Ürün Adı:** {s_isim}")
        with c3:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0, key="input_miktar")
        
        if st.button("➕ Listeye Ekle", use_container_width=True):
            if s_adres and s_Kod:
                yeni_kayit = {
                    "Tarih": datetime.now().strftime("%d.%m.%Y"),
                    "Zaman": datetime.now().strftime("%H:%M"),
                    "Personel": st.session_state['user_name'],
                    "Adres": s_adres,
                    "Kod": s_Kod,
                    "Ürün Adı": s_isim,
                    "Miktar": s_miktar
                }
                st.session_state['gecici_sayim_listesi'].append(yeni_kayit)
                st.toast(f"✅ {s_Kod} eklendi.", icon="📥")
            else:
                st.warning("Lütfen Adres ve Kod alanlarını doldurun!")

    # Sepet Gösterimi
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.dataframe(df_gecici, use_container_width=True)
        
        col_onay, col_iptal = st.columns(2)
        if col_onay.button("📤 SAYIMI ONAYLA VE DRIVE'A GÖNDER", use_container_width=True, type="primary"):
            try:
                with st.spinner("Drive güncelleniyor..."):
                    df_db = conn.read(worksheet="sayim", ttl=0)
                    df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                    conn.update(worksheet="sayim", data=df_son)
                    st.session_state['gecici_sayim_listesi'] = []
                    st.success("✅ Veriler Drive'a kaydedildi!")
                    st.balloons()
            except Exception as e:
                st.error(f"Kayıt Hatası: {e}")
        
        if col_iptal.button("🗑️ Listeyi Temizle", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: HİZALANMIŞ VE FİLTRELİ RAPORLAMA ---
with tab2:
    st.subheader("🔍 Gelişmiş Filtreleme ve Tarih Analizi")
    
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        # Karşılaştırma Hazırlığı
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        # --- FİLTRELEME ALANI ---
        f_exp = st.expander("🛠️ Filtreleri Aç/Kapat", expanded=True)
        with f_exp:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                # Tarih Filtresi
                tarih_opsiyon = ["Hepsi"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Hepsi"]
                f_tarih = st.selectbox("📅 Sayım Tarihi", tarih_opsiyon)
            with c2:
                f_kod = st.multiselect("📦 Kod", options=kod_listesi)
            with c3:
                f_ad = st.multiselect("📝 Ürün Adı", options=ad_listesi)
            with c4:
                f_adres = st.multiselect("📍 Adres", options=sorted(sistem["Adres"].unique().tolist()))

        # Sayım verisini tarihe göre ön filtrele
        current_sayim = df_sayim_db.copy()
        if f_tarih != "Hepsi":
            current_sayim = current_sayim[current_sayim["Tarih"] == f_tarih]

        # Gruplama
        if not current_sayim.empty:
            current_sayim['Miktar'] = pd.to_numeric(current_sayim['Miktar'], errors='coerce').fillna(0)
            sayim_ozet = current_sayim.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            sayim_ozet.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            sayim_ozet = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        # Birleştirme ve Fark
        final_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Kod'], how='outer').fillna(0)
        final_df['FARK'] = final_df['Sayılan_Miktar'] - final_df['Sistem_Miktarı']

        # Multiselect Filtrelerini Uygula
        if f_kod: final_df = final_df[final_df["Kod"].isin(f_kod)]
        if f_ad: final_df = final_df[final_df["Ürün Adı"].isin(f_ad)]
        if f_adres: final_df = final_df[final_df["Adres"].isin(f_adres)]

        # Tabloyu Göster
        def color_fark(val):
            if val < 0: return 'background-color: #ffcccc; color: red'
            if val > 0: return 'background-color: #ccffcc; color: green'
            return ''

        st.dataframe(final_df.style.map(color_fark, subset=['FARK']), use_container_width=True)

        # Metrikler
        m1, m2, m3 = st.columns(3)
        m1.metric("Toplam Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Toplam Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Net Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
