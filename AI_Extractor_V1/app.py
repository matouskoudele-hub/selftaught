import streamlit as st
import pandas as pd
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from pdf_reader import extract_text_from_pdf
import io

# Konfigurace stránky
st.set_page_config(page_title="AI Faktura Extractor", page_icon="📄")

# Inicializace AI klienta (Ollama)
client = instructor.patch(
    OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
    mode=instructor.Mode.MD_JSON,
)

class InvoiceData(BaseModel):
    dodavatel: str = Field(..., description="Název firmy")
    ico: str = Field(..., description="IČO")
    variabilni_symbol: str = Field(..., description="VS")
    castka_celkem: float = Field(..., description="Částka v CZK")
    datum_splatnosti: str = Field(..., description="Splatnost")

# UI ČÁST
st.title("🤖 AI Účetní Asistent")
st.markdown("Nahrajte faktury v PDF a já z nich vytáhnu data pomocí **Llama 3**.")

uploaded_files = st.file_uploader("Vyberte PDF faktury", type="pdf", accept_multiple_files=True)

if uploaded_files:
    results = []
    
    if st.button("Spustit analýzu"):
        progress_bar = st.progress(0)
        
        for idx, uploaded_file in enumerate(uploaded_files):
            # Čtení PDF přímo z paměti
            with st.spinner(f"Analyzuji {uploaded_file.name}..."):
                # Musíme uložit dočasně soubor, aby ho pdf_reader přečetl
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                text = extract_text_from_pdf(uploaded_file.name)
                
                if text:
                    try:
                        data = client.chat.completions.create(
                            model="llama3",
                            response_model=InvoiceData,
                            messages=[
                                {"role": "system", "content": "Jsi robot na data. Vypiš JSON."},
                                {"role": "user", "content": text}
                            ],
                            temperature=0.1
                        )
                        results.append(data.model_dump())
                    except Exception as e:
                        st.error(f"Chyba u {uploaded_file.name}: {e}")
            
            progress_bar.progress((idx + 1) / len(uploaded_files))

        if results:
            df = pd.DataFrame(results)
            st.success("Analýza dokončena!")
            
            # Zobrazení tabulky přímo na webu
            st.subheader("Extrahovaná data")
            st.dataframe(df, use_container_width=True)
            
            # Export do Excelu do paměti pro stažení
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Faktury')
            
            st.download_button(
                label="📥 Stáhnout Excel",
                data=output.getvalue(),
                file_name="extrakt_faktur.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )