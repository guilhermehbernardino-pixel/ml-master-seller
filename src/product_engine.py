"""
ML MASTER AFILIADO - Product Discovery Engine
Encontra os melhores produtos para divulgação com base em:
- Comissão máxima por categoria
- Volume de vendas / popularidade
- Desconto e urgência (oferta relâmpago)
- Ticket médio para maximizar comissão absoluta
"""

import asyncio
import aiohttp
import json
import random
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import sqlite3
import os

logger = logging.getLogger("ProductEngine")

# ============================================================
# TABELA DE COMISSÕES POR CATEGORIA (atualizada 2025)
# Fonte: programa oficial ML Afiliados
# ============================================================
COMMISSION_TABLE = {
    "MLB1430": {"name": "Beleza e Cuidados Pessoais", "commission": 16.0},
    "MLB1276": {"name": "Calçados, Roupas e Bolsas",  "commission": 16.0},
    "MLB1281": {"name": "Esportes e Fitness",          "commission": 16.0},
    "MLB1182": {"name": "Ferramentas e Construção",    "commission": 12.0},
    "MLB1574": {"name": "Casa, Móveis e Decoração",    "commission": 12.0},
    "MLB1367": {"name": "Bebês",                       "commission": 12.0},
    "MLB1953": {"name": "Animais",                     "commission": 10.0},
    "MLB1144": {"name": "Acessórios para Veículos",    "commission": 8.0},
    "MLB1499": {"name": "Informática",                 "commission": 7.0},
    "MLB1051": {"name": "Celulares e Smartphones",     "commission": 7.0},
    "MLB1000": {"name": "Eletrônicos",                 "commission": 5.0},
}

# Categorias ordenadas por comissão (melhores primeiro)
PRIORITY_CATEGORIES = sorted(
    COMMISSION_TABLE.items(),
    key=lambda x: x[1]["commission"],
    reverse=True
)

# ============================================================
# URLs da API ML
# ============================================================
ML_SEARCH_URL     = "https://api.mercadolibre.com/sites/MLB/search"
ML_OFFERS_URL     = "https://api.mercadolibre.com/sites/MLB/search"
ML_ITEM_URL       = "https://api.mercadolibre.com/items/{item_id}"
ML_TRENDING_URL   = "https://api.mercadolibre.com/trends/MLB"
ML_HIGHLIGHTS_URL = "https://api.mercadolibre.com/highlights/MLB/category/{category_id}"
ML_PRODUCT_URL    = "https://api.mercadolibre.com/products/{product_id}"
ML_PROD_ITEMS_URL = "https://api.mercadolibre.com/products/{product_id}/items"


@dataclass
class Product:
    """Representa um produto para divulgação"""
    id: str
    title: str
    price: float
    original_price: float
    discount_pct: float
    category_id: str
    category_name: str
    commission_pct: float
    commission_value: float
    url: str
    affiliate_url: str = ""
    thumbnail: str = ""
    sold_quantity: int = 0
    rating: float = 0.0
    reviews: int = 0
    free_shipping: bool = False
    is_flash_deal: bool = False
    seller_reputation: str = ""
    score: float = 0.0
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__

    @property
    def roi_score(self) -> float:
        """Score composto para priorização"""
        commission_weight = self.commission_pct * 2
        discount_weight = self.discount_pct * 1.5
        popularity_weight = min(self.sold_quantity / 100, 10)
        flash_bonus = 5 if self.is_flash_deal else 0
        shipping_bonus = 2 if self.free_shipping else 0
        ticket_weight = min(self.price / 100, 5)  # até 5 pontos para ticket alto
        return commission_weight + discount_weight + popularity_weight + flash_bonus + shipping_bonus + ticket_weight


ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class MLTokenManager:
    """
    Gerencia o access_token da API ML via OAuth2 (client_credentials).
    Registro gratuito em: https://developers.mercadolivre.com.br/
    """

    def __init__(self):
        self.client_id = os.getenv("ML_CLIENT_ID", "")
        self.client_secret = os.getenv("ML_CLIENT_SECRET", "")
        self._token: str = ""
        self._token_expires: float = 0.0

    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def get_token(self, session: aiohttp.ClientSession) -> str:
        """Retorna access_token válido, renovando automaticamente se expirado."""
        if self._token and time.time() < self._token_expires - 300:
            return self._token

        if not self.has_credentials():
            return ""

        try:
            async with session.post(
                ML_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._token = data.get("access_token", "")
                    expires_in = data.get("expires_in", 21600)
                    self._token_expires = time.time() + expires_in
                    logger.info("Token ML obtido com sucesso")
                    return self._token
                else:
                    body = await resp.text()
                    logger.error(f"Falha ao obter token ML ({resp.status}): {body[:120]}")
        except Exception as e:
            logger.error(f"Erro ao obter token ML: {e}")
        return ""


class ProductEngine:
    """Motor de descoberta de produtos para afiliados ML"""

    def __init__(self, db_path: str = "data/products.db"):
        self.db_path = db_path
        self.session: Optional[aiohttp.ClientSession] = None
        self._token_manager = MLTokenManager()
        self._setup_db()
        self._request_count = 0
        self._last_request_time = 0

    def _setup_db(self):
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                title TEXT,
                price REAL,
                original_price REAL,
                discount_pct REAL,
                category_id TEXT,
                category_name TEXT,
                commission_pct REAL,
                commission_value REAL,
                url TEXT,
                affiliate_url TEXT,
                thumbnail TEXT,
                sold_quantity INTEGER,
                rating REAL,
                reviews INTEGER,
                free_shipping INTEGER,
                is_flash_deal INTEGER,
                score REAL,
                fetched_at TEXT,
                posted INTEGER DEFAULT 0,
                posted_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                date TEXT PRIMARY KEY,
                products_found INTEGER,
                products_posted INTEGER,
                clicks INTEGER,
                conversions INTEGER,
                revenue REAL
            )
        """)
        conn.commit()
        conn.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Accept-Language": "pt-BR,pt;q=0.9",
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def _auth_headers(self) -> dict:
        """Retorna headers com Authorization se o token estiver disponível."""
        session = await self._get_session()
        token = await self._token_manager.get_token(session)
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    async def _human_delay(self):
        """Delay humano entre requisições"""
        now = time.time()
        elapsed = now - self._last_request_time
        min_delay = random.uniform(0.5, 1.5)
        if elapsed < min_delay:
            await asyncio.sleep(min_delay - elapsed + random.uniform(0, 0.5))
        self._last_request_time = time.time()
        self._request_count += 1

    async def _search_category(
        self,
        category_id: str,
        sort: str = "sold_quantity_desc",
        limit: int = 20,
        flash_only: bool = False
    ) -> List[dict]:
        """Busca produtos via highlights + products API (substitui search bloqueado)"""
        await self._human_delay()
        session = await self._get_session()
        auth = await self._auth_headers()

        # 1. Pega os destaques da categoria
        highlights_url = ML_HIGHLIGHTS_URL.format(category_id=category_id)
        try:
            async with session.get(highlights_url, headers=auth,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"Highlights retornou {resp.status} para {category_id}")
                    return []
                highlights = await resp.json()
        except Exception as e:
            logger.error(f"Erro ao buscar highlights {category_id}: {e}")
            return []

        # 2. Extrai IDs de produtos do catálogo
        catalog_ids = [
            x["id"] for x in highlights.get("content", [])
            if x.get("type") == "PRODUCT"
        ][:limit]

        if not catalog_ids:
            return []

        # 3. Para cada produto, busca detalhes + item com melhor preço em paralelo
        results = []
        for prod_id in catalog_ids:
            await self._human_delay()
            try:
                prod_url = ML_PRODUCT_URL.format(product_id=prod_id)
                items_url = ML_PROD_ITEMS_URL.format(product_id=prod_id)

                async with session.get(prod_url, headers=auth,
                                       timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status != 200:
                        continue
                    prod = await r.json()

                async with session.get(items_url, headers=auth,
                                       timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status != 200:
                        continue
                    items_data = await r.json()

                item_results = items_data.get("results", [])
                if not item_results:
                    continue

                # Usa o item com menor preço
                best = min(item_results, key=lambda x: x.get("price") or 999999)
                price = best.get("price") or 0
                original = best.get("original_price") or price

                pics = prod.get("pictures", [])
                thumbnail = pics[0].get("url", "") if pics else ""

                results.append({
                    "id": prod.get("catalog_product_id", prod_id),
                    "title": prod.get("name", "")[:200],
                    "price": price,
                    "original_price": original,
                    "category_id": category_id,
                    "permalink": prod.get("permalink") or f"https://www.mercadolivre.com.br/p/{prod_id}",
                    "thumbnail": thumbnail,
                    "sold_quantity": 0,
                    "tags": prod.get("tags", []),
                    "shipping": best.get("shipping", {}),
                    "seller": {},
                })
            except Exception as e:
                logger.debug(f"Erro ao buscar produto {prod_id}: {e}")
                continue

        return results

    async def _search_offers(self, limit: int = 50) -> List[dict]:
        """Ofertas relâmpago — endpoint indisponível, retorna vazio"""
        return []

    def _parse_product(self, item: dict) -> Optional[Product]:
        """Converte resultado da API em objeto Product"""
        try:
            item_id = item.get("id", "")
            price = float(item.get("price", 0))
            original = float(item.get("original_price") or price)
            discount = round(((original - price) / original) * 100, 1) if original > price else 0

            category_id = item.get("category_id", "")
            cat_info = COMMISSION_TABLE.get(category_id, {"name": "Outros", "commission": 5.0})
            commission_pct = cat_info["commission"]
            commission_value = round(price * commission_pct / 100, 2)

            # Filtra produtos sem comissão relevante
            if commission_value < 1.0:
                return None

            shipping = item.get("shipping", {})
            attributes = item.get("attributes", [])
            
            # Detecta oferta relâmpago
            tags = item.get("tags", [])
            is_flash = "deal_of_the_day" in tags or "good_deal" in tags

            # Reputação do vendedor
            seller = item.get("seller", {})
            rep = seller.get("seller_reputation", {})
            rep_level = rep.get("level_id", "") if rep else ""

            product = Product(
                id=item_id,
                title=item.get("title", "")[:200],
                price=price,
                original_price=original,
                discount_pct=discount,
                category_id=category_id,
                category_name=cat_info["name"],
                commission_pct=commission_pct,
                commission_value=commission_value,
                url=item.get("permalink", f"https://www.mercadolivre.com.br/p/{item_id}"),
                thumbnail=item.get("thumbnail", "").replace("I.jpg", "O.jpg"),
                sold_quantity=item.get("sold_quantity", 0),
                free_shipping=shipping.get("free_shipping", False),
                is_flash_deal=is_flash,
                seller_reputation=rep_level,
            )
            product.score = product.roi_score
            return product
        except Exception as e:
            logger.debug(f"Erro ao parsear produto: {e}")
            return None

    async def discover_best_products(
        self,
        top_n: int = 20,
        min_commission_pct: float = 5.0,
        min_discount: float = 10.0
    ) -> List[Product]:
        """
        Descobre os melhores produtos para divulgação.
        Estratégia multicamada:
        1. Alta comissão (Beleza, Roupas, Esportes - 16%)
        2. Ofertas relâmpago (urgência = maior CTR)
        3. Mais vendidos por categoria
        """
        logger.info("🔍 Iniciando descoberta de produtos...")
        all_products: List[Product] = []

        # Layer 1: Categorias de alta comissão (top 5)
        for cat_id, cat_info in PRIORITY_CATEGORIES[:5]:
            items = await self._search_category(cat_id, sort="sold_quantity_desc", limit=15)
            for item in items:
                p = self._parse_product(item)
                if p and p.commission_pct >= min_commission_pct:
                    all_products.append(p)
            logger.info(f"  ✅ {cat_info['name']}: {len(items)} produtos ({cat_info['commission']}% comissão)")
            await asyncio.sleep(random.uniform(0.3, 0.8))

        # Layer 2: Ofertas relâmpago (urgência + desconto)
        flash_items = await self._search_offers(limit=30)
        flash_count = 0
        for item in flash_items:
            p = self._parse_product(item)
            if p and p.commission_pct >= min_commission_pct:
                p.is_flash_deal = True
                p.score += 5  # bônus por urgência
                all_products.append(p)
                flash_count += 1
        logger.info(f"  ⚡ Ofertas relâmpago: {flash_count} produtos")

        # Layer 3: Deduplicação e rankeamento
        seen_ids = set()
        unique = []
        for p in all_products:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                unique.append(p)

        # Aplica filtros mínimos
        filtered = [
            p for p in unique
            if p.discount_pct >= min_discount or p.commission_pct >= 12
        ]

        # Ordena por score ROI
        filtered.sort(key=lambda x: x.score, reverse=True)
        best = filtered[:top_n]

        # Salva no banco
        self._save_products(best)
        logger.info(f"📦 {len(best)} produtos selecionados (de {len(unique)} únicos)")
        return best

    def _save_products(self, products: List[Product]):
        conn = sqlite3.connect(self.db_path)
        for p in products:
            conn.execute("""
                INSERT OR REPLACE INTO products 
                (id, title, price, original_price, discount_pct, category_id, category_name,
                 commission_pct, commission_value, url, affiliate_url, thumbnail, sold_quantity,
                 free_shipping, is_flash_deal, score, fetched_at, posted)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    COALESCE((SELECT posted FROM products WHERE id=?), 0))
            """, (
                p.id, p.title, p.price, p.original_price, p.discount_pct,
                p.category_id, p.category_name, p.commission_pct, p.commission_value,
                p.url, p.affiliate_url, p.thumbnail, p.sold_quantity,
                int(p.free_shipping), int(p.is_flash_deal), p.score, p.fetched_at, p.id
            ))
        conn.commit()
        conn.close()

    def get_unposted_products(self, limit: int = 5) -> List[dict]:
        """Retorna produtos ainda não postados, ordenados por score"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT * FROM products 
            WHERE posted = 0 AND affiliate_url != ''
            ORDER BY score DESC, is_flash_deal DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        cols = ["id","title","price","original_price","discount_pct","category_id",
                "category_name","commission_pct","commission_value","url","affiliate_url",
                "thumbnail","sold_quantity","rating","reviews","free_shipping","is_flash_deal",
                "score","fetched_at","posted","posted_at"]
        return [dict(zip(cols, r)) for r in rows]

    def mark_as_posted(self, product_id: str):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE products SET posted=1, posted_at=? WHERE id=?",
            (datetime.now().isoformat(), product_id)
        )
        conn.commit()
        conn.close()

    def update_affiliate_url(self, product_id: str, affiliate_url: str):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE products SET affiliate_url=? WHERE id=?",
            (affiliate_url, product_id)
        )
        conn.commit()
        conn.close()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# Teste rápido
if __name__ == "__main__":
    async def main():
        engine = ProductEngine()
        products = await engine.discover_best_products(top_n=10)
        for p in products[:5]:
            print(f"[{p.commission_pct}%] R${p.price:.0f} | -{p.discount_pct:.0f}% | Score:{p.score:.1f} | {p.title[:60]}")
        await engine.close()
    asyncio.run(main())
