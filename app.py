with tab2:
    if st.button("Raporu Hesapla"):
        try:
            # 1. "stok" sekmesini oku (Sistem verisi)
            df_sistem_stok = conn.read(worksheet="stok", ttl=0)
            
            # 2. "sayim" sekmesini oku (Personel verisi)
            df_sayim_verisi = conn.read(worksheet="sayim", ttl=0)

            if df_sistem_stok.empty:
                st.warning("⚠️ 'stok' sekmesinde sistem verisi bulunamadı.")
            else:
                # Sistem stoğunu hazırla
                sistem = df_sistem_stok[['Adres', 'Malzeme Kodu', 'Miktar']].copy()
                sistem['Miktar'] = pd.to_numeric(sistem['Miktar'], errors='coerce').fillna(0)
                sistem.columns = ["Adres", "Malzeme Kodu", "Sistem_Miktarı"]

                # Sayım stoğunu toplayarak hazırla (Aynı adreste aynı üründen birden fazla kayıt olabilir)
                if not df_sayim_verisi.empty:
                    df_sayim_verisi['Miktar'] = pd.to_numeric(df_sayim_verisi['Miktar'], errors='coerce').fillna(0)
                    sayim_ozet = df_sayim_verisi.groupby(['Adres', 'Malzeme Kodu'])['Miktar'].sum().reset_index()
                    sayim_ozet.columns = ["Adres", "Malzeme Kodu", "Sayılan_Miktar"]
                else:
                    sayim_ozet = pd.DataFrame(columns=["Adres", "Malzeme Kodu", "Sayılan_Miktar"])

                # --- KARŞILAŞTIRMA ---
                # Hem sistemde hem sayımda olanları birleştir
                fark_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Malzeme Kodu'], how='outer').fillna(0)
                
                # Farkı hesapla
                fark_df['FARK'] = fark_df['Sayılan_Miktar'] - fark_df['Sistem_Miktarı']

                st.write("### 🔍 Stok & Sayım Karşılaştırma Raporu")
                
                # Renklendirme fonksiyonu (Fark varsa kırmızı/yeşil gösterir)
                def color_fark(val):
                    color = 'red' if val < 0 else ('green' if val > 0 else 'black')
                    return f'color: {color}'

                st.dataframe(fark_df.style.applymap(color_fark, subset=['FARK']), use_container_width=True)
                
        except Exception as e:
            st.error(f"Rapor hazırlanırken bir hata oluştu: {e}")
