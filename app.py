import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="BRN Depo Sayım v1.0", layout="wide")

# --- VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # HAREKETLER sekmesini büyük harfle okuyoruz
    df_hareketler = conn.read(worksheet="HAREKETLER", ttl=0)
except Exception as e:
    st.error("Veritabanına bağlanılamadı. Lütfen Secrets ayarlarını ve Excel paylaşım iznini kontrol edin.")
    st.stop()

# --- GİRİŞ PANELİ ---
if 'login_status' not in st.session_state:
    st.session_state['login_status'] = False

if not st.session_state['login_status']:
    st.title("🔐 BRN Depo Sistemi Giriş")
    kullanici = st.text_input("Kullanıcı Adı")
    sifre = st.text_input("Şifre", type="password")
    
    if st.button("Giriş Yap"):
        if kullanici in st.secrets["users"] and st.secrets["users"][kullanici] == sifre:
            st.session_state['login_status'] = True
            st.session_state['user'] = kullanici
            st.rerun()
        else:
            st.error("Hatalı Giriş!")
    st.stop()

# --- ANA SAYFA ---
st.sidebar.success(f"Giriş Yapıldı: {st.session_state['user']}")
if st.sidebar.button("Çıkış Yap"):
    st.session_state['login_status'] = False
    st.rerun()

st.title("🔢 Depo Sayım ve Stok Kontrol")

tab1, tab2 = st.tabs(["📋 Yeni Sayım Girişi", "📊 Sayım Fark Raporu"])

with tab1:
    with st.form("sayim_formu"):
        col1, col2 = st.columns(2)
        with col1:
            adres = st.text_input("📍 Adres (Örn: A-01-01)").upper()
            kod = st.text_input("📦 Malzeme Kodu").upper()
        with col2:
            miktar = st.number_input("⚖️ Sayılan Miktar", min_value=0.0, step=1.0)
            birim = st.selectbox("📏 Birim", ["ADET", "KG", "MT", "PAKET"])
        
        onay = st.form_submit_button("SAYIMI KAYDET")
        
        if onay:
            if adres and kod:
                try:
                    # sayim sekmesini küçük harfle okuyoruz
                    mevcut_sayim = conn.read(worksheet="sayim", ttl=0)
                    yeni_satir = pd.DataFrame({
                        "Tarih": [datetime.now().strftime("%d.%m.%Y %H:%M")],
                        "Personel": [st.session_state['user']],
                        "Adres": [adres],
                        "Malzeme Kodu": [kod],
                        "Miktar": [miktar],
                        "Birim": [birim]
                    })
                    guncel_liste = pd.concat([mevcut_sayim, yeni_satir], ignore_index=True)
                    conn.update(worksheet="sayim", data=guncel_liste)
                    st.success(f"✅ {kod} başarıyla kaydedildi.")
                except Exception as e:
                    st.error(f"Kayıt Hatası: {e}")
            else:
                st.warning("Lütfen tüm alanları doldurun!")

with tab2:
    if st.button("Raporu Hesapla"):
        # Sistem Stoğu (HAREKETLER sekmesinden)
        df_h = df_hareketler.copy()
        df_h['Miktar'] = pd.to_numeric(df_h['Miktar'], errors='coerce').fillna(0)
        df_h['Net'] = df_h.apply(lambda r: r['Miktar'] if str(r['İşlem']).upper() == 'GİRİŞ' else -r['Miktar'], axis=1)
        
        sis_stok = df_h.groupby(['Adres', 'Malzeme Kodu'])['Net'].sum().reset_index()
        sis_stok.columns = ["Adres", "Malzeme Kodu", "Sistem_Miktarı"]
        
        # Sayım Stoğu (sayim sekmesinden)
        df_s = conn.read(worksheet="sayim", ttl=0)
        if not df_s.empty:
            df_s['Miktar'] = pd.to_numeric(df_s['Miktar'], errors='coerce').fillna(0)
            say_stok = df_s.groupby(['Adres', 'Malzeme Kodu'])['Miktar'].sum().reset_index()
            say_stok.columns = ["Adres", "Malzeme Kodu", "Sayılan_Miktar"]
            
            # Karşılaştırma
            fark_df = pd.merge(sis_stok, say_stok, on=['Adres', 'Malzeme Kodu'], how='outer').fillna(0)
            fark_df['FARK'] = fark_df['Sayılan_Miktar'] - fark_df['Sistem_Miktarı']
            
            st.write("### 🔍 Stok Fark Analizi")
            st.dataframe(fark_df, use_container_width=True)
        else:
            st.info("Henüz sayım verisi bulunmuyor.")
