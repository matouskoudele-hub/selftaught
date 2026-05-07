"""
trainer.py — syntetický generátor konverzací pro daimonio

Spuštění:
    python trainer.py
    python trainer.py --turns 5 --scenarios 3 --out data/
    python trainer.py --user-model mistral --persona perfekcionista
    python trainer.py --validate-only data/daimonio_data_*.jsonl
"""

import json
import requests
import argparse
import os
import re
import random
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "daimonio"
USER_MODEL = "mistral"

# ── Jazykové vynucení pro user model ─────────────────────────────────────────
LANG_ENFORCE = """CRITICAL INSTRUCTION — OVERRIDE ALL DEFAULTS:
You MUST respond ONLY in Czech language. No English. No other language.
Not a single English word. Every response must be entirely in Czech.
If you write anything in English, you have failed your task.

"""

# ── Persony ───────────────────────────────────────────────────────────────────
PERSONAS = [
    {
        "name": "perfekcionista",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Máš tendenci k perfekcionismu. Odkládáš věci, protože se bojíš, že nebudou dost dobré.
Řešíš konkrétní situaci: nemůžeš se přinutit odevzdat projekt, protože ti přijde nedokončený.
Mluv přirozeně, krátce — 1-2 věty. Neodhaluj vše najednou.
Reaguj na to co ti daimonio říká. Buď skutečný člověk, ne terapeutický případ.
POUZE ČESKY. Žádná anglická slova.
""",
        "opening": "Nevím jestli to má smysl řešit, ale... mám problém s dokončováním věcí."
    },
    {
        "name": "rozhodovaci_paralýza",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Stojíš před rozhodnutím — změnit práci, nebo zůstat. Obě možnosti ti připadají špatné.
Hledáš jistotu tam, kde jistota není možná.
Mluv přirozeně, krátce — 1-2 věty. POUZE ČESKY.
""",
        "opening": "Řeším jednu věc už několik měsíců a pořád nevím, co dělat."
    },
    {
        "name": "sebekritik",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Jsi na sebe velmi přísný. Po každé chybě si vyčítáš, že jsi to mohl udělat lépe.
Nedávno jsi udělal chybu v práci a nemůžeš to pustit.
Mluv přirozeně, krátce — 1-2 věty. POUZE ČESKY.
""",
        "opening": "Udělal jsem chybu v práci a nemůžu přestat na to myslet."
    },
    {
        "name": "vztahova_nejistota",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Cítíš se nejistě ve vztahu — ne kvůli partnerovi, ale kvůli sobě.
Nevíš, jestli tvoje pocity jsou reálné nebo jen úzkost.
Mluv přirozeně, krátce — 1-2 věty. POUZE ČESKY.
""",
        "opening": "Mám pocit, že ve vztahu něco není v pořádku, ale nevím jestli je to problém ve mně."
    },
    {
        "name": "smysl_prace",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Máš dobrou práci, slušný plat, ale práce tě nenaplňuje.
Nevíš jestli to změnit nebo přijmout.
Mluv přirozeně, krátce — 1-2 věty. POUZE ČESKY.
""",
        "opening": "Mám práci, která je v pohodě, ale mám pocit, že mi něco chybí."
    },
    {
        "name": "vyhybani_konfliktu",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Vyhýbáš se konfliktům, i když víš, že by bylo potřeba něco říct.
Teď ti někdo v práci opakovaně překáží, ale mlčíš.
Mluv přirozeně, krátce — 1-2 věty. POUZE ČESKY.
""",
        "opening": "Je jedna věc, kterou bych měl asi říct nahlas, ale nějak nemůžu."
    },
    {
        "name": "prehnana_odpovednost",
        "system": """
Hraješ roli člověka, který mluví s aplikací daimonio.
Cítíš se zodpovědný za věci, které nemůžeš ovlivnit.
Nedávno se něco pokazilo v týmu a ty si to bereš osobně, přestože to nebyla tvoje chyba.
Mluv přirozeně, krátce — 1-2 věty. POUZE ČESKY.
""",
        "opening": "V práci se něco pokazilo a mám pocit, že za to nějak můžu, i když vím, že to není úplně pravda."
    },
]


# ── Validace kvality ──────────────────────────────────────────────────────────

# Anglická stop-slova pro detekci
ENGLISH_STOPWORDS = {
    "the", "and", "you", "that", "this", "for", "are", "with", "have",
    "not", "what", "your", "from", "they", "can", "but", "its", "was",
    "has", "been", "will", "also", "just", "more", "some", "than",
    "then", "when", "which", "there", "their", "would", "could", "should",
    "maybe", "things", "something", "anything", "everything",
}

# Fráze které daimonio nesmí říkat
FORBIDDEN_PHRASES = [
    "skvělé", "výborně", "to je dobrý začátek", "super", "perfektní",
    "pamatuj si", "nezapomeň", "dovolte mi", "pokusím se",
    "rád bych ti pomohl", "jsem zde", "jako ai",
    # anglické zbytky
    "things", "maybe", "sorry", "ok ", "okay",
]

# Závorky s metakomentářem — daimonio je nemá používat
META_COMMENT_PATTERN = re.compile(r'\(.*?(pozn|pokusím|snažím|abych better|aby jsem better).*?\)', re.IGNORECASE)


def score_message(role: str, text: str) -> dict:
    """
    Ohodnotí jednu zprávu. Vrátí dict s chybami a skóre (0-100).
    Čím vyšší skóre, tím lepší zpráva.
    """
    errors = []
    score  = 100
    words  = text.lower().split()

    # 1. Detekce angličtiny
    if words:
        eng_ratio = sum(1 for w in words if w.strip(".,!?\"'") in ENGLISH_STOPWORDS) / len(words)
        if eng_ratio > 0.10:
            errors.append(f"angličtina ({eng_ratio:.0%} stop-slov)")
            score -= 40
        elif eng_ratio > 0.05:
            errors.append(f"pravděpodobná angličtina ({eng_ratio:.0%} stop-slov)")
            score -= 20

    # 2. Zakázané fráze (jen pro daimonio)
    if role == "assistant":
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text.lower():
                errors.append(f"zakázaná fráze: '{phrase}'")
                score -= 15

        # 3. Metakomentáře v závorkách
        if META_COMMENT_PATTERN.search(text):
            errors.append("metakomentář v závorkách")
            score -= 15

        # 4. Příliš mnoho otázek
        question_count = text.count("?")
        if question_count > 1:
            errors.append(f"příliš mnoho otázek ({question_count})")
            score -= 10 * (question_count - 1)

        # 5. Příliš dlouhá odpověď
        if len(words) > 80:
            errors.append(f"příliš dlouhá odpověď ({len(words)} slov)")
            score -= 15

    # 6. Prázdná zpráva
    if len(text.strip()) < 5:
        errors.append("příliš krátká zpráva")
        score -= 50

    return {"score": max(0, score), "errors": errors}


def validate_conversation(conv: dict) -> dict:
    """Zvaliduje celou konverzaci. Vrátí report."""
    messages = conv.get("messages", conv.get("conversations", []))
    results  = []
    total    = 0

    for i, msg in enumerate(messages):
        result = score_message(msg["role"], msg["content"])
        result["turn"]    = i
        result["role"]    = msg["role"]
        result["preview"] = msg["content"][:60].replace("\n", " ")
        results.append(result)
        total += result["score"]

    avg_score = total / len(results) if results else 0
    passed    = avg_score >= 70 and all(r["score"] >= 50 for r in results)

    return {
        "persona":   conv.get("persona", "?"),
        "avg_score": round(avg_score, 1),
        "passed":    passed,
        "turns":     results,
    }


def print_validation_report(report: dict, verbose: bool = False):
    status = "✓ OK " if report["passed"] else "✗ FAIL"
    print(f"  {status}  persona: {report['persona']:25s}  skóre: {report['avg_score']}/100")
    if not report["passed"] or verbose:
        for t in report["turns"]:
            if t["errors"] or verbose:
                role = "daimonio" if t["role"] == "assistant" else "uživatel"
                print(f"         turn {t['turn']} [{role}] skóre:{t['score']:3d}  {t['preview']!r}")
                for e in t["errors"]:
                    print(f"           → {e}")


# ── Modely ────────────────────────────────────────────────────────────────────

def call_model(system_prompt: str, history: list, model: str) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, *history],
                "stream": False,
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise SystemExit("[CHYBA] Nelze se připojit k Ollama. Spusť: ollama serve")
    except requests.exceptions.Timeout:
        raise SystemExit("[CHYBA] Ollama neodpověděla včas.")
    except (KeyError, requests.exceptions.JSONDecodeError) as e:
        raise SystemExit(f"[CHYBA] Neočekávaná odpověď od modelu: {e}")


def is_english(text: str) -> bool:
    words = text.lower().split()
    if not words:
        return False
    ratio = sum(1 for w in words if w.strip(".,!?\"'") in ENGLISH_STOPWORDS) / len(words)
    return ratio > 0.08


def force_czech(text: str, user_model: str) -> str:
    if not is_english(text):
        return text
    print("    [!] detekována angličtina — překládám...")
    history = [{"role": "user", "content": f"Přelož do češtiny. Vrať POUZE přeložený text:\n{text}"}]
    translated = call_model(
        "Jsi překladač. Překládáš text do češtiny. Vrať POUZE přeložený text, bez jakéhokoliv komentáře.",
        history,
        user_model,
    )
    return translated


# ── Generátor konverzací ──────────────────────────────────────────────────────

def generate_conversation(
    persona: dict,
    num_turns: int,
    daimonio_system: str,
    user_model: str,
    max_retries: int = 2,
) -> dict | None:
    """
    Vygeneruje jednu konverzaci. Pokud průměrné skóre < 70, zkusí to znovu.
    Vrátí None pokud se ani po max_retries nepodaří vygenerovat kvalitní data.
    """
    user_system = LANG_ENFORCE + persona["system"]

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"    [retry {attempt}/{max_retries}]")

        user_history     = []
        daimonio_history = []
        turns_log        = []
        user_msg         = persona["opening"]

        for turn in range(num_turns):
            # Uživatel mluví
            print(f"\n  [uživatel] {user_msg[:80]}")
            turns_log.append({"role": "user", "content": user_msg})
            daimonio_history.append({"role": "user", "content": user_msg})

            # Daimonio odpovídá
            daimonio_reply = call_model(daimonio_system, daimonio_history, MODEL)
            print(f"  [daimonio] {daimonio_reply[:80]}")

            # Rychlá inline validace daimonia
            qscore = score_message("assistant", daimonio_reply)
            if qscore["errors"]:
                print(f"    [!] {', '.join(qscore['errors'])}")

            turns_log.append({"role": "assistant", "content": daimonio_reply})
            daimonio_history.append({"role": "assistant", "content": daimonio_reply})

            if turn == num_turns - 1:
                break

            # User model reaguje
            user_history.append({"role": "user",      "content": user_msg})
            user_history.append({"role": "assistant", "content": daimonio_reply})

            reminder = {
                "role": "user",
                "content": (
                    f"daimonio ti právě řeklo: \"{daimonio_reply}\"\n\n"
                    "Reaguj na to jako tvoje postava. 1-2 věty, česky, přirozeně. POUZE ČESKY."
                )
            }
            raw      = call_model(user_system, user_history + [reminder], user_model)
            user_msg = force_czech(raw, user_model)

        conv = {
            "persona":   persona["name"],
            "timestamp": datetime.now().isoformat(),
            "turns":     num_turns,
            "messages":  turns_log,
        }

        # Validace celé konverzace
        report = validate_conversation(conv)
        if report["passed"]:
            return conv

        print(f"    [!] konverzace nesplňuje kvalitu (skóre {report['avg_score']}) — zkouším znovu")

    print(f"    [SKIP] persona {persona['name']} neprodukuje kvalitní data, přeskakuji")
    return None


def load_daimonio_system():
    try:
        with open("Modelfile", "r", encoding="utf-8") as f:
            content = f.read()
        start = content.find('"""') + 3
        end   = content.rfind('"""')
        if start > 3 and end > start:
            return content[start:end].strip()
    except FileNotFoundError:
        pass
    return "Jsi daimonio. Tichý vnitřní hlas. Korektiv myšlení. Odpovídej česky, krátce, věcně."


# ── Ukládání ──────────────────────────────────────────────────────────────────

def save_jsonl(conversations: list, path: str):
    with open(path, "w", encoding="utf-8") as f:
        for conv in conversations:
            record = {
                "conversations": conv["messages"],
                "metadata": {"persona": conv["persona"], "timestamp": conv["timestamp"]}
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_txt(conversations: list, path: str):
    with open(path, "w", encoding="utf-8") as f:
        for i, conv in enumerate(conversations, 1):
            f.write(f"{'═' * 60}\n")
            f.write(f"Konverzace #{i} — persona: {conv['persona']}\n")
            f.write(f"Čas: {conv['timestamp']}\n")
            f.write(f"{'─' * 60}\n\n")
            for msg in conv["messages"]:
                speaker = "ty" if msg["role"] == "user" else "daimonio"
                f.write(f"{speaker}:\n{msg['content']}\n\n")
            f.write("\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_validate(paths: list[str], verbose: bool):
    """Zvaliduje existující JSONL soubory."""
    for path in paths:
        print(f"\n  soubor: {path}")
        try:
            with open(path, encoding="utf-8") as f:
                lines = [json.loads(l) for l in f if l.strip()]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [CHYBA] {e}")
            continue

        passed = 0
        for conv in lines:
            report = validate_conversation(conv)
            print_validation_report(report, verbose)
            if report["passed"]:
                passed += 1

        print(f"  celkem: {passed}/{len(lines)} konverzací prošlo validací")


def cmd_generate(args):
    """Generuje nové konverzace."""
    os.makedirs(args.out, exist_ok=True)

    daimonio_system = load_daimonio_system()
    print(f"  [OK] System prompt daimonia načten ({len(daimonio_system)} znaků)")
    print(f"  [OK] User model: {args.user_model}")

    if args.persona:
        personas = [p for p in PERSONAS if p["name"] == args.persona]
        if not personas:
            print(f"[CHYBA] Persona '{args.persona}' nenalezena.")
            print(f"Dostupné: {', '.join(p['name'] for p in PERSONAS)}")
            return
    else:
        personas = PERSONAS[:args.scenarios]
        random.shuffle(personas)

    print(f"\n◈ daimonio trainer")
    print(f"  person: {len(personas)}  |  výměn na konverzaci: {args.turns}")
    print(f"  výstup: {os.path.abspath(args.out)}\n")

    conversations = []
    skipped       = 0

    for persona in personas:
        print(f"\n  persona: {persona['name']}")
        print(f"  {'─' * 52}")
        conv = generate_conversation(
            persona, args.turns, daimonio_system, args.user_model
        )
        if conv:
            conversations.append(conv)
        else:
            skipped += 1

    if not conversations:
        print("\n[!] Žádná konverzace neprojekla kvalitou. Zkus jiný model nebo uprav persony.")
        return

    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = os.path.join(args.out, f"daimonio_data_{ts}.jsonl")
    txt_path   = os.path.join(args.out, f"daimonio_data_{ts}.txt")

    save_jsonl(conversations, jsonl_path)
    save_txt(conversations,   txt_path)

    print(f"\n{'═' * 60}")
    print(f"  Vygenerováno:  {len(conversations)} konverzací")
    if skipped:
        print(f"  Přeskočeno:    {skipped} (nesplňovaly kvalitu)")
    print(f"  JSONL:         {jsonl_path}")
    print(f"  TXT:           {txt_path}")
    print(f"{'═' * 60}")


def main():
    import sys

    # Pokud první argument není "validate", chovej se jako generate
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        parser = argparse.ArgumentParser()
        parser.add_argument("validate")
        parser.add_argument("files", nargs="+")
        parser.add_argument("--verbose", "-v", action="store_true")
        args = parser.parse_args()
        cmd_validate(args.files, args.verbose)
    else:
        parser = argparse.ArgumentParser(description="Generátor trénovacích konverzací pro daimonio")
        parser.add_argument("--turns",      type=int, default=4,
                            help="Počet výměn v každé konverzaci (default: 4)")
        parser.add_argument("--scenarios",  type=int, default=len(PERSONAS),
                            help=f"Počet person (max {len(PERSONAS)}, default: všechny)")
        parser.add_argument("--out",        type=str, default=".",
                            help="Výstupní složka (default: aktuální)")
        parser.add_argument("--persona",    type=str, default=None,
                            help="Jen konkrétní persona (podle jména)")
        parser.add_argument("--user-model", "--user_model", dest="user_model",
                            type=str, default=USER_MODEL,
                            help=f"Model hrající uživatele (default: {USER_MODEL})")
        args = parser.parse_args()
        cmd_generate(args)


if __name__ == "__main__":
    main()
