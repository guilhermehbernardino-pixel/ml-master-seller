#!/usr/bin/env python3
"""
ML MASTER SELLER — Orquestrador Principal v1.0
Ponto de entrada unificado para o sistema de afiliados.

Uso:
  python main.py            → Inicia Dashboard + bot completo
  python main.py setup      → Assistente de configuração
  python main.py test       → Teste E2E de todos os componentes
  python main.py products   → Busca e rankeia produtos (sem postar)
  python main.py export     → Exporta produtos qualificados para CSV
"""

import sys
import os

# Garante diretório correto (run.py cuida do UTF-8)
from pathlib import Path
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

from run import main, setup_wizard, discover_products, test_components
import asyncio


def export_products():
    """Exporta produtos qualificados do banco para CSV."""
    import sqlite3, csv, json
    from datetime import datetime

    os.makedirs("outputs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"outputs/produtos_qualificados_{ts}.csv"

    conn = sqlite3.connect("data/products.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, price, original_price, discount_pct,
               category_name, commission_pct, commission_value,
               url, free_shipping, is_flash_deal, score, fetched_at
        FROM products
        ORDER BY score DESC
    """).fetchall()
    conn.close()

    if not rows:
        print("[AVISO] Nenhum produto no banco. Execute 'python main.py products' primeiro.")
        return

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])

    print(f"[OK] {len(rows)} produtos exportados → {out_path}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

    if cmd == "export":
        export_products()
    else:
        # Delega para run.py (que já trata setup/test/products/start)
        sys.argv[1] = cmd if cmd != "start" else "start"
        main()
