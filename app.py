import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Ayarları
st.set_page_config(page_title="BRN Depo Sayım v2.1", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Veri Temizliği: Boşlukları temizle ve metne çevir
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod", "İsim"])
    df_Stok_ana["Kod"] = df_Stok_ana["Kod"].astype(str).str.strip()
    
    # Kod -> İsim Sözlüğü (Anlık eşleşme için)
    kod_isim_dict = pd.Series(df_Stok_ana.İsim.values, index=df_Stok_ana.Kod).to_dict()
    kod_listesi = sorted(list(kod_isim_dict.keys()))
    ad_listesi = sorted(df_Stok_ana["İsim"].unique().tolist())
except Exception as e:
    st.error(f"Bağlantı hatası! Stok sekmesini kontrol edin. Hata: {e}")
    st.stop()

# --- 2. GİRİŞ VE BELLEK SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'gecici_sayim_listesi' not in st.session_state:
    st.session_state['gecici_sayim_listesi'] = []

if not st.session_state['logged_in']:
    st.title("🔐 BRN Depo Girişi")
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

st.title("🚀 Sayım İşlemleri")

tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Sayım Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI (OTOMATİK DOLAN KUTUCUK) ---
with tab1:
    st.subheader("📍 Yeni Veri Girişi")
    
    with st.container(border=True):
        # Hizalama Sütunları
        col_adr, col_kod, col_isim, col_mik = st.columns([1, 1.5, 2.5, 1])
        
        with col_adr:
            s_adres = st.text_input("📍 Adres", key="adr_box").upper()
        
        with col_kod:
            # Seçim kutusu
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi, key="kod_box")
            
        with col_isim:
            # KRİTİK DÜZELTME: Ürün adı burada 'key' olmadan, doğrudan 's_Kod'a bağlı çalışır
            current_name = kod_isim_dict.get(str(s_Kod), "")
            st.text_input("📝 Ürün Adı", value=current_name, disabled=True)
            
        with col_mik:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0, key="mik_box")
        
        if st.button("➕ Listeye Ekle", use_container_width=True):
            if s_adres and s_Kod:
                st.session_state['gecici_sayim_listesi'].append({
                    "Tarih": datetime.now().strftime("%d.%m.%Y"),
                    "Personel": st.session_state['user_name'],
                    "Adres": s_adres,
                    "Kod": s_Kod,
                    "Ürün Adı": current_name,
                    "Miktar": s_miktar
                })
                st.toast(f"{s_Kod} sepete eklendi.")
            else:
                st.warning("Eksik alanları doldurun!")

    # Onay Bekleyen Liste
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        st.markdown("### 📥 Onay Bekleyen Sayımlar")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.dataframe(df_gecici, use_container_width=True)
        
        c_onay, c_iptal = st.columns(2)
        if c_onay.button("📤 DRIVE'A GÖNDER VE KAYDET", type="primary", use_container_width=True):
            try:
                df_db = conn.read(worksheet="sayim", ttl=0)
                df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                conn.update(worksheet="sayim", data=df_son)
                st.session_state['gecici_sayim_listesi'] = []
                st.success("Veriler Drive'a aktarıldı!")
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")
        
        if c_iptal.button("🗑️ Listeyi Temizle", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: TEMİZ TARİH VE TÜM FİLTRELER ---
with tab2:
    st.subheader("🔍 Sayım Listeleri")
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        if not df_sayim_db.empty:
            df_sayim_db["Tarih"] = df_sayim_db["Tarih"].astype(str).str[:10]
        
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        with st.expander("🛠️ Filtreler", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                t_list = ["Hepsi"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Hepsi"]
                f_tarih = st.selectbox("📅 Tarih", t_list)
            with f2:
                f_kod = st.multiselect("📦 Kod", kod_listesi)
            with f3:
                f_ad = st.multiselect("📝 Ürün Adı", ad_listesi)
            with f4:
                f_adr = st.multiselect("📍 Adres", sorted(sistem["Adres"].unique().tolist()))

        act_sayim = df_sayim_db.copy()
        if f_tarih != "Hepsi":
            act_sayim = act_sayim[act_sayim["Tarih"] == f_tarih]

        if not act_sayim.empty:
            act_sayim['Miktar'] = pd.to_numeric(act_sayim['Miktar'], errors='coerce').fillna(0)
            s_ozet = act_sayim.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            s_ozet.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            s_ozet = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        final_df = pd.merge(sistem, s_ozet, on=['Adres', 'Kod'], how='outer').fillna(0)
        final_df['FARK'] = final_df['Sayılan_Miktar'] - final_df['Sistem_Miktarı']

        if f_kod: final_df = final_df[final_df["Kod"].isin(f_kod)]
        if f_ad: final_df = final_df[final_df["Ürün Adı"].isin(f_ad)]
        if f_adr: final_df = final_df[final_df["Adres"].isin(f_adr)]

        def style_f(v):
            if v < 0: return 'background-color: #ffcccc; color: red'
            if v > 0: return 'background-color: #ccffcc; color: green'
            return ''

        st.dataframe(final_df.style.map(style_f, subset=['FARK']), use_container_width=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
