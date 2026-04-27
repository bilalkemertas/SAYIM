with tab2:
    if st.button("Raporu Hesapla"):
        try:
            # 1. Verileri Oku
            # "stok" sekmesi bizim sistem referansımız
            df_stok_sekmesi = conn.read(worksheet="stok", ttl=0)
            # "sayim" sekmesi personelin terminalden girdiği veriler
            df_sayim_sekmesi = conn.read(worksheet="sayim", ttl=0)

            if df_stok_sekmesi.empty:
                st.warning("⚠️ 'stok' sekmesinde hiç veri bulunamadı. Lütfen önce sistem stoğunu kontrol edin.")
            else:
                # 2. Sistem Stoğunu Hazırla
                # Sütun isimlerinin Adres, Malzeme Kodu ve Miktar olduğundan emin oluyoruz
                sistem = df_stok_sekmesi[['Adres', 'Malzeme Kodu', 'Miktar']].copy()
                sistem['Miktar'] = pd.to_numeric(sistem['Miktar'], errors='coerce').fillna(0)
                sistem.columns = ["Adres", "Malzeme Kodu", "Sistem_Miktarı"]

                # 3. Sayım Verilerini Hazırla (Aynı ürünü farklı zamanlarda saymış olabilirler, topluyoruz)
                if not df_sayim_sekmesi.empty:
                    df_sayim_verisi = df_sayim_sekmesi.copy()
                    df_sayim_verisi['Miktar'] = pd.to_numeric(df_sayim_verisi['Miktar'], errors='coerce').fillna(0)
                    sayim_ozet = df_sayim_verisi.groupby(['Adres', 'Malzeme Kodu'])['Miktar'].sum().reset_index()
                    sayim_ozet.columns = ["Adres", "Malzeme Kodu", "Sayılan_Miktar"]
                else:
                    sayim_ozet = pd.DataFrame(columns=["Adres", "Malzeme Kodu", "Sayılan_Miktar"])

                # 4. İki Tabloyu Eşleştir (Hizala)
                # 'how=outer' kullanıyoruz ki sistemde olup sayılmayan veya tam tersi durumlar kaçmasın
                fark_df = pd.merge(sistem, sayim_ozet, on=['Adres', 'Malzeme Kodu'], how='outer').fillna(0)
                
                # 5. Farkı Hesapla
                fark_df['FARK'] = fark_df['Sayılan_Miktar'] - fark_df['Sistem_Miktarı']

                st.write("### 📊 Sayım Fark Raporu (Stok vs Sayım)")
                
                # Görselleştirme: Farklı olanları renklendirerek dikkat çekelim
                def color_fark(val):
                    if val < 0: return 'background-color: #ffcccc; color: red' # Eksik
                    if val > 0: return 'background-color: #ccffcc; color: green' # Fazla
                    return ''

                st.dataframe(
                    fark_df.style.applymap(color_fark, subset=['FARK']), 
                    use_container_width=True
                )
                
                # Özet Bilgi
                toplam_eksik = fark_df[fark_df['FARK'] < 0]['FARK'].sum()
                toplam_fazla = fark_df[fark_df['FARK'] > 0]['FARK'].sum()
                
                c1, c2 = st.columns(2)
                c1.metric("Toplam Eksik", f"{toplam_eksik:,.2f}")
                c2.metric("Toplam Fazla", f"{toplam_fazla:,.2f}")

        except Exception as e:
            st.error(f"Rapor hizalanırken hata oluştu: {e}")
