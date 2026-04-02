"""
ML MASTER AFILIADO - Content Creator
Usa Claude API para criar conteúdo viral e persuasivo para cada produto.
Adapta o tom e formato para o canal de distribuição (Telegram, WhatsApp, etc.)
"""

import os
import json
import random
import logging
import asyncio
import aiohttp
from typing import Optional

logger = logging.getLogger("ContentCreator")

# Templates de prompt para diferentes estilos de post
CONTENT_STYLES = {
    "urgencia": "Com urgência máxima, destacando tempo limitado e escassez",
    "beneficio": "Focado nos benefícios práticos do produto para o dia a dia",  
    "economia": "Destacando quanto o comprador vai economizar em reais",
    "trending": "Estilo de post viral das redes sociais, com emojis estratégicos",
    "autoridade": "Como um especialista recomendando com base em qualidade",
}

TELEGRAM_SYSTEM_PROMPT = """Você é o MASTER VENDEDOR - o melhor copywriter de afiliados do Brasil.
Crie posts altamente persuasivos para Telegram que geram CLIQUES e VENDAS.

REGRAS DE OURO:
1. Comece sempre com emojis chamativos
2. Destaque o DESCONTO em percentual e reais economizados
3. Mencione FRETE GRÁTIS quando disponível (isso dobra CTR)
4. Use URGÊNCIA real: "Oferta por tempo limitado", "Estoque acabando"
5. Finalize com call-to-action forte: "👆 PEGAR OFERTA AGORA"
6. Máximo 300 caracteres no texto principal
7. Use formatação Markdown do Telegram: **negrito**, _itálico_
8. Não mencione que é afiliado, apenas recomende naturalmente
9. Tom: animado, confiante, de amigo que está avisando de uma oportunidade

ESTRUTURA IDEAL:
🔥 [Emoji produto] **NOME CURTO**
💰 De R$XXX por apenas R$XXX (-XX%)
[Frete se grátis]
⚡ [Benefício principal em 1 linha]
🕐 [Urgência]

[link]

[Hashtags relevantes]"""

WHATSAPP_SYSTEM_PROMPT = """Você é o MASTER VENDEDOR - especialista em vendas via WhatsApp.
Crie mensagens conversacionais que parecem de um amigo avisando de uma oferta incrível.

REGRAS:
1. Tom de conversa informal, como uma mensagem de amigo
2. Comece com algo que captura atenção imediata
3. Destaque a economia em reais (quanto vai economizar)
4. Seja direto e breve (máximo 150 palavras)
5. Use emojis moderadamente
6. Finalize com CTA simples: "Cola o link no ML e aproveita!"
7. Pareça genuíno, não robótico"""


class ContentCreator:
    """Cria conteúdo viral para posts de afiliado"""

    ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._post_count = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _call_claude(self, system: str, user_message: str) -> Optional[str]:
        """Chama a Claude API para geração de conteúdo"""
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY não configurada, usando template padrão")
            return None

        session = await self._get_session()
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key,
        }
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        }
        try:
            async with session.post(self.ANTHROPIC_API, json=body, headers=headers, 
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["content"][0]["text"]
                else:
                    logger.error(f"Claude API erro {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Erro ao chamar Claude: {e}")
            return None

    def _format_price(self, price: float) -> str:
        return f"R${price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _get_savings(self, price: float, original: float) -> str:
        savings = original - price
        return self._format_price(savings)

    def _build_product_context(self, product: dict) -> str:
        """Monta contexto do produto para o prompt"""
        ctx = f"""
PRODUTO: {product['title']}
PREÇO ATUAL: {self._format_price(product['price'])}
PREÇO ORIGINAL: {self._format_price(product['original_price'])}
DESCONTO: {product['discount_pct']:.0f}%
ECONOMIA: {self._get_savings(product['price'], product['original_price'])}
CATEGORIA: {product['category_name']}
FRETE GRÁTIS: {'SIM ✅' if product.get('free_shipping') else 'NÃO'}
OFERTA RELÂMPAGO: {'SIM ⚡' if product.get('is_flash_deal') else 'NÃO'}
LINK AFILIADO: {product.get('affiliate_url', product['url'])}
"""
        return ctx.strip()

    async def create_telegram_post(self, product: dict) -> str:
        """Cria post otimizado para Telegram"""
        style = random.choice(list(CONTENT_STYLES.items()))
        product_ctx = self._build_product_context(product)
        
        user_msg = f"""Crie um post para Telegram no estilo: {style[1]}

{product_ctx}

O post deve incluir o link de afiliado no final.
Use Markdown do Telegram para formatação."""

        # Tenta usar Claude
        ai_content = await self._call_claude(TELEGRAM_SYSTEM_PROMPT, user_msg)
        
        if ai_content:
            self._post_count += 1
            return ai_content
        
        # Fallback: template manual
        return self._telegram_template(product)

    def _telegram_template(self, product: dict) -> str:
        """Template de fallback para post no Telegram"""
        title = product['title'][:50]
        price = self._format_price(product['price'])
        original = self._format_price(product['original_price'])
        discount = int(product['discount_pct'])
        savings = self._get_savings(product['price'], product['original_price'])
        url = product.get('affiliate_url') or product['url']
        
        shipping = "🚚 **FRETE GRÁTIS!**\n" if product.get('free_shipping') else ""
        flash = "⚡ **OFERTA RELÂMPAGO** — Corre!\n" if product.get('is_flash_deal') else ""
        
        emojis = ["🔥", "💥", "🎯", "⭐", "🏆", "💎", "🚀", "✅"]
        emoji = random.choice(emojis)
        
        cat_emojis = {
            "Beleza": "💄", "Roupas": "👗", "Calçados": "👟", 
            "Esportes": "💪", "Casa": "🏠", "Eletrônicos": "📱",
            "Informática": "💻", "Bebês": "👶", "Animais": "🐾",
        }
        cat_emoji = next((v for k, v in cat_emojis.items() 
                          if k.lower() in product['category_name'].lower()), "🛍️")

        template = f"""{emoji} {cat_emoji} **OFERTA IMPERDÍVEL!**

🛒 {title}...
💰 ~~{original}~~ por apenas **{price}**
📉 **{discount}% OFF** — Economia de **{savings}**
{shipping}{flash}
👉 Garante o seu aqui: {url}

#oferta #desconto #mercadolivre #compras"""

        return template

    async def create_whatsapp_message(self, product: dict) -> str:
        """Cria mensagem para WhatsApp"""
        product_ctx = self._build_product_context(product)
        
        user_msg = f"""Crie uma mensagem curta e natural de WhatsApp para esse produto:

{product_ctx}

Máximo 120 palavras. Tom de amigo avisando de oferta."""

        ai_content = await self._call_claude(WHATSAPP_SYSTEM_PROMPT, user_msg)
        
        if ai_content:
            return ai_content
        
        return self._whatsapp_template(product)

    def _whatsapp_template(self, product: dict) -> str:
        title = product['title'][:40]
        price = self._format_price(product['price'])
        discount = int(product['discount_pct'])
        savings = self._get_savings(product['price'], product['original_price'])
        url = product.get('affiliate_url') or product['url']
        
        shipping = " + frete grátis!" if product.get('free_shipping') else ""
        
        templates = [
            f"Ei, olha essa oferta que achei no ML! 👀\n{title}... por {price} ({discount}% OFF{shipping})\nEconomia de {savings}!\n{url}",
            f"🔥 Corre que achou uma oferta boa!\n{title[:35]} por apenas {price} (-{discount}%)\n{savings} de desconto{shipping}\n{url}",
            f"Para quem estava precisando de {title[:30]}...\nMercado Livre tá com {discount}% OFF por {price}!\n{url}",
        ]
        return random.choice(templates)

    async def create_seo_description(self, product: dict) -> str:
        """Cria descrição SEO para blog/site"""
        product_ctx = self._build_product_context(product)
        system = """Você é um especialista em SEO e copywriting de e-commerce.
Crie um parágrafo curto (80-120 palavras) otimizado para SEO que descreve 
e recomenda o produto, incluindo palavras-chave naturais."""
        
        ai_content = await self._call_claude(system, f"Descreva e recomende este produto:\n{product_ctx}")
        return ai_content or f"Aproveite esta oferta imperdível: {product['title']}"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# Teste
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    async def main():
        creator = ContentCreator()
        
        # Produto de teste
        product = {
            "id": "MLB001",
            "title": "Monitor Gamer LG UltraGear 34 polegadas 2K 160Hz",
            "price": 1998.90,
            "original_price": 2839.99,
            "discount_pct": 29.6,
            "category_name": "Informática",
            "free_shipping": True,
            "is_flash_deal": False,
            "commission_pct": 7,
            "affiliate_url": "https://meli.la/2JYyLQJ",
            "url": "https://www.mercadolivre.com.br/...",
        }
        
        print("=== POST TELEGRAM ===")
        post = await creator.create_telegram_post(product)
        print(post)
        
        print("\n=== MENSAGEM WHATSAPP ===")
        msg = await creator.create_whatsapp_message(product)
        print(msg)
        
        await creator.close()
    
    asyncio.run(main())
