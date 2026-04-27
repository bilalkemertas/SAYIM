import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Genişlik Ayarı
st.set_page_config(page_title="BRN Depo Sayım v1.1", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_stok_ana = conn.read(worksheet="stok", ttl=0)
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Lütfen 'stok' sekmesini kontrol et. Hata: {e}")
    st.stop()

# --- 2. GİRİŞ (LOGIN) SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

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
            st.error("Hatalı kullanıcı adı veya şifre!")
    st.stop()

# --- 3. ANA UYGULAMA ---
st.sidebar.info(f"👤 Personel: {st.session_state['user_name']}")
if st.sidebar.button("Güvenli Çıkış"):
    st.session_state['logged_in'] = False
    st.rerun()

st.title("🔢 Depo Sayım ve Envanter Kontrolü")

tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Stok Karşılaştırma Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI ---
with tab1:
    with st.form("sayim_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            s_adres = st.text_input("📍 Adres").upper()
            s_kod = st.text_input("📦 Kod (Ürün Kodu)").upper() # "kod" sütununa gidecek veri
        with c2:
            s_miktar = st.number_input("⚖️ Sayılan Miktar", min_value=0.0, step=1.0)
            s_birim = st.selectbox("📏 Birim", ["ADET", "KG", "MT", "PAKET"])
        
        if st.form_submit_button("💾 Sayımı Sisteme Kaydet"):
            if s_adres and s_kod:
                try:
                    df_sayim_mevcut = conn.read(worksheet="sayim", ttl=0)
                    yeni_veri = pd.DataFrame({
                        "Tarih": [datetime.now().strftime("%d.%m.%Y %H:%M")],
                        "Personel": [st.session_state['user_name']],
                        "Adres": [s_adres],
                        "kod": [s_kod], # Sütun adını "kod" yaptık
                        "Miktar": [s_miktar],
                        "Birim": [s_birim]
                    })
                    df_sayim_son = pd.concat([df_sayim_mevcut, yeni_veri], ignore_index=True)
                    conn.update(worksheet="sayim", data=df_sayim_son)
                    st.success(f"✅ {s_kod} kaydedildi.")
                except Exception as e:
                    st.error(f"Kayıt Hatası: {e}")
            else:
                st.warning("Lütfen Adres ve Kod alanlarını doldurun!")

# --- TAB 2: HİZALANMIŞ RAPORLAMA ---
with tab2:
    if st.button("🔄 Raporu Yenile ve Hesapla"):
        try:
            # 1. Sistem Stoğu (stok sekmesi)
            # Senin tablolarında "kod" sütunu olduğu için sütun adlarını buna göre seçiyoruz
            sistem = df_stok_ana[['Adres', 'kod', 'Miktar']].copy()
            sistem['Miktar'] = pd.to_numeric(sistem['Miktar'], errors='coerce').fillna(0)
            sistem.columns = ["Adres", "kod", "Sistem_Miktarı"]

            # 2. Sayım Verileri (sayim sekmesi)
            df_sayim_raw = conn.read(worksheet="sayim", ttl=0)
            if not df_sayim_raw.empty:
                df_sayim_raw['Miktar'] = pd.to_numeric(df_sayim_raw['Miktar'], errors='coerce').fillna(0)
                sayim_ozet = df_sayim_raw.groupby(['Adres', 'kod'])['Miktar'].sum().reset_index()
                sayim_ozet.columns = ["Adres", "kod", "Sayılan_Miktar"]
            else:
                sayim_ozet = pd.DataFrame(columns=["Adres", "kod", "Sayılan_Miktar"])

            # 3. Hizalama (Outer Join)
            rapor_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'kod'], how='outer').fillna(0)
            rapor_df['FARK'] = rapor_df['Sayılan_Miktar'] - rapor_df['Sistem_Miktarı']

            # 4. Renklendirme ve Görselleştirme (Hata veren applymap yerine map kullanıldı)
            def color_fark(val):
                if val < 0: return 'background-color: #ffcccc; color: red'
                if val > 0: return 'background-color: #ccffcc; color: green'
                return ''

            st.write("### 📊 Stok vs Sayım Fark Analizi")
            # Pandas 2.x+ sürümü için map kullanıyoruz
            st.dataframe(
                rapor_df.style.map(color_fark, subset=['FARK']), 
                use_container_width=True
            )

            # Özet Bilgi
            c1, c2, c3 = st.columns(3)
            c1.metric("Sistem Toplam", f"{rapor_df['Sistem_Miktarı'].sum():,.0f}")
            c2.metric("Sayılan Toplam", f"{rapor_df['Sayılan_Miktar'].sum():,.0f}")
            c3.metric("Net Fark", f"{rapor_df['FARK'].sum():,.0f}")

        except Exception as e:
            st.error(f"Rapor hatası: {e}. Lütfen sekmelerdeki sütun başlıklarının 'Adres', 'kod' ve 'Miktar' olduğundan emin olun.")
