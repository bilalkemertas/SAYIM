import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Ayarları
st.set_page_config(page_title="BRN Depo Sayım v2.3", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_Stok_ana = conn.read(worksheet="Stok", ttl=0)
    
    # Veri Temizliği
    df_Stok_ana = df_Stok_ana.dropna(subset=["Kod", "İsim"])
    df_Stok_ana["Kod"] = df_Stok_ana["Kod"].astype(str).str.strip()
    
    # Sözlükler
    kod_isim_dict = pd.Series(df_Stok_ana.İsim.values, index=df_Stok_ana.Kod).to_dict()
    kod_listesi = sorted(list(kod_isim_dict.keys()))
    ad_listesi = sorted(df_Stok_ana["İsim"].unique().tolist())
    
    # Standart Durum Listesi
    durum_opsiyonlari = ["Kullanılabilir", "Hasarlı", "Kayıp", "İncelemede"]
    
except Exception as e:
    st.error(f"Bağlantı hatası! Hata: {e}")
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

st.title("🚀 Gelişmiş Sayım ve Durum Takibi")

tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Sayım Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI ---
with tab1:
    st.subheader("📍 Yeni Veri Girişi")
    
    with st.container(border=True):
        # Durum sütunu için genişliği ayarladık
        col_adr, col_kod, col_isim, col_mik, col_durum = st.columns([1, 1.2, 1.8, 0.8, 1.2])
        
        with col_adr:
            s_adres = st.text_input("📍 Adres", key="adr_box").upper()
        with col_kod:
            s_Kod = st.selectbox("📦 Ürün Kodu", [""] + kod_listesi, key="kod_box")
        with col_isim:
            current_name = kod_isim_dict.get(str(s_Kod), "")
            st.text_input("📝 Ürün Adı", value=current_name, disabled=True)
        with col_mik:
            s_miktar = st.number_input("⚖️ Miktar", min_value=0.0, step=1.0, key="mik_box")
        with col_durum:
            s_durum = st.selectbox("🛠️ Ürün Durumu", durum_opsiyonlari, key="durum_box")
        
        if st.button("➕ Listeye Ekle", use_container_width=True):
            if s_adres and s_Kod:
                st.session_state['gecici_sayim_listesi'].append({
                    "Tarih": datetime.now().strftime("%d.%m.%Y"),
                    "Personel": st.session_state['user_name'],
                    "Adres": s_adres,
                    "Kod": s_Kod,
                    "Ürün Adı": current_name,
                    "Miktar": s_miktar,
                    "Durum": s_durum
                })
                st.toast(f"{s_Kod} ({s_durum}) eklendi.")
            else:
                st.warning("Adres ve Kod alanları zorunludur!")

    # --- DİNAMİK SİLİNEBİLİR LİSTE ---
    if st.session_state['gecici_sayim_listesi']:
        st.write("---")
        st.markdown("### 📥 Onay Bekleyen Sayımlar")
        
        # Başlıklar
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1, 1, 1.5, 0.8, 1.2, 0.5])
        h_col1.caption("📍 Adres")
        h_col2.caption("📦 Kod")
        h_col3.caption("📝 Ürün Adı")
        h_col4.caption("⚖️ Miktar")
        h_col5.caption("🛠️ Durum")
        h_col6.caption("❌")

        for index, item in enumerate(st.session_state['gecici_sayim_listesi']):
            r_col1, r_col2, r_col3, r_col4, r_col5, r_col6 = st.columns([1, 1, 1.5, 0.8, 1.2, 0.5])
            r_col1.write(item["Adres"])
            r_col2.write(item["Kod"])
            r_col3.write(item["Ürün Adı"])
            r_col4.write(f"{item['Miktar']:,.0f}")
            # Duruma göre renkli vurgu yapabiliriz
            status_color = "🔴" if item["Durum"] == "Hasarlı" else "🟢"
            r_col5.write(f"{status_color} {item['Durum']}")
            
            if r_col6.button("🗑️", key=f"del_{index}"):
                st.session_state['gecici_sayim_listesi'].pop(index)
                st.rerun()

        st.write("---")
        c_onay, c_iptal = st.columns(2)
        if c_onay.button("📤 DRIVE'A GÖNDER VE KAYDET", type="primary", use_container_width=True):
            try:
                df_gecici = pd.DataFrame(st.session_state['gecici_sayim_listesi'])
                df_db = conn.read(worksheet="sayim", ttl=0)
                df_son = pd.concat([df_db, df_gecici], ignore_index=True)
                conn.update(worksheet="sayim", data=df_son)
                st.session_state['gecici_sayim_listesi'] = []
                st.success("Tüm veriler durum bilgisiyle beraber kaydedildi!")
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")
        
        if c_iptal.button("⚠️ Tüm Listeyi Boşalt", use_container_width=True):
            st.session_state['gecici_sayim_listesi'] = []
            st.rerun()

# --- TAB 2: DURUM BAZLI RAPOR EKRANI ---
with tab2:
    st.subheader("🔍 Sayım ve Durum Analizi")
    try:
        df_sayim_db = conn.read(worksheet="sayim", ttl=0)
        
        if not df_sayim_db.empty:
            df_sayim_db["Tarih"] = df_sayim_db["Tarih"].astype(str).str[:10]
        
        sistem = df_Stok_ana[['Adres', 'Kod', 'İsim', 'Miktar']].copy()
        sistem.columns = ["Adres", "Kod", "Ürün Adı", "Sistem_Miktarı"]
        
        with st.expander("🛠️ Filtreler", expanded=True):
            f1, f2, f3, f4, f5 = st.columns(5)
            with f1:
                t_list = ["Hepsi"] + sorted(df_sayim_db["Tarih"].unique().tolist(), reverse=True) if not df_sayim_db.empty else ["Hepsi"]
                f_tarih = st.selectbox("📅 Tarih", t_list)
            with f2:
                f_kod = st.multiselect("📦 Kod", kod_listesi)
            with f3:
                f_ad = st.multiselect("📝 Ürün Adı", ad_listesi)
            with f4:
                f_adr = st.multiselect("📍 Adres", sorted(sistem["Adres"].unique().tolist()))
            with f5:
                # Durum filtresi eklendi
                f_durum = st.multiselect("🛠️ Durum", durum_opsiyonlari)

        act_sayim = df_sayim_db.copy()
        if f_tarih != "Hepsi":
            act_sayim = act_sayim[act_sayim["Tarih"] == f_tarih]
        if f_durum:
            act_sayim = act_sayim[act_sayim["Durum"].isin(f_durum)]

        if not act_sayim.empty:
            act_sayim['Miktar'] = pd.to_numeric(act_sayim['Miktar'], errors='coerce').fillna(0)
            # Raporu Duruma göre grupluyoruz ki sağlam ve hasarlı miktarlar ayrı görünsün
            s_ozet = act_sayim.groupby(['Adres', 'Kod', 'Durum'])['Miktar'].sum().reset_index()
            s_ozet.columns = ["Adres", "Kod", "Durum", "Sayılan_Miktar"]
        else:
            s_ozet = pd.DataFrame(columns=["Adres", "Kod", "Durum", "Sayılan_Miktar"])

        # Karşılaştırma (Sistem stoğu genellikle durumu bilmez, o yüzden outer join yapıyoruz)
        final_df = pd.merge(sistem, s_ozet, on=['Adres', 'Kod'], how='outer').fillna({"Sayılan_Miktar": 0, "Sistem_Miktarı": 0, "Durum": "Sayılmadı"})
        
        # Fark hesaplama (Sadece Kullanılabilir olanları sistemle kıyaslamak mantıklı olabilir ama biz genel farkı gösteriyoruz)
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
        m1.metric("Toplam Sistem", f"{final_df['Sistem_Miktarı'].sum():,.0f}")
        m2.metric("Toplam Sayılan", f"{final_df['Sayılan_Miktar'].sum():,.0f}")
        m3.metric("Toplam Fark", f"{final_df['FARK'].sum():,.0f}", delta=int(final_df['FARK'].sum()))

    except Exception as e:
        st.error(f"Rapor hatası: {e}")
