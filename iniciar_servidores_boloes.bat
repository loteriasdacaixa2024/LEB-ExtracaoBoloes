@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ========================================
echo  Extrator de boloes — uma janela so
echo ========================================

set "PASTA_BOLOES=%~dp0"
if "%PASTA_BOLOES:~-1%"=="\" set "PASTA_BOLOES=%PASTA_BOLOES:~0,-1%"

set "RAIZ="
set "SERVIDOR_PY="
set "PYTHON_EXE="
set "PYTHON_VENV="

:: Servidor em uso: LAPDSO.py na porta 5151 (nao servidor_boloes.py na 5001)
call :resolver_raiz "D:\Loterias\LAPDSO-AnalisePorPosicaoDiaDeSorte"
if "%RAIZ%"=="" call :resolver_raiz "%PASTA_BOLOES%\.."
if "%RAIZ%"=="" call :resolver_raiz "%PASTA_BOLOES%\..\LBS-LoteriasBoloesDaSorte"
if "%RAIZ%"=="" call :resolver_raiz "I:\Meu Drive\LoteriasBoloesDaSorte"
if "%RAIZ%"=="" call :resolver_raiz "D:\Loterias\LBS-LoteriasBoloesDaSorte"

if "%RAIZ%"=="" (
  echo.
  echo [ERRO] Nao encontrei LAPDSO.py ^(porta 5151^) com o Python do LAPDSO_venv.
  echo.
  pause
  exit /b 1
)

if not exist "%PASTA_BOLOES%\script\baixar_boloes-API.py" (
  echo.
  echo [ERRO] Extrator nao encontrado:
  echo   %PASTA_BOLOES%\script\baixar_boloes-API.py
  echo.
  pause
  exit /b 1
)

:: Python do proprio projeto (venv em D:), que tem flask, flask-cors e selenium
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=%PYTHON_VENV%"

echo.
echo [OK] Servidor : %RAIZ%\%SERVIDOR_PY%
echo [OK] Python   : %PYTHON_EXE%
echo [OK] Extrator : %PASTA_BOLOES%\script\baixar_boloes-API.py
echo [OK] Login auto: LIGADO ^(LOGIN_CAIXA_AUTO=1^)
echo.
echo Verificando selenium e flask...
"%PYTHON_EXE%" -c "import selenium, flask, flask_cors" >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Este Python nao tem selenium, flask ou flask-cors.
  echo Instalando dependencias...
  "%PYTHON_EXE%" -m pip install "flask>=3.0,<4" flask-cors selenium
  if errorlevel 1 (
    echo.
    echo [ERRO] Nao consegui instalar selenium/flask em:
    echo   %PYTHON_EXE%
    echo.
    pause
    exit /b 1
  )
)
echo [OK] selenium, flask e flask-cors prontos
echo.

if /I "%~1"=="check" (
  echo CHECK_OK
  echo UMA_JANELA
  exit /b 0
)

<<<<<<< HEAD
:: LAPDSO fica sem janela. O unico console e este, do extrator.
title EXTRATOR
echo Verificando LAPDSO na porta 5151...
netstat -ano | findstr /C:":5151 " | findstr "LISTENING" >nul
if errorlevel 1 (
  echo [OK] Porta 5151 livre. Ligando LAPDSO em segundo plano, sem janela.
  call :ligar_lapdso_oculto
) else (
  echo [OK] LAPDSO ja esta em http://127.0.0.1:5151
  echo      Nenhuma janela extra.
)
=======
:: Painel 1 = servidor (liga direto) | Painel 2 = extrator + login (inicia direto)
"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe" ^
  -d "%RAIZ%" cmd /k "title SERVIDOR & echo ======================================== & echo  SERVIDOR PRINCIPAL ^(%SERVIDOR_PY%^) & echo ======================================== & echo Pasta: %RAIZ% & echo. & echo Ligando servidor... & \"%PYTHON_EXE%\" \"%RAIZ%\%SERVIDOR_PY%\"" ^
  ; split-pane -H -d "%PASTA_BOLOES%" cmd /k "title EXTRATOR & set LOGIN_CAIXA_AUTO=1 & echo ======================================== & echo  EXTRATOR DE BOLOES - Caixa ^(API^) & echo  VERSAO: CICLO-COMPLETO-v4.4.17 & echo ======================================== & echo LOGIN AUTOMATICO: ligado ^(mesmo Edge^) & echo   1^) Digite o codigo do e-mail no Edge & echo   2^) Clique MANUAL em Enviar & echo   3^) App clica ENTRAR sozinho apos a senha & echo   4^) No menu digite C ^(CICLO COMPLETO^) & echo   5^) SIM nos cards → Compre seu bolao → outro SIM na lista & echo Credenciais: config.local.json ^(gitignore^) & echo. & echo Iniciando extrator... & \"%PYTHON_EXE%\" -u \"%PASTA_BOLOES%\script\baixar_boloes-API.py\""
  ; split-pane -H -d "%PASTA_BOLOES%" cmd /k "title EXTRATOR & set LOGIN_CAIXA_AUTO=1 & echo ======================================== & echo  EXTRATOR DE BOLOES - Caixa ^(API^) & echo  VERSAO: CICLO-COMPLETO-v4.4.17 & echo ======================================== & echo LOGIN AUTOMATICO: ligado ^(mesmo Edge^) & echo   1^) Digite o codigo do e-mail no Edge & echo   2^) Clique MANUAL em Enviar & echo   3^) App clica ENTRAR sozinho apos a senha & echo   4^) No menu digite C ^(CICLO COMPLETO^) & echo   5^) SIM nos cards → Compre seu bolao → outro SIM na lista & echo Credenciais: config.local.json ^(gitignore^) & echo. & echo Iniciando extrator... & \"%PYTHON_EXE%\" -u \"%PASTA_BOLOES%\script\baixar_boloes-API.py\""
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257

echo.
echo ========================================
echo  EXTRATOR DE BOLOES - Caixa (API)
echo ========================================
echo LOGIN AUTOMATICO: ligado (mesmo Edge)
echo   1) Digite o codigo do e-mail no Edge
echo   2) Clique MANUAL em Enviar
echo   3) App clica ENTRAR sozinho apos a senha
echo   4) No menu digite C (CICLO COMPLETO)
echo   5) SIM nos cards - Compre seu bolao - outro SIM na lista
echo Credenciais: config.local.json (gitignore)
echo Python: %PYTHON_EXE%
echo.
echo Iniciando extrator nesta janela...
echo.
set LOGIN_CAIXA_AUTO=1
"%PYTHON_EXE%" -u "%PASTA_BOLOES%\script\baixar_boloes-API.py"
echo.
echo Extrator encerrou. Esta janela pode ser fechada.
pause
endlocal
exit /b 0


:ligar_lapdso_oculto
set "OCULTO=%PASTA_BOLOES%\_run_servidor_oculto.vbs"
> "%OCULTO%" echo Set sh = CreateObject("WScript.Shell")
>> "%OCULTO%" echo sh.CurrentDirectory = "%RAIZ%"
>> "%OCULTO%" echo sh.Run """%PYTHON_EXE%"" -u ""%RAIZ%\%SERVIDOR_PY%""", 0, False
wscript //nologo "%OCULTO%"
goto :eof


:resolver_raiz
:: %1 = candidato a pasta raiz do servidor
set "CAND=%~f1"
if not exist "%CAND%" goto :eof

set "SRV="
if exist "%CAND%\LAPDSO.py" set "SRV=LAPDSO.py"
if "%SRV%"=="" if exist "%CAND%\servidor.py" set "SRV=servidor.py"
if "%SRV%"=="" if exist "%CAND%\app.py" set "SRV=app.py"
if "%SRV%"=="" goto :eof

set "PY="
if exist "%CAND%\LAPDSO_venv\Scripts\python.exe" set "PY=%CAND%\LAPDSO_venv\Scripts\python.exe"
if "%PY%"=="" if exist "%CAND%\diadesorte\Scripts\python.exe" set "PY=%CAND%\diadesorte\Scripts\python.exe"
if "%PY%"=="" if exist "%CAND%\.venv\Scripts\python.exe" set "PY=%CAND%\.venv\Scripts\python.exe"
if "%PY%"=="" if exist "%CAND%\venv\Scripts\python.exe" set "PY=%CAND%\venv\Scripts\python.exe"
if "%PY%"=="" if exist "D:\Python_\python.exe" set "PY=D:\Python_\python.exe"
if "%PY%"=="" goto :eof

set "RAIZ=%CAND%"
set "SERVIDOR_PY=%SRV%"
set "PYTHON_VENV=%PY%"
set "PYTHON_EXE=%PY%"
goto :eof
