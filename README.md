# ML MASTER AFILIADO v1.0

> Sistema automático de afiliados para Mercado Livre  
> **Meta: R$1.000/dia em comissões**

---

## ⚡ Início Rápido (Windows)

```
1. Extraia o ZIP
2. Clique duas vezes em: INICIAR.bat
3. Escolha [1] na primeira vez (configuração)
4. Pronto — dashboard abre em http://localhost:8080
```

---

## 📦 Estrutura do Projeto

```
mlmaster/
├── INICIAR.bat              ← Windows: duplo clique para iniciar
├── run.py                   ← Runner principal Python
├── server.py                ← API + Dashboard (FastAPI)
├── requirements.txt         ← Dependências
├── .env.example             ← Modelo de configuração
├── dashboard/
│   └── index.html           ← Painel de controle web
└── src/
    ├── product_engine.py    ← Busca e rankeia produtos (ML API pública)
    ├── link_generator.py    ← Gera links de afiliado (Playwright)
    ├── content_creator.py   ← Posts virais com Claude AI
    ├── distributor.py       ← Telegram + scheduler inteligente
    ├── whatsapp_distributor.py ← WhatsApp via Evolution API
    └── analytics.py         ← Métricas reais + relatórios
```

---

## 🔧 Instalação Manual (se o .bat não funcionar)

```bash
# Dependências
pip install -r requirements.txt
playwright install chromium

# Configurar
cp .env.example .env
# Edite o .env com suas credenciais

# Rodar
python run.py
```

---

## ⚙️ Configuração do .env

```env
# OBRIGATÓRIO
ML_EMAIL=seu@email.com
ML_PASSWORD=sua_senha
ML_AFFILIATE_TAG=sua_tag_afiliado   # ex: begu5752228

# TELEGRAM (principal canal de distribuição)
TELEGRAM_BOT_TOKEN=token_do_botfather
TELEGRAM_CHANNEL_ID=-1001234567890

# OPCIONAL — Claude AI para conteúdo melhor
ANTHROPIC_API_KEY=sk-ant-...

# OPCIONAL — WhatsApp via Evolution API
WHATSAPP_API_URL=http://localhost:8080
WHATSAPP_API_KEY=sua_chave
WA_GROUP_GERAL=grupo_id@g.us
```

---

## 📊 Como Funciona

```
ProductEngine → Busca melhores produtos (API pública ML)
      ↓
LinkGenerator → Login ML + gera link de afiliado (Playwright)
      ↓
ContentCreator → Cria post persuasivo (Claude API ou template)
      ↓
SmartScheduler → Determina horário ideal (pico BR: 12h, 19h)
      ↓
TelegramDistributor → Publica no canal com imagem + link
      ↓
Analytics → Coleta métricas reais do painel ML
```

---

## 💰 Comissões por Categoria

| Categoria | Comissão |
|---|---|
| Beleza e Cuidados | **16%** |
| Roupas e Calçados | **16%** |
| Esportes e Fitness | **16%** |
| Casa e Decoração | **12%** |
| Bebês | **12%** |
| Eletrônicos | 7% |
| Celulares | 7% |

---

## 📅 Sprints

| Sprint | Semana | Meta |
|---|---|---|
| 1 — Fundação | Semana 1 | Sistema rodando + links gerados |
| 2 — Telegram | Semana 2 | Primeiro post automático |
| 3 — Otimização | Semana 3 | R$200-400/dia |
| 4 — Escala | Semana 4+ | R$1.000/dia |

---

## ⚠️ Regras Importantes

- ❌ NÃO use Google Ads com links de afiliado
- ❌ NÃO use o nome "Mercado Livre" em domínios
- ✅ Use canais Telegram, WhatsApp, Instagram, blog
- ✅ Divulgue de forma clara e honesta

---

## 📞 Comandos

```bash
python run.py          # Inicia dashboard
python run.py setup    # Reconfigura credenciais
python run.py test     # Testa todos os componentes
python run.py products # Busca produtos sem postar
```

---

*Versão 1.0 · Uso pessoal · Março 2026*
