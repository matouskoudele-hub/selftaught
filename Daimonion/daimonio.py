import tkinter as tk
from tkinter import font as tkfont
import requests
import json
import threading
import time

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


# Load once at startup
profile = load_profile()
memory  = load_memory()

system_context = f"""
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

# Left accent bar
accent_bar = tk.Frame(header, bg=ACCENT, width=3)
accent_bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0))

title_lbl = tk.Label(
    header,
    text="◈  daimonio",
    bg=BG_PANEL,
    fg=ACCENT,
    font=FONT_TITLE,
)
title_lbl.pack(side=tk.LEFT, padx=(16, 0), pady=14)

status_dot = tk.Label(header, text="●", bg=BG_PANEL, fg=ACCENT, font=("Courier New", 10))
status_dot.pack(side=tk.RIGHT, padx=(0, 18))
status_lbl = tk.Label(header, text="online", bg=BG_PANEL, fg=META_CLR, font=FONT_MONO_S)
status_lbl.pack(side=tk.RIGHT, padx=(0, 4))

# thin separator line below header
sep = tk.Frame(window, bg=BORDER, height=1)
sep.pack(fill=tk.X)

# ── Chat area ─────────────────────────────────────────────────────────────────
chat_frame = tk.Frame(window, bg=BG_DEEP)
chat_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

scrollbar = tk.Scrollbar(chat_frame, bg=BG_PANEL, troughcolor=BG_DEEP,
                         activebackground=ACCENT_DIM, bd=0, width=8)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 2))

chat_box = tk.Text(
    chat_frame,
    wrap=tk.WORD,
    bg=BG_DEEP,
    fg=USER_CLR,
    font=FONT_MONO,
    relief=tk.FLAT,
    bd=0,
    padx=20,
    pady=16,
    insertbackground=ACCENT,
    selectbackground=ACCENT_DIM,
    selectforeground=BG_DEEP,
    yscrollcommand=scrollbar.set,
    state=tk.DISABLED,
    cursor="arrow",
)
chat_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=chat_box.yview)

# Text tags
chat_box.tag_config("user_label", foreground=META_CLR,   font=FONT_MONO_S)
chat_box.tag_config("user_text",  foreground=USER_CLR,   font=FONT_MONO,  lmargin1=20, lmargin2=20)
chat_box.tag_config("bot_label",  foreground=ACCENT,     font=FONT_MONO_S)
chat_box.tag_config("bot_text",   foreground=BOT_CLR,    font=FONT_MONO,  lmargin1=20, lmargin2=20)
chat_box.tag_config("error_text", foreground=ERR_CLR,    font=FONT_MONO,  lmargin1=20, lmargin2=20)
chat_box.tag_config("divider",    foreground=BORDER)
chat_box.tag_config("spacing",    font=tkfont.Font(size=4))

# ── Separator ─────────────────────────────────────────────────────────────────
sep2 = tk.Frame(window, bg=BORDER, height=1)
sep2.pack(fill=tk.X)

# ── Input row ─────────────────────────────────────────────────────────────────
input_frame = tk.Frame(window, bg=BG_PANEL, height=60)
input_frame.pack(fill=tk.X, side=tk.BOTTOM)
input_frame.pack_propagate(False)

prompt_lbl = tk.Label(input_frame, text="›", bg=BG_PANEL, fg=ACCENT,
                      font=tkfont.Font(family="Courier New", size=16, weight="bold"))
prompt_lbl.pack(side=tk.LEFT, padx=(16, 6))

entry = tk.Entry(
    input_frame,
    bg=BG_INPUT,
    fg=USER_CLR,
    font=FONT_MONO,
    relief=tk.FLAT,
    bd=0,
    insertbackground=ACCENT,
    selectbackground=ACCENT_DIM,
    selectforeground=BG_DEEP,
    highlightthickness=1,
    highlightcolor=ACCENT,
    highlightbackground=BORDER,
)
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=(0, 12))


# ── Send button with hover effect ─────────────────────────────────────────────
send_button = tk.Button(
    input_frame,
    text="SEND",
    bg=SEND_BG,
    fg=SEND_FG,
    font=tkfont.Font(family="Courier New", size=10, weight="bold"),
    relief=tk.FLAT,
    bd=0,
    padx=18,
    pady=10,
    cursor="hand2",
    activebackground=SEND_HOV,
    activeforeground=SEND_FG,
)
send_button.pack(side=tk.RIGHT, padx=(0, 14), pady=10)


def on_enter_btn(e):  send_button.config(bg=SEND_HOV)
def on_leave_btn(e):  send_button.config(bg=SEND_BG if str(send_button["state"]) == "normal" else BG_PANEL)

send_button.bind("<Enter>", on_enter_btn)
send_button.bind("<Leave>", on_leave_btn)


# ── Chat helpers ──────────────────────────────────────────────────────────────
def append_chat(label, label_tag, text, text_tag):
    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, "\n", "spacing")
    ts = time.strftime("%H:%M")
    chat_box.insert(tk.END, f"  {label}  {ts}\n", label_tag)
    chat_box.insert(tk.END, f"  {text}\n", text_tag)
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)


# ── Typing indicator (animated dots) ─────────────────────────────────────────
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
    if not _typing_visible:
        return
    dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    d = dots[_typing_dots % len(dots)]
    chat_box.config(state=tk.NORMAL)
    # rewrite the typing line
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
    if _typing_after_id:
        window.after_cancel(_typing_after_id)
        _typing_after_id = None
    _typing_visible = False
    chat_box.config(state=tk.NORMAL)
    try:
        start = chat_box.index(TYPING_MARK)
        end   = chat_box.index(f"{TYPING_MARK} lineend +1c")
        chat_box.delete(start, end)
    except tk.TclError:
        pass
    chat_box.config(state=tk.DISABLED)


# ── Send logic ────────────────────────────────────────────────────────────────
def send_message(event=None):
    user_input = entry.get().strip()
    if not user_input:
        return

    append_chat("ty", "user_label", user_input, "user_text")
    entry.delete(0, tk.END)
    send_button.config(state=tk.DISABLED, bg=BG_PANEL, fg=META_CLR)
    status_lbl.config(text="thinking...")
    status_dot.config(fg=ACCENT_DIM)

    conversation_history.append({"role": "user", "content": user_input})
    show_typing()
    threading.Thread(target=fetch_reply, daemon=True).start()


def fetch_reply():
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_context},
                    *conversation_history,
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        reply = response.json()["message"]["content"]
        conversation_history.append({"role": "assistant", "content": reply})
        window.after(0, lambda: display_reply(reply, error=False))
    except requests.exceptions.ConnectionError:
        window.after(0, lambda: display_reply("[Chyba: Nelze se připojit k Ollama. Běží server?]", error=True))
    except requests.exceptions.Timeout:
        window.after(0, lambda: display_reply("[Chyba: Požadavek vypršel.]", error=True))
    except (KeyError, requests.exceptions.JSONDecodeError):
        window.after(0, lambda: display_reply("[Chyba: Neočekávaná odpověď od modelu.]", error=True))


def display_reply(reply, error=False):
    hide_typing()
    tag = "error_text" if error else "bot_text"
    append_chat("daimonio", "bot_label", reply, tag)
    send_button.config(state=tk.NORMAL, bg=SEND_BG, fg=SEND_FG)
    status_lbl.config(text="online")
    status_dot.config(fg=ACCENT)


# ── Boot message ──────────────────────────────────────────────────────────────
def boot_message():
    chat_box.config(state=tk.NORMAL)
    lines = [
        ("  ◈ daimonio v1.0\n",          "bot_label"),
        ("  session initialized\n",       "bot_text"),
        ("  " + "─" * 44 + "\n",         "user_label"),
    ]
    for text, tag in lines:
        chat_box.insert(tk.END, text, tag)
    chat_box.config(state=tk.DISABLED)


boot_message()

entry.bind("<Return>", send_message)
send_button.config(command=send_message)

window.mainloop()