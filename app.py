import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io
import sqlite3
from datetime import datetime, date, timedelta
import calendar
import holidays

# ==========================================
# SAYFA VE VERİ TABANI AYARLARI
# ==========================================
st.set_page_config(
    page_title="Aylık ve Kümilatif Nöbet Sistemi",
    page_icon="📅",
    layout="wide"
)

DB_FILE = "nobet_veritabani.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS nobetler (
                    tarih TEXT PRIMARY KEY,
                    yil_ay TEXT,
                    gun_adi TEXT,
                    kategori TEXT,
                    personel TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS personeller (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isim TEXT UNIQUE
                )''')
    conn.commit()
    conn.close()

init_db()

def db_personel_getir():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS personeller (id INTEGER PRIMARY KEY AUTOINCREMENT, isim TEXT UNIQUE)")
    c.execute("SELECT isim FROM personeller ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    if rows:
        return [r[0] for r in rows]
    return ["Ali", "Ayşe", "Mehmet", "Fatma", "Can", "Zeynep", "Mustafa", "Elif"]

def db_personel_kaydet(personel_listesi):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS personeller (id INTEGER PRIMARY KEY AUTOINCREMENT, isim TEXT UNIQUE)")
    c.execute("DELETE FROM personeller")
    for p in personel_listesi:
        if p.strip():
            c.execute("INSERT OR IGNORE INTO personeller (isim) VALUES (?)", (p.strip(),))
    conn.commit()
    conn.close()

def db_gecmis_nobetleri_getir():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM nobetler", conn)
    conn.close()
    return df

def db_ay_kaydet(df_ay, yil_ay_str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM nobetler WHERE yil_ay = ?", (yil_ay_str,))
    
    for _, row in df_ay.iterrows():
        c.execute('''INSERT OR REPLACE INTO nobetler (tarih, yil_ay, gun_adi, kategori, personel)
                     VALUES (?, ?, ?, ?, ?)''', 
                  (str(row['Tarih']), yil_ay_str, row['Gün Adı'], row['Kategori'], row['Nöbetçi Personel']))
    conn.commit()
    conn.close()

# ==========================================
# ARAYÜZ BAŞLIĞI VE AY SEÇİMİ
# ==========================================
st.title("📅 Aylık Nöbet Dağıtım ve Takip Sistemi")
st.caption("Aylık Manuel Düzenleme, X'li Çizelge Görünümü & Veri Tabanı Destekli Kumülatif Adalet Dengesi")

st.sidebar.header("⚙️ Ay ve Yıl Seçimi")
simdiki_yil = datetime.now().year
secilen_yil = st.sidebar.number_input("Yıl:", min_value=2025, max_value=2030, value=simdiki_yil)

ay_isimleri = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
secilen_ay_adi = st.sidebar.selectbox("Ay:", ay_isimleri, index=datetime.now().month - 1)
secilen_ay_num = ay_isimleri.index(secilen_ay_adi) + 1
yil_ay_key = f"{secilen_yil}-{secilen_ay_num:02d}"

if st.sidebar.button("🗑️ Veri Tabanını Sıfırla (Tüm Geçmişi Sil)"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM nobetler")
    c.execute("DELETE FROM personeller")
    conn.commit()
    conn.close()
    st.sidebar.success("Veri tabanı temizlendi!")
    st.rerun()

# ==========================================
# 1. BÖLÜM: PERSONEL KADROSU
# ==========================================
st.header("1. Personel Kadrosu (Kalıcı Kayıt)")

kayitli_personeller = db_personel_getir()
varsayilan_metin = "\n".join(kayitli_personeller)

col_pers1, col_pers2 = st.columns([3, 1])

with col_pers1:
    personel_metni = st.text_area(
        "Personel İsimleri (Her satıra bir isim):",
        value=varsayilan_metin,
        height=160,
        help="İsimleri girdikten sonra 'Personel Kadrosunu Kaydet' butonuna basarsanız veya nöbet oluşturduğunuzda isimleriniz otomatik saklanır."
    )
    personel_listesi = [p.strip() for p in personel_metni.split("\n") if p.strip()]

with col_pers2:
    st.write(" ")
    st.write(" ")
    if st.button("💾 Personel Kadrosunu Kaydet", use_container_width=True):
        if personel_listesi:
            db_personel_kaydet(personel_listesi)
            st.success("✅ Personel isimleri veri tabanına kaydedildi!")
        else:
            st.error("Lütfen en az bir personel ismi girin.")

df_gecmis_tum = db_gecmis_nobetleri_getir()

# Geçmiş İstatistiklerin Hesaplanması
gecmis_stats = {p: {"toplam": 0, "hs": 0, "bayram": 0, "per": 0, "cmt": 0, "cum": 0, "paz": 0} for p in personel_listesi}

if not df_gecmis_tum.empty:
    for _, row in df_gecmis_tum.iterrows():
        p = row['personel']
        if p in gecmis_stats:
            gecmis_stats[p]["toplam"] += 1
            if "Hafta Sonu" in row['kategori']:
                gecmis_stats[p]["hs"] += 1
            if "🎉" in row['kategori']:
                gecmis_stats[p]["bayram"] += 1
            
            g_adi = row['gun_adi']
            if g_adi == "Perşembe": gecmis_stats[p]["per"] += 1
            elif g_adi == "Cuma": gecmis_stats[p]["cum"] += 1
            elif g_adi == "Cumartesi": gecmis_stats[p]["cmt"] += 1
            elif g_adi == "Pazar": gecmis_stats[p]["paz"] += 1

df_gecmis_ozet = pd.DataFrame([
    {
        "Personel": p,
        "Geçmiş Toplam": stats["toplam"],
        "Geçmiş Hafta Sonu": stats["hs"],
        "Geçmiş Bayram": stats["bayram"],
        "Perşembe": stats["per"],
        "Cumartesi": stats["cmt"],
        "Cuma": stats["cum"],
        "Pazar": stats["paz"]
    }
    for p, stats in gecmis_stats.items()
])

with st.expander("📊 Veri Tabanındaki Geçmiş Toplam Nöbet İstatistikleri (İncelemek için tıklayın)", expanded=False):
    st.dataframe(df_gecmis_ozet, use_container_width=True, hide_index=True)

# ==========================================
# 2. BÖLÜM: SEÇİLEN AYIN DETAYLARI VE İZİNLER
# ==========================================
st.divider()
st.header(f"2. {secilen_ay_adi} {secilen_yil} İzin ve Tatil Takvimi")

_, ay_gun_sayisi = calendar.monthrange(secilen_yil, secilen_ay_num)
ay_baslangic = date(secilen_yil, secilen_ay_num, 1)
ay_bitis = date(secilen_yil, secilen_ay_num, ay_gun_sayisi)
ay_tarihleri = [ay_baslangic + timedelta(days=i) for i in range(ay_gun_sayisi)]

tr_holidays = holidays.TR(years=[secilen_yil])
otomatik_tatil_dict = {dt: name for dt, name in tr_holidays.items() if ay_baslangic <= dt <= ay_bitis}

st.subheader("🇹🇷 Ay İçindeki Resmi Tatiller")
resmi_tatiller_secim = st.multiselect(
    "Resmi Tatil Günleri:",
    options=ay_tarihleri,
    default=list(otomatik_tatil_dict.keys()),
    format_func=lambda d: f"{d.strftime('%d.%m.%Y')} - {otomatik_tatil_dict.get(d, 'Özel Tatil')} ({d.strftime('%A')})"
)
resmi_tatil_set = set(resmi_tatiller_secim)

st.subheader("👤 Personel İzin Günleri")
izinler = {}
cols = st.columns(min(len(personel_listesi), 2) if personel_listesi else 1)
for i, isim in enumerate(personel_listesi):
    col = cols[i % 2]
    with col:
        secilen_tarihler = st.multiselect(
            f"👤 {isim} İzinli Tarihler:",
            options=ay_tarihleri,
            format_func=lambda x: x.strftime("%d %B (%a)"),
            key=f"izin_{secilen_yil}_{secilen_ay_num}_{isim}"
        )
        izinler[isim] = [(t - ay_baslangic).days for t in secilen_tarihler]

# ==========================================
# 3. BÖLÜM: YAPAY ZEKA HESAPLAMA MOTORU
# ==========================================
def aylik_kumulatif_nobet_hesapla(personel, yil, ay, izinler, tatiller_set, gecmis_stats):
    num_personel = len(personel)
    _, gun_sayisi = calendar.monthrange(yil, ay)
    tum_personeller = range(num_personel)
    tum_gunler = range(gun_sayisi)
    
    tarih_listesi = [date(yil, ay, g + 1) for g in tum_gunler]

    hafta_sonu_gunleri, bayram_gunleri = [], []
    persembe_gunleri, cuma_gunleri, cumartesi_gunleri, pazar_gunleri = [], [], [], []

    for g, dt in enumerate(tarih_listesi):
        w = dt.weekday()
        if w == 3: persembe_gunleri.append(g)
        elif w == 4: cuma_gunleri.append(g)
        elif w == 5: cumartesi_gunleri.append(g)
        elif w == 6: pazar_gunleri.append(g)

        if w in [5, 6]: hafta_sonu_gunleri.append(g)
        if dt in tatiller_set: bayram_gunleri.append(g)

    model = cp_model.CpModel()
    nobet = {}
    for p in tum_personeller:
        for g in tum_gunler:
            nobet[(p, g)] = model.NewBoolVar(f'nobet_p{p}_g{g}')

    for g in tum_gunler:
        model.AddExactlyOne(nobet[(p, g)] for p in tum_personeller)

    for p in tum_personeller:
        for g in range(gun_sayisi - 1):
            model.AddImplication(nobet[(p, g)], nobet[(p, g + 1)].Not())

    for p, isim in enumerate(personel):
        for g_indeks in izinler.get(isim, []):
            if 0 <= g_indeks < gun_sayisi:
                model.Add(nobet[(p, g_indeks)] == 0)

    toplam_hafta = (gun_sayisi + 6) // 7
    for h in range(toplam_hafta):
        per, cum, cmt, paz = h * 7 + 3, h * 7 + 4, h * 7 + 5, h * 7 + 6
        for p in tum_personeller:
            if per < gun_sayisi and cmt < gun_sayisi:
                model.Add(nobet[(p, per)] + nobet[(p, cmt)] <= 1)
            if cum < gun_sayisi and paz < gun_sayisi:
                model.Add(nobet[(p, cum)] + nobet[(p, paz)] <= 1)

    toplam_gecmis = sum(gecmis_stats[p]["toplam"] for p in personel)
    yeni_toplam_hedef = toplam_gecmis + gun_sayisi
    min_tot = yeni_toplam_hedef // num_personel
    max_tot = min_tot + 1
    for p, isim in enumerate(personel):
        gecmis_val = gecmis_stats[isim]["toplam"]
        model.AddLinearConstraint(gecmis_val + sum(nobet[(p, g)] for g in tum_gunler), min_tot, max_tot)

    toplam_gecmis_hs = sum(gecmis_stats[p]["hs"] for p in personel)
    yeni_hs_hedef = toplam_gecmis_hs + len(hafta_sonu_gunleri)
    min_hs = yeni_hs_hedef // num_personel
    max_hs = min_hs + 1
    for p, isim in enumerate(personel):
        gecmis_hs_val = gecmis_stats[isim]["hs"]
        model.AddLinearConstraint(gecmis_hs_val + sum(nobet[(p, g)] for g in hafta_sonu_gunleri), min_hs, max_hs)

    if bayram_gunleri:
        toplam_gecmis_bayram = sum(gecmis_stats[p]["bayram"] for p in personel)
        yeni_bayram_hedef = toplam_gecmis_bayram + len(bayram_gunleri)
        min_bay = yeni_bayram_hedef // num_personel
        max_bay = min_bay + 1
        for p, isim in enumerate(personel):
            gecmis_bay_val = gecmis_stats[isim]["bayram"]
            model.AddLinearConstraint(gecmis_bay_val + sum(nobet[(p, g)] for g in bayram_gunleri), min_bay, max_bay)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        gun_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        liste_data = []

        for g in tum_gunler:
            dt = tarih_listesi[g]
            gun_adi = gun_tr[dt.weekday()]
            
            kategori = "Hafta İçi"
            if dt in tatiller_set:
                tatil_adi = otomatik_tatil_dict.get(dt, "Resmi Tatil / Bayram")
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
                "Gün": dt.strftime("%d"),
                "Gün Adı": gun_adi,
                "Kategori": kategori,
                "Nöbetçi Personel": nobetci
            })

        return pd.DataFrame(liste_data)
    else:
        return None

# ==========================================
# X'Lİ MATRİS / ÇİZELGE OLUŞTURMA FONKSİYONU
# ==========================================
def cizelge_matrisi_olustur(df_ay, personel_listesi, yil, ay):
    _, gun_sayisi = calendar.monthrange(yil, ay)
    gun_sutunlari = [f"{g:02d}" for g in range(1, gun_sayisi + 1)]
    
    # Matris hazırlığı
    matris_data = {p: {g_str: "" for g_str in gun_sutunlari} for p in personel_listesi}
    
    # Nöbetçi olan günlere X koy
    for _, row in df_ay.iterrows():
        p = row["Nöbetçi Personel"]
        g_str = str(row["Gün"]).zfill(2)
        if p in matris_data and g_str in matris_data[p]:
            matris_data[p][g_str] = "X"
            
    rows = []
    for p in personel_listesi:
        row_dict = {"Personel": p}
        toplam_x = 0
        for g_str in gun_sutunlari:
            val = matris_data[p][g_str]
            row_dict[g_str] = val
            if val == "X":
                toplam_x += 1
        row_dict["Aylık Toplam"] = toplam_x
        rows.append(row_dict)
        
    df_cizelge = pd.DataFrame(rows)
    return df_cizelge

# ==========================================
# 4. BÖLÜM: OTOMATİK OLUŞTURMA VE GÖRÜNÜMLER
# ==========================================
st.divider()

col_btn1, col_btn2 = st.columns([2, 1])

with col_btn1:
    if st.button(f"🤖 {secilen_ay_adi} {secilen_yil} Nöbetini Yapay Zeka İle Oluştur", type="primary", use_container_width=True):
        if len(personel_listesi) < 2:
            st.error("En az 2 personel girmelisiniz.")
        else:
            db_personel_kaydet(personel_listesi) # Otomatik kaydet
            with st.spinner("Geçmiş veri tabanı okunarak adil nöbet taslağı hazırlanıyor..."):
                df_taslak = aylik_kumulatif_nobet_hesapla(
                    personel_listesi, secilen_yil, secilen_ay_num, izinler, resmi_tatil_set, gecmis_stats
                )
                if df_taslak is not None:
                    st.session_state['aktif_taslak'] = df_taslak
                    st.success("✅ Nöbet taslağı oluşturuldu!")
                else:
                    st.error("❌ Çakışan izinler nedeniyle nöbet üretilemedi. İzinleri esnetip tekrar deneyin.")

if 'aktif_taslak' not in st.session_state:
    df_db_ay = df_gecmis_tum[df_gecmis_tum['yil_ay'] == yil_ay_key]
    if not df_db_ay.empty:
        st.session_state['aktif_taslak'] = df_db_ay.rename(columns={
            "tarih": "Tarih", "gun_adi": "Gün Adı", "kategori": "Kategori", "personel": "Nöbetçi Personel"
        })[["Tarih", "Gün Adı", "Kategori", "Nöbetçi Personel"]]
        st.session_state['aktif_taslak']["Gün"] = st.session_state['aktif_taslak']["Tarih"].apply(lambda x: str(x).split("-")[-1])

if 'aktif_taslak' in st.session_state:
    st.subheader(f"📋 {secilen_ay_adi} {secilen_yil} Nöbet Planı ve Çizelgesi")
    
    tab_liste, tab_cizelge = st.tabs(["✏️ Manuel Düzenlenebilir Liste Görünümü", "📊 Günlük X'li Çizelge Görünümü"])

    with tab_liste:
        st.info("💡 **Nasıl Değiştirilir?** 'Nöbetçi Personel' sütunundaki isimlere tıklayıp farklı bir personel seçerek manuel değişiklik yapabilirsiniz.")
        
        edited_df = st.data_editor(
            st.session_state['aktif_taslak'],
            column_config={
                "Nöbetçi Personel": st.column_config.SelectboxColumn(
                    "Nöbetçi Personel",
                    help="Değiştirmek istediğiniz personeli seçin",
                    width="medium",
                    options=personel_listesi,
                    required=True
                ),
                "Tarih": st.column_config.Column(disabled=True),
                "Gün Adı": st.column_config.Column(disabled=True),
                "Kategori": st.column_config.Column(disabled=True),
                "Gün": st.column_config.Column(disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="nobet_editor"
        )

        if st.button("💾 Manuel Değişiklikleri Veri Tabanına Kaydet", type="secondary", use_container_width=True):
            db_ay_kaydet(edited_df, yil_ay_key)
            db_personel_kaydet(personel_listesi)
            st.session_state['aktif_taslak'] = edited_df
            st.success(f"✅ {secilen_ay_adi} {secilen_yil} nöbetleri ve personel kadrosu veri tabanına işlendi!")
            st.rerun()

    with tab_cizelge:
        st.subheader("📅 Aylık Nöbet Dağılım Çizelgesi (X Görünümü)")
        df_cizelge = cizelge_matrisi_olustur(st.session_state['aktif_taslak'], personel_listesi, secilen_yil, secilen_ay_num)
        st.dataframe(df_cizelge, use_container_width=True, hide_index=True)

    # Excel İndirme (Hem Liste Hem Çizelge Sayfalı)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        st.session_state['aktif_taslak'].to_excel(writer, sheet_name='Nöbet Listesi', index=False)
        df_cizelge = cizelge_matrisi_olustur(st.session_state['aktif_taslak'], personel_listesi, secilen_yil, secilen_ay_num)
        df_cizelge.to_excel(writer, sheet_name='Aylık X Çizelgesi', index=False)

    st.download_button(
        label="📥 Bu Ayın Nöbetini ve Çizelgesini Excel Olarak İndir (.xlsx)",
        data=excel_buffer.getvalue(),
        file_name=f"nobet_ve_cizelge_{yil_ay_key}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

