"""
ML MASTER AFILIADO - Analytics Engine
Integra com o painel oficial de afiliados ML para coletar métricas reais.
Gera relatórios de performance e sugere otimizações automáticas.
"""

import asyncio
import aiohttp
import json
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from playwright.async_api import async_playwright

logger = logging.getLogger("Analytics")

# Métricas alvo para meta de R$1.000/dia
DAILY_TARGETS = {
    "revenue":     1000.0,   # R$ comissão/dia
    "clicks":      2500,     # cliques nos links
    "conversions": 50,       # vendas geradas
    "ctr":         3.0,      # % de clique nos posts
    "conv_rate":   2.0,      # % de cliques → venda
}


class MLAffiliateMetrics:
    """
    Coleta métricas reais do painel de afiliados do Mercado Livre.
    Usa Playwright para fazer login e extrair os dados do dashboard.
    """

    DASHBOARD_URL = "https://www.mercadolivre.com.br/afiliados/dashboard"

    def __init__(self, ml_session=None):
        self.session = ml_session
        self._cache: Dict = {}
        self._cache_ts: float = 0

    async def fetch_real_metrics(self, days: int = 7) -> dict:
        """
        Acessa o painel de afiliados ML e extrai as métricas reais.
        Retorna dict com clicks, conversões, receita etc.
        """
        if not self.session or not self.session._page:
            logger.warning("Sessão ML não disponível para métricas")
            return self._get_cached_or_empty()

        # Cache de 30min para não sobrecarregar
        import time
        if time.time() - self._cache_ts < 1800 and self._cache:
            return self._cache

        page = self.session._page
        try:
            date_end = datetime.now()
            date_start = date_end - timedelta(days=days)
            
            url = (f"{self.DASHBOARD_URL}?"
                   f"filter_time_range={date_start.strftime('%Y-%m-%d')}T00:00:00.000-03:00"
                   f"--{date_end.strftime('%Y-%m-%d')}T23:59:59.000-03:00")
            
            logger.info("📊 Coletando métricas reais do painel ML...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Extrai via JavaScript — adapte os seletores se o ML mudar o layout
            metrics = await page.evaluate("""
                () => {
                    const getText = (sel) => {
                        const el = document.querySelector(sel);
                        return el ? el.textContent.trim() : '0';
                    };
                    const parseNum = (s) => {
                        if (!s) return 0;
                        return parseFloat(s.replace(/[^0-9,.]/g,'').replace(',','.')) || 0;
                    };
                    
                    // Tenta extrair via API calls interceptadas
                    const metrics = {
                        clicks: parseNum(getText('[data-testid="clicks-value"]') || 
                                          getText('.metric-clicks .value') || '0'),
                        conversions: parseNum(getText('[data-testid="conversions-value"]') ||
                                              getText('.metric-conversions .value') || '0'),
                        revenue: parseNum(getText('[data-testid="revenue-value"]') ||
                                          getText('.metric-revenue .value') || '0'),
                        ctr: parseNum(getText('[data-testid="ctr-value"]') || '0'),
                        raw_html_length: document.body.innerHTML.length,
                    };
                    return metrics;
                }
            """)

            if metrics and metrics.get("raw_html_length", 0) > 1000:
                metrics.pop("raw_html_length", None)
                metrics["period_days"] = days
                metrics["fetched_at"] = datetime.now().isoformat()
                self._cache = metrics
                self._cache_ts = time.time()
                logger.info(f"✅ Métricas obtidas: {metrics}")
                self._save_metrics(metrics)
                return metrics

        except Exception as e:
            logger.error(f"Erro ao coletar métricas: {e}")

        return self._get_cached_or_empty()

    def _get_cached_or_empty(self) -> dict:
        if self._cache:
            return self._cache
        return {
            "clicks": 0, "conversions": 0, "revenue": 0.0,
            "ctr": 0.0, "period_days": 7,
            "fetched_at": datetime.now().isoformat()
        }

    def _save_metrics(self, metrics: dict):
        """Salva métricas no banco local para histórico"""
        conn = sqlite3.connect("data/analytics.db")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                clicks INTEGER,
                conversions INTEGER,
                revenue REAL,
                ctr REAL,
                fetched_at TEXT
            )
        """)
        conn.execute("""
            INSERT INTO metrics_history (date, clicks, conversions, revenue, ctr, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d"),
            metrics.get("clicks", 0),
            metrics.get("conversions", 0),
            metrics.get("revenue", 0),
            metrics.get("ctr", 0),
            metrics.get("fetched_at", "")
        ))
        conn.commit()
        conn.close()


class PerformanceAnalyzer:
    """
    Analisa performance e sugere otimizações automáticas.
    """

    def __init__(self, db_path: str = "data/products.db"):
        self.db_path = db_path

    def get_top_categories(self, days: int = 7) -> List[dict]:
        """Retorna as categorias com melhor ROI nos últimos N dias"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT 
                category_name,
                COUNT(*) as total_posted,
                AVG(commission_pct) as avg_commission,
                SUM(commission_value) as total_commission_est,
                AVG(discount_pct) as avg_discount
            FROM products
            WHERE posted = 1
            AND posted_at >= datetime('now', ?)
            GROUP BY category_name
            ORDER BY total_commission_est DESC
        """, (f"-{days} days",)).fetchall()
        conn.close()

        return [
            {
                "category": r[0], "posts": r[1],
                "avg_commission": round(r[2], 1),
                "revenue_est": round(r[3], 2),
                "avg_discount": round(r[4], 1)
            }
            for r in rows
        ]

    def get_best_products(self, limit: int = 10) -> List[dict]:
        """Produtos com melhor score já postados"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT title, price, commission_pct, commission_value, score, category_name
            FROM products
            WHERE posted = 1
            ORDER BY score DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [
            {"title": r[0][:50], "price": r[1], "commission_pct": r[2],
             "commission_value": r[3], "score": r[4], "category": r[5]}
            for r in rows
        ]

    def calculate_daily_estimate(self) -> dict:
        """Estima receita do dia baseado nos posts realizados"""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        
        # Posts do dia
        row = conn.execute("""
            SELECT COUNT(*), SUM(commission_value), AVG(commission_pct)
            FROM products
            WHERE posted = 1
            AND posted_at >= ?
        """, (today,)).fetchone()
        conn.close()

        posts = row[0] or 0
        commission_est = row[1] or 0.0
        avg_comm = row[2] or 0.0

        # Estimativa baseada em CTR médio de 3% e conversão de 2%
        # Assumindo 500 membros por canal em média
        avg_reach = 2000  # impressões por post
        estimated_clicks = posts * avg_reach * 0.03
        estimated_conversions = estimated_clicks * 0.02
        
        # Ticket médio estimado por categoria (comissão de volta ao valor)
        avg_ticket = 150.0  # R$ ticket médio conservador
        estimated_revenue = estimated_conversions * avg_ticket * (avg_comm / 100)

        return {
            "posts_today": posts,
            "commission_estimate": round(estimated_revenue, 2),
            "clicks_estimate": int(estimated_clicks),
            "conversions_estimate": int(estimated_conversions),
            "progress_pct": round((estimated_revenue / 1000) * 100, 1),
            "projected_monthly": round(estimated_revenue * 30, 2),
        }

    def generate_recommendations(self, metrics: dict) -> List[str]:
        """Gera recomendações automáticas baseadas na performance"""
        recs = []

        revenue = metrics.get("revenue", 0)
        clicks = metrics.get("clicks", 0)
        conv_rate = (metrics.get("conversions", 0) / max(clicks, 1)) * 100

        if revenue < DAILY_TARGETS["revenue"] * 0.3:
            recs.append("🚨 CRÍTICO: Receita muito abaixo da meta. Aumente a frequência de posts e foque em categorias 16%.")

        if clicks < DAILY_TARGETS["clicks"] * 0.5:
            recs.append("📉 Poucos cliques. Revise o conteúdo dos posts — títulos mais chamativos e emojis estratégicos aumentam CTR.")

        if conv_rate < DAILY_TARGETS["conv_rate"]:
            recs.append("🎯 Taxa de conversão baixa. Priorize produtos com maior desconto (40%+) e ofertas relâmpago.")

        if revenue > DAILY_TARGETS["revenue"] * 0.8:
            recs.append("🔥 Quase na meta! Aumente posts nas próximas 2h para ultrapassar R$1.000 hoje.")

        if not recs:
            recs.append("✅ Performance dentro do esperado. Continue com a estratégia atual.")

        return recs


class ReportGenerator:
    """Gera relatórios completos de performance"""

    def __init__(self):
        self.analyzer = PerformanceAnalyzer()

    def daily_report(self) -> str:
        """Gera relatório diário formatado para Telegram/WhatsApp"""
        estimate = self.analyzer.calculate_daily_estimate()
        top_cats = self.analyzer.get_top_categories(7)
        best = self.analyzer.get_best_products(3)

        top_cats_txt = ""
        for c in top_cats[:3]:
            top_cats_txt += f"  • {c['category']}: {c['posts']} posts | {c['avg_commission']}% COM\n"

        best_txt = ""
        for p in best[:3]:
            best_txt += f"  • {p['title'][:35]}... [+{p['commission_pct']}%]\n"

        report = f"""📊 RELATÓRIO DIÁRIO — {datetime.now().strftime('%d/%m/%Y')}

💰 Comissão estimada: R${estimate['commission_estimate']:.2f}
📈 Meta (R$1.000): {estimate['progress_pct']:.1f}%
📤 Posts hoje: {estimate['posts_today']}
👆 Cliques estimados: {estimate['clicks_estimate']:,}
🛒 Vendas estimadas: {estimate['conversions_estimate']}

📁 TOP CATEGORIAS (7 dias):
{top_cats_txt or '  Sem dados ainda'}

🏆 MELHORES PRODUTOS:
{best_txt or '  Sem dados ainda'}

🗓️ Projeção mensal: R${estimate['projected_monthly']:,.2f}"""

        return report

    def save_report(self, report: str, filename: str = None):
        """Salva o relatório em arquivo"""
        os.makedirs("logs", exist_ok=True)
        if not filename:
            filename = f"logs/report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"📄 Relatório salvo: {filename}")
        return filename


# Teste
if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()
    gen = ReportGenerator()
    
    print("=== RELATÓRIO DIÁRIO ===")
    print(gen.daily_report())
    
    print("\n=== ESTIMATIVA HOJE ===")
    est = analyzer.calculate_daily_estimate()
    for k, v in est.items():
        print(f"  {k}: {v}")
