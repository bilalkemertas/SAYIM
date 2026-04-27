import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Genişlik Ayarı
st.set_page_config(page_title="BRN Depo Sayım v1.2", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    # Filtreler için listeleri hazırla
    kod_listesi = sorted(df_Stok_ana["Kod"].unique().tolist())
    ad_listesi = sorted(df_Stok_ana["Ad"].unique().tolist()) if "Ad" in df_Stok_ana.columns else []
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Lütfen 'Stok' sekmesini kontrol et. Hata: {e}")
    st.stop()

# --- 2. GİRİŞ (LOGIN) SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'gecici_sayim_listesi' not in st.session_state:
    st.session_state['gecici_sayim_listesi'] = [] # Veriyi burada tutacağız (Cache)

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
    st.session_state.clear()
    st.rerun()

st.title("🚀 Hızlı Sayım ve Akıllı Raporlama")

tab1, tab2 = st.tabs(["📝 Hızlı Sayım Girişi", "📊 Stok Karşılaştırma Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI (CACHE MANTIĞI) ---
with tab1:
    st.subheader("📍 Yerel Sayım Listesi (Henüz Drive'a Yazılmadı)")
    
    with st.form("sayim_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1,2,1])
        with c1:
            s_adres = st.text_input("📍 Adres").upper()
        with c2:
            s_Kod = st.selectbox("📦 Ürün Kodu Seçin", [""] + kod_listesi)
        with c3:
            s_miktar = st.number_input("⚖️ Sayılan Miktar", min_value=0.0, step=1.0)
        
        if st.form_submit_button("➕ Listeye Ekle"):
            if s_adres and s_Kod and s_miktar >= 0:
                yeni_kayit = {
                    "Tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
                    "Personel": st.session_state['user_name'],
                    "Adres": s_adres,
                    "Kod": s_Kod,
                    "Miktar": s_miktar,
                    "Birim": "ADET" # Varsayılan
                }
                st.session_state['gecici_sayim_listesi'].append(yeni_kayit)
                st.toast(f"✅ {s_Kod} listeye eklendi.", icon="📥")
            else:
                st.warning("Lütfen Adres ve Kod seçiniz!")

    # Sepetteki verileri göster
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.dataframe(df_gecici, use_container_width=True)
        
        col_onay, col_iptal = st.columns(2)
        if col_onay.button("📤 SAYIMI ONAYLA VE DRIVE'A GÖNDER", use_container_width=True, type="primary"):
            try:
                with st.spinner("Veriler Drive'a aktarılıyor..."):
                    df_sayim_mevcut = conn.read(worksheet="sayim", ttl=0)
                    df_son = pd.concat([df_sayim_mevcut, df_gecici], ignore_index=True)
                    conn.update(worksheet="sayim", data=df_son)
                    st.session_state['gecici_sayim_listesi'] = [] # Cache temizle
                    st.success("✅ Tüm veriler başarıyla Drive'a kaydedildi!")
                    st.balloons()
            except Exception as e:
                st.error(f"Kayıt Hatası: {e}")
        
        if col_iptal.button("🗑️ Listeyi Temizle", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: HİZALANMIŞ VE FİLTRELİ RAPORLAMA ---
with tab2:
    st.subheader("🔍 Gelişmiş Filtreleme Paneli")
    
    # Rapor verilerini çek ve hazırla
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        # Karşılaştırma Mantığı
        sistem = df_Stok_ana[['Adres', 'Kod', 'Ad', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        if not df_sayim_db.empty:
            df_sayim_db['Miktar'] = pd.to_numeric(df_sayim_db['Miktar'], errors='coerce').fillna(0)
            sayim_ozet = df_sayim_db.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            sayim_ozet.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            sayim_ozet = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        rapor_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Kod'], how='outer').fillna(0)
        rapor_df['FARK'] = rapor_df['Sayılan_Miktar'] - rapor_df['Sistem_Miktarı']

        # FİLTRELEME ALANI
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            f_kod = st.multiselect("📦 Kod Filtresi", options=kod_listesi)
        with f_col2:
            f_ad = st.multiselect("📝 Ürün Adı Filtresi", options=ad_listesi)
        with f_col3:
            f_adres = st.multiselect("📍 Adres Filtresi", options=sorted(rapor_df["Adres"].unique().tolist()))

        # Filtreleri Uygula
        final_df = rapor_df.copy()
        if f_kod:
            final_df = final_df[final_df["Kod"].isin(f_kod)]
        if f_ad:
            final_df = final_df[final_df["Ürün Adı"].isin(f_ad)]
        if f_adres:
            final_df = final_df[final_df["Adres"].isin(f_adres)]

        # Tabloyu Göster
        def color_fark(val):
            if val < 0: return 'background-color: #ffcccc; color: red'
            if val > 0: return 'background-color: #ccffcc; color: green'
            return ''

        st.dataframe(
            final_df.style.map(color_fark, subset=['FARK']), 
            use_container_width=True
        )

        # Özet Metrikler
        m1, m2, m3 = st.columns(3)
        m1.metric("Toplam Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Toplam Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Net Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
