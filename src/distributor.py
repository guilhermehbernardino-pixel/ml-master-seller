"""
ML MASTER AFILIADO - Distributor & Scheduler
Distribui links de afiliado pelo Telegram com timing inteligente.
Simula comportamento humano nos horários de pico de engajamento.
"""

import asyncio
import aiohttp
import json
import os
import random
import logging
import sqlite3
from datetime import datetime, time as dt_time
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger("Distributor")


# ============================================================
# HORÁRIOS DE PICO para o Brasil (engajamento máximo no Telegram)
# Baseado em estudos de comportamento de usuários BR 2024
# ============================================================
PEAK_HOURS_BR = [
    # (hora, peso) - quanto maior o peso, mais provável postar nesse horário
    (7, 3),   # Manhã cedo - commute
    (8, 4),   # Início do trabalho
    (9, 5),   # Pico manhã
    (10, 6),  # 🔥 Golden hour
    (11, 7),  # 🔥🔥 Pré-almoço
    (12, 8),  # 🔥🔥🔥 ALMOÇO - maior engajamento
    (13, 7),  # Pós-almoço
    (14, 5),  # Tarde
    (15, 4),  # Tarde
    (16, 5),  # Pré-saída
    (17, 7),  # 🔥🔥 Saída do trabalho
    (18, 8),  # 🔥🔥🔥 Maior pico do dia
    (19, 9),  # 🔥🔥🔥🔥 PICO MÁXIMO
    (20, 8),  # Noite
    (21, 7),  # Noite
    (22, 5),  # Noite tardio
]

# Posts por dia que maximizam engajamento sem spam
OPTIMAL_POSTS_PER_DAY = {
    "weekday": 8,   # Segunda a sexta
    "weekend": 5,   # Sábado e domingo (menos engajamento)
}


class TelegramDistributor:
    """Distribui posts no Telegram"""

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._posts_today = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send_message(
        self, 
        text: str, 
        image_url: Optional[str] = None,
        channel_id: Optional[str] = None
    ) -> bool:
        """Envia mensagem/post para o canal Telegram"""
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN não configurado")
            return False

        channel = channel_id or self.channel_id
        if not channel:
            logger.warning("TELEGRAM_CHANNEL_ID não configurado")
            return False

        session = await self._get_session()
        base_url = self.API_BASE.format(token=self.token)

        try:
            if image_url:
                # Envia foto com legenda
                url = f"{base_url}/sendPhoto"
                payload = {
                    "chat_id": channel,
                    "photo": image_url,
                    "caption": text[:1024],  # Limite de legenda do Telegram
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                }
            else:
                # Envia só texto
                url = f"{base_url}/sendMessage"
                payload = {
                    "chat_id": channel,
                    "text": text[:4096],
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                }

            async with session.post(url, json=payload, 
                                     timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    self._posts_today += 1
                    logger.info(f"✅ Post enviado para Telegram (#{self._posts_today} hoje)")
                    return True
                else:
                    logger.error(f"❌ Erro Telegram: {data.get('description')}")
                    return False

        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False

    async def send_product(self, product: dict, content: str) -> bool:
        """Envia um produto completo (imagem + conteúdo)"""
        thumbnail = product.get("thumbnail", "")
        
        # Tenta com imagem primeiro
        if thumbnail:
            success = await self.send_message(content, thumbnail)
            if success:
                return True
        
        # Fallback: só texto
        return await self.send_message(content)

    async def send_batch_report(self, stats: dict):
        """Envia relatório de performance para um canal admin"""
        admin_channel = os.getenv("TELEGRAM_ADMIN_CHANNEL", self.channel_id)
        
        report = f"""📊 **RELATÓRIO ML MASTER AFILIADO**
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}

📦 Produtos descobertos: {stats.get('products_found', 0)}
📤 Posts enviados: {stats.get('posts_sent', 0)}
🔗 Links gerados: {stats.get('links_generated', 0)}
👆 Cliques estimados: {stats.get('clicks_estimated', 0)}
💰 Comissão estimada: R${stats.get('commission_estimated', 0):.2f}

📈 **Meta diária:** R$1.000,00
✅ **Progresso:** {stats.get('daily_progress', 0):.1f}%
"""
        await self.send_message(report, channel_id=admin_channel)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


class SmartScheduler:
    """
    Agenda posts em horários estratégicos.
    Comportamento humano: posts irregulares, horários de pico,
    pausas nos finais de semana, variação de frequência.
    """

    def __init__(self, db_path: str = "data/scheduler.db"):
        self.db_path = db_path
        self._setup_db()

    def _setup_db(self):
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                channel TEXT,
                content_preview TEXT,
                sent_at TEXT,
                success INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                posts_sent INTEGER DEFAULT 0,
                products_found INTEGER DEFAULT 0,
                links_generated INTEGER DEFAULT 0,
                commission_estimated REAL DEFAULT 0.0
            )
        """)
        conn.commit()
        conn.close()

    def get_posts_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT posts_sent FROM daily_stats WHERE date=?", (today,)
        ).fetchone()
        conn.close()
        return row[0] if row else 0

    def get_max_posts_today(self) -> int:
        is_weekend = datetime.now().weekday() >= 5
        return OPTIMAL_POSTS_PER_DAY["weekend" if is_weekend else "weekday"]

    def can_post_now(self) -> bool:
        """Verifica se é um bom momento para postar"""
        now = datetime.now()
        hour = now.hour
        
        # Não posta entre 23h e 6h
        if hour >= 23 or hour < 7:
            return False
        
        # Verifica limite diário
        if self.get_posts_today() >= self.get_max_posts_today():
            logger.info("Limite diário de posts atingido")
            return False

        return True

    def time_until_next_post(self) -> float:
        """Retorna segundos até o próximo post ideal"""
        if not self.can_post_now():
            # Calcula quando vai poder postar novamente
            from datetime import timedelta
            now = datetime.now()
            if now.hour >= 23:
                # Espera até as 7h do próximo dia (timedelta evita bug no último dia do mês)
                next_post = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
            else:
                next_post = now.replace(hour=7, minute=0, second=0, microsecond=0)
            return (next_post - now).total_seconds()

        # Calcula próximo intervalo baseado no horário de pico atual
        posts_today = self.get_posts_today()
        max_posts = self.get_max_posts_today()
        
        if posts_today == 0:
            return random.uniform(30, 120)  # Primeiro post logo
        
        # Distribui posts restantes nas horas de pico restantes
        hours_remaining = max(1, 22 - datetime.now().hour)
        posts_remaining = max(1, max_posts - posts_today)
        base_interval = (hours_remaining * 3600) / posts_remaining
        
        # Adiciona jitter humano (±30%)
        jitter = base_interval * random.uniform(-0.3, 0.3)
        interval = max(1800, base_interval + jitter)  # Mínimo 30min
        
        return interval

    def log_post(self, product_id: str, channel: str, content_preview: str, success: bool):
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO posts_log (product_id, channel, content_preview, sent_at, success)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, channel, content_preview[:100], datetime.now().isoformat(), int(success)))
        
        if success:
            conn.execute("""
                INSERT INTO daily_stats (date, posts_sent) VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET posts_sent = posts_sent + 1
            """, (today,))
        conn.commit()
        conn.close()

    def get_stats_today(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM daily_stats WHERE date=?", (today,)
        ).fetchone()
        conn.close()
        
        if row:
            return {
                "date": row[0],
                "posts_sent": row[1],
                "products_found": row[2],
                "links_generated": row[3],
                "commission_estimated": row[4],
            }
        return {"date": today, "posts_sent": 0, "products_found": 0, 
                "links_generated": 0, "commission_estimated": 0.0}


class MasterCampaign:
    """
    Orquestra toda a campanha de afiliados.
    Integra: ProductEngine → LinkGenerator → ContentCreator → Distributor
    """

    def __init__(self):
        from src.product_engine import ProductEngine
        from src.link_generator import MLSession, AffiliateLinkGenerator
        from src.content_creator import ContentCreator

        self.product_engine = ProductEngine()
        self.ml_session = MLSession()
        self.content_creator = ContentCreator()
        self.distributor = TelegramDistributor()
        self.scheduler = SmartScheduler()
        self._running = False
        self._link_generator: Optional[object] = None

    async def initialize(self):
        """Inicializa todos os componentes"""
        logger.info("🚀 Iniciando ML MASTER AFILIADO...")

        # Tenta iniciar sessão ML com browser; falha graciosamente
        try:
            await self.ml_session.start(headless=True)
            logged_in = await self.ml_session.login()
        except Exception as e:
            logger.warning(f"⚠️ Playwright indisponível ({e.__class__.__name__}): usando links diretos")
            logged_in = False

        if logged_in:
            from src.link_generator import AffiliateLinkGenerator
            self._link_generator = AffiliateLinkGenerator(self.ml_session)
            logger.info("✅ Sessão ML ativa")
        else:
            logger.warning("⚠️ Usando modo sem autenticação ML (links simplificados)")

    async def run_cycle(self):
        """Executa um ciclo completo: descobrir → gerar links → criar conteúdo → publicar"""
        logger.info("🔄 Iniciando novo ciclo...")

        # 1. Descobre produtos
        products = await self.product_engine.discover_best_products(top_n=15, min_commission_pct=5)
        logger.info(f"📦 {len(products)} produtos descobertos")

        # 2. Gera links de afiliado
        for product in products:
            if self._link_generator:
                link = await self._link_generator.generate_link(product.url, product.id)
                if link:
                    product.affiliate_url = link
                    self.product_engine.update_affiliate_url(product.id, link)
            else:
                # Modo sem auth: link direto com ref tag
                tag = self.ml_session.affiliate_tag
                if product.id and product.id.startswith("MLB"):
                    product.affiliate_url = f"https://www.mercadolivre.com.br/p/{product.id}?ref={tag}"
                else:
                    sep = "&" if "?" in product.url else "?"
                    product.affiliate_url = f"{product.url}{sep}ref={tag}"
                self.product_engine.update_affiliate_url(product.id, product.affiliate_url)

        logger.info(f"🔗 Links gerados para {len([p for p in products if p.affiliate_url])} produtos")

        # 3. Seleciona os melhores para postar agora
        unposted = self.product_engine.get_unposted_products(limit=3)

        for product in unposted:
            if not self.scheduler.can_post_now():
                logger.info("⏸️ Aguardando janela de postagem...")
                break

            # 4. Cria conteúdo
            content = await self.content_creator.create_telegram_post(product)

            # 5. Distribui
            success = await self.distributor.send_product(product, content)

            # 6. Registra
            self.scheduler.log_post(
                product["id"],
                "telegram",
                content[:100],
                success
            )
            if success:
                self.product_engine.mark_as_posted(product["id"])

            # Delay humano entre posts
            await asyncio.sleep(random.uniform(30, 120))

        # 7. Relatório
        stats = self.scheduler.get_stats_today()
        logger.info(f"📊 Dia: {stats['posts_sent']} posts | R${stats['commission_estimated']:.2f} estimado")

    async def run_forever(self):
        """Loop principal - roda indefinidamente com scheduling inteligente"""
        self._running = True
        await self.initialize()

        logger.info("🤖 ML MASTER AFILIADO ativo. Iniciando campanha automática...")

        while self._running:
            try:
                if self.scheduler.can_post_now():
                    await self.run_cycle()
                
                # Calcula próxima execução
                wait_time = self.scheduler.time_until_next_post()
                logger.info(f"⏰ Próximo ciclo em {wait_time/60:.0f} minutos")
                await asyncio.sleep(wait_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no ciclo: {e}", exc_info=True)
                await asyncio.sleep(300)  # Espera 5min em caso de erro

    async def stop(self):
        self._running = False
        await self.ml_session.stop()
        await self.content_creator.close()
        await self.distributor.close()
        await self.product_engine.close()
        logger.info("⛔ ML MASTER AFILIADO encerrado")
