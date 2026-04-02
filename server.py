"""
ML MASTER AFILIADO - Backend Server
FastAPI para servir o dashboard e expor endpoints de controle.
"""

import asyncio
import json
import os
import sys
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 ML MASTER AFILIADO Server iniciando...")
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    yield


app = FastAPI(title="ML Master Afiliado API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta arquivos estáticos do dashboard
if os.path.exists("dashboard"):
    app.mount("/static", StaticFiles(directory="dashboard"), name="static")

# Estado global da campanha
campaign_state = {
    "running": False,
    "initialized": False,
    "posts_today": 0,
    "revenue_today": 0.0,
    "products_in_pipeline": 0,
    "last_cycle": None,
}

campaign = None



@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve o dashboard principal"""
    with open("dashboard/index.html", encoding="utf-8") as f:
        return f.read()


@app.post("/api/run-cycle")
async def run_cycle(background_tasks: BackgroundTasks):
    """Dispara um ciclo manual de busca e publicação"""
    background_tasks.add_task(_run_cycle_task)
    return JSONResponse({"success": True, "message": "Ciclo iniciado em background"})


async def _run_cycle_task():
    """Executa o ciclo em background"""
    from src.product_engine import ProductEngine

    try:
        logger.info("🔄 Executando ciclo...")
        engine = ProductEngine()
        
        min_commission = float(os.getenv("MIN_COMMISSION", 5))
        products = await engine.discover_best_products(
            top_n=15, 
            min_commission_pct=min_commission
        )
        
        campaign_state["products_in_pipeline"] = len(products)
        campaign_state["last_cycle"] = datetime.now().isoformat()
        
        logger.info(f"✅ {len(products)} produtos no pipeline")
        await engine.close()
        
    except Exception as e:
        logger.error(f"Erro no ciclo: {e}", exc_info=True)


@app.get("/api/products")
async def get_products(limit: int = 10):
    """Retorna produtos do pipeline"""
    try:
        conn = sqlite3.connect("data/products.db")
        rows = conn.execute("""
            SELECT id, title, price, original_price, discount_pct, 
                   category_name, commission_pct, commission_value,
                   url, affiliate_url, thumbnail, is_flash_deal, score
            FROM products
            WHERE posted = 0
            ORDER BY score DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()

        products = []
        for r in rows:
            products.append({
                "id": r[0], "title": r[1], "price": r[2],
                "original_price": r[3], "discount_pct": r[4],
                "category": r[5], "comm": r[6], "commission_value": r[7],
                "url": r[8], "affiliate_url": r[9], "thumbnail": r[10],
                "flash": bool(r[11]), "score": r[12], "disc": int(r[4])
            })
        return {"products": products, "total": len(products)}
    except Exception as e:
        return {"products": [], "total": 0}


@app.get("/api/stats")
async def get_stats():
    """Retorna estatísticas do dia"""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect("data/scheduler.db")
        row = conn.execute(
            "SELECT * FROM daily_stats WHERE date=?", (today,)
        ).fetchone()
        conn.close()
        
        if row:
            return {
                "date": row[0], "posts_sent": row[1],
                "products_found": row[2], "links_generated": row[3],
                "commission_estimated": row[4],
                "goal": 1000.0,
                "progress_pct": min(row[4] / 10, 100)
            }
    except:
        pass
    
    return {
        "date": today, "posts_sent": 0, "products_found": 0,
        "links_generated": 0, "commission_estimated": 0.0,
        "goal": 1000.0, "progress_pct": 0.0
    }


@app.get("/api/status")
async def get_status():
    """Status do sistema"""
    return {
        **campaign_state,
        "timestamp": datetime.now().isoformat(),
        "ml_email": os.getenv("ML_EMAIL", "não configurado"),
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "claude_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


@app.post("/api/start")
async def start_campaign(background_tasks: BackgroundTasks):
    """Inicia a campanha automática"""
    if campaign_state["running"]:
        return {"success": False, "message": "Campanha já está rodando"}
    
    campaign_state["running"] = True
    background_tasks.add_task(_campaign_loop)
    return {"success": True, "message": "Campanha iniciada!"}


@app.post("/api/stop")
async def stop_campaign():
    """Para a campanha"""
    campaign_state["running"] = False
    return {"success": True, "message": "Campanha pausada"}


async def _campaign_loop():
    """Loop principal da campanha"""
    from src.distributor import SmartScheduler
    
    scheduler = SmartScheduler()
    logger.info("🤖 Campanha automática iniciada")
    
    while campaign_state["running"]:
        try:
            if scheduler.can_post_now():
                await _run_cycle_task()
            
            wait = scheduler.time_until_next_post()
            logger.info(f"⏰ Próximo ciclo em {wait/60:.0f}min")
            await asyncio.sleep(min(wait, 300))  # Max 5min entre checks
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erro no loop: {e}")
            await asyncio.sleep(60)
    
    logger.info("⛔ Campanha encerrada")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("DASHBOARD_PORT", 8080))
    logger.info(f"🌐 Dashboard: http://localhost:{port}")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
