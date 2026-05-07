import tkinter as tk
from tkinter import messagebox
import subprocess
import os

def spust_analyzu():
    try:
        # Spustí tvůj import.py
        result = subprocess.run(['python', 'import.py'], capture_output=True, text=True)
        if result.returncode == 0:
            messagebox.showinfo("Hotovo", "AI analýza proběhla úspěšně!\nObjednávky byly vytvořeny.")
        else:
            messagebox.showerror("Chyba", f"Analýza selhala:\n{result.stderr}")
    except Exception as e:
        messagebox.showerror("Chyba", str(e))

def otevri_slozku():
    os.startfile('.') # Otevře aktuální složku ve Windows

# Hlavní okno
root = tk.Tk()
root.title("Gastro AI Skladník v1.0")
root.geometry("400x300")
root.configure(bg="#f0f0f0")

# Obsah
label = tk.Label(root, text="🤖 Gastro AI Management", font=("Arial", 16, "bold"), bg="#f0f0f0", pady=20)
label.pack()

btn_run = tk.Button(root, text="VYGENEROVAT OBJEDNÁVKY", command=spust_analyzu, 
                   bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=25, height=2)
btn_run.pack(pady=10)

btn_folder = tk.Button(root, text="OTEVŘÍT SLOŽKU S PDF", command=otevri_slozku,
                      bg="#2196F3", fg="white", font=("Arial", 10), width=25)
btn_folder.pack(pady=10)

status = tk.Label(root, text="Systém připraven", bd=1, relief=tk.SUNKEN, anchor=tk.W)
status.pack(side=tk.BOTTOM, fill=tk.X)

root.mainloop()