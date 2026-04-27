import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Genişlik Ayarı
st.set_page_config(page_title="BRN Depo Sayım v1.5", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Veri Temizliği: Kod veya İsim sütunu boş olanları ele
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod", "İsim"])
    
    # Eşleşme Sözlüğü (Kod girince İsim getirmek için)
    # Büyük/Küçük harf duyarlılığını önlemek için keyleri temizliyoruz
    kod_isim_dict = pd.Series(df_Stok_ana.İsim.values, index=df_Stok_ana.Kod.astype(str)).to_dict()
    kod_listesi = sorted(list(kod_isim_dict.keys()))
    ad_listesi = sorted(df_Stok_ana["İsim"].unique().tolist())
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Hata: {e}")
    st.stop()

# --- 2. GİRİŞ VE BELLEK (CACHE) SİSTEMİ ---
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

st.title("🚀 BRN Hızlı Sayım Sistemi")

tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Fark Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI ---
with tab1:
    st.subheader("📍 Yeni Sayım Ekle")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([1,2,1])
        with c1:
            s_adres = st.text_input("📍 Raf Adresi").upper()
        with c2:
            # Ürün Kodu Seçimi
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi)
            
            # ÜRÜN ADINI GETİRME (Kritik Alan)
            s_isim = kod_isim_dict.get(str(s_Kod), "")
            if s_Kod != "":
                if s_isim:
                    st.success(f"✅ **Ürün Adı:** {s_isim}")
                else:
                    st.warning("⚠️ Bu kodun ismi Stok listesinde bulunamadı!")
        with c3:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0)
        
        if st.button("➕ Listeye Ekle", use_container_width=True):
            if s_adres and s_Kod and s_miktar >= 0:
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
                st.warning("Lütfen Adres ve Kod giriniz!")

    # Geçici Liste (Sepet)
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        st.markdown("### 📥 Onay Bekleyen Sayımlar")
        df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
        st.table(df_gecici) # Daha okunaklı olması için tablo kullandık
        
        onay_col, iptal_col = st.columns(2)
        if onay_col.button("📤 HEPSİNİ DRIVE'A GÖNDER", type="primary", use_container_width=True):
            try:
                df_db = conn.read(worksheet="sayim", ttl=0)
                df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                conn.update(worksheet="sayim", data=df_son)
                st.session_state['gecici_sayim_listesi'] = []
                st.success("Tüm sayımlar başarıyla kaydedildi!")
                st.balloons()
            except Exception as e:
                st.error(f"Hata: {e}")
        
        if iptal_col.button("🗑️ Listeyi Boşalt", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: GÜN BAZLI FİLTRELİ RAPOR ---
with tab2:
    st.subheader("🔍 Günlük Fark Analizi")
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        # Karşılaştırma Hazırlığı
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        # --- FİLTRE PANELİ ---
        with st.expander("🛠️ Rapor Filtreleri", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                # Sadece Gün Filtresi (Zaman yok)
                tarih_ops = ["Tüm Zamanlar"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Tüm Zamanlar"]
                f_tarih = st.selectbox("📅 Sayım Günü", tarih_ops)
            with f2:
                f_kod = st.multiselect("📦 Ürün Kodu", kod_listesi)
            with f3:
                f_ad = st.multiselect("📝 Ürün İsimleri", ad_listesi)
            with f4:
                f_adr = st.multiselect("📍 Adresler", sorted(sistem["Adres"].unique().tolist()))

        # Filtreleme Mantığı
        active_sayim = df_sayim_db.copy()
        if f_tarih != "Tüm Zamanlar":
            active_sayim = active_sayim[active_sayim["Tarih"] == f_tarih]

        if not active_sayim.empty:
            active_sayim['Miktar'] = pd.to_numeric(active_sayim['Miktar'], errors='coerce').fillna(0)
            sayim_ozet = active_sayim.groupby(['Adres', 'Kod'])['Miktar'].sum().reset_index()
            sayim_ozet.columns = ["Adres", "Kod", "Sayılan_Miktar"]
        else:
            sayim_ozet = pd.DataFrame(columns=["Adres", "Kod", "Sayılan_Miktar"])

        # Birleştirme
        final_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Kod'], how='outer').fillna(0)
        final_df['FARK'] = final_df['Sayılan_Miktar'] - final_df['Sistem_Miktarı']

        # Multi-seçim filtreleri
        if f_kod: final_df = final_df[final_df["Kod"].isin(f_kod)]
        if f_ad: final_df = final_df[final_df["Ürün Adı"].isin(f_ad)]
        if f_adr: final_df = final_df[final_df["Adres"].isin(f_adr)]

        # Tabloyu Renklendirerek Göster
        def style_fark(v):
            if v < 0: return 'background-color: #ffcccc; color: red'
            if v > 0: return 'background-color: #ccffcc; color: green'
            return ''

        st.dataframe(final_df.style.map(style_fark, subset=['FARK']), use_container_width=True)

        # Alt Toplam Metrikleri
        m1, m2, m3 = st.columns(3)
        m1.metric("Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
