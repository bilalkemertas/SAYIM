import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Ayarları
st.set_page_config(page_title="BRN Depo Sayım v1.8", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Boş verileri temizle ve eşleşme sözlüğü kur
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod", "İsim"])
    
    # Kod -> İsim sözlüğü (Sayım girişinde anlık isim göstermek için)
    kod_isim_dict = pd.Series(df_Stok_ana.İsim.values, index=df_Stok_ana.Kod.astype(str)).to_dict()
    kod_listesi = sorted(list(kod_isim_dict.keys()))
    ad_listesi = sorted(df_Stok_ana["İsim"].unique().tolist())
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Hata: {e}")
    st.stop()

# --- 2. GİRİŞ VE BELLEK SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'gecici_sayim_listesi' not in st.session_state:
    st.session_state['gecici_sayim_listesi'] = []

if not st.session_state['logged_in']:
    st.title("🔐 BRN Depo Giriş")
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

st.title("🚀 Kesin Çözüm: Sayım ve Filtreli Rapor")

tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Fark Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI (ANLIK İSİM GÜNCELLEME) ---
with tab1:
    st.subheader("📍 Sayım Verisi Ekle")
    
    # Form dışında container kullanarak anlık isim gelmesini sağlıyoruz
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            s_adres = st.text_input("📍 Adres", key="adr_input").upper()
        with c2:
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi, key="kod_select")
            
            # --- ÜRÜN ADINI GETİRME (BURASI ARTIK ANLIK) ---
            s_isim = kod_isim_dict.get(str(s_Kod), "")
            if s_Kod != "":
                st.markdown(f"**Ürün Adı:** :blue[{s_isim}]")
        with c3:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0, key="mik_input")
        
        if st.button("➕ Listeye Ekle", use_container_width=True):
            if s_adres and s_Kod:
                yeni_kayit = {
                    "Tarih": datetime.now().strftime("%d.%m.%Y"), # Saat/dakika temizlendi
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

    # Geçici Liste (Sepet)
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        st.markdown("### 📥 Onay Bekleyen Liste")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.dataframe(df_gecici, use_container_width=True)
        
        o_col, i_col = st.columns(2)
        if o_col.button("📤 DRIVE'A GÖNDER VE KAYDET", type="primary", use_container_width=True):
            try:
                df_db = conn.read(worksheet="sayim", ttl=0)
                df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                conn.update(worksheet="sayim", data=df_son)
                st.session_state['gecici_sayim_listesi'] = []
                st.success("Veriler Drive'a aktarıldı!")
                st.rerun()
            except Exception as e:
                st.error(f"Aktarım hatası: {e}")
        
        if i_col.button("🗑️ Listeyi Temizle", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: TEMİZ TARİH VE TÜM FİLTRELER ---
with tab2:
    st.subheader("🔍 Filtreli Stok Karşılaştırma")
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        # --- TARİH TEMİZLEME (SAAT/DAKİKA KESİMİ) ---
        if not df_sayim_db.empty:
            df_sayim_db["Tarih"] = df_sayim_db["Tarih"].astype(str).str[:10]
        
        # Sistem Stoğu
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        # --- FİLTRE PANELİ (Ürün Adı Geri Geldi!) ---
        with st.expander("🛠️ Rapor Filtreleri", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                t_list = ["Hepsi"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Hepsi"]
                f_tarih = st.selectbox("📅 Tarih", t_list)
            with f2:
                f_kod = st.multiselect("📦 Kod", kod_listesi)
            with f3:
                # Ürün Adı Filtresi Burası!
                f_ad = st.multiselect("📝 Ürün Adı", ad_listesi)
            with f4:
                f_adr = st.multiselect("📍 Adres", sorted(sistem["Adres"].unique().tolist()))

        # Sayım Verisi Filtreleme
        act_sayim = df_sayim_db.copy()
        if f_tarih != "Hepsi":
            act_sayim = act_sayim[act_sayim["Tarih"] == f_tarih]

        if not act_sayim.empty:
            act_sayim['Miktar'] = pd.to_numeric(act_sayim['Miktar'], errors='coerce').fillna(0)
            s_ozet = act_sayim.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            s_ozet.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            s_ozet = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        # Birleştirme
        final_df = pd.merge(sistem, s_ozet, on=['Adres', 'Kod'], how='outer').fillna(0)
        final_df['FARK'] = final_df['Sayılan_Miktar'] - final_df['Sistem_Miktarı']

        # Multi Filtre Uygulama
        if f_kod: final_df = final_df[final_df["Kod"].isin(f_kod)]
        if f_ad: final_df = final_df[final_df["Ürün Adı"].isin(f_ad)]
        if f_adr: final_df = final_df[final_df["Adres"].isin(f_adr)]

        # Tabloyu Göster
        def style_logic(v):
            if v < 0: return 'background-color: #ffcccc; color: red'
            if v > 0: return 'background-color: #ccffcc; color: green'
            return ''

        st.dataframe(final_df.style.map(style_logic, subset=['FARK']), use_container_width=True)

        # Metrikler
        m1, m2, m3 = st.columns(3)
        m1.metric("Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
