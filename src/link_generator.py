"""
ML MASTER AFILIADO - Link Generator
Gera links de afiliado automaticamente via automação de browser.
Simula comportamento humano para evitar detecção.
Mantém sessão logada via cookies persistentes.
"""

import asyncio
import json
import os
import random
import time
import logging
from pathlib import Path
from typing import Optional, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger("LinkGenerator")


class HumanSimulator:
    """Simula comportamento humano no browser"""

    @staticmethod
    async def random_delay(min_s: float = 0.5, max_s: float = 2.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    @staticmethod
    async def human_click(page: Page, selector: str):
        """Clique com movimento natural de mouse"""
        element = await page.wait_for_selector(selector, timeout=10000)
        box = await element.bounding_box()
        if box:
            # Move para perto do elemento primeiro
            x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            await page.mouse.move(x + random.uniform(-5, 5), y + random.uniform(-5, 5))
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await page.mouse.click(x, y)

    @staticmethod
    async def human_type(page: Page, selector: str, text: str):
        """Digita com velocidade humana"""
        await page.click(selector)
        for char in text:
            await page.keyboard.type(char, delay=random.uniform(50, 150))
            if random.random() < 0.05:  # 5% chance de pausa maior
                await asyncio.sleep(random.uniform(0.2, 0.5))

    @staticmethod
    async def random_scroll(page: Page):
        """Scroll aleatório para simular leitura"""
        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, random.randint(100, 400))
            await asyncio.sleep(random.uniform(0.3, 0.8))

    @staticmethod
    def get_random_user_agent() -> str:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ]
        return random.choice(agents)


class MLSession:
    """Gerencia sessão autenticada no Mercado Livre"""

    COOKIES_FILE = "data/ml_cookies.json"
    
    def __init__(self, email: str = "", password: str = ""):
        self.email = email or os.getenv("ML_EMAIL", "")
        self.password = password or os.getenv("ML_PASSWORD", "")
        self.affiliate_tag = os.getenv("ML_AFFILIATE_TAG", "")
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_logged_in = False

    async def start(self, headless: bool = True):
        """Inicia o browser"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                f"--window-size={random.randint(1280,1920)},{random.randint(800,1080)}"
            ]
        )
        # Contexto com fingerprint humano
        context_options = {
            "user_agent": HumanSimulator.get_random_user_agent(),
            "viewport": {"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo",
            "color_scheme": "light",
            "java_script_enabled": True,
        }

        # Carrega cookies salvos se existirem
        if os.path.exists(self.COOKIES_FILE):
            self._context = await self._browser.new_context(**context_options)
            with open(self.COOKIES_FILE) as f:
                cookies = json.load(f)
            await self._context.add_cookies(cookies)
            logger.info("🍪 Cookies carregados de sessão anterior")
        else:
            self._context = await self._browser.new_context(**context_options)

        # Anti-detecção: remove webdriver flag
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)

        self._page = await self._context.new_page()

    async def login(self) -> bool:
        """Faz login no ML com comportamento humano"""
        if not self._page:
            raise RuntimeError("Sessão não iniciada. Chame start() primeiro.")

        logger.info("🔐 Verificando sessão...")
        
        # Testa se já está logado
        try:
            await self._page.goto("https://www.mercadolivre.com.br/afiliados/dashboard",
                                   wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        await HumanSimulator.random_delay(1, 2)

        if "afiliados" in self._page.url and "login" not in self._page.url:
            logger.info("✅ Sessão válida (cookies funcionando)")
            self._is_logged_in = True
            return True

        # Precisa fazer login
        logger.info("🔑 Fazendo login...")
        # Timeout curto: se ML bloquear (anti-bot), cai rápido no fallback
        self._page.set_default_timeout(8000)
        try:
            await self._page.goto("https://www.mercadolivre.com.br/jms/mlb/lgz/login",
                                   wait_until="domcontentloaded", timeout=15000)
            await HumanSimulator.random_delay(1, 2)

            await HumanSimulator.human_type(self._page, '#user_id', self.email)
            await HumanSimulator.random_delay(0.5, 1.5)
            await self._page.keyboard.press("Enter")
            await HumanSimulator.random_delay(1.5, 3)

            await HumanSimulator.human_type(self._page, '#password', self.password)
            await HumanSimulator.random_delay(0.5, 1.5)
            await self._page.keyboard.press("Enter")
            await HumanSimulator.random_delay(3, 5)

            if "mercadolivre.com.br" in self._page.url and "login" not in self._page.url:
                logger.info("✅ Login realizado com sucesso!")
                self._is_logged_in = True
                await self._save_cookies()
                return True
            else:
                logger.warning("⚠️ Login não concluído — usando links diretos")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Login bloqueado ({e.__class__.__name__}) — usando links diretos")
            return False
        finally:
            self._page.set_default_timeout(30000)

    async def _save_cookies(self):
        """Salva cookies para reutilizar sessão"""
        os.makedirs("data", exist_ok=True)
        cookies = await self._context.cookies()
        with open(self.COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
        logger.info("💾 Cookies salvos para próximas sessões")

    async def stop(self):
        if self._context:
            await self._save_cookies()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


class AffiliateLinkGenerator:
    """Gera links de afiliado para produtos ML"""

    def __init__(self, session: MLSession):
        self.session = session
        self._generated_count = 0

    async def generate_link(self, product_url: str, product_id: str = "") -> Optional[str]:
        """
        Gera link de afiliado para um produto.
        Navega até o produto, clica em Compartilhar e extrai o link.
        """
        page = self.session._page
        if not page:
            logger.error("Sessão não iniciada")
            return None

        try:
            logger.info(f"🔗 Gerando link para: {product_url[:60]}...")

            # Navega para o produto
            await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            await HumanSimulator.random_delay(1.5, 3)
            await HumanSimulator.random_scroll(page)

            # Procura botão Compartilhar (barra de afiliados)
            share_btn = None
            matched_selector = None
            selectors = [
                'button[data-testid="affiliate-share-button"]',
                'button:has-text("Compartilhar")',
                '.affiliate-share-button',
                'button.share-button',
            ]

            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=3000)
                    if el:
                        share_btn = el
                        matched_selector = sel
                        break
                except:
                    continue

            if not share_btn or not matched_selector:
                # Tenta via URL direta da API de afiliados
                logger.warning("Botão Compartilhar não encontrado, tentando método alternativo...")
                return await self._generate_link_api(product_url, product_id)

            # Clica no botão (passa o seletor CSS, não o ElementHandle)
            await HumanSimulator.human_click(page, matched_selector)
            await HumanSimulator.random_delay(1, 2)

            # Extrai o link do modal
            link = await self._extract_affiliate_link(page)

            if link:
                self._generated_count += 1
                logger.info(f"✅ Link gerado: {link}")
                # Fecha o modal
                try:
                    await page.keyboard.press("Escape")
                except:
                    pass
                return link

            return None

        except Exception as e:
            logger.error(f"Erro ao gerar link: {e}")
            return None

    async def _extract_affiliate_link(self, page: Page) -> Optional[str]:
        """Extrai o link do modal de compartilhamento"""
        selectors = [
            'input[value*="meli.la"]',
            'input[value*="mercadolivre.com.br"][readonly]',
            '.affiliate-link-input',
            'input[data-testid="affiliate-link"]',
        ]
        
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    value = await el.get_attribute("value")
                    if value and ("meli.la" in value or "mercadolivre" in value):
                        return value
            except:
                continue

        # Tenta extrair via JavaScript
        try:
            link = await page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input[readonly]');
                    for (const inp of inputs) {
                        if (inp.value && (inp.value.includes('meli.la') || 
                            inp.value.includes('mercadolivre'))) {
                            return inp.value;
                        }
                    }
                    return null;
                }
            """)
            return link
        except:
            return None

    async def _generate_link_api(self, product_url: str, product_id: str) -> Optional[str]:
        """
        Método alternativo: constrói URL de afiliado manualmente.
        Usa a tag do afiliado para rastrear vendas.
        """
        tag = self.session.affiliate_tag
        if not tag:
            logger.warning("Tag de afiliado não configurada")
            return None

        # URL real do catálogo ML com tag de afiliado
        if product_id and product_id.startswith("MLB"):
            affiliate_url = f"https://www.mercadolivre.com.br/p/{product_id}?ref={tag}"
        else:
            separator = "&" if "?" in product_url else "?"
            affiliate_url = f"{product_url}{separator}ref={tag}"

        return affiliate_url

    async def generate_batch(self, product_urls: List[tuple]) -> dict:
        """
        Gera links para múltiplos produtos.
        product_urls: lista de (product_id, url)
        """
        results = {}
        for product_id, url in product_urls:
            link = await self.generate_link(url, product_id)
            results[product_id] = link
            # Delay humano entre gerações
            await HumanSimulator.random_delay(
                random.uniform(2, 4),
                random.uniform(4, 8)
            )
        return results


# Teste rápido
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    async def main():
        session = MLSession()
        await session.start(headless=False)  # headless=False para ver o browser
        
        logged_in = await session.login()
        if logged_in:
            generator = AffiliateLinkGenerator(session)
            # Teste com um produto
            test_url = "https://www.mercadolivre.com.br/monitor-gamerlg-ultragearcurvo-tela-vade-34-2k-wqhd-3440-x-1440-ultrawide-formato-219-160hz-1ms-mbr-amd-freesyncpremium-34gp63a-b/p/MLB23087768"
            link = await generator.generate_link(test_url, "MLB23087768")
            print(f"Link gerado: {link}")
        
        await session.stop()

    asyncio.run(main())
