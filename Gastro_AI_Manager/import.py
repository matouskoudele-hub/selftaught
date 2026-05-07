import pandas as pd
from prophet import Prophet
from fpdf import FPDF
from datetime import datetime
import os

# --- 1. NAČTENÍ A KONTROLA DAT ---
try:
    df = pd.read_csv('data.csv')
    # Odstraníme případné neviditelné mezery v názvech sloupců
    df.columns = df.columns.str.strip()
    
    # KONTROLA SLOUPCŮ - Pokud chybí, vytvoříme je, aby program nespadl
    if 'dodavatel' not in df.columns:
        print("⚠️ VAROVÁNÍ: Sloupec 'dodavatel' nenalezen v CSV. Používám výchozí 'Neznamy'.")
        df['dodavatel'] = 'Neznamy'
    
    if 'cena_jednotka' not in df.columns:
        print("⚠️ VAROVÁNÍ: Sloupec 'cena_jednotka' nenalezen. Nastavuji 0 Kč.")
        df['cena_jednotka'] = 0

    # Převod na čísla
    df['prodano_kusu'] = pd.to_numeric(df['prodano_kusu'], errors='coerce')
    df['sklad_rano'] = pd.to_numeric(df['sklad_rano'], errors='coerce')
    df['cena_jednotka'] = pd.to_numeric(df['cena_jednotka'], errors='coerce')
    df = df.dropna(subset=['prodano_kusu', 'sklad_rano'])

except Exception as e:
    print(f"❌ KRITICKÁ CHYBA při načítání CSV: {e}")
    exit()

# --- 2. FUNKCE PRO PDF ---
def generuj_pdf_objednavku(dodavatel, polozky):
    pdf = FPDF()
    pdf.add_page()
    
    # Cesta k fontu podle tvého screenshotu (složka freesans)
    font_path = os.path.join('freesans', 'FreeSans.ttf')
    font_name = 'helvetica'
    
    try:
        pdf.add_font('FreeSans', style='', fname=font_path)
        font_name = 'FreeSans'
    except:
        print(f"⚠️ Font nenalezen v: {font_path}. Používám helvetica.")

    pdf.set_font(font_name, size=16)
    pdf.cell(190, 10, txt=f"OBJEDNÁVKA: {dodavatel}", ln=1, align='C')
    pdf.set_font(font_name, size=10)
    pdf.cell(190, 10, txt=f"Vygenerováno: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=1, align='C')
    pdf.ln(10)

    # Tabulka
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(70, 10, 'Polozka', border=1, fill=True)
    pdf.cell(30, 10, 'Koupit (ks)', border=1, fill=True, align='C')
    pdf.cell(40, 10, 'Cena/ks', border=1, fill=True, align='C')
    pdf.cell(50, 10, 'Celkem', border=1, fill=True, align='C')
    pdf.ln()

    total_order_price = 0
    pdf.set_font(font_name, size=10)
    for p in polozky:
        subtotal = p['Koupit'] * p['Cena_ks']
        total_order_price += subtotal
        pdf.cell(70, 10, p['Název'], border=1)
        pdf.cell(30, 10, str(p['Koupit']), border=1, align='C')
        pdf.cell(40, 10, f"{p['Cena_ks']} Kc", border=1, align='R')
        pdf.cell(50, 10, f"{subtotal} Kc", border=1, align='R')
        pdf.ln()

    pdf.set_font(font_name, size=12)
    pdf.ln(5)
    pdf.cell(140, 10, txt="CELKEM K ZAPLACENI:", align='R')
    pdf.cell(50, 10, txt=f"{total_order_price} Kc", border=1, align='R')

    pdf.output(f"Objednavka_{dodavatel}.pdf")
    print(f" Vytvořeno: Objednavka_{dodavatel}.pdf")

# --- 3. ANALÝZA ---
seznam_polozek = df['polozka'].unique()
objednavky = {}

print("--- AI ANALÝZA START ---")

for polozka in seznam_polozek:
    df_i = df[df['polozka'] == polozka].copy()
    
    # Prophet AI
    df_ai = df_i[['datum', 'prodano_kusu']].rename(columns={'datum': 'ds', 'prodano_kusu': 'y'})
    m = Prophet(yearly_seasonality=False, daily_seasonality=False, weekly_seasonality=False).fit(df_ai)
    forecast = m.predict(m.make_future_dataframe(periods=2))
    
    predpoved_2d = forecast['yhat'].iloc[-2:].sum()
    aktualni = df_i['sklad_rano'].iloc[-1] - df_i['prodano_kusu'].iloc[-1]
    
    if aktualni <= (predpoved_2d * 1.1):
        koupit = round(max(0, (predpoved_2d * 3.5) - aktualni))
        if koupit > 0:
            dod = df_i['dodavatel'].iloc[0]
            if dod not in objednavky: objednavky[dod] = []
            objednavky[dod].append({
                "Název": polozka, "Koupit": koupit, "Cena_ks": df_i['cena_jednotka'].iloc[0]
            })

for dodavatel, polozky in objednavky.items():
    generuj_pdf_objednavku(dodavatel, polozky)