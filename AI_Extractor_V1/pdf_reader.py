from pypdf import PdfReader

def extract_text_from_pdf(pdf_path):
    try:
        # Otevřeme PDF soubor
        reader = PdfReader(pdf_path)
        full_text = ""
        
        # Projdeme všechny stránky (faktury mají většinou jednu, ale jistota je jistota)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        return full_text.strip()
    
    except Exception as e:
        return f"Chyba při čtení PDF: {e}"

# --- TESTOVACÍ ČÁST ---
if __name__ == "__main__":
    # Tady změň 'faktura.pdf' na název tvého souboru ve složce
    SOUBOR = "faktura-857874.pdf" 
    vysledek = extract_text_from_pdf(SOUBOR)
    
    print("--- EXTRAHOVANÝ TEXT ---")
    print(vysledek)
    print("------------------------")