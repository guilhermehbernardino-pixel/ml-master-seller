@echo off
chcp 65001 > nul
title ML Master Afiliado

echo.
echo ============================================================
echo   ML MASTER AFILIADO v1.0
echo   Sistema Automatico de Afiliados - Mercado Livre
echo ============================================================
echo.

:: Verifica se Python está instalado
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo Instale em: https://python.org/downloads
    echo Marque "Add Python to PATH" na instalacao.
    pause
    exit /b 1
)

:: Garante que esta no diretorio correto independente de onde foi clicado
cd /d "%~dp0"

:: Verifica se esta no diretorio correto
if not exist "run.py" (
    echo [ERRO] Arquivo run.py nao encontrado em %~dp0
    pause
    exit /b 1
)

:: Cria .env se não existir
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado.
    echo Iniciando assistente de configuracao...
    echo.
    python -X utf8 run.py setup
    echo.
    echo Configuracao salva! Reiniciando...
    timeout /t 2 > nul
)

:: Instala dependências se necessário
if not exist "node_modules" (
    echo [INFO] Verificando dependencias...
    pip install -r requirements.txt -q
    playwright install chromium --quiet
    echo [OK] Dependencias instaladas.
    echo.
)

:: Ativa UTF-8 para evitar erro de encoding com caracteres especiais
chcp 65001 > nul

:: Menu de opções
echo Escolha uma opcao:
echo.
echo   [1] Iniciar Dashboard (recomendado)
echo   [2] Testar componentes
echo   [3] Buscar produtos agora
echo   [4] Reconfigurar .env
echo   [5] Sair
echo.
set /p opcao=Opcao: 

if "%opcao%"=="1" goto start
if "%opcao%"=="2" goto test
if "%opcao%"=="3" goto products
if "%opcao%"=="4" goto setup
if "%opcao%"=="5" exit

:start
echo.
echo [INFO] Iniciando servidor...
echo [INFO] Dashboard abrindo em http://localhost:8080
echo [INFO] Pressione CTRL+C para encerrar
echo.
python -X utf8 run.py
goto end

:test
echo.
python -X utf8 run.py test
pause
goto menu

:products
echo.
python -X utf8 run.py products
pause
goto menu

:setup
echo.
python -X utf8 run.py setup
pause
goto start

:menu
cls
goto :eof

:end
pause
