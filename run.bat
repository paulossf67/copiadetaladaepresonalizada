@echo off
chcp 65001 >nul
title Copy Assistant Pro

echo.
echo ================================================
echo Copy Assistant Pro - Desktop Windows
echo ================================================
echo.
echo Verificando dependências...
python -m pip install -q -r requirements.txt 2>nul
if %errorlevel% neq 0 (
    echo Erro ao instalar dependências. Verifique sua conexão com a internet.
    pause
    exit /b 1
)
echo Dependências OK!
echo.
echo Iniciando aplicação...
echo ================================================
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Erro ao executar a aplicação.
    echo Verifique a instalação de Python 3.10+
    pause
)
