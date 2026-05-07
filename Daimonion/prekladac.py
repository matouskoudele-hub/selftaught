import PyPDF2
import os

def extrahuj_platona(pdf_path):
    output_dir = "knihovna"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Definice stránek podle obsahu tvého PDF (přibližně)
    dialogy = {
        "euthyfron": (7, 30),
        "obrana_sokrata": (31, 62),
        "kriton": (63, 80),
        "faidon": (81, 160),
        "kratylos": (161, 236),
        "theaitetos": (237, 332),
        "sofistes": (333, 410),
        "politikos": (411, 488)
    }

    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            
            for jmeno, (start, konec) in dialogy.items():
                text = ""
                # PyPDF2 indexuje od 0, v obsahu je to od 1
                for page_num in range(start-1, konec):
                    page = reader.pages[page_num]
                    text += page.extract_text()
                
                # Uložení do TXT v UTF-8
                with open(f"{output_dir}/{jmeno}.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"Uloženo: {jmeno}.txt")
                
    except Exception as e:
        print(f"Chyba při zpracování: {e}")

# Spusť toto ve složce s tvým PDF
import glob

# Najde jakékoli PDF v aktuální složce a zkusí ho zpracovat
pdf_soubory = glob.glob("*.pdf")
if pdf_soubory:
    print(f"Nalezen soubor: {pdf_soubory[0]}")
    extrahuj_platona(pdf_soubory[0])
else:
    print("Chyba: V této složce nebylo nalezeno žádné PDF!")