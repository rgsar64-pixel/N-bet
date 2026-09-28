import calendar
import datetime
import io
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Nöbet Hazırlama Uygulaması", layout="wide")
st.title("📅 Otomatik Nöbet Çizelgesi Oluşturucu")

# --- YAN MENÜ: GİRDİLER ---
st.sidebar.header("Çizelge Parametreleri")
year = st.sidebar.number_input(
    "Yıl", min_value=2024, max_value=2030, value=2026
)
month = st.sidebar.selectbox(
    "Ay",
    range(1, 13),
    index=8,
    format_func=lambda x: [
        "Ocak",
        "Şubat",
        "Mart",
        "Nisan",
        "Mayıs",
        "Haziran",
        "Temmuz",
        "Ağustos",
        "Eylül",
        "Ekim",
        "Kasım",
        "Aralık",
    ][x - 1],
)

emp_input = st.sidebar.text_area(
    "Personel Listesi (Her satıra bir isim)",
    value="Ahmet Yılmaz\nMehmet Demir\nAyşe Kaya\nFatma Çelik\nAli Öztürk",
)
employees = [e.strip() for e in emp_input.split("\n") if e.strip()]

holiday_input = st.sidebar.text_input(
    "Resmi Tatil Günleri (Virgülle ayırın)", value="29"
)
holidays = [
    int(x.strip())
    for x in holiday_input.split(",")
    if x.strip().isdigit()
]

num_days = calendar.monthrange(year, month)[1]

st.sidebar.subheader("Mazeret Girişleri (M)")
excuses = {}
for emp in employees:
    exc_days = st.sidebar.text_input(f"{emp} Mazeret Günleri", value="")
    excuses[emp] = [
        int(x.strip())
        for x in exc_days.split(",")
        if x.strip().isdigit()
    ]

# --- NÖBET HESAPLAMA MOTORU ---
if st.button("Nöbet Çizelgesini Oluştur", type="primary"):
    schedule = {emp: ["" for _ in range(num_days + 1)] for emp in employees}
    last_shift_day = {emp: -10 for emp in employees}
    shift_counts = {emp: 0 for emp in employees}

    # Mazeretlerin İşlenmesi
    for emp, exc_days in excuses.items():
        for d in exc_days:
            if 1 <= d <= num_days:
                schedule[emp][d] = "M"

    # Algoritma Dağıtımı
    for day in range(1, num_days + 1):
        available = [emp for emp in employees if schedule[emp][day] != "M"]
        if not available:
            continue

        # 1. Öncelik: En az 2 gün dinlenmiş kişiler (Kural: 1 gün arayla nöbet yazmama)
        candidates = [
            emp for emp in available if (day - last_shift_day[emp]) >= 3
        ]

        # 2. Öncelik (Zorunlu Hal): Mazeret sıkışıklığında 1 gün araya izin verme
        if not candidates:
            candidates = [
                emp for emp in available if (day - last_shift_day[emp]) >= 2
            ]

        if not candidates:
            candidates = available

        selected_emp = min(candidates, key=lambda x: shift_counts[x])
        schedule[selected_emp][day] = "X"
        last_shift_day[selected_emp] = day
        shift_counts[selected_emp] += 1

    # --- PANDAS DATAFRAME OLUŞTURMA ---
    cols = [
        f"{d} ({datetime.date(year, month, d).strftime('%a')})"
        for d in range(1, num_days + 1)
    ]
    df_data = []

    for emp in employees:
        row = [schedule[emp][d] for d in range(1, num_days + 1)]
        df_data.append(row)

    df = pd.DataFrame(df_data, columns=cols, index=employees)

    # --- HÜCRE RENKLENDİRME STİLİ ---
    def style_schedule(val, col_name):
        day_num = int(col_name.split(" ")[0])
        date_obj = datetime.date(year, month, day_num)
        weekday = date_obj.weekday()  # 0:Pzt, 3:Per, 4:Cum, 5:Cts, 6:Paz

        # Değer bazlı stiller
        if val == "M":
            return "background-color: #FFB4B4; color: black; font-weight: bold;"  # Pembe (Mazeret)
        elif val == "X":
            return "background-color: #6BCB77; color: black; font-weight: bold;"  # Yeşil (Nöbet)

        # Gün tipi bazlı arkaplan (Boş hücreler için)
        if day_num in holidays:
            return "background-color: #FF6B6B; color: white;"  # Kırmızı (Tatil)
        elif weekday in [5, 6]:
            return "background-color: #4D96FF; color: white;"  # Mavi (Hafta Sonu)
        elif weekday in [3, 4]:
            return "background-color: #FFD93D; color: black;"  # Sarı (Perşembe-Cuma)

        return ""

    # DataFrame Stillendirme
    styled_df = df.style.apply(
        lambda col: [style_schedule(v, col.name) for v in col], axis=0
    )

    st.subheader("📋 Ay Nöbet Çizelgesi")
    st.dataframe(styled_df, use_container_width=True)

    # --- EXCEL İNDİRME BUTONU ---
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nöbet Listesi"

    # Excel Başlıkları ve Renklendirmeleri
    fill_holiday = PatternFill("solid", fgColor="FF6B6B")
    fill_weekend = PatternFill("solid", fgColor="4D96FF")
    fill_thu_fri = PatternFill("solid", fgColor="FFD93D")
    fill_excuse = PatternFill("solid", fgColor="FFB4B4")
    fill_shift = PatternFill("solid", fgColor="6BCB77")

    ws.cell(row=1, column=1, value="Personel")
    for d in range(1, num_days + 1):
        c = ws.cell(row=1, column=d + 1, value=f"{d}")
        w = datetime.date(year, month, d).weekday()
        if d in holidays:
            c.fill = fill_holiday
        elif w in [5, 6]:
            c.fill = fill_weekend
        elif w in [3, 4]:
            c.fill = fill_thu_fri

    for r_idx, emp in enumerate(employees, start=2):
        ws.cell(row=r_idx, column=1, value=emp)
        for d in range(1, num_days + 1):
            val = schedule[emp][d]
            c = ws.cell(row=r_idx, column=d + 1, value=val)
            if val == "M":
                c.fill = fill_excuse
            elif val == "X":
                c.fill = fill_shift

    wb.save(output)
    st.download_button(
        label="📥 Renkli Excel Olarak İndir",
        data=output.getvalue(),
        file_name=f"Nobet_Listesi_{month}_{year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

