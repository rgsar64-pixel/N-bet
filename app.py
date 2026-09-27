import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
from datetime import datetime, timedelta
import holidays

# Sayfa Yapılandırması
st.set_page_config(
    page_title="Yıllık Nöbet Dağıtım Sistemi",
    page_icon="📅",
    layout="wide"
)

st.title("📅 Yıllık Otomatik Nöbet Dağıtım Sistemi")
st.caption("Google OR-Tools Yapay Zeka Çözücüsü ve Otomatik Türkiye Tatil Takvimi Entegrasyonlu")

# ==========================================
# 1. BÖLÜM: GENEL AYARLAR VE OTOMATİK TATİLLER
# ==========================================
st.header("1. Genel Bilgiler ve Başlangıç Tarihi")

col1, col2 = st.columns(2)

with col1:
    personel_metni = st.text_area(
        "Personel İsimleri (Her satıra bir isim):",
        value="Ali\nAyşe\nMehmet\nFatma\nCan\nZeynep\nMustafa\nElif",
        height=180
    )
    personel_listesi = [p.strip() for p in personel_metni.split("\n") if p.strip()]

with col2:
    baslangic_tarihi = st.date_input(
        "Nöbet Başlangıç Tarihi:",
        value=datetime(2026, 1, 1).date()
    )
    toplam_gun = st.number_input(
        "Kaç Günlük Planlama Yapılacak?",
        min_value=30,
        max_value=366,
        value=365,
        step=1,
        help="Tam 1 yıl için 365 gün seçebilirsiniz."
    )
    bitis_tarihi = baslangic_tarihi + timedelta(days=toplam_gun - 1)

# Otomatik Türkiye Tatil Takvimi Hesabı
def turkiye_tatillerini_getir(baslangic, bitis):
    yillar = list(range(baslangic.year, bitis.year + 1))
    tr_holidays = holidays.TR(years=yillar)
    
    otomatik_dict = {}
    for dt, name in sorted(tr_holidays.items()):
        if baslangic <= dt <= bitis:
            otomatik_dict[dt] = name
    return otomatik_dict

otomatik_tatil_haritasi = turkiye_tatillerini_getir(baslangic_tarihi, bitis_tarihi)
tum_tarihler_listesi = [baslangic_tarihi + timedelta(days=i) for i in range(toplam_gun)]

st.subheader("🇹🇷 Otomatik Tespit Edilen Resmi Tatiller ve Bayramlar")
resmi_tatiller_secim = st.multiselect(
    "Sistem tarafından otomatik tespit edilen bayramlar (Gerekirse ekleme/çıkarma yapabilirsiniz):",
    options=tum_tarihler_listesi,
    default=list(otomatik_tatil_haritasi.keys()),
    format_func=lambda d: f"{d.strftime('%d.%m.%Y')} - {otomatik_tatil_haritasi.get(d, 'Özel Tatil')} ({d.strftime('%A')})"
)
resmi_tatil_set = set(resmi_tatiller_secim)

# ==========================================
# 2. BÖLÜM: PERSONEL İZİNLERİ
# ==========================================
st.divider()
st.header("2. Yıllık İzin ve Mazeret Tarihleri")
st.info("Her personel için yıl içinde nöbet tutamayacağı tarihleri takvimden seçin.")

izinler = {}

cols = st.columns(min(len(personel_listesi), 2) if personel_listesi else 1)
for i, isim in enumerate(personel_listesi):
    col = cols[i % 2]
    with col:
        secilen_tarihler = st.multiselect(
            f"👤 {isim} İzinli Tarihler:",
            options=tum_tarihler_listesi,
            format_func=lambda x: x.strftime("%d.%m.%Y (%a)"),
            key=f"izin_{isim}"
        )
        izinler[isim] = [(t - baslangic_tarihi).days for t in secilen_tarihler]

# ==========================================
# 3. BÖLÜM: YILLIK YAPAY ZEKA ÇÖZÜCÜSÜ
# ==========================================
def yillik_nobet_hesapla(personel, baslangic_dt, toplam_gun, izinler, tatiller_set):
    num_personel = len(personel)
    tum_personeller = range(num_personel)
    tum_gunler = range(toplam_gun)

    tarih_listesi = [baslangic_dt + timedelta(days=g) for g in tum_gunler]
    
    aylik_gunler = {}
    hafta_sonu_gunleri = []
    bayram_gunleri = []
    persembe_gunleri = []
    cuma_gunleri = []
    cumartesi_gunleri = []
    pazar_gunleri = []

    for g, dt in enumerate(tarih_listesi):
        m_key = (dt.year, dt.month)
        if m_key not in aylik_gunler:
            aylik_gunler[m_key] = []
        aylik_gunler[m_key].append(g)

        w = dt.weekday()
        if w == 3: persembe_gunleri.append(g)
        elif w == 4: cuma_gunleri.append(g)
        elif w == 5: cumartesi_gunleri.append(g)
        elif w == 6: pazar_gunleri.append(g)

        if w in [5, 6]:
            hafta_sonu_gunleri.append(g)
        if dt in tatiller_set:
            bayram_gunleri.append(g)

    model = cp_model.CpModel()
    nobet = {}
    for p in tum_personeller:
        for g in tum_gunler:
            nobet[(p, g)] = model.NewBoolVar(f'nobet_p{p}_g{g}')

    # Kısıtlar
    for g in tum_gunler:
        model.AddExactlyOne(nobet[(p, g)] for p in tum_personeller)

    for p in tum_personeller:
        for g in range(toplam_gun - 1):
            model.AddImplication(nobet[(p, g)], nobet[(p, g + 1)].Not())

    for p, isim in enumerate(personel):
        for g_indeks in izinler.get(isim, []):
            if 0 <= g_indeks < toplam_gun:
                model.Add(nobet[(p, g_indeks)] == 0)

    toplam_hafta = (toplam_gun + 6) // 7
    for h in range(toplam_hafta):
        per, cum, cmt, paz = h * 7 + 3, h * 7 + 4, h * 7 + 5, h * 7 + 6
        for p in tum_personeller:
            if per < toplam_gun and cmt < toplam_gun:
                model.Add(nobet[(p, per)] + nobet[(p, cmt)] <= 1)
            if cum < toplam_gun and paz < toplam_gun:
                model.Add(nobet[(p, cum)] + nobet[(p, paz)] <= 1)

    # Yıllık Eşitlik
    min_yillik = toplam_gun // num_personel
    max_yillik = min_yillik + 1
    for p in tum_personeller:
        model.AddLinearConstraint(sum(nobet[(p, g)] for g in tum_gunler), min_yillik, max_yillik)

    # Aylık Denge
    for m_key, g_list in aylik_gunler.items():
        gun_sayisi_ay = len(g_list)
        min_aylik = gun_sayisi_ay // num_personel
        max_aylik = min_aylik + 1
        for p in tum_personeller:
            model.AddLinearConstraint(sum(nobet[(p, g)] for g in g_list), min_aylik, max_aylik)

    # Hafta Sonu Eşitliği
    min_hs = len(hafta_sonu_gunleri) // num_personel
    max_hs = min_hs + 1
    for p in tum_personeller:
        model.AddLinearConstraint(sum(nobet[(p, g)] for g in hafta_sonu_gunleri), min_hs, max_hs)

    # Bayram Eşitliği
    if bayram_gunleri:
        min_bayram = len(bayram_gunleri) // num_personel
        max_bayram = min_bayram + 1
        for p in tum_personeller:
            model.AddLinearConstraint(sum(nobet[(p, g)] for g in bayram_gunleri), min_bayram, max_bayram)

    # Gün Çiftleri Dengesi
    for p in tum_personeller:
        toplam_per = sum(nobet[(p, g)] for g in persembe_gunleri)
        toplam_cmt = sum(nobet[(p, g)] for g in cumartesi_gunleri)
        toplam_cum = sum(nobet[(p, g)] for g in cuma_gunleri)
        toplam_paz = sum(nobet[(p, g)] for g in pazar_gunleri)

        model.Add(toplam_per - toplam_cmt <= 1)
        model.Add(toplam_cmt - toplam_per <= 1)
        model.Add(toplam_cum - toplam_paz <= 1)
        model.Add(toplam_paz - toplam_cum <= 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        gun_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        liste_data = []

        for g in tum_gunler:
            dt = tarih_listesi[g]
            gun_adi = gun_tr[dt.weekday()]
            
            kategori = "Hafta İçi"
            if dt in tatiller_set:
                tatil_adi = otomatik_tatil_haritasi.get(dt, "Resmi Tatil / Bayram")
                kategori = f"🎉 {tatil_adi}"
            elif dt.weekday() in [5, 6]:
                kategori = "Hafta Sonu"

            nobetci = ""
            for p in tum_personeller:
                if solver.Value(nobet[(p, g)]):
                    nobetci = personel[p]
                    break

            liste_data.append({
                "Tarih": dt.strftime("%Y-%m-%d"),
                "Yıl-Ay": dt.strftime("%Y-%m"),
                "Gün": dt.strftime("%d"),
                "Gün Adı": gun_adi,
                "Kategori": kategori,
                "Nöbetçi Personel": nobetci
            })

        istatistik_data = []
        for p, isim in enumerate(personel):
            tot = sum(solver.Value(nobet[(p, g)]) for g in tum_gunler)
            hs = sum(solver.Value(nobet[(p, g)]) for g in hafta_sonu_gunleri)
            bay = sum(solver.Value(nobet[(p, g)]) for g in bayram_gunleri) if bayram_gunleri else 0
            per = sum(solver.Value(nobet[(p, g)]) for g in persembe_gunleri)
            cmt = sum(solver.Value(nobet[(p, g)]) for g in cumartesi_gunleri)
            cum = sum(solver.Value(nobet[(p, g)]) for g in cuma_gunleri)
            paz = sum(solver.Value(nobet[(p, g)]) for g in pazar_gunleri)

            istatistik_data.append({
                "Personel": isim,
                "Yıllık Toplam Nöbet": tot,
                "Hafta Sonu Nöbeti": hs,
                "Bayram/Tatil Nöbeti": bay,
                "Perşembe": per,
                "Cumartesi": cmt,
                "Cuma": cum,
                "Pazar": paz
            })

        return pd.DataFrame(liste_data), pd.DataFrame(istatistik_data)
    else:
        return None, None

# ==========================================
# 4. BÖLÜM: ÇALIŞTIRMA VE RAPORLAMA
# ==========================================
st.divider()

if st.button("🚀 Otomatik Tatilli Yıllık Nöbet Planını Hesapla", type="primary", use_container_width=True):
    if len(personel_listesi) < 2:
        st.error("Lütfen en az 2 personel girin.")
    else:
        with st.spinner("Resmi tatiller, bayramlar ve yıllık adalet dengesi hesaplanıyor..."):
            df_liste, df_stats = yillik_nobet_hesapla(
                personel_listesi, baslangic_tarihi, toplam_gun, izinler, resmi_tatil_set
            )

        if df_liste is not None:
            st.success("✅ Nöbet planı otomatik tatil entegrasyonuyla başarıyla adil bir şekilde dağıtıldı!")

            tab1, tab2, tab3 = st.tabs(["📅 Aylık Görünüm", "📋 Tüm Yıllık Liste", "📊 Yıllık Adalet İstatistikleri"])

            with tab1:
                aylar = df_liste["Yıl-Ay"].unique()
                secilen_ay = st.selectbox("İncelemek İstediğiniz Ayı Seçin:", aylar)
                df_aylik = df_liste[df_liste["Yıl-Ay"] == secilen_ay]
                st.dataframe(df_aylik.drop(columns=["Yıl-Ay"]), use_container_width=True, hide_index=True)

            with tab2:
                st.dataframe(df_liste, use_container_width=True, hide_index=True)

            with tab3:
                st.subheader("1 Yıllık Dağıtım Adalet Tablosu")
                st.dataframe(df_stats, use_container_width=True, hide_index=True)

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_stats.to_excel(writer, sheet_name='Yıllık İstatistikler', index=False)
                df_liste.to_excel(writer, sheet_name='Tüm Yıllık Liste', index=False)
                for ay in df_liste["Yıl-Ay"].unique():
                    df_ay = df_liste[df_liste["Yıl-Ay"] == ay]
                    df_ay.to_excel(writer, sheet_name=f'Ay {ay}', index=False)

            st.download_button(
                label="📥 Tüm Yıllık Nöbet Planını Excel Olarak İndir (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name=f"yillik_nobet_plani_{baslangic_tarihi.year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.error("❌ Belirtilen mazeretler ve kısıtlar altında uygun nöbet listesi bulunamadı. Lütfen çakışan izinleri azaltıp tekrar deneyin.")

