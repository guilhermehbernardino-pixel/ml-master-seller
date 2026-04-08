#!/usr/bin/env python3
"""
Campaign runner — executado pelo launcher.py como subprocess.
Roda MasterCampaign.run_forever() com logs em stdout.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Força UTF-8 no Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Log vai para stdout para o launcher capturar
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
    force=True,
)

CMD = sys.argv[1] if len(sys.argv) > 1 else "campaign"


async def run_campaign():
    from src.distributor import MasterCampaign
    campaign = MasterCampaign()
    try:
        await campaign.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        await campaign.stop()


async def run_products():
    from src.product_engine import ProductEngine
    engine = ProductEngine()
    products = await engine.discover_best_products(top_n=20)
    for i, p in enumerate(products[:15], 1):
        print(f"{i:2}. [{p.commission_pct:.0f}%] R${p.price:.0f} | -{p.discount_pct:.0f}% | {p.title[:50]}")
    print(f"\n✅ {len(products)} produtos encontrados e salvos.")
    await engine.close()


if CMD == "campaign":
    asyncio.run(run_campaign())
elif CMD == "products":
    asyncio.run(run_products())
