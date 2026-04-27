import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Ayarları
st.set_page_config(page_title="BRN Depo Sayım v1.6", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Boş verileri temizle ve eşleşme sözlüğü kur
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod", "İsim"])
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

# --- TAB 1: SAYIM GİRİŞ EKRANI (DİNAMİK) ---
with tab1:
    st.subheader("📍 Sayım Verisi Ekle")
    
    # Form yerine container kullanarak anlık güncelleme sağlıyoruz
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            s_adres = st.text_input("📍 Adres").upper()
        with c2:
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi)
            # Kod seçildiği anda ismi getiriyoruz
            s_isim = kod_isim_dict.get(str(s_Kod), "")
            if s_Kod != "":
                st.info(f"🔍 **Ürün Adı:** {s_isim}") # Seçim yapıldığı an burası güncellenir
        with c3:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0)
        
        if st.button("➕ Listeye Ekle", use_container_width=True, type="secondary"):
            if s_adres and s_Kod:
                st.session_state['gecici_sayim_listesi'].append({
                    "Tarih": datetime.now().strftime("%d.%m.%Y"), # Sadece Gün
                    "Personel": st.session_state['user_name'],
                    "Adres": s_adres,
                    "Kod": s_Kod,
                    "Ürün Adı": s_isim,
                    "Miktar": s_miktar
                })
                st.toast(f"{s_Kod} sepete eklendi.")
            else:
                st.warning("Lütfen Adres ve Ürün seçiniz!")

    # Onay Bekleyen Liste
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        st.markdown("### 📥 Onay Bekleyen Liste")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.dataframe(df_gecici, use_container_width=True)
        
        co1, co2 = st.columns(2)
        if co1.button("📤 DRIVE'A GÖNDER VE KAYDET", type="primary", use_container_width=True):
            try:
                df_db = conn.read(worksheet="sayim", ttl=0)
                df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                conn.update(worksheet="sayim", data=df_son)
                st.session_state['gecici_sayim_listesi'] = []
                st.success("Tüm veriler Drive'a aktarıldı!")
                st.balloons()
            except Exception as e:
                st.error(f"Aktarım hatası: {e}")
        
        if co2.button("🗑️ Listeyi Temizle", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: TEMİZ TARİH FİLTRELİ RAPOR ---
with tab2:
    st.subheader("🔍 Günlük/Genel Stok Karşılaştırma")
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        # Karşılaştırma Hazırlığı
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        with st.expander("🛠️ Filtreleme Paneli", expanded=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                # Tarih filtresini gün bazlı sadeleştirdik
                tarih_ops = ["Hepsi"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Hepsi"]
                f_tarih = st.selectbox("📅 Sayım Tarihi", tarih_ops)
            with f2:
                f_kod = st.multiselect("📦 Kod Filtresi", kod_listesi)
            with f3:
                f_adr = st.multiselect("📍 Adres Filtresi", sorted(sistem["Adres"].unique().tolist()))

        # Sayım Verisini Ön Filtrele
        curr_sayim = df_sayim_db.copy()
        if f_tarih != "Hepsi":
            curr_sayim = curr_sayim[curr_sayim["Tarih"] == f_tarih]

        if not curr_sayim.empty:
            curr_sayim['Miktar'] = pd.to_numeric(curr_sayim['Miktar'], errors='coerce').fillna(0)
            sayim_oz = curr_sayim.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            sayim_oz.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            sayim_oz = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        # Join ve Fark Hesaplama
        final_df = pd.merge(sistem, sayim_oz, on=['Adres', 'Kod'], how='outer').fillna(0)
        final_df['FARK'] = final_df['Sayılan_Miktar'] - final_df['Sistem_Miktarı']

        # Multi-seçim Filtreleri
        if f_kod: final_df = final_df[final_df["Kod"].isin(f_kod)]
        if f_adr: final_df = final_df[final_df["Adres"].isin(f_adr)]

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
