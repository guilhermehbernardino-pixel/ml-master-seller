#!/usr/bin/env python3
"""
ML MASTER SELLER — Desktop Launcher
Interface gráfica para iniciar, parar e monitorar a campanha de afiliados.
Execute com pythonw.exe para rodar sem janela de console.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import subprocess
import sys
import os
import queue
import logging
from pathlib import Path
from datetime import datetime

# Garante que o diretório do projeto está no path
BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

APP_NAME = "ML Master Seller"
VERSION = "v1.0"
BRAND_COLOR = "#FFE600"       # Amarelo ML
BRAND_DARK = "#2D3436"        # Fundo escuro
BRAND_GREEN = "#00B050"       # Verde sucesso
BRAND_RED = "#E84118"         # Vermelho erro
BRAND_LIGHT = "#F5F6FA"       # Fundo claro
TEXT_COLOR = "#2D3436"


class QueueHandler(logging.Handler):
    """Redireciona logs do Python para uma fila (thread-safe)."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class MLMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {VERSION}")
        self.resizable(False, False)
        self.configure(bg=BRAND_DARK)

        self._process = None
        self._log_queue = queue.Queue()
        self._running = False

        self._set_icon()
        self._build_ui()
        self._start_log_poll()

        # Centraliza na tela
        self.update_idletasks()
        w, h = 700, 520
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    #  ÍCONE                                                               #
    # ------------------------------------------------------------------ #
    def _set_icon(self):
        icon_path = BASE_DIR / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  INTERFACE                                                           #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BRAND_COLOR, pady=10)
        header.pack(fill="x")

        tk.Label(
            header,
            text="🛒  ML Master Seller",
            font=("Segoe UI", 18, "bold"),
            bg=BRAND_COLOR,
            fg=BRAND_DARK,
        ).pack(side="left", padx=18)

        tk.Label(
            header,
            text="Sistema de Afiliados Automático",
            font=("Segoe UI", 10),
            bg=BRAND_COLOR,
            fg=BRAND_DARK,
        ).pack(side="left")

        self._status_dot = tk.Label(
            header, text="●", font=("Segoe UI", 14),
            bg=BRAND_COLOR, fg="#888888"
        )
        self._status_dot.pack(side="right", padx=18)

        self._status_lbl = tk.Label(
            header, text="Parado",
            font=("Segoe UI", 9, "bold"),
            bg=BRAND_COLOR, fg=BRAND_DARK
        )
        self._status_lbl.pack(side="right")

        # ── Botões de ação ───────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BRAND_DARK, pady=10)
        btn_frame.pack(fill="x", padx=18)

        btn_style = dict(font=("Segoe UI", 10, "bold"), width=16,
                         relief="flat", cursor="hand2", pady=6)

        self._btn_start = tk.Button(
            btn_frame, text="▶  Iniciar Campanha",
            bg=BRAND_GREEN, fg="white",
            command=self._start_campaign, **btn_style
        )
        self._btn_start.pack(side="left", padx=(0, 8))

        self._btn_stop = tk.Button(
            btn_frame, text="■  Parar",
            bg=BRAND_RED, fg="white",
            command=self._stop_campaign, state="disabled", **btn_style
        )
        self._btn_stop.pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="🔍  Buscar Produtos",
            bg="#0984E3", fg="white",
            command=self._discover_only, **btn_style
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="📊  Exportar CSV",
            bg="#6C5CE7", fg="white",
            command=self._export_csv, **btn_style
        ).pack(side="left")

        # ── Stats cards ─────────────────────────────────────────────────
        cards_frame = tk.Frame(self, bg=BRAND_DARK)
        cards_frame.pack(fill="x", padx=18, pady=(0, 8))

        self._card_posts = self._make_card(cards_frame, "Posts Hoje", "0")
        self._card_products = self._make_card(cards_frame, "Produtos", "0")
        self._card_links = self._make_card(cards_frame, "Links Gerados", "0")
        self._card_commission = self._make_card(cards_frame, "Comissão Est.", "R$ 0,00")

        # ── Log ─────────────────────────────────────────────────────────
        log_header = tk.Frame(self, bg=BRAND_DARK)
        log_header.pack(fill="x", padx=18, pady=(4, 0))
        tk.Label(log_header, text="Log em tempo real",
                 font=("Segoe UI", 9, "bold"),
                 bg=BRAND_DARK, fg=BRAND_LIGHT).pack(side="left")
        tk.Button(log_header, text="Limpar", font=("Segoe UI", 8),
                  bg="#636E72", fg="white", relief="flat", cursor="hand2",
                  command=self._clear_log, padx=6).pack(side="right")

        self._log_box = scrolledtext.ScrolledText(
            self, font=("Consolas", 9), bg="#1E1E1E", fg="#D4D4D4",
            insertbackground="white", wrap="word", height=14,
            relief="flat", borderwidth=0
        )
        self._log_box.pack(fill="both", expand=True, padx=18, pady=(4, 14))
        self._log_box.config(state="disabled")

        # Tag de cores para diferentes níveis
        self._log_box.tag_config("INFO",    foreground="#9CDCFE")
        self._log_box.tag_config("WARNING", foreground="#DCDCAA")
        self._log_box.tag_config("ERROR",   foreground="#F44747")
        self._log_box.tag_config("SUCCESS", foreground="#4EC9B0")

    def _make_card(self, parent, label: str, value: str):
        frame = tk.Frame(parent, bg="#3D3D3D", padx=12, pady=8)
        frame.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(frame, text=label, font=("Segoe UI", 8),
                 bg="#3D3D3D", fg="#AAAAAA").pack(anchor="w")
        lbl = tk.Label(frame, text=value, font=("Segoe UI", 13, "bold"),
                       bg="#3D3D3D", fg=BRAND_YELLOW if label != "Comissão Est." else BRAND_GREEN)
        lbl.pack(anchor="w")
        return lbl

    # ------------------------------------------------------------------ #
    #  AÇÕES                                                               #
    # ------------------------------------------------------------------ #
    def _start_campaign(self):
        if self._running:
            return
        self._running = True
        self._btn_start.config(state="disabled")
        self._btn_stop.config(state="normal")
        self._set_status("Rodando", BRAND_GREEN)
        self._log_info("🚀 Iniciando campanha automática...")
        self._run_subprocess(["run_campaign"])

    def _stop_campaign(self):
        if self._process:
            self._process.terminate()
        self._running = False
        self._btn_start.config(state="normal")
        self._btn_stop.config(state="disabled")
        self._set_status("Parado", "#888888")
        self._log_info("⛔ Campanha encerrada pelo usuário.")

    def _discover_only(self):
        self._log_info("🔍 Buscando e ranqueando produtos...")
        self._run_subprocess(["products"])

    def _export_csv(self):
        self._log_info("📊 Exportando produtos para CSV...")
        self._run_subprocess(["export"])

    def _run_subprocess(self, args: list):
        """Executa main.py em thread separada e captura saída para o log."""
        def target():
            python = str(BASE_DIR / "venv" / "Scripts" / "pythonw.exe")
            if not Path(python).exists():
                python = sys.executable

            cmd = [python, str(BASE_DIR / "main.py")] + args
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(BASE_DIR),
            )
            for line in self._process.stdout:
                line = line.rstrip()
                if line:
                    self._log_queue.put(line)

            self._process.wait()
            rc = self._process.returncode
            if self._running:
                self._log_queue.put(f"[processo encerrado — código {rc}]")
                self.after(0, self._stop_campaign)

        threading.Thread(target=target, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  LOG                                                                 #
    # ------------------------------------------------------------------ #
    def _start_log_poll(self):
        """Poll da fila de logs a cada 150ms (thread-safe)."""
        self._drain_log()
        self.after(150, self._start_log_poll)

    def _drain_log(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass

    def _append_log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        tag = "INFO"
        if "ERROR" in text or "❌" in text or "Erro" in text:
            tag = "ERROR"
        elif "WARNING" in text or "⚠" in text:
            tag = "WARNING"
        elif "✅" in text or "sucesso" in text.lower() or "enviado" in text.lower():
            tag = "SUCCESS"

        self._log_box.config(state="normal")
        self._log_box.insert("end", f"[{ts}] {text}\n", tag)
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    def _log_info(self, text: str):
        self._log_queue.put(text)

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")

    # ------------------------------------------------------------------ #
    #  STATUS                                                              #
    # ------------------------------------------------------------------ #
    def _set_status(self, text: str, color: str):
        self._status_lbl.config(text=text)
        self._status_dot.config(fg=color)

    # ------------------------------------------------------------------ #
    #  FECHAR                                                              #
    # ------------------------------------------------------------------ #
    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("Sair", "A campanha está rodando. Deseja encerrar?"):
                return
        self._stop_campaign()
        self.destroy()


# Corrige referência à constante que estava indefinida
BRAND_YELLOW = BRAND_COLOR


if __name__ == "__main__":
    app = MLMasterApp()
    app.mainloop()
