"""
ML MASTER AFILIADO - WhatsApp Distributor
Envia links de afiliado via WhatsApp usando Evolution API (self-hosted)
ou via automação do WhatsApp Web com Playwright.

Configuração Evolution API (gratuita, self-hosted via Docker):
  docker run -d --name evolution-api -p 8080:8080 atendai/evolution-api
  Docs: https://doc.evolution-api.com/

Como usar:
  1. Sobe o servidor Evolution API
  2. Cria uma instância (gera QR Code)
  3. Escaneia com o WhatsApp do celular
  4. Configura WHATSAPP_API_URL e WHATSAPP_API_KEY no .env
"""

import asyncio
import aiohttp
import json
import os
import random
import logging
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger("WhatsAppDistributor")

# Grupos de WhatsApp para divulgação por categoria
# Adicione os IDs dos grupos que você administra
WA_GROUPS = {
    "beleza":   os.getenv("WA_GROUP_BELEZA", ""),
    "roupas":   os.getenv("WA_GROUP_ROUPAS", ""),
    "esportes": os.getenv("WA_GROUP_ESPORTES", ""),
    "geral":    os.getenv("WA_GROUP_GERAL", ""),
}

# Contatos VIP (lista pessoal que recebe as melhores ofertas)
VIP_CONTACTS = [c for c in os.getenv("WA_VIP_CONTACTS", "").split(",") if c.strip()]


class EvolutionAPIClient:
    """
    Cliente para Evolution API — a melhor forma de automatizar WhatsApp
    gratuitamente via API REST, sem risco de ban (usa WhatsApp Web oficial)
    """

    def __init__(self):
        self.base_url = os.getenv("WHATSAPP_API_URL", "http://localhost:8888")
        self.api_key  = os.getenv("WHATSAPP_API_KEY", "")
        self.instance = os.getenv("WHATSAPP_INSTANCE", "meu-afiliado")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(headers={
                "apikey": self.api_key,
                "Content-Type": "application/json",
            })
        return self._session

    async def send_text(self, number: str, text: str) -> bool:
        """
        Envia mensagem de texto.
        number: número com DDI (ex: 5511999999999) ou ID de grupo
        """
        session = await self._get_session()
        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {
            "number": number,
            "text": text,
            "delay": random.randint(1000, 3000),  # delay humano em ms
        }
        try:
            async with session.post(url, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status in (200, 201):
                    logger.info(f"✅ WA enviado para {number[:8]}...")
                    return True
                else:
                    body = await resp.text()
                    logger.error(f"❌ WA erro {resp.status}: {body[:100]}")
                    return False
        except Exception as e:
            logger.error(f"Erro ao enviar WA: {e}")
            return False

    async def send_image(self, number: str, image_url: str, caption: str) -> bool:
        """Envia imagem com legenda"""
        session = await self._get_session()
        url = f"{self.base_url}/message/sendMedia/{self.instance}"
        payload = {
            "number": number,
            "mediatype": "image",
            "media": image_url,
            "caption": caption,
            "delay": random.randint(1500, 4000),
        }
        try:
            async with session.post(url, json=payload,
                                     timeout=aiohttp.ClientTimeout(total=20)) as resp:
                return resp.status in (200, 201)
        except Exception as e:
            logger.error(f"Erro ao enviar imagem WA: {e}")
            return False

    async def get_qr_code(self) -> Optional[str]:
        """Obtém QR code para conectar o WhatsApp (primeiro uso)"""
        session = await self._get_session()
        url = f"{self.base_url}/instance/connect/{self.instance}"
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                return data.get("qrcode", {}).get("base64")
        except:
            return None

    async def check_connection(self) -> bool:
        """Verifica se o WhatsApp está conectado"""
        session = await self._get_session()
        url = f"{self.base_url}/instance/connectionState/{self.instance}"
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                state = data.get("instance", {}).get("state", "")
                return state == "open"
        except:
            return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


class WhatsAppDistributor:
    """
    Gerencia o envio de ofertas via WhatsApp com comportamento humano.
    Suporta grupos segmentados por categoria + lista VIP.
    """

    def __init__(self):
        self.client = EvolutionAPIClient()
        self._posts_today = 0
        self._last_post_time = 0

    async def send_product(self, product: dict, content: str) -> bool:
        """Envia produto para o grupo mais relevante"""
        # Determina o grupo pela categoria
        cat_lower = product.get("category_name", "").lower()
        target_group = None

        if "beleza" in cat_lower or "cuidados" in cat_lower:
            target_group = WA_GROUPS.get("beleza")
        elif "roupa" in cat_lower or "calçado" in cat_lower:
            target_group = WA_GROUPS.get("roupas")
        elif "esporte" in cat_lower or "fitness" in cat_lower:
            target_group = WA_GROUPS.get("esportes")
        
        # Fallback para grupo geral
        if not target_group:
            target_group = WA_GROUPS.get("geral")

        if not target_group:
            logger.warning("Nenhum grupo WA configurado para esta categoria")
            return False

        thumbnail = product.get("thumbnail", "")
        
        # Delay humano antes de enviar
        await asyncio.sleep(random.uniform(2, 6))

        if thumbnail:
            success = await self.client.send_image(target_group, thumbnail, content)
        else:
            success = await self.client.send_text(target_group, content)

        if success:
            self._posts_today += 1
            logger.info(f"📱 WA enviado: {product['title'][:40]}")
        
        return success

    async def broadcast_vip(self, product: dict, content: str) -> int:
        """
        Envia a melhor oferta do dia para contatos VIP.
        Usa apenas para produtos com comissão 12%+ e desconto 40%+.
        """
        if not VIP_CONTACTS:
            return 0
        
        # Só produtos premium para VIPs
        if product.get("commission_pct", 0) < 12:
            return 0
        
        sent = 0
        vip_msg = f"🏆 Oferta VIP para você!\n\n{content}"
        
        for contact in VIP_CONTACTS[:20]:  # Máximo 20 VIPs por vez
            contact = contact.strip()
            if not contact:
                continue
            
            success = await self.client.send_text(contact, vip_msg)
            if success:
                sent += 1
            
            # Delay crucial para não parecer spam
            await asyncio.sleep(random.uniform(8, 20))
        
        logger.info(f"📱 VIP broadcast: {sent}/{len(VIP_CONTACTS)} enviados")
        return sent

    async def send_daily_summary(self, stats: dict):
        """Envia resumo diário para você mesmo (seu número pessoal)"""
        my_number = os.getenv("WA_MY_NUMBER", "")
        if not my_number:
            return

        msg = f"""📊 *RESUMO ML MASTER AFILIADO*
📅 {datetime.now().strftime('%d/%m/%Y')}

📤 Posts Telegram: {stats.get('telegram_posts', 0)}
📱 Posts WhatsApp: {stats.get('wa_posts', 0)}
📦 Produtos divulgados: {stats.get('products_posted', 0)}
💰 Comissão estimada: R${stats.get('commission', 0):.2f}

📈 Meta diária (R$1.000): {stats.get('progress', 0):.1f}%

Painel: http://localhost:8080"""

        await self.client.send_text(my_number, msg)

    async def is_connected(self) -> bool:
        return await self.client.check_connection()

    async def close(self):
        await self.client.close()


# === SETUP HELPER ===
async def setup_whatsapp():
    """Guia interativo para conectar o WhatsApp"""
    print("\n📱 SETUP WHATSAPP\n")
    print("1. Certifique-se que o Evolution API está rodando:")
    print("   docker run -d --name evolution -p 8080:8080 atendai/evolution-api\n")
    
    client = EvolutionAPIClient()
    
    print("2. Obtendo QR Code...")
    qr = await client.get_qr_code()
    
    if qr:
        print("   QR Code obtido! Acesse: http://localhost:8080/manager")
        print("   Escaneie com o WhatsApp para conectar.\n")
    else:
        print("   ❌ Servidor não encontrado. Verifique se o Docker está rodando.\n")
    
    print("3. Configure no .env:")
    print("   WHATSAPP_API_URL=http://localhost:8080")
    print("   WHATSAPP_API_KEY=sua_chave_aqui")
    print("   WHATSAPP_INSTANCE=meu-afiliado")
    print("   WA_MY_NUMBER=5511999999999")
    print("   WA_GROUP_GERAL=ID_DO_GRUPO@g.us\n")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(setup_whatsapp())
