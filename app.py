import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Sayfa Genişlik Ayarı
st.set_page_config(page_title="BRN Depo Sayım v1.0", layout="wide")

# --- 1. VERİTABANI BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Ana verileri başlangıçta bir kez çekiyoruz
    df_hareketler = conn.read(worksheet="HAREKETLER", ttl=0)
    df_stok_ana = conn.read(worksheet="Stok", ttl=0)
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası! Lütfen Secrets ve Excel ayarlarını kontrol et. Hata: {e}")
    st.stop()

# --- 2. GİRİŞ (LOGIN) SİSTEMİ ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 BRN Depo Sistemi Giriş")
    with st.container():
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

# --- 3. ANA UYGULAMA ARAYÜZÜ ---
st.sidebar.info(f"👤 Personel: {st.session_state['user_name']}")
if st.sidebar.button("Güvenli Çıkış"):
    st.session_state['logged_in'] = False
    st.rerun()

st.title("🔢 Depo Sayım ve Envanter Kontrolü")

# Sekmeleri oluşturuyoruz
tab1, tab2 = st.tabs(["📝 Sayım Girişi", "📊 Stok Karşılaştırma Raporu"])

# --- TAB 1: SAYIM GİRİŞ EKRANI ---
with tab1:
    st.subheader("Yeni Sayım Verisi Gir")
    with st.form("sayim_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            s_adres = st.text_input("📍 Sayım Yapılan Adres").upper()
            s_kod = st.text_input("📦 Malzeme Kodu").upper()
        with c2:
            s_miktar = st.number_input("⚖️ Raf Miktarı (Fiili)", min_value=0.0, step=1.0)
            s_birim = st.selectbox("📏 Birim", ["ADET", "KG", "MT", "PAKET"])
        
        submit = st.form_submit_button("💾 Sayımı Sisteme Kaydet")
        
        if submit:
            if s_adres and s_kod and s_miktar >= 0:
                try:
                    # Mevcut sayımları çek
                    df_sayim_mevcut = conn.read(worksheet="sayim", ttl=0)
                    
                    # Yeni satırı hazırla
                    yeni_veri = pd.DataFrame({
                        "Tarih": [datetime.now().strftime("%d.%m.%Y %H:%M")],
                        "Personel": [st.session_state['user_name']],
                        "Adres": [s_adres],
                        "Malzeme Kodu": [s_kod],
                        "Miktar": [s_miktar],
                        "Birim": [s_birim]
                    })
                    
                    # Birleştir ve Guncelle
                    df_sayim_son = pd.concat([df_sayim_mevcut, yeni_veri], ignore_index=True)
                    conn.update(worksheet="sayim", data=df_sayim_son)
                    st.success(f"✅ {s_kod} ürünü {s_adres} adresi için başarıyla kaydedildi.")
                except Exception as e:
                    st.error(f"Kayıt sırasında hata oluştu: {e}")
            else:
                st.warning("⚠️ Lütfen tüm alanları (Adres ve Kod) eksiksiz doldurun!")

# --- TAB 2: HİZALANMIŞ RAPORLAMA EKRANI ---
with tab2:
    st.subheader("🔍 Stok vs Sayım Karşılaştırması")
    if st.button("🔄 Raporu Güncelle ve Hesapla"):
        try:
            # 1. Sistem Stoğunu (stok sekmesi) Hazırla
            if df_stok_ana.empty:
                st.warning("Sistem stoğu ('stok' sekmesi) boş görünüyor.")
            else:
                sistem = df_stok_ana[['Adres', 'Malzeme Kodu', 'Miktar']].copy()
                sistem['Miktar'] = pd.to_numeric(sistem['Miktar'], errors='coerce').fillna(0)
                sistem.columns = ["Adres", "Malzeme Kodu", "Sistem_Miktarı"]

                # 2. Sayım Verilerini (sayim sekmesi) Hazırla ve Grupla
                df_sayim_raw = conn.read(worksheet="sayim", ttl=0)
                if not df_sayim_raw.empty:
                    df_sayim_raw['Miktar'] = pd.to_numeric(df_sayim_raw['Miktar'], errors='coerce').fillna(0)
                    sayim_ozet = df_sayim_raw.groupby(['Adres', 'Malzeme Kodu'])['Miktar'].sum().reset_index()
                    sayim_ozet.columns = ["Adres", "Malzeme Kodu", "Sayılan_Miktar"]
                else:
                    sayim_ozet = pd.DataFrame(columns=["Adres", "Malzeme Kodu", "Sayılan_Miktar"])

                # 3. İki Dünyayı Birleştir (Hizala)
                rapor_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Malzeme Kodu'], how='outer').fillna(0)
                
                # 4. Fark Hesapla
                rapor_df['FARK'] = rapor_df['Sayılan_Miktar'] - rapor_df['Sistem_Miktarı']

                # 5. Görselleştirme
                def style_fark(val):
                    if val < 0: return 'color: red; font-weight: bold'
                    if val > 0: return 'color: green; font-weight: bold'
                    return 'color: gray'

                st.dataframe(
                    rapor_df.style.applymap(style_fark, subset=['FARK']),
                    use_container_width=True
                )

                # Özet Kartları
                c1, c2, c3 = st.columns(3)
                c1.metric("Sistem Toplamı", f"{rapor_df['Sistem_Miktarı'].sum():,.0f}")
                c2.metric("Sayılan Toplam", f"{rapor_df['Sayılan_Miktar'].sum():,.0f}")
                fark_toplam = rapor_df['FARK'].sum()
                c3.metric("Net Fark", f"{fark_toplam:,.0f}", delta=float(fark_toplam))

        except Exception as e:
            st.error(f"Rapor oluşturulurken bir hata meydana geldi: {e}")
