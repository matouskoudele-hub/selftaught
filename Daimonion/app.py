import tkinter as tk
from tkinter import font as tkfont
import requests
import json
import threading
import time
import os  # Přidáno pro práci se soubory

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "daimonio"

# ── Colour palette ────────────────────────────────────────────────────────────
BG_DEEP    = "#0a0c10"   # near-black background
BG_PANEL   = "#0f1218"   # slightly lighter panel
BG_INPUT   = "#141820"   # input field background
BORDER     = "#1e2530"   # subtle border
ACCENT     = "#00d4ff"   # cyan accent
ACCENT_DIM = "#006680"   # dimmed accent
USER_CLR   = "#e8eaf0"   # user text
BOT_CLR    = "#00d4ff"   # bot text (accent)
META_CLR   = "#3a4455"   # timestamps / labels
ERR_CLR    = "#ff4466"   # error messages
SEND_BG    = "#00d4ff"
SEND_FG    = "#0a0c10"
SEND_HOV   = "#00a8cc"


def load_profile():
    try:
        with open("user_profile.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: could not load profile: {e}")
        return {}


def load_memory():
    try:
        with open("memory.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

# ── RAG Logic: Hledání v knihovně ──────────────────────────────────────────────
def hledej_v_knihovne(dotaz_uzivatele):
    """Prohledá složku 'knihovna' a vrátí relevantní úryvky textu."""
    knihovna_cesta = "knihovna"
    if not os.path.exists(knihovna_cesta):
        return ""

    relevantni_texty = ""
    # Rozdělíme dotaz na slova a filtrujeme krátká slova
    klicova_slova = [s.lower() for s in dotaz_uzivatele.split() if len(s) > 4]
    
    for soubor in os.listdir(knihovna_cesta):
        if soubor.endswith(".txt"):
            try:
                with open(os.path.join(knihovna_cesta, soubor), "r", encoding="utf-8") as f:
                    obsah = f.read()
                    obsah_lower = obsah.lower()
                    
                    for slovo in klicova_slova:
                        if slovo in obsah_lower:
                            # Najdeme pozici a vezmeme kontext kolem slova
                            index = obsah_lower.find(slovo)
                            start = max(0, index - 200)
                            konec = min(len(obsah), index + 400)
                            uryvek = obsah[start:konec].replace("\n", " ")
                            relevantni_texty += f"\n[Inspirace z: {soubor}]\n...{uryvek}...\n"
                            break # Z každého souboru stačí jeden úryvek
            except Exception as e:
                print(f"Chyba při čtení {soubor}: {e}")
                
    return relevantni_texty[:2000] # Omezení délky pro stabilitu modelu


# Load once at startup
profile = load_profile()
memory  = load_memory()

# Základní systémový prompt (tvé definované "daimonio")
base_system_prompt = f"""
PROFIL UŽIVATELE:
{json.dumps(profile, indent=2, ensure_ascii=False)}

DOSAVADNÍ POZNATKY:
{memory}
"""

conversation_history = []


# ── App window ────────────────────────────────────────────────────────────────
window = tk.Tk()
window.title("daimonio")
window.configure(bg=BG_DEEP)
window.geometry("720x600")
window.minsize(520, 420)

# ── Fonts ─────────────────────────────────────────────────────────────────────
try:
    FONT_MONO   = tkfont.Font(family="Cascadia Code",   size=11)
    FONT_MONO_S = tkfont.Font(family="Cascadia Code",   size=9)
    FONT_TITLE  = tkfont.Font(family="Cascadia Code",   size=13, weight="bold")
except Exception:
    FONT_MONO   = tkfont.Font(family="Courier New", size=11)
    FONT_MONO_S = tkfont.Font(family="Courier New", size=9)
    FONT_TITLE  = tkfont.Font(family="Courier New", size=13, weight="bold")

# ── Header ────────────────────────────────────────────────────────────────────
header = tk.Frame(window, bg=BG_PANEL, height=52)
header.pack(fill=tk.X, side=tk.TOP)
header.pack_propagate(False)

accent_bar = tk.Frame(header, bg=ACCENT, width=3)
accent_bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0))

title_lbl = tk.Label(header, text="◈  daimonio", bg=BG_PANEL, fg=ACCENT, font=FONT_TITLE)
title_lbl.pack(side=tk.LEFT, padx=(16, 0), pady=14)

status_dot = tk.Label(header, text="●", bg=BG_PANEL, fg=ACCENT, font=("Courier New", 10))
status_dot.pack(side=tk.RIGHT, padx=(0, 18))
status_lbl = tk.Label(header, text="online", bg=BG_PANEL, fg=META_CLR, font=FONT_MONO_S)
status_lbl.pack(side=tk.RIGHT, padx=(0, 4))

sep = tk.Frame(window, bg=BORDER, height=1)
sep.pack(fill=tk.X)

# ── Chat area ─────────────────────────────────────────────────────────────────
chat_frame = tk.Frame(window, bg=BG_DEEP)
chat_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

scrollbar = tk.Scrollbar(chat_frame, bg=BG_PANEL, troughcolor=BG_DEEP,
                         activebackground=ACCENT_DIM, bd=0, width=8)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 2))

chat_box = tk.Text(chat_frame, wrap=tk.WORD, bg=BG_DEEP, fg=USER_CLR, font=FONT_MONO,
                   relief=tk.FLAT, bd=0, padx=20, pady=16, insertbackground=ACCENT,
                   yscrollcommand=scrollbar.set, state=tk.DISABLED, cursor="arrow")
chat_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=chat_box.yview)

chat_box.tag_config("user_label", foreground=META_CLR,   font=FONT_MONO_S)
chat_box.tag_config("user_text",  foreground=USER_CLR,   font=FONT_MONO,  lmargin1=20, lmargin2=20)
chat_box.tag_config("bot_label",  foreground=ACCENT,     font=FONT_MONO_S)
chat_box.tag_config("bot_text",   foreground=BOT_CLR,    font=FONT_MONO,  lmargin1=20, lmargin2=20)
chat_box.tag_config("error_text", foreground=ERR_CLR,    font=FONT_MONO,  lmargin1=20, lmargin2=20)
chat_box.tag_config("spacing",    font=tkfont.Font(size=4))

sep2 = tk.Frame(window, bg=BORDER, height=1)
sep2.pack(fill=tk.X)

# ── Input row ─────────────────────────────────────────────────────────────────
input_frame = tk.Frame(window, bg=BG_PANEL, height=60)
input_frame.pack(fill=tk.X, side=tk.BOTTOM)
input_frame.pack_propagate(False)

prompt_lbl = tk.Label(input_frame, text="›", bg=BG_PANEL, fg=ACCENT, font=("Courier New", 16, "bold"))
prompt_lbl.pack(side=tk.LEFT, padx=(16, 6))

entry = tk.Entry(input_frame, bg=BG_INPUT, fg=USER_CLR, font=FONT_MONO, relief=tk.FLAT, bd=0,
                 insertbackground=ACCENT, highlightthickness=1, highlightcolor=ACCENT, highlightbackground=BORDER)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=(0, 12))

send_button = tk.Button(input_frame, text="SEND", bg=SEND_BG, fg=SEND_FG, font=("Courier New", 10, "bold"),
                        relief=tk.FLAT, bd=0, padx=18, pady=10, cursor="hand2")
send_button.pack(side=tk.RIGHT, padx=(0, 14), pady=10)

def on_enter_btn(e):  send_button.config(bg=SEND_HOV)
def on_leave_btn(e):  send_button.config(bg=SEND_BG if str(send_button["state"]) == "normal" else BG_PANEL)
send_button.bind("<Enter>", on_enter_btn)
send_button.bind("<Leave>", on_leave_btn)

# ── Helpers & Logic ───────────────────────────────────────────────────────────
def append_chat(label, label_tag, text, text_tag):
    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, "\n", "spacing")
    ts = time.strftime("%H:%M")
    chat_box.insert(tk.END, f"  {label}  {ts}\n", label_tag)
    chat_box.insert(tk.END, f"  {text}\n", text_tag)
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)

_typing_after_id = None
_typing_dots      = 0
_typing_visible   = False
TYPING_MARK       = "typing_start"

def show_typing():
    global _typing_visible, _typing_dots
    _typing_visible = True
    _typing_dots = 0
    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, "\n", "spacing")
    chat_box.mark_set(TYPING_MARK, tk.END)
    chat_box.insert(tk.END, "  daimonio  …\n", "bot_label")
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)
    _animate_typing()

def _animate_typing():
    global _typing_after_id, _typing_dots
    if not _typing_visible: return
    dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    d = dots[_typing_dots % len(dots)]
    chat_box.config(state=tk.NORMAL)
    start = chat_box.index(TYPING_MARK)
    end   = chat_box.index(f"{TYPING_MARK} lineend +1c")
    chat_box.delete(start, end)
    ts = time.strftime("%H:%M")
    chat_box.insert(start, f"  daimonio  {ts}  {d}\n", "bot_label")
    chat_box.config(state=tk.DISABLED)
    _typing_dots += 1
    _typing_after_id = window.after(80, _animate_typing)

def hide_typing():
    global _typing_visible, _typing_after_id
    if _typing_after_id: window.after_cancel(_typing_after_id)
    _typing_visible = False
    chat_box.config(state=tk.NORMAL)
    try:
        start = chat_box.index(TYPING_MARK)
        end   = chat_box.index(f"{TYPING_MARK} lineend +1c")
        chat_box.delete(start, end)
    except: pass
    chat_box.config(state=tk.DISABLED)

def send_message(event=None):
    user_input = entry.get().strip()
    if not user_input: return
    append_chat("ty", "user_label", user_input, "user_text")
    entry.delete(0, tk.END)
    send_button.config(state=tk.DISABLED, bg=BG_PANEL, fg=META_CLR)
    status_lbl.config(text="thinking...")
    status_dot.config(fg=ACCENT_DIM)
    conversation_history.append({"role": "user", "content": user_input})
    show_typing()
    threading.Thread(target=fetch_reply, args=(user_input,), daemon=True).start()

def fetch_reply(last_user_input):
    try:
        # KROK 1: Vyhledání inspirace v knihovně
        moudrost = hledej_v_knihovne(last_user_input)
        
        # KROK 2: Sestavení rozšířeného kontextu
        current_context = base_system_prompt
        if moudrost:
            current_context += "\n\nRELEVANTNÍ FILOZOFICKÁ INSPIRACE (Přečti si a použij pro svou otázku):\n" + moudrost

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": current_context},
                    *conversation_history,
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        reply = response.json()["message"]["content"]
        conversation_history.append({"role": "assistant", "content": reply})
        window.after(0, lambda: display_reply(reply, error=False))
    except Exception as e:
        window.after(0, lambda: display_reply(f"[Chyba: {str(e)}]", error=True))

def display_reply(reply, error=False):
    hide_typing()
    tag = "error_text" if error else "bot_text"
    append_chat("daimonio", "bot_label", reply, tag)
    send_button.config(state=tk.NORMAL, bg=SEND_BG, fg=SEND_FG)
    status_lbl.config(text="online")
    status_dot.config(fg=ACCENT)

def boot_message():
    chat_box.config(state=tk.NORMAL)
    lines = [
        ("  ◈ daimonio v1.1\n",          "bot_label"),
        ("  library initialized\n",       "bot_text"),
        ("  " + "─" * 44 + "\n",         "user_label"),
    ]
    for text, tag in lines:
        chat_box.insert(tk.END, text, tag)
    chat_box.config(state=tk.DISABLED)

boot_message()
entry.bind("<Return>", send_message)
send_button.config(command=send_message)
window.mainloop()