#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           ML MASTER AFILIADO — RUNNER PRINCIPAL             ║
║                     v1.0.0                                  ║
╚══════════════════════════════════════════════════════════════╝

Uso:
  python run.py          → Abre o Dashboard + inicia o bot
  python run.py setup    → Assistente de configuração inicial
  python run.py test     → Testa todos os componentes
  python run.py products → Busca produtos agora (sem postar)
"""

import asyncio
import os
import sys
import subprocess
import threading
import webbrowser
import time
from pathlib import Path

# Força UTF-8 no Windows para evitar UnicodeEncodeError com caracteres especiais
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ["PYTHONUTF8"] = "1"

# Garante que estamos no diretório correto
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    load_dotenv()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_banner():
    if HAS_RICH:
        console = Console()
        console.print(Panel.fit(
            "[bold yellow]ML MASTER AFILIADO[/] [bold white]v1.0.0[/]\n"
            "[dim]Afiliado automático • Mercado Livre • Telegram[/]\n\n"
            "[green]→ Meta:[/] [bold]R$1.000/dia em comissões[/]",
            border_style="yellow",
            padding=(1, 3)
        ))
    else:
        print("=" * 50)
        print("  ML MASTER AFILIADO v1.0.0")
        print("=" * 50)


def setup_wizard():
    """Assistente interativo de configuração"""
    print("\n🔧 ASSISTENTE DE CONFIGURAÇÃO\n")
    
    config = {}
    
    print("1. Credenciais do Mercado Livre")
    config["ML_EMAIL"] = input("   Email da conta ML: ").strip()
    config["ML_PASSWORD"] = input("   Senha da conta ML: ").strip()
    
    print("\n2. Tag de Afiliado")
    print("   (Encontre em: mercadolivre.com.br/afiliados/perfil)")
    config["ML_AFFILIATE_TAG"] = input("   Sua tag (ex: begu5752228): ").strip()
    
    print("\n3. Telegram Bot")
    print("   (Crie um bot em @BotFather e obtenha o token)")
    config["TELEGRAM_BOT_TOKEN"] = input("   Token do Bot: ").strip()
    config["TELEGRAM_CHANNEL_ID"] = input("   ID do Canal (ex: -1001234567890): ").strip()
    
    print("\n4. Claude API (para conteúdo com IA - opcional)")
    print("   (https://console.anthropic.com/)")
    config["ANTHROPIC_API_KEY"] = input("   API Key (ENTER para pular): ").strip()
    
    # Salva .env
    with open(".env", "w") as f:
        f.write("# ML MASTER AFILIADO - Configurações\n\n")
        for k, v in config.items():
            if v:
                f.write(f"{k}={v}\n")
        
        # Defaults
        f.write("\n# Configurações automáticas\n")
        f.write("MIN_POST_INTERVAL=1800\n")
        f.write("MAX_POST_INTERVAL=3600\n")
        f.write("PRODUCTS_PER_ROUND=10\n")
        f.write("MIN_COMMISSION=5\n")
        f.write("DASHBOARD_PORT=8080\n")
    
    print("\n✅ Configuração salva em .env")
    print("   Execute: python run.py")


async def test_components():
    """Testa todos os componentes do sistema"""
    print("\n🧪 TESTANDO COMPONENTES...\n")
    results = []

    # Teste 1: Variáveis de ambiente
    ml_email = os.getenv("ML_EMAIL", "")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    
    results.append(("ML Email", "✅" if ml_email else "❌ Não configurado"))
    results.append(("Telegram Bot", "✅" if tg_token else "❌ Não configurado"))
    results.append(("Claude API", "✅" if api_key else "⚠️ Opcional - não configurado"))

    # Teste 2: Busca de produtos
    try:
        from src.product_engine import ProductEngine
        engine = ProductEngine()
        
        print("  🔍 Testando busca de produtos...")
        products = await engine.discover_best_products(top_n=3)
        results.append(("API Mercado Livre", f"✅ {len(products)} produtos encontrados"))
        
        if products:
            p = products[0]
            print(f"\n  Melhor produto: [{p.commission_pct}%] R${p.price:.0f} | {p.title[:50]}")
        
        await engine.close()
    except Exception as e:
        results.append(("API Mercado Livre", f"❌ {str(e)[:40]}"))

    # Teste 3: Gerador de conteúdo
    try:
        from src.content_creator import ContentCreator
        creator = ContentCreator()
        test_product = {
            "title": "Produto Teste", "price": 99.90, "original_price": 199.90,
            "discount_pct": 50, "category_name": "Beleza", "commission_pct": 16,
            "free_shipping": True, "is_flash_deal": True,
            "affiliate_url": "https://meli.la/test", "url": "https://meli.la/test"
        }
        content = await creator.create_telegram_post(test_product)
        results.append(("Gerador de Conteúdo", "✅ Funcionando"))
        await creator.close()
    except Exception as e:
        results.append(("Gerador de Conteúdo", f"❌ {str(e)[:40]}"))

    # Exibe resultados
    print("\n📊 RESULTADO DOS TESTES:\n")
    for name, status in results:
        print(f"  {status} {name}")
    
    print("\n")


async def discover_products():
    """Busca e exibe os melhores produtos sem postar"""
    from src.product_engine import ProductEngine
    
    print("\n🔍 BUSCANDO MELHORES PRODUTOS...\n")
    engine = ProductEngine()
    products = await engine.discover_best_products(top_n=20)
    
    if HAS_RICH:
        console = Console()
        table = Table(box=box.ROUNDED, border_style="yellow", show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Título", max_width=40)
        table.add_column("Preço", justify="right")
        table.add_column("DESC", justify="center")
        table.add_column("COM", justify="center", style="green")
        table.add_column("Score", justify="right", style="yellow")
        table.add_column("Flash", justify="center")
        
        for i, p in enumerate(products[:15], 1):
            table.add_row(
                str(i),
                p.title[:38] + ("…" if len(p.title) > 38 else ""),
                f"R${p.price:.0f}",
                f"-{p.discount_pct:.0f}%",
                f"{p.commission_pct:.0f}%",
                f"{p.score:.1f}",
                "⚡" if p.is_flash_deal else ""
            )
        
        console.print(table)
    else:
        for i, p in enumerate(products[:10], 1):
            print(f"{i:2}. [{p.commission_pct:.0f}%COM] R${p.price:.0f} | -{p.discount_pct:.0f}% | {p.title[:45]}")
    
    print(f"\n💡 {len(products)} produtos qualificados encontrados e salvos no banco.")
    await engine.close()


def start_server():
    """Inicia o servidor FastAPI"""
    port = os.getenv("DASHBOARD_PORT", "8080")
    url = f"http://localhost:{port}"

    print(f"\n🌐 Dashboard: {url}")
    print("   Pressione CTRL+C para encerrar\n")

    # Abre o browser somente depois que o servidor iniciar (evita race condition)
    def _open_browser():
        time.sleep(2.5)
        try:
            webbrowser.open(url)
        except:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()

    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "server:app",
        "--host", "0.0.0.0",
        "--port", port,
        "--log-level", "info"
    ])


def main():
    print_banner()
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if cmd == "setup":
        setup_wizard()
    elif cmd == "test":
        asyncio.run(test_components())
    elif cmd == "products":
        asyncio.run(discover_products())
    else:  # start / default
        if not os.path.exists(".env") and not os.getenv("ML_EMAIL"):
            print("\n⚠️  Configuração não encontrada!")
            print("   Execute: python run.py setup\n")
            sys.exit(1)
        start_server()


if __name__ == "__main__":
    main()
