import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io

# Sayfa Yapılandırması (Mobil Uyumlu Arayüz)
st.set_page_config(
    page_title="Nöbet Dağıtım Sistemi",
    page_icon="📅",
    layout="wide"
)

st.title("📅 Otomatik Nöbet Dağıtım Sistemi")
st.caption("Google OR-Tools Yapay Zeka Çözücüsü Destekli")

# ==========================================
# GİRDİ ALANLARI (YAN PANEL / SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Genel Ayarlar")

# Personel Listesi
personel_metni = st.sidebar.text_area(
    "Personel İsimleri (Her satıra bir isim)",
    value="Ali\nAyşe\nMehmet\nFatma\nCan\nZeynep",
    height=150
)
personel_listesi = [p.strip() for p in personel_metni.split("\n") if p.strip()]

# Gün Sayısı
gun_sayisi = st.sidebar.number_input("Kaç Günlük Nöbet Yazılacak?", min_value=7, max_value=60, value=30)

# Resmi Tatiller
resmi_tatil_str = st.sidebar.text_input("Resmi Tatil / Bayram Günleri (Örn: 10, 11, 23)", value="10, 11, 23")
resmi_tatiller = []
if resmi_tatil_str:
    try:
        resmi_tatiller = [int(g.strip()) - 1 for g in resmi_tatil_str.split(",") if g.strip().isdigit()]
    except:
        st.sidebar.error("Tatil günlerini geçerli sayılar olarak girin.")

# ==========================================
# İZİN VE MAZERET SEÇİMİ
# ==========================================
st.header("1. Personel İzin Günleri")
st.info("Her personel için izinli veya mazeretli olduğu günleri seçin.")

izinler = {}
gun_secenekleri = list(range(1, gun_sayisi + 1))

cols = st.columns(min(len(personel_listesi), 3) if personel_listesi else 1)
for i, isim in enumerate(personel_listesi):
    col = cols[i % 3]
    with col:
        secilen_gunler = st.multiselect(
            f"👤 {isim} İzin Günleri:",
            options=gun_secenekleri,
            key=f"izin_{isim}"
        )
        izinler[isim] = [g - 1 for g in secilen_gunler]

# ==========================================
# ÇÖZÜCÜ FONKSİYONU
# ==========================================
def nobet_hesapla(personel, gun_sayisi, izinler, resmi_tatiller):
    num_personel = len(personel)
    tum_personeller = range(num_personel)
    tum_gunler = range(gun_sayisi)
    toplam_hafta = (gun_sayisi + 6) // 7

    persembe_gunleri  = [g for g in tum_gunler if g % 7 == 3]
    cuma_gunleri      = [g for g in tum_gunler if g % 7 == 4]
    cumartesi_gunleri = [g for g in tum_gunler if g % 7 == 5]
    pazar_gunleri     = [g for g in tum_gunler if g % 7 == 6]

    model = cp_model.CpModel()
    nobet = {}
    for p in tum_personeller:
        for g in tum_gunler:
            nobet[(p, g)] = model.NewBoolVar(f'nobet_p{p}_g{g}')

    # Kısıt 1: Her gün 1 nöbetçi
    for g in tum_gunler:
        model.AddExactlyOne(nobet[(p, g)] for p in tum_personeller)

    # Kısıt 2: Üst üste nöbet yasak
    for p in tum_personeller:
        for g in range(gun_sayisi - 1):
            model.AddImplication(nobet[(p, g)], nobet[(p, g + 1)].Not())

    # Kısıt 3: İzinler
    for p, isim in enumerate(personel):
        for g_indeks in izinler.get(isim, []):
            if 0 <= g_indeks < gun_sayisi:
                model.Add(nobet[(p, g_indeks)] == 0)

    # Kısıt 4: Çapraz Hafta (Aynı hafta Per-Cmt veya Cum-Paz yasak)
    for h in range(toplam_hafta):
        per, cum, cmt, paz = h * 7 + 3, h * 7 + 4, h * 7 + 5, h * 7 + 6
        for p in tum_personeller:
            if per < gun_sayisi and cmt < gun_sayisi:
                model.Add(nobet[(p, per)] + nobet[(p, cmt)] <= 1)
            if cum < gun_sayisi and paz < gun_sayisi:
                model.Add(nobet[(p, cum)] + nobet[(p, paz)] <= 1)

    # Kısıt 5: Eşitlik / Adalet
    min_toplam = gun_sayisi // num_personel
    max_toplam = min_toplam + 1
    for p in tum_personeller:
        model.AddLinearConstraint(sum(nobet[(p, g)] for g in tum_gunler), min_toplam, max_toplam)

        toplam_per = sum(nobet[(p, g)] for g in persembe_gunleri)
        toplam_cmt = sum(nobet[(p, g)] for g in cumartesi_gunleri)
        toplam_cum = sum(nobet[(p, g)] for g in cuma_gunleri)
        toplam_paz = sum(nobet[(p, g)] for g in pazar_gunleri)
        
        model.Add(toplam_per - toplam_cmt <= 1)
        model.Add(toplam_cmt - toplam_per <= 1)
        model.Add(toplam_cum - toplam_paz <= 1)
        model.Add(toplam_paz - toplam_cum <= 1)

    if resmi_tatiller:
        min_tatil = len(resmi_tatiller) // num_personel
        max_tatil = min_tatil + 1
        for p in tum_personeller:
            model.AddLinearConstraint(sum(nobet[(p, g)] for g in resmi_tatiller), min_tatil, max_tatil)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        gun_isimleri = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        liste_data = []
        
        for g in tum_gunler:
            gun_adi = gun_isimleri[g % 7]
            tatil_durumu = "Resmi Tatil / Bayram" if g in resmi_tatiller else ("Hafta Sonu" if g % 7 in [5, 6] else "Hafta İçi")
            nobetci_isim = ""
            for p in tum_personeller:
                if solver.Value(nobet[(p, g)]):
                    nobetci_isim = personel[p]
                    break
            liste_data.append({
                "Gün No": g + 1,
                "Gün Adı": gun_adi,
                "Kategori": tatil_durumu,
                "Nöbetçi Personel": nobetci_isim
            })

        istatistik_data = []
        for p, isim in enumerate(personel):
            tot = sum(solver.Value(nobet[(p, g)]) for g in tum_gunler)
            per = sum(solver.Value(nobet[(p, g)]) for g in persembe_gunleri)
            cmt = sum(solver.Value(nobet[(p, g)]) for g in cumartesi_gunleri)
            cum = sum(solver.Value(nobet[(p, g)]) for g in cuma_gunleri)
            paz = sum(solver.Value(nobet[(p, g)]) for g in pazar_gunleri)
            tat = sum(solver.Value(nobet[(p, g)]) for g in resmi_tatiller) if resmi_tatiller else 0
            
            istatistik_data.append({
                "Personel": isim,
                "Toplam Nöbet": tot,
                "Perşembe": per,
                "Cumartesi": cmt,
                "Cuma": cum,
                "Pazar": paz,
                "Bayram/Tatil": tat
            })

        return pd.DataFrame(liste_data), pd.DataFrame(istatistik_data)
    else:
        return None, None

# ==========================================
# NÖBET OLUŞTURMA VE SONUÇ
# ==========================================
st.divider()

if st.button("🚀 Nöbet Listesini Oluştur", type="primary", use_container_width=True):
    if len(personel_listesi) < 2:
        st.error("Lütfen en az 2 personel girin.")
    else:
        with st.spinner("Yapay zeka kurallara en uygun dağıtımı hesaplıyor..."):
            df_liste, df_stats = nobet_hesapla(personel_listesi, gun_sayisi, izinler, resmi_tatiller)

        if df_liste is not None:
            st.success("✅ Nöbet listesi başarıyla oluşturuldu!")
            
            tab1, tab2 = st.tabs(["📋 Nöbet Listesi", "📊 Adalet İstatistikleri"])
            
            with tab1:
                st.dataframe(df_liste, use_container_width=True, hide_index=True)
            
            with tab2:
                st.dataframe(df_stats, use_container_width=True, hide_index=True)

            # Excel İndirme
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_liste.to_excel(writer, sheet_name='Nöbet Listesi', index=False)
                df_stats.to_excel(writer, sheet_name='İstatistikler', index=False)
            
            st.download_button(
                label="📥 Excel Dosyası Olarak İndir (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name="nobet_listesi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.error("❌ Belirtilen izinler ve kurallar altında geçerli bir nöbet listesi dağıtılamadı! Lütfen çakışan izinleri azaltıp tekrar deneyin.")

