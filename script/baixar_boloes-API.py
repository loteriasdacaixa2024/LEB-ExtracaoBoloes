# -*- coding: utf-8 -*-
"""
Extrator de bolões via API (interceptação JSON) — Caixa.

Fluxo [C] CICLO COMPLETO (recomendado):
  1. Login → abre inicio-bolao → lê cards (modalidade + concurso)
  2. Sem SIM/ENTER — clica Compre seu bolão e extrai cada modalidade
  3. Relatório + Excel + JSON consolidado ao final

Fluxo [1] AUTOMÁTICO (uma modalidade):
  1. Terminal pede: MODALIDADE + CONCURSO
  2. Edge → login → PAUSA → SIM → pagina a lista do site

Fluxo [2] MANUAL: ENTER a cada página / vários filtros na mesma sessão.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Optional, Tuple

from selenium import webdriver

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from boloes_api_caixa import (
    LEGENDA_API,
    aguardar_capturas_api,
    aguardar_detalhes_visiveis,
    contar_respostas_detalhar,
    detalhar_pagina_ate_esperado,
    detectar_detalhes_pagina,
    instalar_interceptador_api,
    ler_capturas_api,
    ler_metadados_paginacao_api,
    limpar_capturas_api,
    limpar_marcas_detalhes_pagina,
    preparar_pagina_para_detalhes,
    resumo_capturas,
    salvar_capturas_brutas,
)
from boloes_modalidades import (
    TECLAS_ESPECIAIS,
    TODAS_MODALIDADES,
    extrair_concurso_de_boloes,
    extrair_modalidade_de_boloes,
    imprimir_menu_modalidades,
    nome_arquivo_consolidado_padrao,
    nome_arquivo_sessao,
    resolver_modalidade_menu,
)
from boloes_consolidar import (
    carregar_json_boloes,
    consolidar_sessao,
    hashes_de_lista,
    hashes_pagina,
    localizar_arquivo_sessao_existente,
    mesclar_listas,
    salvar_json_boloes,
    salvar_json_continuacao,
)
from boloes_checkpoint import (
    STATUS_CONCLUIDO,
    STATUS_EXECUTANDO,
    STATUS_PAUSADO,
    carregar_checkpoint,
    instruir_pause,
    pause_solicitada,
    perguntar_retomada,
    reset_pause_flags,
    resolver_pagina_retomada,
<<<<<<< HEAD
=======
    decidir_pagina_inicial,
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    salvar_checkpoint,
)
from boloes_estados import estados_varredura, imprimir_fila_estados
from boloes_pasta_bds import detectar_lista_boloes_aberta, detectar_modalidade_site
from boloes_filtro_loterica import (
    FiltroLotericaConfig,
    _carregar_config_cache,
    aplicar_filtro_varredura_automatica,
    bolao_atende_filtro,
    bolao_corresponde_loterica,
    cfg_qualquer_loterica,
    gerar_arquivo_base,
    garantir_sessao_caixa,
    ler_config_extracao,
    ler_filtro_aplicado_site,
    parse_termo_loterica,
    aplicar_filtro_loterica,
    ir_proxima_pagina_lista,
    ir_para_pagina_lista,
    ir_direto_para_pagina_lista,
    preparar_pagina_loterica,
    sessao_caixa_ativa,
    slug_loterica,
)

CONFERENCIAS_BOLOES_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
PASTA_JSON = os.path.join(CONFERENCIAS_BOLOES_DIR, 'json-boloes')
PASTA_CAPTURAS = os.path.join(CONFERENCIAS_BOLOES_DIR, 'capturas-api')
URL_BOLOES = 'https://www.loteriasonline.caixa.gov.br/silce-web/#/bolao-caixa'
URL_INICIO_BOLAO = (
    'https://www.loteriasonline.caixa.gov.br/silce-web/#/inicio-bolao'
)

MSG_ULTIMA_PAGINA = (
    'Paginação desta modalidade esgotada — todas as páginas. '
    'Segue para a próxima modalidade.'
)

<<<<<<< HEAD
VERSAO_EXTRATOR = 'CICLO-COMPLETO-v4.4.22 (pagina até todos os estados)'
=======
VERSAO_EXTRATOR = 'CICLO-COMPLETO-v4.6.1 (salto direto; fallback Seguinte)'
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257


for _pasta in (CONFERENCIAS_BOLOES_DIR, PASTA_JSON, PASTA_CAPTURAS):
    os.makedirs(_pasta, exist_ok=True)

driver = None
FILTRO_LOTERICA: Optional[FiltroLotericaConfig] = None
ROTULO_ARQUIVO = None
ROTULO_NOME = 'modalidade atual'
SESSAO_AUTORIZADA = False


def _login_auto_habilitado() -> bool:
    """True se o .bat (LOGIN_CAIXA_AUTO) ou config.local.json pedir login automático."""
    flag = (os.environ.get('LOGIN_CAIXA_AUTO') or '').strip().lower()
    if flag in ('1', 'true', 'sim', 'yes', 'on'):
        return True
    if flag in ('0', 'false', 'nao', 'não', 'no', 'off'):
        return False
    cfg = os.path.join(CONFERENCIAS_BOLOES_DIR, 'config.local.json')
    if not os.path.isfile(cfg):
        return False
    try:
        with open(cfg, encoding='utf-8') as f:
            dados = json.load(f)
        return bool(dados.get('login_automatico'))
    except Exception:
        return False


def _janela_edge_viva() -> bool:
    """False se o Edge/WebDriver morreu (janela fechada, sessão inválida)."""
    if driver is None:
        return False
    try:
        handles = driver.window_handles
        if not handles:
            return False
        _ = driver.current_url
        return True
    except Exception:
        return False


def _erro_indica_janela_morta(exc: BaseException) -> bool:
    msg = str(exc or '').lower()
    return any(
        x in msg
        for x in (
            'no such window',
            'target window already closed',
            'web view not found',
            'invalid session id',
            'chrome not reachable',
            'disconnected',
        )
    )


<<<<<<< HEAD
def _aguardar_sessao_sem_enter(log, segundos: int = 60) -> bool:
    """Espera a sessão voltar no Edge, sem input() no terminal."""
    from boloes_filtro_loterica import sessao_caixa_ativa
    fim = time.time() + max(5, int(segundos))
    while time.time() < fim:
        try:
            if driver is not None and (sessao_caixa_ativa(driver) or _usuario_logado_caixa()):
                log('  [SESSÃO] Sessão voltou — segue a paginação.')
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


=======
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
def _relugar_caixa_no_edge(out_fn=None) -> bool:
    """Reexecuta login (auto se ligado) e volta ao hub de bolões."""
    log = out_fn or _out
    if not _janela_edge_viva():
        return False

    if _login_auto_habilitado():
        log('  [SESSÃO] Login automático de novo (código do e-mail no Edge se pedir)...')
        try:
            from login_caixa.fluxo import (
                LoginAutomatizadoError,
                executar_login_automatizado,
            )
            executar_login_automatizado(driver=driver, manter_navegador_aberto=True)
            log('  [SESSÃO] Login automático concluído.')
        except LoginAutomatizadoError as exc:
            log(f'  [SESSÃO] Login auto pausou: {exc}')
<<<<<<< HEAD
            log('  [SESSÃO] Complete o código no Edge se pedir. O ciclo não para no ENTER.')
            _aguardar_sessao_sem_enter(log, segundos=90)
        except Exception as exc:
            log(f'  [SESSÃO] Falha no login auto: {exc}')
            log('  [SESSÃO] Nova tentativa em seguida — sem parar no ENTER.')
            _aguardar_sessao_sem_enter(log, segundos=20)
    else:
        log('  [SESSÃO] Sessão expirou — tentando de novo sem parar no ENTER.')
        _aguardar_sessao_sem_enter(log, segundos=30)
=======
            log('  >>> Complete o login no Edge (código → Enviar → senha se preciso).')
            try:
                input('\n>>> ENTER após login no Edge... ')
            except EOFError:
                pass
        except Exception as exc:
            log(f'  [SESSÃO] Falha no login auto: {exc}')
            log('  >>> Faça login MANUALMENTE no Edge.')
            try:
                input('\n>>> ENTER após login no Edge... ')
            except EOFError:
                pass
    else:
        log('  [SESSÃO] Sessão expirou — faça login no Edge e pressione ENTER.')
        try:
            input('\n>>> ENTER após login no Edge... ')
        except EOFError:
            pass
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257

    try:
        driver.get(URL_BOLOES)
        time.sleep(2.0)
    except Exception as exc:
        log(f'  [SESSÃO] Aviso ao abrir bolões: {exc}')
    try:
        from boloes_cards_inicio import ir_para_inicio_bolao
        ir_para_inicio_bolao(driver, log_fn=log, espera=2.0)
    except Exception:
        pass

    try:
        from boloes_filtro_loterica import sessao_caixa_ativa
        ok = bool(sessao_caixa_ativa(driver) or _usuario_logado_caixa())
    except Exception:
        ok = _usuario_logado_caixa()
    if ok:
        log('  [SESSÃO] Sessão OK — pode trocar de modalidade.')
    else:
        log('  [SESSÃO] Ainda sem sessão ativa no portal.')
    return ok


def garantir_sessao_ciclo(out_fn=None) -> bool:
    """
    Antes de trocar de modalidade / abrir card:
      - se Edge morreu → reabre + login
      - se Keycloak / sessão caiu → reloga
      - ping para manter sessão viva
    """
    global driver
    log = out_fn or _out

    if not _janela_edge_viva():
        log('  [SESSÃO] Edge fechou ou conexão caiu — reiniciando navegador...')
        try:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
        except Exception:
            pass
        driver = None
        if not iniciar_navegador():
            log('  [SESSÃO] Não foi possível reabrir o Edge.')
            return False
        try:
            from boloes_cards_inicio import ir_para_inicio_bolao
            ir_para_inicio_bolao(driver, log_fn=log, espera=2.0)
        except Exception:
            pass
        try:
            from boloes_filtro_loterica import sessao_caixa_ativa
            if sessao_caixa_ativa(driver) or _usuario_logado_caixa():
                log('  [SESSÃO] Edge + login OK após reinício.')
                return True
        except Exception:
            pass
        # iniciar_navegador já tentou login; se ainda falhou, força relogin
        return _relugar_caixa_no_edge(log)

    try:
        url = (driver.current_url or '').lower()
    except Exception as exc:
        if _erro_indica_janela_morta(exc):
            return garantir_sessao_ciclo(log)
        url = ''

    if any(x in url for x in ('login.caixa.gov.br', 'openid-connect', '/auth/realms/')):
        log('  [SESSÃO] Caixa pediu login de novo (conexão/sessão expirou).')
        return _relugar_caixa_no_edge(log)

    try:
        from boloes_filtro_loterica import manter_sessao_ativa, sessao_caixa_ativa
        if sessao_caixa_ativa(driver) or _usuario_logado_caixa():
            manter_sessao_ativa(driver)
            return True
    except Exception as exc:
        if _erro_indica_janela_morta(exc):
            return garantir_sessao_ciclo(log)
        log(f'  [SESSÃO] Aviso ao checar sessão: {exc}')

    log('  [SESSÃO] Sessão duvidosa / expirada — renovando login...')
    return _relugar_caixa_no_edge(log)


<<<<<<< HEAD
def _retomar_lista_na_pagina(mod, pagina: int, concurso: str = '') -> bool:
    """Reloga, reabre a lista da modalidade e salta para a página do checkpoint."""
    global driver
    rotulo = getattr(mod, 'label', '') or 'a lista'
    _out(
        f'  [SESSÃO] Relogin automático — retoma {rotulo} '
        f'na página {pagina} (checkpoint). Sem procurar estado no site.'
    )
    if not garantir_sessao_ciclo(_out):
        return False
    if mod is not None and driver is not None:
        try:
            from boloes_cards_inicio import abrir_lista_do_card
            ok_lista = abrir_lista_do_card(
                driver,
                label=getattr(mod, 'label', '') or '',
                concurso=str(concurso or ''),
                slug=getattr(mod, 'slug', '') or '',
                log_fn=_out,
                timeout_detalhes=35.0,
            )
        except Exception as exc:
            _out(f'  [SESSÃO] Não reabriu a lista: {exc}')
            ok_lista = False
        if not ok_lista:
            return False
    if driver is None:
        return False
    # Garante Detalhes antes de saltar página (evita avançar em lista vazia).
    n_det = aguardar_detalhes_visiveis(driver, minimo=1, timeout=15, log_fn=_out)
    if n_det < 1:
        _out(f'  [SESSÃO] Lista de {rotulo} reaberta sem Detalhes — retoma falhou.')
        return False
    if int(pagina or 1) <= 1:
        return True
    from boloes_filtro_loterica import _ler_pagina_atual_ui, ir_direto_para_pagina_lista
    ir_direto_para_pagina_lista(driver, int(pagina), _out)
    ui = _ler_pagina_atual_ui(driver)
    n_apos = aguardar_detalhes_visiveis(driver, minimo=1, timeout=12, log_fn=_out)
    if n_apos < 1:
        _out(
            f'  [CHECKPOINT] Salto para pág. {pagina} deixou 0 Detalhes — '
            f'fica na lista aberta (UI={ui or "?"}).'
        )
        return False
    if (ui or 0) == int(pagina):
        _out(f'  [CHECKPOINT] De volta à página {pagina}. Segue a paginação.')
        return True
    _out(f'  [CHECKPOINT] Após relogin a UI está em {ui or "?"} (alvo {pagina}).')
    # Ainda tem Detalhes: deixa o loop continuar a paginação a partir daqui.
    return True


=======
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
def _aviso_sonoro_extracao_completa() -> None:
    """Beep quando a lista do site foi paginada até o fim."""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        for freq, dur in ((784, 180), (988, 180), (1175, 350)):
            winsound.Beep(freq, dur)
    except Exception:
        try:
            print('\a\a\a', end='', flush=True)
        except Exception:
            pass
    _out('\n  [SOM] Extração completa — todas as páginas processadas.')


# ─────────────────────────────────────────────────────────────────────────────
# NOVO: coleta de modalidade + concurso ANTES de abrir o Edge
# ─────────────────────────────────────────────────────────────────────────────

MAPA_MODALIDADES_RAPIDO = {
    '1': 'MEGA_SENA',
    '2': 'QUINA',
    '3': 'LOTOFACIL',
    '4': 'LOTOMANIA',
    '5': 'TIMEMANIA',
    '6': 'DIA_DE_SORTE',
    '7': 'SUPER_SETE',
    '8': 'DUPLA_SENA',
    '9': 'MAIS_MILIONARIA',
}

    # Especiais: usa diretamente o TECLAS_ESPECIAIS já definido no seu código


def _separador(char='=', n=60):
    print(char * n, flush=True)


def _out(msg: str = '') -> None:
    """Print imediato no terminal."""
    print(msg, flush=True)


def _coletar_modalidade_pre_extracao() -> Optional[object]:
    """
    Pergunta a modalidade ANTES de abrir o Edge.
    Retorna objeto de modalidade ou None (auto-detectar depois).
    """
    _separador()
    _out('  PASSO 1 — MODALIDADE')
    _out('  Informe a modalidade que você vai extrair no site:')
    _out('')
    _out('  [1] Mega-Sena       [2] Quina         [3] Lotofácil')
    _out('  [4] Lotomania       [5] Timemania      [6] Dia de Sorte')
    _out('  [7] Super Sete      [8] Dupla Sena     [9] +Milionária')
    _out('  Especiais: QSJ | DSP | LTI | MSV | MS3')
    _out('  ENTER = detectar automaticamente no site')
    _separador('-')

    try:
        resp = input('  Modalidade: ').strip().upper()
    except EOFError:
        return None

    if not resp:
        _out('  [OK] Modalidade será detectada automaticamente ao iniciar.')
        return None

    # Número 1-9
    if resp in MAPA_MODALIDADES_RAPIDO:
        slug = MAPA_MODALIDADES_RAPIDO[resp]
        mod = resolver_modalidade_menu(slug)
        if mod:
            _out(f'  [OK] Modalidade: {mod.label}')
            return mod

    # Especiais: QSJ, DSP, LTI, etc. — usa o mesmo TECLAS_ESPECIAIS do seu código
    if resp in TECLAS_ESPECIAIS:
        mod = resolver_modalidade_menu(resp)
        if mod:
            _out(f'  [OK] Modalidade especial: {mod.label}')
            return mod

    # Texto livre (MEGA_SENA, QUINA, etc.)
    mod = resolver_modalidade_menu(resp)
    if mod:
        _out(f'  [OK] Modalidade: {mod.label}')
        return mod

    _out(f'  [AVISO] "{resp}" não reconhecido — será detectado automaticamente.')
    return None


def _coletar_concurso_pre_extracao() -> str:
    """
    Pergunta o número do concurso ANTES de abrir o Edge.
    Retorna string com dígitos ou '' para auto-detectar.
    """
    _separador()
    _out('  PASSO 2 — CONCURSO')
    _out('  Informe o número do concurso que você vai extrair:')
    _out('  Exemplo: 3024  |  ENTER = detectar automaticamente no site')
    _separador('-')

    try:
        resp = input('  Concurso nº: ').strip()
    except EOFError:
        return ''

    digits = re.sub(r'\D', '', resp)
    if digits:
        _out(f'  [OK] Concurso informado: {digits}')
        return digits

    _out('  [OK] Concurso será detectado automaticamente da primeira página.')
    return ''


def _exibir_resumo_pre_extracao(mod, concurso: str, cfg) -> None:
    """Mostra no terminal o resumo completo antes de abrir o Edge."""
    _separador()
    _out('  RESUMO — CONFIGURAÇÃO DA EXTRAÇÃO')
    _separador('-')
    _out(f'  Modalidade  : {mod.label if mod else "detectar automaticamente"}')
    _out(f'  Concurso    : {concurso if concurso else "detectar automaticamente"}')
    _out('  Lotérica    : qualquer (lista do site — SEM filtro de estado)')
    _out(f'  Destino     : json-boloes/')
    _out(f'  Gravação    : tempo real (KBs crescem a cada página)')
    _separador()
    _out('')
    _out('  Agora:')
    _out('  1. O Edge abre e o LOGIN é automático')
    _out('  2. No Edge: escolha a MODALIDADE (+ concurso). Sem filtrar estado')
    _out('  3. PAUSA — volte aqui e digite SIM (Enter vazio NÃO inicia)')
    _out('  4. O script clica Detalhes e avança páginas até acabar')
    _separador()


# ─────────────────────────────────────────────────────────────────────────────
# Utilitários gerais
# ─────────────────────────────────────────────────────────────────────────────

def _driver_url(timeout: float = 6.0) -> str:
    if driver is None:
        return ''

    def _ler() -> str:
        try:
            return (driver.execute_script('return window.location.href || "";') or '').strip()
        except Exception:
            return (driver.current_url or '').strip()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_ler).result(timeout=timeout)
    except FuturesTimeout:
        _out('  [AVISO] Edge não respondeu a tempo — clique na janela do navegador.')
        return ''
    except Exception:
        return ''


def _no_site_boloes() -> bool:
    url = _driver_url().lower()
    if not url:
        return driver is not None and sessao_caixa_ativa(driver)
    if any(x in url for x in ('login.caixa.gov.br', 'openid-connect', '/auth/realms/')):
        return False
    return 'loteriasonline.caixa.gov.br' in url or 'silce-web' in url


def _novo_painel_extracao() -> dict:
    return {
        'paginas_processadas': 0,
        'paginas_com_dados': 0,
        'paginas_vazias': 0,
        'capturas_api': 0,
        'descartados_loterica': 0,
        'por_pagina': {},
    }


def _imprimir_painel_pagina(pagina: int, n_novos: int, boloes: list, hashes: set, painel: dict) -> None:
    painel['paginas_processadas'] = pagina
    painel['por_pagina'][pagina] = n_novos
    if n_novos > 0:
        painel['paginas_com_dados'] += 1
    else:
        painel['paginas_vazias'] += 1

    pag_com = painel['paginas_com_dados']
    pag_vaz = painel['paginas_vazias']
    caps_pag = painel.get('capturas_ultima_pagina', 0)
    n_det = painel.get('detalhes_tela_pagina', 0)
    pend = painel.get('pendentes_pagina', 0)

    # Mostra tamanho do arquivo JSON em tempo real
    ab = painel.get('arquivo_base', '')
    kb_info = ''
    if ab:
        path_json = os.path.join(PASTA_JSON, f'{ab}.json')
        if os.path.isfile(path_json):
            kb = os.path.getsize(path_json) / 1024
            kb_info = f' | 💾 {kb:.1f} KB no disco'

    print('\n  ' + '-' * 56)
    print(f'  [PAINEL] Página {pagina} concluída{kb_info}')
    linha = f'    Nesta página : +{n_novos} registro(s) | {caps_pag} captura(s) API'
    if n_det:
        linha += f' | detalhes_tela={n_det}'
        if pend:
            linha += f' | faltam={pend}'
    print(linha)
    print(f'    Total sessão  : {len(boloes)} registro(s) | {len(hashes)} único(s)')
    print(f'    Páginas       : {pagina} processada(s) | {pag_com} com dados | {pag_vaz} vazia(s)')
    if painel['capturas_api']:
        print(f'    Capturas API  : {painel["capturas_api"]} acumulada(s) na sessão')
    if painel['descartados_loterica']:
        print(f'    Descartados   : {painel["descartados_loterica"]} (outra lotérica)')
    print('  ' + '-' * 56)


def _imprimir_resumo_final(
    boloes: list,
    hashes: set,
    painel: dict,
    arquivo_base: str,
    cfg,
    tempo_seg: int,
) -> None:
    path_sessao = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
    kb_final = os.path.getsize(path_sessao) / 1024 if os.path.isfile(path_sessao) else 0

    print('\n' + '=' * 60)
    print('  RESUMO FINAL DA EXTRAÇÃO')
    print('=' * 60)
    print(f'\n  Lotérica alvo      : {cfg.termo or ("QUALQUER" if cfg.qualquer_loterica else "(filtro manual)")}')
    print(f'  Páginas processadas: {painel["paginas_processadas"]}')
    print(f'  Páginas com dados  : {painel["paginas_com_dados"]}')
    print(f'  Páginas vazias     : {painel["paginas_vazias"]}')
    print(f'  Registros no arquivo : {len(boloes)} (modalidade + concurso — pronto p/ importar)')
    if painel.get('registros_loterica_alvo') is not None and cfg.termo:
        print(f'  Lotérica alvo (ref.) : {painel["registros_loterica_alvo"]} reg.')
    print(f'  Hashes únicos sessão : {len(hashes)}')
    cont = painel.get('continuidade')
    if cont:
        print(f'  Base preservada    : {cont["existentes"]} reg. em {cont["arquivo"]} ({cont.get("kb", "?")} KB)')
    if os.path.isfile(path_sessao):
        total_disco = len(carregar_json_boloes(path_sessao))
        novos_sessao = max(0, total_disco - (cont['existentes'] if cont else 0))
        print(f'  Total no arquivo   : {total_disco} reg. (+{novos_sessao} novo(s) nesta extração)')
    print(f'  Capturas API       : {painel["capturas_api"]} JSON(s)')
    if painel['descartados_loterica']:
        print(f'  Descartados        : {painel["descartados_loterica"]} (lotérica diferente)')
    if painel.get('descartados_modalidade'):
        print(f'  Descartados        : {painel["descartados_modalidade"]} (modalidade diferente)')
    print(f'  Tempo              : {tempo_seg // 60}min {tempo_seg % 60}s')
    print(f'  Arquivo            : {path_sessao}')
    print(f'  Tamanho final      : {kb_final:.1f} KB')

    if painel['por_pagina']:
        print('\n  Registros por página:')
        for pg in sorted(painel['por_pagina']):
            n = painel['por_pagina'][pg]
            barra = '#' * min(n, 40) if n else '(vazia)'
            print(f'    Pág {pg:>3}: {n:>4}  {barra}')
    print('=' * 60)


def _rotulo_nome() -> str:
    return ROTULO_ARQUIVO.label if ROTULO_ARQUIVO else 'modalidade atual'


def _rotulo_modalidade_menu() -> str:
    if not ROTULO_ARQUIVO:
        return '(não configurada)'
    m = ROTULO_ARQUIVO
    if getattr(m, 'especial', False) and m.tecla:
        return f'{m.tecla} — {m.label}'
    num = getattr(m, 'numero', None)
    if num and num <= 9:
        return f'[{num}] {m.label}'
    return m.label


def _imprimir_tabela_modalidades_resumida() -> None:
    _out('\n  OPCIONAL — forçar parser no terminal (senão usa API do site):')
    _out('  M1 Mega-Sena   M2 Quina        M3 Lotofácil')
    _out('  M4 Lotomania   M5 Timemania    M6 Dia de Sorte')
    _out('  M7 Super Sete  M8 Dupla Sena   M9 +Milionária')
    _out('  Especiais: DSP | QSJ | LTI | MSV | MS3')


def _imprimir_status_modalidade() -> None:
    if ROTULO_ARQUIVO:
        _out(f'\n  Parser terminal (opcional): {_rotulo_modalidade_menu()}')
    else:
        _out('\n  Modalidade: vem da API do site (MEGA_SENA, QUINA…) — não precisa M1.')


def _aplicar_modalidade(mod) -> bool:
    global ROTULO_ARQUIVO, ROTULO_NOME
    if not mod:
        return False
    ROTULO_ARQUIVO = mod
    ROTULO_NOME = _rotulo_nome()
    _out(f'\n>>> Modalidade: {_rotulo_modalidade_menu()}')
    if getattr(mod, 'especial', False):
        _out(f'>>> Base: {mod.base_label} | Época: {mod.epoca}')
    _out(f'>>> Extrai: {mod.extracao}')
    return True


def _trocar_modalidade_por_entrada(entrada: str) -> bool:
    mod = resolver_modalidade_menu(entrada)
    if not mod:
        return False
    return _aplicar_modalidade(mod)


# ─────────────────────────────────────────────────────────────────────────────
# Navegador
# ─────────────────────────────────────────────────────────────────────────────

def iniciar_navegador() -> bool:
    global driver
    if driver is not None:
        return True
    try:
        _out('\nIniciando Edge (hook API)...')
        opts = webdriver.EdgeOptions()
        opts.page_load_strategy = 'eager'
        opts.add_experimental_option('detach', True)
        driver = webdriver.Edge(options=opts)
        driver.set_page_load_timeout(45)
        instalar_interceptador_api(driver)

        # Login automatizado opcional (ativado pelo .bat via LOGIN_CAIXA_AUTO=1
        # ou por "login_automatico": true em config.local.json).
        # Não altera o restante do extrator — só antecipa a autenticação.
        if _login_auto_habilitado():
            _out('\n  [LOGIN AUTO] Fluxo de autenticação Caixa (módulo isolado)...')
            try:
                from login_caixa.fluxo import (
                    LoginAutomatizadoError,
                    executar_login_automatizado,
                    _parece_logado_no_portal,
                )
                executar_login_automatizado(driver=driver, manter_navegador_aberto=True)
                _out('  [LOGIN AUTO] Login concluído.')
            except LoginAutomatizadoError as exc:
                _out(f'  [LOGIN AUTO] Interrompido: {exc}')
                _out('  >>> Continue o login MANUALMENTE no Edge.')
            except Exception as exc:
                _out(f'  [LOGIN AUTO] Falha inesperada: {exc}')
                _out('  >>> Continue o login MANUALMENTE no Edge.')

            # Após login: só garante estar no portal logado.
            # Modalidade/filtros = MANUAL no Edge. Extração só depois do SIM.
            try:
                ja_logado = _parece_logado_no_portal(driver)
            except Exception:
                ja_logado = False
            try:
                url_atual = (driver.current_url or '').lower()
            except Exception:
                url_atual = ''

            if ja_logado and 'bolao-caixa' not in url_atual:
                _out('  Abrindo Bolões Caixa (você já está logado)...')
                try:
                    driver.get(URL_BOLOES)
                except Exception as exc:
                    _out(f'  [AVISO] Não abriu bolões automaticamente: {exc}')
            elif not ja_logado:
                _out('  [AVISO] Sessão ainda não confirmada — abra Bolões no Edge se precisar.')
                try:
                    driver.get(URL_BOLOES)
                except Exception:
                    pass
        else:
            driver.get(URL_BOLOES)

        _out('')
        _out('  ' + '=' * 56)
        _out('  LOGIN AUTO FINALIZADO (Entrar já clicado pelo app)')
<<<<<<< HEAD
        _out('    [C] UM SIM → Detalhes + próxima página (o site troca o estado)')
        _out('    [1] abra a lista da modalidade e digite SIM')
=======
        _out('    [C] cards → Compre seu bolão → extração automática (sem SIM)')
        _out('    [1] uma modalidade (ainda pede SIM neste modo)')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        _out('  ' + '=' * 56)
        return True
    except Exception as exc:
        print(f'\n>>> ERRO ao abrir Edge: {exc}')
        traceback.print_exc()
        driver = None
        return False


def _aguardar_login_inicial() -> bool:
    """Legado — não usar no [1]; preferir ENTER manual em aguardar_site_pronto()."""
    fim = time.time() + 180
    while time.time() < fim:
        try:
            if _usuario_logado_caixa() or _no_site_boloes():
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def fechar_navegador() -> None:
    global driver
    if driver is not None:
        try:
            print('\nFechando navegador...')
            driver.quit()
        except Exception:
            pass
        driver = None


# ─────────────────────────────────────────────────────────────────────────────
# Configuração de lotérica e modalidade
# ─────────────────────────────────────────────────────────────────────────────

def configurar_modalidade_apenas() -> bool:
    global ROTULO_ARQUIVO, ROTULO_NOME
    try:
        from boloes_modalidades import ler_modalidade_terminal
        ROTULO_ARQUIVO = ler_modalidade_terminal()
        ROTULO_NOME = _rotulo_nome()
        print(f'\n>>> Modalidade: {ROTULO_NOME}')
        print('>>> Modo [2]: lotérica e dezenas você escolhe NO SITE a cada rodada.')
        return True
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f'\n>>> ERRO na modalidade: {exc}')
        return False


def configurar_loterica() -> bool:
    global FILTRO_LOTERICA, ROTULO_ARQUIVO, ROTULO_NOME
    try:
        FILTRO_LOTERICA, ROTULO_ARQUIVO = ler_config_extracao()
        ROTULO_NOME = _rotulo_nome()
        if not FILTRO_LOTERICA or not (FILTRO_LOTERICA.termo or '').strip():
            print('\n>>> Lotérica inválida ou vazia. Tente de novo (ex.: 9833).')
            FILTRO_LOTERICA = None
            return False
        print(f'\n>>> Config OK | Lotérica: {FILTRO_LOTERICA.termo} | Modalidade: {ROTULO_NOME}')
        return True
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f'\n>>> ERRO na configuração: {exc}')
        traceback.print_exc()
        return False


def _exigir_config_extracao(acao: str = 'extrair') -> bool:
    if FILTRO_LOTERICA and (
        (FILTRO_LOTERICA.termo or '').strip()
        or FILTRO_LOTERICA.codigo
        or FILTRO_LOTERICA.qualquer_loterica
    ):
        return True

    print('\n' + '=' * 60)
    print('  FILTRO NÃO CONFIGURADO')
    print('=' * 60)
    print(f'\n  Para {acao}, use [9]:')
    print('    · lotérica fixa (ex.: 9833), ou')
    print('    · * = QUALQUER lotérica + 15 dezenas')
    print('  Abrindo configuração agora (ou CTRL+C para cancelar)...\n')

    if configurar_loterica():
        return True

    print('\n>>> Sem filtro — use [9] no menu antes de [1].')
    return False


def _exigir_modalidade(acao: str = 'extrair') -> bool:
    if ROTULO_ARQUIVO:
        return True
    print('\n' + '=' * 60)
    print('  MODALIDADE NÃO CONFIGURADA')
    print('=' * 60)
    if configurar_modalidade_apenas():
        return bool(ROTULO_ARQUIVO)
    return False


def _cfg_filtro_site() -> FiltroLotericaConfig:
    qtd = 15
    if FILTRO_LOTERICA and FILTRO_LOTERICA.qtd_dezenas:
        qtd = FILTRO_LOTERICA.qtd_dezenas
    return cfg_qualquer_loterica(qtd)


def _inferir_cfg_de_boloes(boloes: list) -> FiltroLotericaConfig:
    if not boloes:
        return _cfg_filtro_site()
    b = boloes[0]
    nome = (b.get('nome_loterica') or '').strip()
    cod_raw = str(b.get('codigo_loterica') or '').strip()
    digits = re.sub(r'\D', '', cod_raw)
    cod = ''
    if digits:
        cod = digits[-4:] if len(digits) >= 4 else digits
    termo = cod or nome[:40] or 'manual'
    return FiltroLotericaConfig(termo=termo, codigo=cod or None, nome=nome or None)


# ─────────────────────────────────────────────────────────────────────────────
# Login / sessão
# ─────────────────────────────────────────────────────────────────────────────

def _payload_tem_usuario(node) -> bool:
    if isinstance(node, dict):
        if node.get('cpf') or node.get('nome'):
            return True
        for val in node.values():
            if _payload_tem_usuario(val):
                return True
    elif isinstance(node, list):
        for item in node:
            if _payload_tem_usuario(item):
                return True
    return False


def _usuario_logado_caixa() -> bool:
    if not _no_site_boloes():
        return False
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            ok = pool.submit(
                driver.execute_script,
                """
                try {
                    var body = (document.body && document.body.innerText) || '';
                    if (/Olá|Ola|Minha conta|Sair/i.test(body)) return true;
                    for (var i = 0; i < localStorage.length; i++) {
                        var k = localStorage.key(i) || '';
                        if (/token|auth|session|access/i.test(k)) {
                            var v = localStorage.getItem(k) || '';
                            if (v.length > 24) return true;
                        }
                    }
                } catch (e) {}
                return false;
                """,
            ).result(timeout=5)
            if ok:
                return True
    except Exception:
        pass
    try:
        for cap in ler_capturas_api(driver):
            url = (cap.get('url') or '').lower()
            if 'recuperar-dados' in url or 'dxn1yXJpb3' in url:
                if _payload_tem_usuario(cap.get('data')):
                    return True
    except Exception:
        pass
    return False


def aguardar_login_caixa() -> bool:
    print('\n' + '=' * 60)
    print('  FAÇA LOGIN (script pausado)')
    print('=' * 60)
    print('\n1. No Edge: LOGIN na Caixa')
    print('2. Abra Bolões Caixa / lista de bolões')
    print('\n3. Volte aqui e pressione ENTER após o login')

    while True:
        try:
            input('\n>>> ENTER após LOGIN no site... ')
        except EOFError:
            return False

        if _usuario_logado_caixa():
            _out('\n  Login OK.')
            return True

        if _no_site_boloes():
            _out('\n  Página de bolões aberta, mas login ainda não confirmado.')
        print('\n  >>> Faça login no Edge e tente de novo.')


def _descartar_enter_fantasma() -> None:
    """Enter colado após escolher opção no menu não deve liberar a extração."""
    try:
        import msvcrt
        time.sleep(0.2)
        while msvcrt.kbhit():
            msvcrt.getwch()
    except Exception:
        pass


def _ler_confirmacao_sim() -> str:
    """
    Lê SIM no terminal — Enter vazio ou colado NÃO conta.
    Windows: leitura caractere a caractere; fallback: input() exige SIM exato.
    """
    print('\n>>> PAUSA: digite SIM e Enter (Enter sozinho NÃO inicia): ', end='', flush=True)
    try:
        import msvcrt
    except ImportError:
        return input().strip().upper()

    buf: list[str] = []
    while True:
        ch = msvcrt.getwche()
        if ch in ('\r', '\n'):
            print(flush=True)
            return ''.join(buf).strip().upper()
        if ch == '\x03':
            raise KeyboardInterrupt
        if ch in ('\b', '\x7f'):
            if buf:
                buf.pop()
                print('\b \b', end='', flush=True)
            continue
        if ch.isprintable():
            buf.append(ch)


def aguardar_site_pronto(modo_ciclo: bool = False) -> bool:
    """
    PAUSA rígida: Enter vazio NÃO inicia.
    Só continua após digitar SIM + login confirmado + bolões visíveis na tela.
    """
    print('\n' + '=' * 60)
    print(f'  ⏸⏸⏸  PAUSA — SCRIPT PARADO  [{VERSAO_EXTRATOR}]')
    print('=' * 60)
    if modo_ciclo:
        print('\n  1. Cards já detectados no Edge (inicio-bolao)')
        print('  2. Pode clicar no site normalmente enquanto o terminal espera')
<<<<<<< HEAD
        print('  3. Digite SIM uma vez — esta é a única confirmação')
        print('  4. Detalhes de todos os bolões da página, grava, próxima página')
        print('     O site percorre os estados. No fim da lista, próxima modalidade')
=======
        print('  3. Digite SIM — o app clica Compre seu bolão')
        print('  4. Depois ESPERA de novo — outro SIM para começar a extração')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    else:
        print('\n  1. Confirme que está LOGADO no Edge (login automático)')
        print('  2. Deixe a lista de bolões aberta (sem filtrar estado)')
        print('  3. Digite SIM — o app só clica Detalhes e passa as páginas')
    print('')
    print('  ⚠  NADA será baixado antes de você digitar SIM.')
    print(f'  JSON: {PASTA_JSON}')
    print('=' * 60)

    _descartar_enter_fantasma()

    while True:
        try:
            resp = _ler_confirmacao_sim()
        except (KeyboardInterrupt, EOFError):
            print('\n  Extração cancelada.')
            return False

        if not resp:
            print('  ⏸  Enter vazio ignorado — digite SIM quando estiver pronto.')
            continue

        if resp in ('N', 'NAO', 'NÃO', 'CANCELAR', 'X', '0'):
            print('  Extração cancelada.')
            return False

        if resp not in ('SIM', 'S', 'OK', 'INICIAR'):
            print('  ⏸  PAUSA mantida — digite SIM (não apenas Enter).')
            continue

        if not _usuario_logado_caixa():
            print('\n  ❌ Login NÃO detectado no Edge. Faça login e digite SIM de novo.')
            continue

        if modo_ciclo:
            _out('\n  ✔ Login OK — próximo passo: clicar Compre seu bolão (extração só no SIM da lista).')
            return True

        _out('  Verificando bolões visíveis na página...')
        n_det = aguardar_detalhes_visiveis(driver, minimo=1, timeout=12, log_fn=_out)
        if n_det < 1:
            print('\n  ❌ Nenhum bolão na tela (0 botões Detalhes).')
            print('  Faça login, abra a lista de bolões e digite SIM novamente.')
            continue

        _out(f'\n  ✔ Confirmado — login OK, {n_det} bolão(ões) visível(eis). Iniciando...')
        return True


def aguardar_sim_apos_compre_bolao(label: str = '', concurso: str = '') -> bool:
    """
    Segunda pausa do [C]: lista já aberta após Compre seu bolão.
    O operador confere concurso/IDs no Edge; extração só depois de SIM.
    """
    print('\n' + '=' * 60)
    print(f'  ⏸⏸⏸  PAUSA — LISTA ABERTA  [{VERSAO_EXTRATOR}]')
    print('=' * 60)
    extra = f'{label or "modalidade"}'
    if concurso:
        extra += f' | concurso {concurso}'
    print(f'\n  Compre seu bolão já clicado: {extra}')
    print('  Tutorial "bolão digital" o app tenta pular sozinho.')
    print('  Se aparecer OUTRA tela/ID estranho, resolva no Edge e só então digite SIM.')
    print('  NADA será baixado agora.')
    print('  Digite SIM novamente para COMEÇAR a extração desta lista.')
    print('  Digite N para cancelar esta modalidade.')
    print(f'  JSON: {PASTA_JSON}')
    print('=' * 60)

    _descartar_enter_fantasma()

    while True:
        try:
            resp = _ler_confirmacao_sim()
        except (KeyboardInterrupt, EOFError):
            print('\n  Extração cancelada.')
            return False

        if not resp:
            print('  ⏸  Enter vazio ignorado — digite SIM quando a lista estiver ok.')
            continue

        if resp in ('N', 'NAO', 'NÃO', 'CANCELAR', 'X', '0'):
            print('  Extração desta lista cancelada.')
            return False

        if resp not in ('SIM', 'S', 'OK', 'INICIAR'):
            print('  ⏸  PAUSA mantida — digite SIM (não apenas Enter).')
            continue

        if not _usuario_logado_caixa():
            print('\n  ❌ Login NÃO detectado no Edge. Faça login e digite SIM de novo.')
            continue

        _out('  Verificando bolões visíveis na página...')
        n_det = aguardar_detalhes_visiveis(driver, minimo=1, timeout=12, log_fn=_out)
        if n_det < 1:
            print('\n  ❌ Nenhum bolão na tela (0 botões Detalhes).')
            print('  Confira a lista no Edge e digite SIM novamente.')
            continue

        _out(f'\n  ✔ SIM OK — {n_det} bolão(ões) visível(eis). Iniciando extração...')
        return True


def aguardar_filtro_manual_pagina1(rodada: int = 1) -> bool:
    print('\n' + '=' * 60)
    if rodada == 1:
        print('  FILTRO NO SITE — página 1')
    else:
        print(f'  FILTRO {rodada} — troque no site (mesma sessão logada)')
    print('=' * 60)

    while True:
        try:
            input(f'\n>>> ENTER após filtro aplicado (rodada {rodada}, página 1)... ')
        except EOFError:
            return False
        _out('\n  OK — verificando página de bolões...')
        if _no_site_boloes():
            return True
        url = _driver_url() or '(sem resposta do Edge)'
        _out(f'\n  >>> Não está na lista de bolões. URL atual: {url}')
        _out('  Abra Bolões Caixa no Edge, aplique filtro e tente de novo.')


# ─────────────────────────────────────────────────────────────────────────────
# Filtros / modalidade
# ─────────────────────────────────────────────────────────────────────────────

def _modalidade_do_bolao_item(bolao: dict):
    from boloes_modalidades import resolver_modalidade_api, resolver_modalidade_menu
    for chave in ('modalidade_slug', 'modalidade', 'nomeModalidade'):
        raw = bolao.get(chave)
        if raw is None:
            continue
        if isinstance(raw, dict):
            raw = raw.get('nome') or raw.get('descricao') or raw.get('codigo') or ''
        mod = resolver_modalidade_api(str(raw)) or resolver_modalidade_menu(str(raw))
        if mod:
            return mod
    texto = str(bolao.get('texto_completo') or '')
    if len(texto) > 20:
        mod = resolver_modalidade_menu(texto[:600])
        if mod:
            return mod
    return None


def _slugs_modalidade_compativeis(slug_a: str, slug_b: str) -> bool:
    """True se é a mesma modalidade ou especial da mesma base (LTI ↔ lotofacil)."""
    a = (slug_a or '').strip().lower()
    b = (slug_b or '').strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    from boloes_modalidades import modalidade_por_slug
    ma, mb = modalidade_por_slug(a), modalidade_por_slug(b)
    if not ma or not mb:
        return False
    if ma.slug == mb.slug:
        return True
    pa = getattr(ma, 'parser_slug', ma.slug)
    pb = getattr(mb, 'parser_slug', mb.slug)
    return pa == pb or ma.slug == pb or mb.slug == pa


def _filtrar_boloes_modalidade(boloes: list, mod_esperada) -> tuple[list, int]:
    """Mantém só a modalidade esperada. Descarta outras (anti-mistura)."""
    if not mod_esperada or not boloes:
        return list(boloes), 0
    ok: list = []
    descartados = 0
    slug_ok = mod_esperada.slug
    parser_ok = getattr(mod_esperada, 'parser_slug', slug_ok)
    exemplos: list[str] = []
    for b in boloes:
        mod = _modalidade_do_bolao_item(b)
        if mod is None:
            ok.append(b)
        elif (
            mod.slug == slug_ok
            or mod.slug == parser_ok
            or getattr(mod, 'parser_slug', '') == parser_ok
            or _slugs_modalidade_compativeis(mod.slug, slug_ok)
        ):
            ok.append(b)
        else:
            descartados += 1
            if len(exemplos) < 3:
                exemplos.append(mod.label)
    if descartados:
        _out(
            f'  [ERRO INTEGRIDADE] {descartados} bolão(ões) de outra modalidade '
            f'(ex.: {", ".join(exemplos)}) — NÃO gravados em {mod_esperada.label}.'
        )
    return ok, descartados


def _concurso_de_arquivo_base(arquivo_base: str) -> str:
    """Extrai concurso de boloes_3024_mega-sena → '3024'."""
    m = re.match(r'boloes_(\d+)_', (arquivo_base or '').strip())
    return m.group(1) if m else ''


def _slug_de_arquivo_base(arquivo_base: str) -> str:
    """boloes_1271_dia-de-sorte → dia-de-sorte."""
    ab = (arquivo_base or '').removesuffix('.json').strip()
    m = re.match(r'^boloes_(?:sem-concurso|\d+)_(.+)$', ab)
    return (m.group(1) if m else '') or ''


def _amarrar_sessao_ao_site(mod_esperada, concurso_alvo: str, arquivo_base: str):
    """
    Modalidade do CICLO/opção [1] define o JSON.
    Site só CONFIRMA — nunca grava Lotofácil Independência em dia-de-sorte.json
    nem troca especial (LTI) pela base (lotofacil) por causa do código API.
    """
    from boloes_modalidades import nome_arquivo_sessao

    conc_final = str(concurso_alvo or '').strip()
    if mod_esperada:
        arq_esperado = nome_arquivo_sessao(conc_final or 'sem-concurso', mod_esperada)
    else:
        arq_esperado = arquivo_base

    if driver is None:
        return mod_esperada, conc_final, arq_esperado or arquivo_base

    info = detectar_lista_boloes_aberta(driver)
    if not info or not info.get('slug'):
        if info and info.get('na_lista'):
            _out('  [AMARRA] Lista aberta, modalidade ainda não lida — usa arquivo da sessão.')
        if mod_esperada:
            _out(
                f'  [AMARRA] {mod_esperada.label} conc={conc_final or "?"} '
                f'→ {arq_esperado}.json'
            )
        return mod_esperada, conc_final, arq_esperado or arquivo_base

    mod_site = info.get('mod')
    if mod_site is None:
        from boloes_modalidades import modalidade_por_slug, resolver_modalidade_menu
        mod_site = modalidade_por_slug(info['slug']) or resolver_modalidade_menu(info['slug'])

    conc_site = str(info.get('concurso') or '').strip()
    if conc_site:
        conc_final = conc_site

    # Ciclo/pedido tem prioridade: site compatível (LTI↔lotofacil) → mantém especial + nome certo
    if mod_esperada:
        if _slugs_modalidade_compativeis(mod_esperada.slug, getattr(mod_site, 'slug', '') or info.get('slug', '')):
            arq = nome_arquivo_sessao(conc_final or 'sem-concurso', mod_esperada)
            _out(
                f'  [AMARRA] Site={getattr(mod_site, "label", info.get("slug"))} '
                f'| sessão={mod_esperada.label} conc={conc_final or "?"} '
                f'→ {arq}.json  (não mistura com outra modalidade)'
            )
            path_ok = os.path.join(PASTA_JSON, f'{arq}.json')
            if os.path.isfile(path_ok):
                n = len(carregar_json_boloes(path_ok))
                _out(f'  [AMARRA] JSON desta modalidade: {n} bolão(ões) — continua nele.')
            else:
                _out(f'  [AMARRA] Criará {arq}.json só para {mod_esperada.label}.')
            return mod_esperada, conc_final, arq

        # Site claramente OUTRA modalidade (ex.: Dia de Sorte vs LTI)
        _out(
            f'  [AMARRA] ATENÇÃO: site={getattr(mod_site, "label", "?")} '
            f'mas ciclo pediu {mod_esperada.label}. '
            f'Mantém {arq_esperado}.json (não grava no arquivo do site).'
        )
        return mod_esperada, conc_final, arq_esperado

    # Sem modalidade pedida: segue o site
    if mod_site is None:
        return None, conc_final, arquivo_base
    arq_site = nome_arquivo_sessao(conc_final or 'sem-concurso', mod_site)
    _out(f'  [AMARRA] Site={mod_site.label} conc={conc_final or "?"} → {arq_site}.json')
    return mod_site, conc_final, arq_site


def _filtrar_boloes_concurso(boloes: list, concurso_alvo: str) -> list:
    if not concurso_alvo:
        return list(boloes)
    alvo = re.sub(r'\D', '', str(concurso_alvo))
    if not alvo:
        return list(boloes)
    return [
        b for b in boloes
        if re.sub(r'\D', '', str(b.get('concurso') or '')) == alvo
    ]


def _boloes_para_json_arquivo(boloes: list, mod_esperada, concurso_alvo: str = '') -> list:
    """
    Bolões que entram em boloes_{concurso}_{modalidade}.json:
    modalidade + concurso — SEM filtro de lotérica (arquivo é da modalidade inteira).
    """
    filtrados, _ = _filtrar_boloes_modalidade(boloes, mod_esperada)
    return _filtrar_boloes_concurso(filtrados, concurso_alvo)


def _salvar_capturas_pagina_disco(pagina: int, rodada: int = 1) -> Optional[str]:
    """Persiste capturas API da página em capturas-api/ (backup + recuperação)."""
    if not driver:
        return None
    caminho = os.path.join(PASTA_CAPTURAS, f'api_r{rodada}_p{pagina}_{int(time.time())}.json')
    try:
        salvar_capturas_brutas(driver, caminho)
        return caminho
    except Exception:
        return None


def _modalidade_extracao(driver=None):
    if ROTULO_ARQUIVO:
        _out(f'  Parser terminal: {ROTULO_ARQUIVO.label}')
        return ROTULO_ARQUIVO
    if driver is not None:
        slug = detectar_modalidade_site(driver)
        if slug:
            mod = resolver_modalidade_menu(slug)
            if mod:
                _out(f'  Modalidade no site: {mod.label}')
                return mod
    _out('  Modalidade: lida da API de cada bolão (campo MEGA_SENA, QUINA…)')
    return None


def _validar_modalidade_coerencia(mod_esperada, boloes: list) -> None:
    if not boloes:
        return
    mod_json = extrair_modalidade_de_boloes(boloes)
    label_json = mod_json.label if mod_json else str(boloes[0].get('modalidade') or '?')
    label_site = mod_esperada.label if mod_esperada else '(não definida)'
    concurso = extrair_concurso_de_boloes(boloes)

    if mod_esperada and mod_json and mod_esperada.slug != mod_json.slug:
        _out(f'\n  ERRO: Modalidade site/terminal ({label_site}) difere da gravada no JSON ({label_json}).')

    if mod_esperada and mod_json:
        arq_ok = nome_arquivo_consolidado_padrao(concurso, mod_esperada)
        arq_json = nome_arquivo_consolidado_padrao(concurso, mod_json)
        if arq_ok != arq_json:
            _out(f'  ERRO: Nome do arquivo ({arq_json}) não bate com modalidade do site ({arq_ok}).')
        else:
            _out(f'  OK modalidade: {label_site} | concurso {concurso} | {arq_ok}')


def _renomear_json_sessao(arquivo_base: str, boloes: list, mod) -> str:
    if not boloes:
        return arquivo_base
    # Isolamento: slug do arquivo SEMPRE o da modalidade da sessão (nunca majority polluída)
    conc = extrair_concurso_de_boloes(boloes)
    novo = nome_arquivo_sessao(conc, mod)
    if novo == arquivo_base:
        return arquivo_base
    antigo = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
    destino = os.path.join(PASTA_JSON, f'{novo}.json')
    if os.path.isfile(antigo) and antigo != destino:
        if os.path.isfile(destino):
            existentes = carregar_json_boloes(destino)
            sessao_antigo = carregar_json_boloes(antigo)
            final, _ = mesclar_listas(existentes, sessao_antigo + boloes)
            salvar_json_boloes(destino, final)
            os.remove(antigo)
        else:
            os.rename(antigo, destino)
        _out(f'  Arquivo renomeado: {os.path.basename(destino)}')
    return novo


def _iniciar_continuidade_inteligente(
    arquivo_base: str,
    mod_esperada,
    painel: dict,
    concurso: str = '',
) -> Tuple[set, str]:
    mod_slug = mod_esperada.slug if mod_esperada else ''
    path, existentes = localizar_arquivo_sessao_existente(
        PASTA_JSON, arquivo_base, mod_slug, concurso,
    )
    if not existentes:
        return set(), arquivo_base

    hashes = hashes_de_lista(existentes)
    arquivo_efetivo = os.path.splitext(os.path.basename(path))[0]
    # Nunca gravar em *_CONSOLIDADO — esse nome é só backup/espelho
    if arquivo_efetivo.endswith('_CONSOLIDADO'):
        arquivo_efetivo = arquivo_efetivo[: -len('_CONSOLIDADO')]
    kb = os.path.getsize(path) / 1024 if path else 0
    painel['continuidade'] = {
        'path': path,
        'arquivo': f'{arquivo_efetivo}.json',
        'existentes': len(existentes),
        'kb': round(kb, 1),
    }
    _out(f'  [CONTINUIDADE] fonte={os.path.basename(path)} | {len(existentes)} reg. ({kb:.1f} KB)')
    _out(f'  [CONTINUIDADE] gravando em: {arquivo_efetivo}.json')
    # Se a sessão estiver ausente/corrompida e a fonte for CONSOLIDADO, restaura
    destino_sessao = os.path.join(PASTA_JSON, f'{arquivo_efetivo}.json')
    if path and os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(destino_sessao)):
        if existentes:
            salvar_json_boloes(destino_sessao, existentes)
            _out(f'  [CONTINUIDADE] Sessao restaurada a partir do backup.')
    return hashes, arquivo_efetivo


def preparar_login_unico() -> bool:
    global SESSAO_AUTORIZADA
    SESSAO_AUTORIZADA = False
    if not iniciar_navegador():
        return False
    print('\n  Edge aberto — faça LOGIN (script aguarda, nada roda ainda).')
    if not aguardar_login_caixa():
        return False
    if not _usuario_logado_caixa():
        print('\n>>> Login não confirmado. Extração cancelada.')
        return False
    print('\n  Sessão logada — pronta para configurar filtros no site.')
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Salvar parcial (tempo real) — exibe KBs no terminal
# ─────────────────────────────────────────────────────────────────────────────

def salvar_parcial(boloes, arquivo_base, pagina: int = 0):
    path = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
    if not boloes:
        if not os.path.isfile(path):
            # Garante o arquivo da modalidade na pasta mesmo com 0 bolões nesta leva
            salvar_json_boloes(path, [])
            _out(
                f'  [SAVE] Criado {os.path.basename(path)} (vazio) — '
                f'modalidade iniciada; aguardando bolões.'
            )
        else:
            kb = os.path.getsize(path) / 1024
            _out(
                f'  [SAVE] Pág {pagina or "?"}: 0 novos nesta leva — '
                f'arquivo mantém {len(carregar_json_boloes(path))} reg. ({kb:.1f} KB).'
            )
        return path

    slug_arq = _slug_de_arquivo_base(arquivo_base)
    if slug_arq:
        mod_b = extrair_modalidade_de_boloes(boloes)
        if mod_b and not _slugs_modalidade_compativeis(mod_b.slug, slug_arq):
            _out(
                f'  [BLOQUEIO] Recusado gravar {mod_b.label} em {arquivo_base}.json '
                f'(arquivo é {slug_arq}). Continuação só no JSON da modalidade do ciclo/site.'
            )
            return path

    sem_hash = sum(1 for b in boloes if not b.get('hash_bolao'))
    if sem_hash:
        _out(f'  [SAVE AVISO] {sem_hash} bolão(ões) sem hash — não entram no JSON.')

    final, novos, anteriores = salvar_json_continuacao(path, boloes)
    if anteriores < 0:
        kb = os.path.getsize(path) / 1024 if os.path.isfile(path) else 0
        _out(
            f'  [SAVE] JSON na pasta não pôde ser lido ({kb:.1f} KB) — '
            f'arquivo preservado, não sobrescrito.'
        )
        return path
    kb = os.path.getsize(path) / 1024 if os.path.isfile(path) else 0
    _out(
        f'  💾 SALVO pág {pagina or "?"}: {len(final)} reg. total (+{novos} novos) | '
        f'{kb:.1f} KB | {os.path.basename(path)}'
    )
    return path


def _garantir_arquivo_modalidade(arquivo_base: str, mod_esperada=None, concurso: str = '') -> str:
    """Cria json-boloes/boloes_{conc}_{mod}.json na hora — aparece na pasta imediatamente."""
    from boloes_modalidades import nome_arquivo_sessao
    ab = (arquivo_base or '').removesuffix('.json').strip()
    if mod_esperada:
        conc = (concurso or _concurso_de_arquivo_base(ab) or 'sem-concurso').strip()
        ab = nome_arquivo_sessao(conc, mod_esperada)
    if not ab:
        return arquivo_base or ''
    path = os.path.join(PASTA_JSON, f'{ab}.json')
    if not os.path.isfile(path):
        salvar_json_boloes(path, [])
        _out(f'  [ARQUIVO] Criado agora: {path}')
        _out('  [ARQUIVO] (vazio [] — será preenchido ao baixar os Detalhes)')
    else:
        n = len(carregar_json_boloes(path))
        kb = os.path.getsize(path) / 1024
        _out(f'  [ARQUIVO] Já existe: {os.path.basename(path)} | {n} reg. | {kb:.1f} KB')
    return ab


def _atualizar_arquivo_base_concurso(arquivo_base: str, concurso: str, mod_esperada) -> str:
    """Renomeia boloes_sem-concurso_* → boloes_{concurso}_* assim que o concurso for detectado."""
    conc = re.sub(r'\D', '', str(concurso or ''))
    if not conc or not mod_esperada:
        return arquivo_base
    novo = nome_arquivo_sessao(conc, mod_esperada)
    if novo == arquivo_base:
        return arquivo_base
    antigo = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
    destino = os.path.join(PASTA_JSON, f'{novo}.json')
    if os.path.isfile(antigo) and antigo != destino:
        if os.path.isfile(destino):
            existentes = carregar_json_boloes(destino)
            sessao = carregar_json_boloes(antigo)
            final, _ = mesclar_listas(existentes, sessao)
            salvar_json_boloes(destino, final)
            os.remove(antigo)
        else:
            os.rename(antigo, destino)
        _out(f'  [ARQUIVO] Renomeado → {novo}.json')
    return novo


def _persistir_json_pagina(
    pagina: int,
    rodada: int,
    arquivo_base: str,
    painel: dict,
    mod_esperada,
    parser_slug: str,
    hashes: set,
    boloes: list,
) -> Tuple[int, str]:
    """
    Gravação garantida após cada página:
    1) salva capturas API em disco
    2) extrai bolões do arquivo de captura
    3) mescla no JSON de sessão (modalidade + concurso)
    """
    from boloes_consolidar import boloes_de_capturas_api
    from boloes_api_caixa import coletar_boloes_das_capturas

    path_cap = _salvar_capturas_pagina_disco(pagina, rodada)
    candidatos: list = []

    if path_cap and os.path.isfile(path_cap):
        candidatos = boloes_de_capturas_api([path_cap])

    if not candidatos and driver:
        candidatos = coletar_boloes_das_capturas(
            driver, set(), None, None, parser_slug, filtrar_dezenas=False,
        )

    conc = painel.get('concurso_alvo') or _concurso_de_arquivo_base(arquivo_base)
    alvo = _boloes_para_json_arquivo(candidatos, mod_esperada, conc)

    if not conc and alvo:
        conc = extrair_concurso_de_boloes(alvo)
        painel['concurso_alvo'] = conc
        alvo = _boloes_para_json_arquivo(candidatos, mod_esperada, conc)

    if conc and mod_esperada:
        arquivo_base = _atualizar_arquivo_base_concurso(arquivo_base, conc, mod_esperada)
        painel['arquivo_base'] = arquivo_base

    if not alvo:
        path = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
        total = len(carregar_json_boloes(path))
        kb = os.path.getsize(path) / 1024 if os.path.isfile(path) else 0
        caps = os.path.basename(path_cap) if path_cap else '—'
        _out(
            f'  [SAVE] Pág {pagina}: 0 bolões parseáveis (captura: {caps}) | '
            f'arquivo: {total} reg. ({kb:.1f} KB)'
        )
        return 0, arquivo_base

    for b in alvo:
        b['pagina'] = pagina
        b['rodada_filtro'] = rodada
        if painel.get('uf_varredura'):
            b['uf_varredura'] = painel['uf_varredura']

    hashes_antes = set(hashes)
    novos_gravar = [b for b in alvo if (b.get('hash_bolao') or '') not in hashes_antes]

    salvar_parcial(alvo, arquivo_base, pagina)

    for b in novos_gravar:
        h = b.get('hash_bolao')
        if h:
            hashes.add(h)
        b['indice'] = len(boloes) + 1
        boloes.append(b)

    return len(novos_gravar), arquivo_base


# ─────────────────────────────────────────────────────────────────────────────
# Captura de página
# ─────────────────────────────────────────────────────────────────────────────

def _capturas_da_rodada(rodada: int) -> list[str]:
    pat = os.path.join(PASTA_CAPTURAS, f'api_r{rodada}_p*.json')
    return sorted(glob.glob(pat))


def _recuperar_boloes_das_capturas(
    cfg,
    parser_slug,
    mod_slug,
    arquivo_base,
    rodada=1,
    mod_esperada=None,
    concurso_alvo: str = '',
    aplicar_filtro_loterica: bool = False,
):
    """Recupera bolões das capturas em disco → JSON de sessão (modalidade+concurso)."""
    from boloes_consolidar import boloes_de_capturas_api

    arquivos = _capturas_da_rodada(rodada)
    if not arquivos:
        arquivos = sorted(glob.glob(os.path.join(PASTA_CAPTURAS, 'api_r*_p*.json')))
    if not arquivos:
        return []

    conc = concurso_alvo or _concurso_de_arquivo_base(arquivo_base)
    cod_lot = cfg.codigo if (aplicar_filtro_loterica and not cfg.qualquer_loterica) else None
    qtd_dez = cfg.qtd_dezenas if aplicar_filtro_loterica else None
    brutos = boloes_de_capturas_api(arquivos, cod_lot, qtd_dez)
    boloes = _boloes_para_json_arquivo(brutos, mod_esperada, conc)
    if aplicar_filtro_loterica:
        boloes = _boloes_do_filtro(boloes, cfg)
    elif not boloes and brutos:
        _out(f'  [RECUPERO] {len(brutos)} bolão(ões) na API, mas 0 para modalidade/concurso alvo.')

    if boloes:
        path = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
        final, novos, anteriores = salvar_json_continuacao(path, boloes)
        # Mantém um único JSON de sessão (sem espelho _CONSOLIDADO)
        kb = os.path.getsize(path) / 1024 if os.path.isfile(path) else 0
        _out(
            f'\n  [RECUPERO] {len(final)} reg. no arquivo (+{novos} novos) | '
            f'{kb:.1f} KB | {len(arquivos)} captura(s) API.'
        )
        return boloes
    return []


def _diagnosticar_capturas_sem_filtro(cfg, parser_slug) -> None:
    if not driver:
        return
    from boloes_api_caixa import coletar_boloes_das_capturas

    todos = coletar_boloes_das_capturas(driver, set(), print, None, parser_slug, filtrar_dezenas=False)
    if not todos:
        _out('  [DIAG] Nenhum bolão parseável nas capturas API desta página.')
        return
    lotericas = {}
    for b in todos:
        nome = (b.get('nome_loterica') or '?')[:40]
        lotericas[nome] = lotericas.get(nome, 0) + 1
    _out(f'  [DIAG] API tem {len(todos)} bolão(ões) SEM filtro de lotérica:')
    for nome, q in sorted(lotericas.items(), key=lambda x: -x[1])[:6]:
        _out(f'         · {q}× {nome}')
    if cfg and cfg.termo:
        _out(f'  [DIAG] Filtro ativo: {cfg.termo} — confira se bate com a lotérica no site.')


def _boloes_do_filtro(boloes: list, cfg: FiltroLotericaConfig) -> list:
    if not cfg:
        return list(boloes)
    if cfg.qualquer_loterica or (
        not (cfg.termo or '').strip() and not cfg.codigo and cfg.qtd_dezenas is not None
    ):
        return [b for b in boloes if bolao_atende_filtro(b, cfg)]
    if not cfg.termo and not cfg.codigo:
        return []
    if cfg.qtd_dezenas is not None:
        return [b for b in boloes if bolao_atende_filtro(b, cfg)]
    return [b for b in boloes if bolao_corresponde_loterica(b, cfg)]


def _capturar_pagina_atual(
    cfg, parser_slug, hashes, pagina, boloes, manual, painel, mod_esperada=None, arquivo_base='',
) -> int:
    if not SESSAO_AUTORIZADA:
        print('  [SESSÃO] Captura bloqueada — conclua login + filtro manual antes.')
        return -1

    def _ao_expirar() -> bool:
        ok = _retomar_lista_na_pagina(
            mod_esperada, pagina, str(painel.get('concurso_alvo') or ''),
        )
        if ok:
            painel['pular_navegacao_proxima'] = True
        return ok

    if not garantir_sessao_caixa(driver, pagina, print, ao_expirar=_ao_expirar):
        print('  [SESSÃO] Página não capturada — o ciclo reloga e tenta esta página de novo.')
        return -1

    if pagina == 1:
        print('  [FILTRO] Página 1 — aguardando botões Detalhes...')
        n_det = aguardar_detalhes_visiveis(driver, minimo=1, timeout=12, log_fn=print)
        if n_det:
            print(f'  [TELA] {n_det} botão(ões) Detalhes visíveis.')
        else:
            print('  [TELA] Nenhum botão Detalhes detectado — confira filtro no site.')
        time.sleep(0.8)
    else:
        meta_preservar = ler_metadados_paginacao_api(driver)
        if meta_preservar:
            painel['paginacao_api'] = meta_preservar
        limpar_capturas_api(driver)
        if painel.pop('pular_navegacao_proxima', False):
            from boloes_filtro_loterica import _ler_pagina_barra_somente, ir_direto_para_pagina_lista
            barra = _ler_pagina_barra_somente(driver)
            ja_no_alvo = barra is not None and int(barra) >= int(pagina)
            if not ja_no_alvo:
                print(
                    f'  [PÁGINA] Barra do site={barra or "?"} | extração pede {pagina} — '
                    f'alinhando na Caixa antes de clicar Detalhes...'
                )
                if not ir_direto_para_pagina_lista(driver, pagina, print):
                    print(
                        f'  [CHECKPOINT] ABORTA: site não foi à pág. {pagina}. '
                        f'Não extrai a lista visível no lugar da página certa.'
                    )
                    return -1
            # Alvo batido: extração começa AQUI, sem novo Seguinte e sem depender da barra.
            print(f'  [CHECKPOINT] Site na página {pagina} — extraindo sem avançar.')
            print(f'  [TELA] Alvo {pagina} atingido — iniciando extração (Detalhes).')
            time.sleep(0.8)
            n_det = aguardar_detalhes_visiveis(driver, minimo=1, timeout=12)
            if n_det:
                print(f'  [TELA] Página {pagina}: {n_det} botão(ões) Detalhes visíveis.')
<<<<<<< HEAD
            elif pagina > 1:
                print(
                    f'  [PÁGINA] Checkpoint na pág. {pagina} sem Detalhes — '
                    f'retoma lista (não encerra modalidade).'
                )
                return -1
=======
            else:
                print(
                    f'  [TELA] Página {pagina}: nenhum Detalhes ainda — '
                    f'seguindo extração mesmo assim.'
                )
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        elif not manual:
            if painel.get('sem_popup'):
                time.sleep(1.2)
            print(f'  [PÁGINA] Avançando para página {pagina} (Seguinte)...')
            from boloes_filtro_loterica import _ler_pagina_atual_ui
            ui_antes = _ler_pagina_atual_ui(driver)
            meta_antes = painel.get('paginacao_api') or ler_metadados_paginacao_api(driver) or {}
            pa_antes = int(meta_antes.get('pagina_atual') or ui_antes or 0)
            up_antes = int(meta_antes.get('ultima_pagina') or 0)
            encerrar_wrap = not bool(painel.get('ignorar_wrap_como_fim'))

            if not ir_proxima_pagina_lista(driver, print, encerrar_no_wrap=encerrar_wrap):
                from boloes_filtro_loterica import (
                    _angular_ir_para_pagina,
                    _assinatura_lista_visivel,
                    _estado_botao_seguinte,
                    _ler_pagina_barra_somente,
                    _localizar_botao_seguinte,
<<<<<<< HEAD
                    _wrap_confirmado,
                )
                ui_depois_fail = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
                seg_agora = _estado_botao_seguinte(driver)
                btn_hab = _localizar_botao_seguinte(driver, apenas_habilitado=True)
                avancou_ui = (
                    ui_antes is not None
                    and ui_depois_fail is not None
                    and int(ui_depois_fail) > int(ui_antes)
                )
                meta_fail = ler_metadados_paginacao_api(driver) or {}
                # Lista quebrada perde a captura recente — usa última paginação boa do painel.
                if not int(meta_fail.get('ultima_pagina') or 0):
                    meta_fail = painel.get('paginacao_api') or meta_antes or meta_fail
                pa_fail = int(meta_fail.get('pagina_atual') or 0)
                up_fail = int(meta_fail.get('ultima_pagina') or 0)
                # API ainda tem página: não é fim de estado nem fim de modalidade.
                if up_fail and pa_fail < up_fail:
                    print(
                        f'  [PÁGINA] API {pa_fail}/{up_fail} — Seguinte não andou. '
                        f'Continua a paginação (não procura estado no site).'
                    )
                    return -3

                # Sem Seguinte e sem próxima na API: o loop ainda confirma antes de encerrar.
                if not avancou_ui and (btn_hab is None or seg_agora != 'habilitado'):
                    print(
                        f'  [PÁGINA] Seguinte ausente/desabilitado '
                        f'(barra={ui_depois_fail or "?"}, estado={seg_agora}). '
                        + (
                            f'API lembrada {pa_fail}/{up_fail}.'
                            if up_fail else 'Sem próxima página na API.'
                        )
                    )
                    return -2

                # Falso wrap (ex.: pág. 10 lida como 1 no reload do Angular)
                if ui_depois_fail is not None and (
                    int(ui_depois_fail) == pagina
                    or (ui_antes is not None and int(ui_depois_fail) > int(ui_antes))
                ):
                    print(
                        f'  [PÁGINA] Wrap aparente descartado — UI em '
                        f'{ui_depois_fail} (alvo {pagina}).'
                    )
                elif cfg.termo:
                    if not preparar_pagina_loterica(driver, cfg, pagina, print):
                        print('  [FILTRO] Falha ao preparar página.')
=======
                    _pagina_erro_rede,
                    _recuperar_apos_erro_rede,
                    _url_lista_ou_padrao,
                    _wrap_confirmado,
                    falha_rede_paginacao,
                    ir_direto_para_pagina_lista,
                )
                if falha_rede_paginacao() or _pagina_erro_rede(driver):
                    print(
                        '  [REDE] Queda de DNS/conexão — NÃO é fim da lista. '
                        'JSON intacto. Realinhando a página...'
                    )
                    if _pagina_erro_rede(driver):
                        if not _recuperar_apos_erro_rede(
                            driver, print, _url_lista_ou_padrao(driver),
                        ):
                            painel['abortar_retomada'] = True
                            return -1
                    if not ir_direto_para_pagina_lista(driver, pagina, print):
                        painel['abortar_retomada'] = True
                        print(
                            f'  [REDE] Não chegou na pág. {pagina}. '
                            f'Pausa nesta modalidade (rode [C] de novo).'
                        )
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
                        return -1
                    print(f'  [REDE] Site na página {pagina} — seguindo a extração.')
                else:
<<<<<<< HEAD
                    wrap_real = _wrap_confirmado(
                        driver, ui_antes, ui_depois_fail,
                        _assinatura_lista_visivel(driver), print,
                    )
                    if wrap_real and not painel.get('ignorar_wrap_como_fim'):
=======
                    ui_depois_fail = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
                    seg_agora = _estado_botao_seguinte(driver)
                    btn_hab = _localizar_botao_seguinte(driver, apenas_habilitado=True)
                    avancou_ui = (
                        ui_antes is not None
                        and ui_depois_fail is not None
                        and int(ui_depois_fail) > int(ui_antes)
                    )

                    # Sem Seguinte clicável e lista não subiu = FIM.
                    # NÃO força Angular (isso inventava pág. 8..16 com 0 bolões).
                    if not avancou_ui and (btn_hab is None or seg_agora != 'habilitado'):
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
                        print(
                            f'  [PÁGINA] FIM REAL — Seguinte ausente/desabilitado '
                            f'(barra={ui_depois_fail or "?"}, estado={seg_agora}). '
                            f'Encerrando modalidade → próxima.'
                        )
                        return -2
<<<<<<< HEAD
                    # Só salto/Angular se Seguinte AINDA está habilitado na UI
                    if btn_hab is None or seg_agora != 'habilitado':
                        print(
                            f'  [PÁGINA] FIM REAL — avanço falhou e sem Seguinte '
                            f'habilitado (barra={ui_depois_fail or "?"}).'
                        )
                        return -2
                    print(
                        f'  [PÁGINA] Avanço padrão falhou (pág. {pagina}'
                        f'{f", UI={ui_depois_fail}" if ui_depois_fail else ""}). '
                        f'Tentando salto direto (fim real só se a lista não mudar)...'
                    )
                    if ir_para_pagina_lista(driver, pagina, print):
                        print(f'  [PÁGINA] Navegou para página {pagina} (fallback direto).')
                    else:
                        meta_nav = ler_metadados_paginacao_api(driver)
                        ultima = (meta_nav or {}).get('ultima_pagina') or 0
                        pa_nav = (meta_nav or {}).get('pagina_atual') or ui_depois_fail or 0
                        if _angular_ir_para_pagina(driver, pagina, print):
                            time.sleep(2.0)
                            ui_ok = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
                            if ui_ok == pagina or (
                                ui_antes is not None and ui_ok and int(ui_ok) > int(ui_antes)
                            ):
                                print(f'  [PÁGINA] Navegou para página {pagina} (Angular forçado).')
                            elif _estado_botao_seguinte(driver) == 'habilitado':
                                print(
                                    f'  [PÁGINA] Angular incerto (UI={ui_ok}) mas '
                                    f'Seguinte ainda habilitado — não encerra.'
                                )
                            else:
                                print(
                                    f'  [PÁGINA] FIM REAL — não avançou além de '
                                    f'{pa_nav or ui_antes}'
                                    + (f' (API ultima={ultima})' if ultima else '')
                                    + f' | barra={ui_ok or "?"}.'
                                )
                                return -2
                        else:
                            if _estado_botao_seguinte(driver) == 'habilitado':
                                print(
                                    '  [PÁGINA] Salto falhou, mas Seguinte ainda '
                                    'habilitado — não trata como fim da modalidade.'
                                )
                            else:
                                print(
                                    f'  [PÁGINA] FIM REAL — impossível ir para página {pagina} '
                                    f'(lista nacional encerrada; não é só fim de um estado).'
                                )
                                return -2
=======

                    # Falso wrap (ex.: pág. 10 lida como 1 no reload do Angular)
                    if ui_depois_fail is not None and (
                        int(ui_depois_fail) == pagina
                        or (ui_antes is not None and int(ui_depois_fail) > int(ui_antes))
                    ):
                        print(
                            f'  [PÁGINA] Wrap aparente descartado — UI em '
                            f'{ui_depois_fail} (alvo {pagina}).'
                        )
                    elif cfg.termo:
                        if not preparar_pagina_loterica(driver, cfg, pagina, print):
                            print('  [FILTRO] Falha ao preparar página.')
                            return -1
                    else:
                        wrap_real = _wrap_confirmado(
                            driver, ui_antes, ui_depois_fail,
                            _assinatura_lista_visivel(driver), print,
                        )
                        if wrap_real and not painel.get('ignorar_wrap_como_fim'):
                            print(
                                f'  [PÁGINA] FIM — paginação voltou '
                                f'({ui_antes} → {ui_depois_fail}). Extração desta lista concluída.'
                            )
                            return -2
                        # Só salto/Angular se Seguinte AINDA está habilitado na UI
                        if btn_hab is None or seg_agora != 'habilitado':
                            print(
                                f'  [PÁGINA] FIM REAL — avanço falhou e sem Seguinte '
                                f'habilitado (barra={ui_depois_fail or "?"}).'
                            )
                            return -2
                        print(
                            f'  [PÁGINA] Avanço padrão falhou (pág. {pagina}'
                            f'{f", UI={ui_depois_fail}" if ui_depois_fail else ""}). '
                            f'Tentando salto direto (fim real só se a lista não mudar)...'
                        )
                        if ir_para_pagina_lista(driver, pagina, print):
                            print(f'  [PÁGINA] Navegou para página {pagina} (fallback direto).')
                        else:
                            meta_nav = ler_metadados_paginacao_api(driver)
                            ultima = (meta_nav or {}).get('ultima_pagina') or 0
                            pa_nav = (meta_nav or {}).get('pagina_atual') or ui_depois_fail or 0
                            if _angular_ir_para_pagina(driver, pagina, print):
                                time.sleep(2.0)
                                ui_ok = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
                                if ui_ok == pagina or (
                                    ui_antes is not None and ui_ok and int(ui_ok) > int(ui_antes)
                                ):
                                    print(f'  [PÁGINA] Navegou para página {pagina} (Angular forçado).')
                                elif _estado_botao_seguinte(driver) == 'habilitado':
                                    print(
                                        f'  [PÁGINA] Angular incerto (UI={ui_ok}) mas '
                                        f'Seguinte ainda habilitado — não encerra.'
                                    )
                                else:
                                    print(
                                        f'  [PÁGINA] FIM REAL — não avançou além de '
                                        f'{pa_nav or ui_antes}'
                                        + (f' (API ultima={ultima})' if ultima else '')
                                        + f' | barra={ui_ok or "?"}.'
                                    )
                                    return -2
                            else:
                                if _estado_botao_seguinte(driver) == 'habilitado':
                                    print(
                                        '  [PÁGINA] Salto falhou, mas Seguinte ainda '
                                        'habilitado — não trata como fim da modalidade.'
                                    )
                                else:
                                    print(
                                        f'  [PÁGINA] FIM REAL — impossível ir para página {pagina} '
                                        f'(lista nacional encerrada; não é só fim de um estado).'
                                    )
                                    return -2
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
            else:
                from boloes_filtro_loterica import _assinatura_lista_visivel, _wrap_confirmado
                ui_depois = _ler_pagina_atual_ui(driver)
                ignorar_wrap = bool(painel.get('ignorar_wrap_como_fim'))
                # [1] e [C]: número tem que SUBIR. Recuo 9→2 = falha, tenta salto à página alvo.
                if (
                    ui_antes is not None
                    and ui_depois is not None
                    and int(ui_depois) < int(ui_antes)
                    and int(ui_depois) > 1
                ):
                    print(
                        f'  [PÁGINA] Recuo {ui_antes} → {ui_depois} (alvo {pagina}). '
                        f'Não extrai esta tela — corrige com salto direto.'
                    )
                    if ir_para_pagina_lista(driver, pagina, print):
                        print(f'  [PÁGINA] Navegou para página {pagina} (corrigiu recuo).')
                    else:
                        from boloes_filtro_loterica import _angular_ir_para_pagina
                        if _angular_ir_para_pagina(driver, pagina, print):
                            time.sleep(2.0)
                        ui_ok = _ler_pagina_atual_ui(driver)
                        if ui_ok == pagina:
                            print(f'  [PÁGINA] Navegou para página {pagina} (Angular).')
                        else:
                            print(
                                f'  [PÁGINA] Ainda em {ui_ok or "?"} (alvo {pagina}) '
                                f'após recuo — não extrai esta tela.'
                            )
                            return -1
                elif ignorar_wrap:
                    print(
                        f'  [PÁGINA] Avanço OK '
                        f'{ui_antes or "?"} → {ui_depois or "nova lista"}.'
                    )
                elif _wrap_confirmado(
                    driver, ui_antes, ui_depois, _assinatura_lista_visivel(driver), print,
                ):
                    print(
                        f'  [PÁGINA] FIM — wrap após Seguinte '
                        f'({ui_antes} → {ui_depois}). Não processa outra lista/UF.'
                    )
                    return -2
                if not ignorar_wrap:
                    meta_depois = ler_metadados_paginacao_api(driver) or {}
                    pa_dep = int(meta_depois.get('pagina_atual') or ui_depois or 0)
                    ui_ok = _ler_pagina_atual_ui(driver)
                    # Wrap real só se UI e API concordam na pág. 1 (não 10 lido como 1)
                    if (
                        pa_antes > 1
                        and pa_dep == 1
                        and ui_ok is not None
                        and int(ui_ok) == 1
                        and _wrap_confirmado(
                            driver, ui_antes, ui_ok, _assinatura_lista_visivel(driver), print,
                        )
                    ):
                        print(
                            f'  [PÁGINA] FIM — paginação resetou para pág. 1 após {pa_antes}'
                            + (f'/{up_antes}' if up_antes else '')
                            + '.'
                        )
                        return -2
            time.sleep(1.2)
            n_det = aguardar_detalhes_visiveis(driver, minimo=1, timeout=12)
            if n_det:
                print(f'  [TELA] Página {pagina}: {n_det} botão(ões) Detalhes visíveis.')
            else:
                # Avanço "OK" sem lista = falso positivo (ex.: 9→"nova lista" vazia).
                # Não processa página vazia nem avança checkpoint — recupera sessão.
                print(
                    f'  [PÁGINA] Após avanço: 0 Detalhes na página {pagina}. '
                    f'Não trata como fim da lista — retoma a paginação.'
                )
                return -1
        else:
            print(f'  [FILTRO] Página {pagina} — modo manual (você navegou).')

    aguardar_capturas_api(driver, minimo=1, timeout=12)
    preparar_pagina_para_detalhes(driver, log_fn=print)
    meta = detectar_detalhes_pagina(driver, cfg, 55, preparar=False, log_fn=print)
    n_esperado = meta['n_esperado']
    codigos = meta['codigos']

    # Retomada intra-página: quantos desta página já estão no JSON
    ab_ck = painel.get('arquivo_base') or arquivo_base
    path_json_pag = os.path.join(PASTA_JSON, f'{ab_ck}.json') if ab_ck else ''
    existentes_pag = carregar_json_boloes(path_json_pag) if path_json_pag else []
    ja_coletados = sum(1 for b in existentes_pag if b.get('pagina') == pagina)
    if ja_coletados:
        print(
            f'  [CHECKPOINT] JSON já tem {ja_coletados} bolão(ões) da página {pagina}'
            + (f' (meta tela={n_esperado}).' if n_esperado else '.')
        )

    if n_esperado:
        print(f'  [TELA] Meta desta página: {n_esperado} bolão(ões).')
        if ja_coletados >= n_esperado:
            print('  [TELA] Página já coberta no JSON — não inicia cliques.')
        else:
            print('  [TELA] Iniciando cliques em Detalhes...')
    else:
        # Página 1 sem Detalhes é tratada no loop; página 2+ vazia = falha de sessão/lista.
        if pagina > 1 and not manual:
            print(
                f'  [PÁGINA] Página {pagina} sem Detalhes — não marca lista esgotada. '
                f'Retoma do checkpoint.'
            )
            return -1
        print('  [TELA] Nenhum Detalhes visível — tentando lista API interceptada...')

    # ── Callback: grava no JSON em tempo real a cada bloco de detalhes ───────
    # IMPORTANTE: NÃO faz boloes.append aqui — isso é feito pelo loop principal
    # depois que detalhar_pagina_ate_esperado retorna. O callback só grava no disco.
    concurso_alvo = painel.get('concurso_alvo') or _concurso_de_arquivo_base(arquivo_base)

    def _salvar_tempo_real(boloes_parciais):
        if not arquivo_base or not boloes_parciais:
            return
        ca = painel.get('concurso_alvo') or concurso_alvo
        alvo = _boloes_para_json_arquivo(boloes_parciais, mod_esperada, ca)
        if alvo:
            for b in alvo:
                b['pagina'] = pagina
                b['rodada_filtro'] = painel.get('rodada_filtro', 1)
            salvar_parcial(alvo, painel.get('arquivo_base') or arquivo_base, pagina)

    detalhar_pagina_ate_esperado(
        driver, cfg, parser_slug, hashes, n_esperado, codigos, print,
        on_progresso=_salvar_tempo_real if arquivo_base else None,
        ja_coletados=ja_coletados,
        sem_popup=bool(painel.get('sem_popup')),
    )

    n_caps = len(ler_capturas_api(driver))
    painel['capturas_ultima_pagina'] = n_caps
    painel['capturas_api'] += n_caps
    meta_pag = ler_metadados_paginacao_api(driver)
    if meta_pag:
        painel['paginacao_api'] = meta_pag
    painel['detalhes_tela_pagina'] = n_esperado

    ab = painel.get('arquivo_base') or arquivo_base
    n_gravados, ab = _persistir_json_pagina(
        pagina, painel.get('rodada_filtro', 1), ab, painel, mod_esperada, parser_slug, hashes, boloes,
    )
    painel['arquivo_base'] = ab

    # Contagem efetiva na página (disco + novos desta passagem)
    existentes_apos = carregar_json_boloes(os.path.join(PASTA_JSON, f'{ab}.json')) if ab else []
    n_pagina_json = sum(1 for b in existentes_apos if b.get('pagina') == pagina)
    n_efetivo = max(n_gravados, n_pagina_json, ja_coletados)

    novos_loterica = _boloes_do_filtro(
        [b for b in boloes if b.get('pagina') == pagina], cfg,
    )
    if cfg.termo and n_efetivo and len(novos_loterica) != n_gravados and n_gravados:
        _out(
            f'  [FILTRO] Lotérica alvo nesta pág.: {len(novos_loterica)} de {n_gravados} '
            f'(todos {n_gravados} foram gravados no JSON da modalidade).'
        )

    if not n_gravados and n_caps > 0 and n_pagina_json < (n_esperado or 1):
        _diagnosticar_capturas_sem_filtro(cfg, parser_slug)

    painel['pendentes_pagina'] = max(0, n_esperado - n_efetivo) if n_esperado else 0
    painel['pagina_completa'] = bool(n_esperado and n_efetivo >= n_esperado) or (not n_esperado and n_efetivo > 0)
    if n_esperado and n_efetivo < n_esperado:
        print(f'  [AVISO] Página incompleta: {n_efetivo}/{n_esperado} bolões no JSON desta página.')
    elif n_esperado and n_efetivo >= n_esperado and n_gravados == 0 and ja_coletados:
        print(f'  [CHECKPOINT] Página {pagina} confirmada no JSON: {n_efetivo}/{n_esperado}.')

    return n_efetivo


# ─────────────────────────────────────────────────────────────────────────────
# Loop principal de páginas
# ─────────────────────────────────────────────────────────────────────────────

def _loop_extracao_paginas(
    cfg, parser_slug, mod_slug, arquivo_base,
    manual_paginas, rodada_filtro=1, voce_encerra=False,
    painel_extra=None, mod_esperada=None, concurso_alvo: str = '',
    forcar_pagina_inicial: Optional[int] = None,
    uf_varredura: str = '',
    ufs_concluidas: Optional[list] = None,
    marcar_concluido_ao_fim: bool = True,
    sem_popup: bool = False,
):
    boloes: list = []
    hashes: set = set()
    hashes_pagina_anterior: set = set()
    painel = _novo_painel_extracao()
    painel['rodada_filtro'] = rodada_filtro
    painel['arquivo_base'] = arquivo_base
    painel['concurso_alvo'] = concurso_alvo or _concurso_de_arquivo_base(arquivo_base)
    painel['sem_popup'] = bool(sem_popup)
<<<<<<< HEAD
    # sem_popup só esconde o popup.
    # Volta à página 1 com lista nova = próximo estado do site, não o fim.
    painel['ignorar_wrap_como_fim'] = True
=======
    # [C] pagina até o fim da UF atual; a troca SP→AC→… é do ciclo.
    # sem_popup só esconde o popup. NÃO amarrar wrap em sem_popup.
    painel['ignorar_wrap_como_fim'] = False
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    if uf_varredura:
        painel['uf_varredura'] = uf_varredura
    if painel_extra:
        painel.update(painel_extra)
        # painel_extra não deve apagar a flag do modo rápido
        if sem_popup:
            painel['sem_popup'] = True
<<<<<<< HEAD
        painel['ignorar_wrap_como_fim'] = True
    if painel.get('sem_popup'):
        _out('  [RÁPIDO] Modo SEM POPUP ativo nesta extração.')
        _out('  [CICLO] Detalhes de todos os bolões da página, grava, próxima página.')
        _out('  [CICLO] Sem filtro de estado — a paginação do site troca a UF.')
=======
        painel['ignorar_wrap_como_fim'] = False
    if painel.get('sem_popup'):
        _out('  [RÁPIDO] Modo SEM POPUP ativo nesta extração.')
        _out('  [CICLO] Paginação desta UF até o fim real; o ciclo segue até o último estado.')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257

    # Continuar: modalidade do site = JSON dessa modalidade (nunca arquivo de outra)
    mod_esperada, concurso_alvo, arquivo_base = _amarrar_sessao_ao_site(
        mod_esperada, concurso_alvo or painel.get('concurso_alvo') or '', arquivo_base,
    )
    if mod_esperada:
        parser_slug = getattr(mod_esperada, 'parser_slug', None) or parser_slug
        mod_slug = mod_esperada.slug or mod_slug
    # Cria o JSON na pasta ANTES de paginar — usuário vê o arquivo da modalidade na hora
    arquivo_base = _garantir_arquivo_modalidade(
        arquivo_base, mod_esperada, concurso_alvo or painel.get('concurso_alvo') or '',
    )
    painel['arquivo_base'] = arquivo_base
    if concurso_alvo:
        painel['concurso_alvo'] = concurso_alvo

    inicio = time.time()
    pagina = 1
    pausado = False
    chegou_ao_fim = False
    ufs_ok = list(ufs_concluidas or [])

    def _extra_ck() -> dict:
        extra = {}
        if uf_varredura:
            extra['uf_atual'] = uf_varredura
        if ufs_ok:
            extra['ufs_concluidas'] = list(ufs_ok)
        return extra

    limpar_capturas_api(driver)
    _out('  [API] Capturas anteriores limpas — só dados desta extração.')

    hashes_base, arquivo_base = _iniciar_continuidade_inteligente(
        arquivo_base, mod_esperada, painel, concurso=painel.get('concurso_alvo') or '',
    )
    hashes.update(hashes_base)
    painel['arquivo_base'] = arquivo_base
    if not painel.get('concurso_alvo'):
        painel['concurso_alvo'] = _concurso_de_arquivo_base(arquivo_base)

    # ── Checkpoint / retomada (não altera login nem parsing) ─────────────────
    path_existente = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
    existentes_disco = carregar_json_boloes(path_existente)
    # Se a sessão estiver vazia/corrompida, tenta CONSOLIDADO / localizar
    if not existentes_disco:
        path_alt, alt = localizar_arquivo_sessao_existente(
            PASTA_JSON, arquivo_base,
            mod_esperada.slug if mod_esperada else mod_slug,
            painel.get('concurso_alvo') or '',
        )
        if alt:
            existentes_disco = alt
            _out(f'  [CHECKPOINT] Usando backup/localizado: {os.path.basename(path_alt or "")} ({len(alt)} reg.)')
            # restaura sessão a partir do backup legível
            if path_alt and path_alt != path_existente and alt:
                salvar_json_boloes(path_existente, alt)
                _out(f'  [CHECKPOINT] Sessão restaurada → {os.path.basename(path_existente)}')

<<<<<<< HEAD
    from boloes_checkpoint import boloes_do_concurso
    conc_filtro = str(painel.get('concurso_alvo') or '')
    base_paginas = boloes_do_concurso(existentes_disco, conc_filtro)
    if uf_varredura:
        sig = uf_varredura.upper()
        base_paginas = [
            b for b in base_paginas
            if str(b.get('uf_varredura') or '').upper() == sig
            or (
                not str(b.get('uf_varredura') or '').strip()
                and str(b.get('uf') or '').upper() == sig
            )
        ]
    ultima_arq, _ck_arq = resolver_pagina_retomada(PASTA_JSON, arquivo_base, base_paginas)
    if conc_filtro and existentes_disco and ultima_arq <= 0:
        if forcar_pagina_inicial and int(forcar_pagina_inicial) > 1:
            _out(
                f'  [CHECKPOINT] Concurso {conc_filtro} não tem páginas 1..N '
                f'{"da UF " + uf_varredura if uf_varredura else "neste JSON"}. '
                f'Ignora a pág. {forcar_pagina_inicial} e começa na 1.'
            )
        if forcar_pagina_inicial is not None:
            forcar_pagina_inicial = 1
    if ultima_arq > 0:
        pagina_arq = ultima_arq + 1
        if forcar_pagina_inicial is None or int(forcar_pagina_inicial) != pagina_arq:
            _out(
                f'  [CHECKPOINT] Arquivo {arquivo_base}.json: última pág. completa={ultima_arq} '
                f'-> retoma na {pagina_arq} (nao na 1).'
            )
        forcar_pagina_inicial = pagina_arq
=======
    existentes_retoma = existentes_disco
    if uf_varredura:
        existentes_retoma = [
            b for b in existentes_disco
            if str(b.get('uf') or '').upper() == str(uf_varredura).upper()
        ]
        if existentes_disco:
            _out(
                f'  [UF] Retomada de {uf_varredura}: {len(existentes_retoma)} bolões desta UF '
                f'(JSON tem {len(existentes_disco)} no total).'
            )
    ultima_arq, n_retoma = decidir_pagina_inicial(
        PASTA_JSON, arquivo_base, existentes_retoma, uf=uf_varredura or '',
    )
    if ultima_arq > 1:
        if forcar_pagina_inicial is None or int(forcar_pagina_inicial) != ultima_arq:
            kb_ex = os.path.getsize(path_existente) / 1024 if os.path.isfile(path_existente) else 0
            _out(
                f'  [CHECKPOINT] Reconhecido {arquivo_base}.json: '
                f'{len(existentes_disco) or n_retoma} bolões | {kb_ex:.1f} KB | '
                f'última pág. completa={ultima_arq - 1} → retoma na {ultima_arq} (não na 1).'
            )
        forcar_pagina_inicial = ultima_arq
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257

    if forcar_pagina_inicial is not None:
        pagina = max(1, int(forcar_pagina_inicial))
        retomou = pagina > 1
        if retomou:
            _out(f'  [UF] Retomando {uf_varredura or "?"} na página {pagina}')
        else:
            _out(f'  [UF] Iniciando {uf_varredura or "?"} na página 1')
    elif sem_popup:
        ultima_auto, _ck_auto = resolver_pagina_retomada(
            PASTA_JSON, arquivo_base, existentes_disco,
        )
        if ultima_auto > 0:
            pagina, retomou = ultima_auto + 1, True
            _out(f'  [AUTO] Retomada automática na página {pagina} (sem confirmação).')
        else:
            pagina, retomou = 1, False
    else:
        pagina, retomou = perguntar_retomada(
            PASTA_JSON, arquivo_base, base_paginas, out_fn=_out,
        )
    reset_pause_flags(PASTA_JSON)
    instruir_pause(PASTA_JSON, _out)

    if retomou and pagina > 1 and not manual_paginas:
<<<<<<< HEAD
        _out(f'  [CHECKPOINT] Indo DIRETO para a pagina {pagina} (sem parar no terminal)...')
        from boloes_filtro_loterica import _ler_pagina_atual_ui
        chegou = False
        for tentativa in range(1, 4):
            ir_direto_para_pagina_lista(driver, pagina, print)
            atual_ui = _ler_pagina_atual_ui(driver)
            if (atual_ui or 0) == pagina:
                chegou = True
                break
            _out(
                f'  [CHECKPOINT] Edge em {atual_ui or "?"} — '
                f'relogin e novo salto ({tentativa}/3).'
            )
            if _retomar_lista_na_pagina(
                mod_esperada, pagina, painel.get('concurso_alvo') or '',
            ):
                chegou = True
                break
        if chegou:
            painel['pular_navegacao_proxima'] = True
            _out(f'  [CHECKPOINT] Iniciando extracao a partir da pagina {pagina}.')
        else:
            _out(
                f'  [CHECKPOINT] Ainda não confirmou a pág. {pagina}. '
                f'O loop segue tentando — não para e não volta para a página 1.'
            )
            painel['forcar_salto_checkpoint'] = pagina
=======
        # Um único alinhamento: dentro de _capturar_pagina_atual, depois EXTRAÇÃO.
        # Não clica Seguinte aqui — senão anda 1→alvo, lê barra="?" e anda de novo.
        _out(
            f'  [CHECKPOINT] Retomada na página {pagina}: '
            f'tenta SALTO DIRETO; se a barra não confirmar, clica SEGUINTE até {pagina}.'
        )
        from boloes_filtro_loterica import _ler_pagina_atual_ui, _ler_pagina_barra_somente
        barra = _ler_pagina_barra_somente(driver)
        atual_ui = barra or _ler_pagina_atual_ui(driver)
        if sem_popup:
            _out(
                f'  [CHECKPOINT] Site agora na barra {barra or atual_ui or "?"} — '
                f'alinha até {pagina} e inicia extração (sem segundo passe).'
            )
        else:
            tentativas_manual = 0
            while (atual_ui or 0) != pagina:
                tentativas_manual += 1
                _out('')
                _out('!' * 60)
                _out(f'  ATENCAO: Edge esta na pagina {atual_ui or "?"} — precisamos da {pagina}.')
                _out(f'  1) No Edge, use a paginacao e va ate a pagina {pagina}')
                _out('  2) Volte neste terminal')
                _out('  3) Digite OK e Enter (ou so Enter para tentar de novo)')
                _out('  Digite FORCAR + Enter para extrair a página visível mesmo assim (não recomendado)')
                _out('  [C] / Continuar NÃO extrai página errada — só OK se a página já for a certa.')
                _out('!' * 60)
                try:
                    resp_pag = input('>>> OK / FORCAR / Enter: ').strip().upper()
                except EOFError:
                    resp_pag = ''
                if resp_pag in ('FORCAR', 'F', 'FORCE'):
                    _out(f'  [CHECKPOINT] FORCAR — extraindo a pagina visivel como se fosse {pagina}.')
                    break
                ir_direto_para_pagina_lista(driver, pagina, print)
                atual_ui = _ler_pagina_atual_ui(driver)
                if (atual_ui or 0) == pagina:
                    break
                if resp_pag in ('OK', 'SIM') and (atual_ui or 0) == pagina:
                    _out('  [CHECKPOINT] OK aceito — página confere.')
                    break
                if resp_pag in ('C', 'CONTINUAR'):
                    _out(
                        '  [AMARRA] Continuar só segue se a página do site for a do JSON. '
                        'Ajuste a paginação no Edge ou digite FORCAR.'
                    )
                if tentativas_manual >= 5:
                    atual_ui = _ler_pagina_atual_ui(driver) or 0
                    if int(atual_ui or 0) < 2 and pagina > 2:
                        _out(
                            f'  [CHECKPOINT] ABORTA: site na pág. {atual_ui or 1}, '
                            f'JSON pede pág. {pagina}. Não extrai do início (não mistura SP de novo).'
                        )
                        painel['abortar_retomada'] = True
                        break
                    _out('  [CHECKPOINT] Muitas tentativas — use FORCAR ou ajuste o Edge.')
        if painel.get('abortar_retomada'):
            _out('  Extração NÃO começou — o site não está na página do JSON.')
            _out('  [CICLO] Modalidade fica PENDENTE (não passa para a próxima).')
            painel['chegou_ao_fim'] = False
            painel['uf_concluida'] = False
            painel['pausado_retomada'] = True
            painel['paginas_processadas'] = max(0, pagina - 1)
            return [], hashes, painel, arquivo_base
        painel['pular_navegacao_proxima'] = True
        _out(f'  [CHECKPOINT] Iniciando extracao a partir da pagina {pagina}.')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        salvar_checkpoint(
            PASTA_JSON,
            modalidade=(mod_esperada.slug if mod_esperada else mod_slug) or '',
            modalidade_label=(mod_esperada.label if mod_esperada else '') or '',
            concurso=painel.get('concurso_alvo') or '',
            arquivo_base=arquivo_base,
            pagina_atual=pagina - 1,
            total_paginas=218,
            boloes_extraidos=len(existentes_disco),
            status=STATUS_EXECUTANDO,
            extra=_extra_ck(),
        )

    dez = cfg.qtd_dezenas or 'qualquer'
    lot_txt = 'QUALQUER lotérica' if cfg.qualquer_loterica else (cfg.termo or '(filtro manual no site)')
    conc_txt = painel.get('concurso_alvo') or 'auto'
    print('\n  [PAINEL] Contadores: páginas | registros/página | total | únicos')
    print(f'  Filtro lotérica: {lot_txt} | dezenas: {dez} (painel/resumo)')
    print(f'  JSON arquivo  : json-boloes/{arquivo_base}.json  (modalidade + concurso {conc_txt})')
    print('  Gravação      : tempo real — um único JSON de sessão (sem CONSOLIDADO duplicado)')
    if mod_esperada:
        print(f'  Modalidade alvo: {mod_esperada.label}')
    if retomou:
        print(f'  Retomada      : iniciando na página {pagina}')

    while True:
        if painel.get('forcar_salto_checkpoint') and not manual_paginas:
            alvo_ck = int(painel['forcar_salto_checkpoint'])
            _out(f'  [CHECKPOINT] Novo salto para a página {alvo_ck}...')
            if _retomar_lista_na_pagina(
                mod_esperada, alvo_ck, painel.get('concurso_alvo') or '',
            ):
                painel.pop('forcar_salto_checkpoint', None)
                painel['pular_navegacao_proxima'] = True
                pagina = alvo_ck
            else:
                time.sleep(4)
                continue

        if manual_paginas and pagina > 1:
            try:
                resp = input(
                    f'\n>>> [{cfg.termo}] PÁGINA {pagina} no site — '
                    f'navegue e ENTER | FIM=acabou | P=pausar: '
                ).strip().upper()
            except EOFError:
                break
            if resp in ('P', 'PAUSAR', 'PAUSE'):
                pausado = True
                painel['pausado_operador'] = True
                _out('  [CHECKPOINT] Pausado pelo usuário.')
                break
            if resp == 'FIM':
                print('  Fim deste filtro (você encerrou).')
                break

        print(f'\n>>> Processando PÁGINA {pagina}...')
        n_novos = _capturar_pagina_atual(
            cfg, parser_slug, hashes, pagina, boloes, manual_paginas, painel, mod_esperada,
            arquivo_base=arquivo_base,
        )
        arquivo_base = painel.get('arquivo_base') or arquivo_base
        if pagina == 1 and n_novos == 0 and (painel.get('detalhes_tela_pagina') or 0) < 1:
            if uf_varredura:
                print(f'\n  [UF] {uf_varredura} sem bolões nesta lista — próximo estado.')
                painel['uf_vazia'] = True
                painel['uf_concluida'] = True
                painel['chegou_ao_fim'] = True
                chegou_ao_fim = True
                break
            falhas_p1 = int(painel.get('_falhas_pagina1') or 0) + 1
            painel['_falhas_pagina1'] = falhas_p1
            print(
                f'\n  [SESSÃO] Página 1 sem bolões ({falhas_p1}). '
                f'Relogin e tenta de novo — não encerra o ciclo.'
            )
            if _retomar_lista_na_pagina(
                mod_esperada, 1, painel.get('concurso_alvo') or '',
            ):
                painel['pular_navegacao_proxima'] = True
                continue
            time.sleep(min(5 * falhas_p1, 30))
            continue
        if n_novos == -3:
            tent = int(painel.get('_retry_avanco') or 0) + 1
            painel['_retry_avanco'] = tent
            meta_r = ler_metadados_paginacao_api(driver) or {}
            pa_r = int(meta_r.get('pagina_atual') or 0)
            up_r = int(meta_r.get('ultima_pagina') or 0)
            print(
                f'  [PÁGINA] Avanço incompleto ({tent}) — API {pa_r or "?"}/{up_r or "?"}. '
                f'Continua a paginação.'
            )
            from boloes_filtro_loterica import ir_para_pagina_lista
            destino = max(pagina, (pa_r + 1) if up_r and pa_r < up_r else pagina)
            if ir_para_pagina_lista(driver, destino, print):
                painel['pular_navegacao_proxima'] = True
                painel['_retry_avanco'] = 0
                pagina = destino
                continue
            if tent <= 6:
                time.sleep(1.5)
                continue
            print('  [PÁGINA] Várias tentativas sem avançar. Relogin e checkpoint.')
            if _retomar_lista_na_pagina(
                mod_esperada, pagina, painel.get('concurso_alvo') or '',
            ):
                painel['pular_navegacao_proxima'] = True
                painel['_retry_avanco'] = 0
                continue
            if up_r and pa_r >= up_r:
                print(f'\n  {MSG_ULTIMA_PAGINA}')
                chegou_ao_fim = True
                break
            time.sleep(3)
            painel['_retry_avanco'] = 0
            continue
        if n_novos == -2:
            from boloes_filtro_loterica import (
                _estado_botao_seguinte,
                _ler_pagina_barra_somente,
                _ler_pagina_atual_ui,
<<<<<<< HEAD
                ir_para_pagina_lista,
            )
            ui_now = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
            seg_now = _estado_botao_seguinte(driver)
            meta_fim = ler_metadados_paginacao_api(driver) or {}
            # Sem captura nova (lista sumiu): usa última API boa — evita encerrar só em SP.
            if not int(meta_fim.get('ultima_pagina') or 0):
                meta_fim = painel.get('paginacao_api') or meta_fim
            pa_api = int(meta_fim.get('pagina_atual') or 0)
            up_api = int(meta_fim.get('ultima_pagina') or 0)
            # API ainda tem página → não é fim. A paginação segue (sem procurar UF).
            if up_api and pa_api < up_api:
                print(
                    f'  [PÁGINA] API {pa_api}/{up_api} — não encerra. '
                    f'Continua a paginação (todas as UFs).'
                )
                destino = max(pagina, pa_api + 1)
                if _retomar_lista_na_pagina(
                    mod_esperada, destino, painel.get('concurso_alvo') or '',
                ) or ir_para_pagina_lista(driver, destino, print):
                    painel['pular_navegacao_proxima'] = True
                    pagina = destino
                continue
            # Seguinte ainda clicável: não é fim.
            if seg_now == 'habilitado':
                recusas = int(painel.get('_recusas_fim_falso') or 0)
                if recusas < 3:
                    painel['_recusas_fim_falso'] = recusas + 1
                    print(
                        f'  [PÁGINA] Fim aparente recusado ({recusas + 1}/3) — '
                        f'UI={ui_now or "?"} Seguinte={seg_now}. '
                        f'Continua na página {pagina}...'
                    )
                    if ui_now is not None and int(ui_now) >= pagina:
                        painel['pular_navegacao_proxima'] = True
                    else:
                        ir_para_pagina_lista(driver, pagina, print)
                        painel['pular_navegacao_proxima'] = True
                    continue
            # Botão ausente: reloga e tenta a mesma página (até 4× — site troca UF na paginação).
            recusas_fim = int(painel.get('_fim_recusado') or 0)
            if recusas_fim < 4:
                painel['_fim_recusado'] = recusas_fim + 1
                print(
                    f'  [PÁGINA] Seguinte={seg_now} (barra={ui_now or "?"}) — '
                    f'não encerra ({recusas_fim + 1}/4). Relogin e segue a paginação.'
                )
                # Retoma na última página boa (não na vazia que sumiu a barra).
                alvo_retoma = max(1, (pa_api or pagina) if pa_api else max(1, pagina - 1))
                if _retomar_lista_na_pagina(
                    mod_esperada, alvo_retoma, painel.get('concurso_alvo') or '',
                ):
                    painel['pular_navegacao_proxima'] = True
                    pagina = alvo_retoma
                continue
            if up_api and pa_api >= up_api and seg_now != 'habilitado':
                print(
                    f'\n  [PÁGINA] API na página {pa_api} de {up_api} '
                    f'e Seguinte={seg_now}. Paginação desta lista esgotada.'
                )
                print(f'  {MSG_ULTIMA_PAGINA}')
                chegou_ao_fim = True
                painel['fim_lista_confirmado'] = True
                break
            if not up_api and seg_now != 'habilitado':
                # Sem meta API: só encerra se já houve várias retomadas sem sucesso.
                giros = int(painel.get('_giros_fim') or 0) + 1
                painel['_giros_fim'] = giros
                if giros < 6:
                    print(
                        f'  [PÁGINA] Seguinte={seg_now} sem meta API '
                        f'(giro {giros}/6) — reabre lista e continua (todas as UFs).'
                    )
                    alvo_retoma = max(1, pagina - 1)
                    if _retomar_lista_na_pagina(
                        mod_esperada, alvo_retoma, painel.get('concurso_alvo') or '',
                    ):
                        painel['pular_navegacao_proxima'] = True
                        pagina = alvo_retoma
                    painel['_fim_recusado'] = 0
                    continue
                print(
                    f'\n  [PÁGINA] Lista esgotada após {giros} tentativas '
                    f'(Seguinte={seg_now}, barra={ui_now or "?"}). Próxima modalidade.'
                )
                print(f'  {MSG_ULTIMA_PAGINA}')
                chegou_ao_fim = True
                painel['fim_lista_confirmado'] = True
                break
            giros = int(painel.get('_giros_fim') or 0) + 1
            painel['_giros_fim'] = giros
            if giros >= 8 and not (up_api and pa_api < up_api):
                print(
                    f'\n  [PÁGINA] {giros} tentativas sem próxima página. '
                    f'Próxima modalidade.'
                )
                print(f'  {MSG_ULTIMA_PAGINA}')
                chegou_ao_fim = True
                painel['fim_lista_confirmado'] = True
                break
            print(
                f'  [PÁGINA] Seguinte ainda em "{seg_now}" (barra={ui_now or "?"}). '
                f'Não encerra — tenta a paginação de novo.'
            )
            painel['_recusas_fim_falso'] = 0
            painel['_fim_recusado'] = 0
            continue
=======
                _pagina_erro_rede,
                falha_rede_paginacao,
                ir_para_pagina_lista,
            )
            if falha_rede_paginacao() or _pagina_erro_rede(driver):
                print(
                    '\n  [REDE] Queda de DNS/conexão — NÃO encerra a modalidade. '
                    'Pausa para retomar no [C] (JSON intacto).'
                )
                painel['abortar_retomada'] = True
                break
            ui_now = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
            seg_now = _estado_botao_seguinte(driver)
            # Seguinte cinza = fim de verdade. NÃO recusar por UI>=contador (51 vs 38).
            if seg_now != 'habilitado':
                print(
                    f'\n  [PÁGINA] Lista esgotada (Seguinte={seg_now}, '
                    f'barra={ui_now or "?"}). Próxima modalidade.'
                )
                print(f'  {MSG_ULTIMA_PAGINA}')
                chegou_ao_fim = True
                break
            recusas = int(painel.get('_recusas_fim_falso') or 0)
            if recusas < 3:
                painel['_recusas_fim_falso'] = recusas + 1
                print(
                    f'  [PÁGINA] Fim aparente recusado ({recusas + 1}/3) — '
                    f'UI={ui_now or "?"} Seguinte={seg_now}. '
                    f'Continua na página {pagina}...'
                )
                if ui_now is not None and int(ui_now) >= pagina:
                    painel['pular_navegacao_proxima'] = True
                else:
                    ir_para_pagina_lista(driver, pagina, print)
                    painel['pular_navegacao_proxima'] = True
                continue
            print(f'\n  {MSG_ULTIMA_PAGINA}')
            chegou_ao_fim = True
            break
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        if n_novos < 0:
            falhas = int(painel.get('_falhas_sessao') or 0) + 1
            painel['_falhas_sessao'] = falhas
            # Página N sem Detalhes após avanço: retoma N-1 (última boa), não a vazia.
            meta_ck = painel.get('paginacao_api') or {}
            pa_ck = int(meta_ck.get('pagina_atual') or 0)
            alvo = max(1, pa_ck or (pagina - 1 if pagina > 1 else 1))
            print(
                f'\n  [SESSÃO] Página {pagina} interrompida ({falhas}). '
                f'Relogin na pág. {alvo} — a modalidade não encerra '
                f'(continua até todos os estados).'
            )
            if _retomar_lista_na_pagina(
                mod_esperada, alvo, painel.get('concurso_alvo') or '',
            ):
                painel['pular_navegacao_proxima'] = True
                painel['_falhas_sessao'] = 0
                pagina = alvo
                continue
            if falhas >= 8:
                print('  [SESSÃO] Várias falhas. Espera 60s e tenta de novo.')
                time.sleep(60)
                painel['_falhas_sessao'] = 0
            else:
                time.sleep(min(4 * falhas, 20))
            continue

        painel['_recusas_fim_falso'] = 0
        painel['_fim_recusado'] = 0
        painel['_retry_avanco'] = 0
        painel['_falhas_sessao'] = 0
        painel['_giros_fim'] = 0

        painel['_recusas_fim_falso'] = 0

        page_boloes = [b for b in boloes if b.get('pagina') == pagina]
        page_loterica = _boloes_do_filtro(page_boloes, cfg)
        h_pag = hashes_pagina(page_boloes)
        if n_novos and h_pag and h_pag == hashes_pagina_anterior:
            print('  [AVISO] Página igual à anterior — confira navegação.')
        if pagina == 1 and h_pag:
            painel['hashes_pagina_1'] = h_pag
        elif (
            pagina > 2
            and h_pag
            and painel.get('hashes_pagina_1')
            and h_pag == painel['hashes_pagina_1']
        ):
<<<<<<< HEAD
            meta_volta = ler_metadados_paginacao_api(driver) or {}
            pa_v = int(meta_volta.get('pagina_atual') or 0)
            up_v = int(meta_volta.get('ultima_pagina') or 0)
            if up_v and pa_v < up_v:
                print(
                    f'  [PÁGINA] Conteúdo parecido com a pág. 1, mas API {pa_v}/{up_v}. '
                    f'Continua a paginação.'
                )
            else:
                print(
                    '  [PÁGINA] Conteúdo igual ao da página 1 e sem próxima na API. '
                    'Paginação desta modalidade esgotada.'
                )
                chegou_ao_fim = True
                break
=======
            print(
                '  [PÁGINA] Conteúdo igual ao da página 1 — lista deu a volta. '
                'Fim real (não é só wrap falso).'
            )
            chegou_ao_fim = True
            break
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        hashes_pagina_anterior = h_pag

        # Anti-loop: barra do site parada + 0 bolões novos → fim da modalidade
        ui_barra = None
        seg_agora = ''
        try:
            from boloes_filtro_loterica import (
                _ler_pagina_barra_somente,
                _ler_pagina_atual_ui as _ler_ui_pag,
                _estado_botao_seguinte as _est_seg,
            )
            ui_barra = _ler_pagina_barra_somente(driver) or _ler_ui_pag(driver)
            seg_agora = _est_seg(driver)
        except Exception:
            pass
        if n_novos == 0 and pagina > 1:
            travada = int(painel.get('_paginas_sem_novo') or 0) + 1
            painel['_paginas_sem_novo'] = travada
            ui_prev = painel.get('_ui_barra_prev')
            painel['_ui_barra_prev'] = ui_barra
            mesma_barra = (
                ui_barra is not None and ui_prev is not None and int(ui_barra) == int(ui_prev)
            )
<<<<<<< HEAD
            if travada >= 4 and (mesma_barra or seg_agora != 'habilitado'):
                meta_loop = ler_metadados_paginacao_api(driver) or {}
                pa_l = int(meta_loop.get('pagina_atual') or 0)
                up_l = int(meta_loop.get('ultima_pagina') or 0)
                if up_l and pa_l < up_l:
                    print(
                        f'  [PÁGINA] {travada} páginas sem bolão novo, mas API {pa_l}/{up_l}. '
                        f'Continua a paginação.'
                    )
                    painel['_paginas_sem_novo'] = 0
                else:
                    print(
                        f'  [PÁGINA] Paginação parada — {travada} páginas sem bolão novo '
                        f'(barra={ui_barra or "?"}). Próxima modalidade.'
                    )
                    chegou_ao_fim = True
                    break
=======
            if travada >= 2 and (mesma_barra or seg_agora != 'habilitado'):
                print(
                    f'  [PÁGINA] LOOP DETECTADO — {travada} páginas sem bolão novo '
                    f'(barra={ui_barra or "?"}). Encerrando modalidade → próxima.'
                )
                chegou_ao_fim = True
                break
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        else:
            painel['_paginas_sem_novo'] = 0
            painel['_ui_barra_prev'] = ui_barra

        _imprimir_painel_pagina(pagina, len(page_boloes), boloes, hashes, painel)
        if page_loterica and cfg.termo:
            print(f'  [FILTRO] Lotérica alvo nesta pág.: {len(page_loterica)} de {len(page_boloes)}')

        conc = painel.get('concurso_alvo') or _concurso_de_arquivo_base(arquivo_base)
        subset_arquivo = _boloes_para_json_arquivo(boloes, mod_esperada, conc)
        if not conc and subset_arquivo:
            conc = extrair_concurso_de_boloes(subset_arquivo)
            painel['concurso_alvo'] = conc
            subset_arquivo = _boloes_para_json_arquivo(boloes, mod_esperada, conc)

        if subset_arquivo:
            novo_base = _renomear_json_sessao(arquivo_base, subset_arquivo, mod_esperada)
            if novo_base != arquivo_base:
                arquivo_base = novo_base
                painel['arquivo_base'] = arquivo_base
                if not painel.get('concurso_alvo'):
                    painel['concurso_alvo'] = _concurso_de_arquivo_base(arquivo_base)

        path_json = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
        total_disco = len(carregar_json_boloes(path_json))
        kb = 0.0
        if os.path.isfile(path_json):
            kb = os.path.getsize(path_json) / 1024
        if total_disco:
            _out(f'  📁 Arquivo: {total_disco} reg. | {kb:.1f} KB | {os.path.basename(path_json)}')

        ui_visivel = None
        try:
            from boloes_filtro_loterica import _ler_pagina_barra_somente, _ler_pagina_atual_ui
            ui_visivel = _ler_pagina_barra_somente(driver) or _ler_pagina_atual_ui(driver)
        except Exception:
            ui_visivel = None
        meta_mon = ler_metadados_paginacao_api(driver) or painel.get('paginacao_api') or {}
        if meta_mon:
            painel['paginacao_api'] = meta_mon
        ufs_pag = sorted({
            str(b.get('uf') or '').upper()
            for b in page_boloes
            if str(b.get('uf') or '').strip()
        })
        from boloes_monitor_paginacao import formatar_monitor_consistencia
        for linha_mon in formatar_monitor_consistencia(
            modalidade=(mod_esperada.label if mod_esperada else '') or mod_slug or '',
            concurso=painel.get('concurso_alvo') or '',
            estado=', '.join(ufs_pag) or (uf_varredura or '—'),
            pagina_api=meta_mon.get('pagina_atual') or pagina,
            ultima_api=meta_mon.get('ultima_pagina'),
            registros_recebidos=len(page_boloes),
            total_acumulado=total_disco or len(boloes),
            arquivo=os.path.basename(path_json) if arquivo_base else '',
            tamanho_kb=kb if kb else None,
            pagina_visual=ui_visivel,
            total_registros_api=meta_mon.get('total_registros'),
        ):
            _out(linha_mon)

        # Checkpoint: só avança pagina_atual se a página estiver completa no JSON.
        meta_pag = ler_metadados_paginacao_api(driver) or painel.get('paginacao_api') or {}
        total_paginas = int(meta_pag.get('ultima_pagina') or 0)
        if meta_pag:
            painel['paginacao_api'] = meta_pag
            pa = int(meta_pag.get('pagina_atual') or pagina)
            up = int(meta_pag.get('ultima_pagina') or pagina)
            print(f'  [PÁGINA] API: página {pa} de {up} ({meta_pag.get("total_registros", "?")} bolões).')

        n_esp = int(painel.get('detalhes_tela_pagina') or 0)
        pagina_ok = bool(painel.get('pagina_completa'))
        if not pagina_ok and n_esp:
            existentes_ck = carregar_json_boloes(path_json)
            n_pag_ck = sum(1 for b in existentes_ck if b.get('pagina') == pagina)
            pagina_ok = n_pag_ck >= n_esp
            if not pagina_ok:
                _out(
                    f'  [CHECKPOINT] Página {pagina} incompleta '
                    f'({n_pag_ck}/{n_esp}) — retomada permanecerá nesta página.'
                )

        pagina_checkpoint = pagina if (pagina_ok or not n_esp) else max(0, pagina - 1)
        salvar_checkpoint(
            PASTA_JSON,
            modalidade=(mod_esperada.slug if mod_esperada else mod_slug) or '',
            modalidade_label=(mod_esperada.label if mod_esperada else '') or '',
            concurso=painel.get('concurso_alvo') or '',
            arquivo_base=arquivo_base,
            pagina_atual=pagina_checkpoint,
            total_paginas=total_paginas,
            boloes_extraidos=total_disco or len(hashes),
            status=STATUS_EXECUTANDO,
            extra=_extra_ck(),
        )
        if pagina_checkpoint >= pagina:
            _out(f'  [CHECKPOINT] Página {pagina} gravada — próximo retomaria em {pagina + 1}.')
        else:
            _out(
                f'  [CHECKPOINT] Página {pagina} incompleta no checkpoint — '
                f'próximo retomaria na página {pagina} (não em {pagina + 1}).'
            )

        if voce_encerra:
            print(
                f'\n  Página {pagina} concluída ({len(page_boloes)} reg. no JSON | '
                f'{len(page_loterica)} da lotérica alvo). '
                f'Arquivo: {total_disco} reg.'
            )
            print(f'  Próxima página? Navegue no site e ENTER. Era a última? Digite FIM.')

        if pause_solicitada(PASTA_JSON):
            pausado = True
            painel['pausado_operador'] = True
            _out('\n  [CHECKPOINT] PAUSA — página atual concluída. Pode fechar e continuar depois.')
            break

        # Fim real só na próxima iteração se o avanço falhar (-2).
        # Não encerra por aparência do Seguinte / ultimaPagina (virada SP→MG).
        pagina += 1

    tempo = int(time.time() - inicio)
    painel['chegou_ao_fim'] = bool(chegou_ao_fim)
    conc = painel.get('concurso_alvo') or _concurso_de_arquivo_base(arquivo_base)
    recuperados = _recuperar_boloes_das_capturas(
        cfg, parser_slug, mod_slug, arquivo_base, rodada_filtro,
        mod_esperada=mod_esperada, concurso_alvo=conc,
    )
    path_json = os.path.join(PASTA_JSON, f'{arquivo_base}.json')
    subset_final = carregar_json_boloes(path_json)
    if recuperados:
        boloes = recuperados
    elif not subset_final:
        subset_final = _boloes_para_json_arquivo(boloes, mod_esperada, conc)

    subset_loterica = _boloes_do_filtro(boloes, cfg)
    painel['registros_loterica_alvo'] = len(subset_loterica)

    total_final = len(subset_final) if subset_final else len(carregar_json_boloes(path_json))
    meta_fim = painel.get('paginacao_api') or {}
    total_paginas_fim = int(meta_fim.get('ultima_pagina') or painel.get('paginas_processadas') or 0)
    ultima_ok = int(painel.get('paginas_processadas') or 0)

    if ultima_ok > 0:
        # UF só é "concluída" com fim REAL (Seguinte desabilitado).
        # NÃO usar pagina >= total_paginas da API — esse total pode estar errado
        # (ex.: total=148 com página 161 ainda válida) e marcava SP como ok cedo demais.
        if pausado:
            status_fim = STATUS_PAUSADO
            painel['uf_concluida'] = False
        elif chegou_ao_fim:
            if uf_varredura and uf_varredura not in ufs_ok:
                ufs_ok.append(uf_varredura)
            status_fim = STATUS_CONCLUIDO if marcar_concluido_ao_fim else STATUS_EXECUTANDO
            painel['uf_concluida'] = True
        else:
            # Interrompido / sessão / abort — mantém UF em andamento (não entra em ufs_concluidas)
            status_fim = STATUS_PAUSADO
            painel['uf_concluida'] = False
        # Ao pausar/interromper: garanta que a UF atual NÃO fique em ufs_concluidas
        if not painel.get('uf_concluida') and uf_varredura and uf_varredura in ufs_ok:
            ufs_ok = [u for u in ufs_ok if u != uf_varredura]
        salvar_checkpoint(
            PASTA_JSON,
            modalidade=(mod_esperada.slug if mod_esperada else mod_slug) or '',
            modalidade_label=(mod_esperada.label if mod_esperada else '') or '',
            concurso=painel.get('concurso_alvo') or '',
            arquivo_base=arquivo_base,
            pagina_atual=ultima_ok,
            total_paginas=total_paginas_fim,
            boloes_extraidos=total_final,
            status=status_fim,
            extra=_extra_ck(),
        )
        if status_fim == STATUS_PAUSADO:
            _out(f'\n  [CHECKPOINT] Status=Pausado | última OK={ultima_ok} | próximo={ultima_ok + 1}')
        elif status_fim == STATUS_CONCLUIDO:
            _out(f'\n  [CHECKPOINT] Status=Concluído | páginas={ultima_ok}')
        elif painel.get('uf_concluida'):
            _out(
                f'\n  [CHECKPOINT] UF {uf_varredura or "?"} ok | páginas={ultima_ok} | '
                f'próximas UFs: {27 - len(ufs_ok)}'
            )
        else:
            _out(
                f'\n  [CHECKPOINT] Status={status_fim} | UF {uf_varredura or "?"} '
                f'pág. {ultima_ok} (ainda em andamento)'
            )
        reset_pause_flags(PASTA_JSON)

    if painel.get('uf_vazia'):
        painel['chegou_ao_fim'] = True
        painel['uf_concluida'] = True
        if uf_varredura and uf_varredura not in ufs_ok:
            ufs_ok.append(uf_varredura)
        _out(f'  [UF] {uf_varredura or "?"} sem bolões — estado encerrado.')
        return [], hashes, painel, arquivo_base

    if painel.get('paginas_com_dados', 0) == 0:
        print('\n  [AVISO] Nenhum bolão baixado nesta sessão — extração não consolidou nada novo.')
        _imprimir_resumo_final([], hashes, painel, arquivo_base, cfg, tempo)
        return [], hashes, painel, arquivo_base

    _imprimir_resumo_final(subset_final, hashes, painel, arquivo_base, cfg, tempo)
    if subset_final:
        _out(f'\n  Arquivo final: {path_json}')
        _out('  (Arquivo único de sessão — não há mais gravação CONSOLIDADO duplicada.)')
    elif painel.get('capturas_api', 0) > 0:
        _out('\n  [AVISO] Extração vazia apesar de capturas API — veja [DIAG] acima.')
    return subset_final, hashes, painel, arquivo_base


def _consolidar_e_resumir(boloes_sessao, mod_esperada):
    """
    Legado: o espelho *_CONSOLIDADO.json era idêntico ao JSON de sessão.
    Mantido apenas para o menu manual de consolidação de capturas.
    Na extração automática NÃO é mais chamado a cada página.
    """
    if not boloes_sessao:
        return None, []
    mod_json = extrair_modalidade_de_boloes(boloes_sessao) or mod_esperada
    concurso = extrair_concurso_de_boloes(boloes_sessao)
    mod_ref = mod_json or mod_esperada
    mod_slug = mod_ref.slug if mod_ref else 'boloes'
    _validar_modalidade_coerencia(mod_esperada, boloes_sessao)
    path, final, novos = consolidar_sessao(PASTA_JSON, concurso, mod_slug, boloes_sessao)
    print(f'\n  CONSOLIDADO (opcional/menu): {path}')
    print(f'  Sessão: {len(boloes_sessao)} | +{novos} novos | total único: {len(final)}')
    return path, final


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAÇÃO AUTOMÁTICA — fluxo [1] com pergunta pré-Edge
# ─────────────────────────────────────────────────────────────────────────────

def _extrair_como_opcao_1(
    mod,
    concurso_pre: str = '',
    *,
    rodada_filtro: int = 1,
    forcar_pagina_inicial: Optional[int] = None,
    sem_popup: bool = False,
    estado=None,
    ufs_concluidas: Optional[list] = None,
    aplicar_filtro_uf: bool = False,
    sem_filtro_dezenas: bool = False,
) -> Tuple[list, Optional[str], dict]:
    """
    Núcleo do [1]/[C]: Detalhes → páginas até o fim da UF atual.

<<<<<<< HEAD
    [C] chama uma vez por UF (aplicar_filtro_uf=True), sem filtrar quantidade
    de dezenas, e grava tudo no mesmo JSON da modalidade.
=======
    [C] aplica filtro de estado (SP → último) sem filtrar dezenas —
    todos os bolões daquela UF entram no mesmo JSON da modalidade.
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    """
    cfg = cfg_qualquer_loterica(None)

<<<<<<< HEAD
    if estado is not None and not sem_filtro_dezenas:
        cfg = cfg_varredura_automatica(mod)
    else:
        cfg = cfg_qualquer_loterica(None)

=======
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    concurso_final = concurso_pre or ''
    arquivo_base = gerar_arquivo_base(cfg, mod, concurso_final)
    mod, concurso_final, arquivo_base = _amarrar_sessao_ao_site(
        mod, concurso_final, arquivo_base,
    )
    mod_slug = mod.slug if mod else 'boloes'
    parser_slug = (getattr(mod, 'parser_slug', None) if mod else None) or mod_slug
    uf_sigla = getattr(estado, 'sigla', '') or ''

    print('\n' + '=' * 60)
    if sem_popup:
        print('  EXTRAÇÃO — VIA API (SEM POPUP)')
    else:
        print('  EXTRAÇÃO — LISTA DO SITE (popup visível)')
    print('=' * 60)
    print(f'  Modalidade : {mod.label if mod else "auto-detectar"}')
    print(f'  Concurso   : {concurso_final if concurso_final else "auto-detectar"}')
    print(f'  Arquivo    : json-boloes/{arquivo_base}.json')
    print(f'  (1 JSON por modalidade — não mistura com Dia de Sorte / outras)')
    if uf_sigla:
        print(f'  Estado/UF  : {uf_sigla} — {getattr(estado, "nome", "")}')
        if cfg.qtd_dezenas:
            print(f'  Filtro     : UF {uf_sigla} + qualquer lotérica + {cfg.qtd_dezenas} dez.')
        else:
            print(f'  Filtro     : UF {uf_sigla} + qualquer lotérica + qualquer quantidade de dezenas')
    else:
        print('  Filtro     : NENHUM (sem estado / lotérica)')
    print('  Ação       : Detalhes → próxima página → até acabar')
    if sem_popup:
        print('  Download   : API detalhar-bolao (sem popup)')
    else:
        print('  Popup      : SIM (você vê abrir/fechar)')
    print(LEGENDA_API)

    if aplicar_filtro_uf and estado is not None and driver is not None:
        ok = aplicar_filtro_varredura_automatica(
            driver, cfg, mod, estado, log_fn=_out,
        )
        if not ok:
            print(f'  [UF] Não aplicou filtro {uf_sigla} — pulando esta UF.')
            return [], arquivo_base, {
                'paginas_processadas': 0,
                'uf_concluida': False,
                'chegou_ao_fim': False,
                'erro_filtro_uf': True,
            }

    boloes_final, _, painel, ab = _loop_extracao_paginas(
        cfg, parser_slug, mod_slug, arquivo_base,
        manual_paginas=False, rodada_filtro=rodada_filtro, mod_esperada=mod,
        concurso_alvo=concurso_final,
        forcar_pagina_inicial=forcar_pagina_inicial,
        uf_varredura=uf_sigla,
        ufs_concluidas=list(ufs_concluidas or []),
        marcar_concluido_ao_fim=True,
        sem_popup=sem_popup,
    )
    arquivo_base = ab or arquivo_base
    if painel is None:
        painel = {}
    if painel.get('uf_concluida') or painel.get('chegou_ao_fim'):
        painel['chegou_ao_fim'] = True

    if boloes_final:
        mod_final = extrair_modalidade_de_boloes(boloes_final) or mod
        ab = _renomear_json_sessao(arquivo_base, boloes_final, mod_final)
        arquivo_base = ab or arquivo_base
        _validar_modalidade_coerencia(mod_final, boloes_final)
        ufs = sorted({(b.get('uf') or '').upper() for b in boloes_final if b.get('uf')})
        if ufs:
            print(f'  UFs presentes no JSON (campo da lotérica): {", ".join(ufs)} ({len(ufs)})')

    return boloes_final or [], arquivo_base, painel or {}


def extrair_automatico() -> Tuple[list, Optional[str]]:
    """
    [1] Fluxo completo:
        Terminal → modalidade + concurso
        Edge → login → lista aberta → SIM
        Script clica Detalhes e pagina até acabar (SEM filtro de estado/lotérica)
    """
    global SESSAO_AUTORIZADA, ROTULO_ARQUIVO, ROTULO_NOME

    mod_pre = _coletar_modalidade_pre_extracao()
    if mod_pre:
        ROTULO_ARQUIVO = mod_pre
        ROTULO_NOME = mod_pre.label

    concurso_pre = _coletar_concurso_pre_extracao()

    cfg_atual = FILTRO_LOTERICA if (
        FILTRO_LOTERICA and FILTRO_LOTERICA.qualquer_loterica
    ) else cfg_qualquer_loterica(None)

    _exibir_resumo_pre_extracao(mod_pre or ROTULO_ARQUIVO, concurso_pre, cfg_atual)

    if driver is None:
        if not iniciar_navegador():
            return [], None
    elif not _no_site_boloes():
        try:
            driver.get(URL_BOLOES)
            time.sleep(2)
        except Exception:
            pass
        _out('\n  Edge já aberto — faça login e escolha a modalidade se precisar.')

    SESSAO_AUTORIZADA = False
    _out('\n  ⏸⏸⏸  PAUSA ATIVA — digite SIM no terminal para liberar a extração.')
    if not aguardar_site_pronto():
        return [], None

    SESSAO_AUTORIZADA = True

    mod = ROTULO_ARQUIVO or _modalidade_extracao(driver)
    boloes_final, ab, painel = _extrair_como_opcao_1(mod, concurso_pre)

    if painel.get('uf_concluida'):
        _aviso_sonoro_extracao_completa()
    else:
        ck_fim = carregar_checkpoint(PASTA_JSON) or {}
        if ck_fim.get('status') == STATUS_CONCLUIDO:
            _aviso_sonoro_extracao_completa()

    return boloes_final or [], ab


def extrair_ciclo_completo() -> dict:
    """
    [C] — ciclo automático: cards inicio-bolao → Compre seu bolão → 1 JSON/mod.
    """
    from boloes_ciclo_completo import executar_ciclo_completo
    import sys as _sys
    return executar_ciclo_completo(_sys.modules[__name__], out_fn=_out)


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAÇÃO MANUAL — fluxo [2]
# ─────────────────────────────────────────────────────────────────────────────

def _resolver_cfg_filtro_rodada():
    _out('\n  Lendo filtro aplicado no site...')
    cfg = ler_filtro_aplicado_site(driver, _out)
    if cfg and (cfg.termo or cfg.codigo or cfg.qualquer_loterica):
        return cfg

    _out('\n' + '-' * 60)
    _out('  Filtro no site não lido automaticamente.')
    if FILTRO_LOTERICA and FILTRO_LOTERICA.qualquer_loterica:
        _out(f'  [ENTER] = qualquer lotérica + {FILTRO_LOTERICA.qtd_dezenas or 15} dezenas')
    elif FILTRO_LOTERICA and FILTRO_LOTERICA.termo:
        _out(f'  [ENTER] = usar config salva ({FILTRO_LOTERICA.termo})')
    _out('  * = qualquer + 15 dez | ou código/nome | X = menu')
    _out('-' * 60)
    try:
        resp = input('>>> ').strip()
    except EOFError:
        return None
    if not resp:
        if FILTRO_LOTERICA:
            return FILTRO_LOTERICA
        return cfg_qualquer_loterica(15)
    if resp.upper() == 'X':
        return None
    if resp in ('*', '-', 'todas', 'qualquer', 'QUALQUER', 'TODAS'):
        qtd = FILTRO_LOTERICA.qtd_dezenas if FILTRO_LOTERICA and FILTRO_LOTERICA.qtd_dezenas else 15
        return cfg_qualquer_loterica(qtd)
    codigo, nome = parse_termo_loterica(resp)
    qtd = FILTRO_LOTERICA.qtd_dezenas if FILTRO_LOTERICA else None
    return FiltroLotericaConfig(termo=resp, codigo=codigo, nome=nome, qtd_dezenas=qtd)


def extrair_sessao_multi_filtros() -> None:
    global SESSAO_AUTORIZADA

    print('\n' + '=' * 60)
    print('  MODO FILTRO MANUAL — MESMA SESSÃO LOGADA')
    print('=' * 60)
    print('\n  Login 1x → filtro no site → ENTER → baixa pág. 1')
    print('  Mesmo filtro: pág. 2, 3… → ENTER a cada página → FIM')
    print('  Novo filtro: aplique no site → ENTER → repete')
    print(LEGENDA_API)

    if driver is None:
        if not preparar_login_unico():
            return
    elif not _usuario_logado_caixa():
        if _no_site_boloes():
            print('\n  [AVISO] Login não confirmado, mas site de bolões aberto — continuando.')
        else:
            print('\n  Sessão expirada — faça login de novo.')
            if not preparar_login_unico():
                return

    mod_slug = ROTULO_ARQUIVO.slug if ROTULO_ARQUIVO else 'quina'
    parser_slug = ROTULO_ARQUIVO.parser_slug if ROTULO_ARQUIVO else 'quina'

    rodada = 1
    resumos_rodadas: list = []

    while True:
        if not aguardar_filtro_manual_pagina1(rodada=rodada):
            break

        cfg = _resolver_cfg_filtro_rodada()
        if not cfg or not (cfg.termo or cfg.codigo or cfg.qualquer_loterica):
            _out('\n  Rodada cancelada — voltando ao menu.')
            break

        mod = _modalidade_extracao(driver)
        mod_slug = mod.slug if mod else mod_slug
        parser_slug = mod.parser_slug if mod else parser_slug

        SESSAO_AUTORIZADA = True
        limpar_capturas_api(driver)
        arquivo_base = gerar_arquivo_base(cfg, mod)

        print(f'\n  Iniciando rodada {rodada}...')
        boloes, hashes, painel, arquivo_base = _loop_extracao_paginas(
            cfg, parser_slug, mod_slug, arquivo_base,
            manual_paginas=True, rodada_filtro=rodada,
            voce_encerra=True, mod_esperada=mod,
        )

        resumos_rodadas.append({
            'rodada': rodada,
            'loterica': cfg.termo,
            'dezenas': cfg.qtd_dezenas or 'qualquer',
            'registros': len(boloes),
            'arquivo': f'{arquivo_base}.json',
        })

        print('\n' + '-' * 60)
        print(f'  RODADA {rodada} CONCLUÍDA — {len(boloes)} reg. | filtro {cfg.termo}')
        print('-' * 60)

        try:
            resp = input('\n>>> Aplicar OUTRO filtro no site? [S/n] ').strip().lower()
        except EOFError:
            break
        if resp == 'n':
            break
        rodada += 1

    if resumos_rodadas:
        print('\n' + '=' * 60)
        print('  RESUMO — TODOS OS FILTROS DESTA SESSÃO')
        print('=' * 60)
        total = 0
        for r in resumos_rodadas:
            print(f"  Rodada {r['rodada']}: {r['registros']:>4} reg. | {r['loterica']} | {r['arquivo']}")
            total += r['registros']
        print(f'\n  Total: {total} reg. em {len(resumos_rodadas)} filtro(s).')
        print('=' * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Configurações iniciais / menu
# ─────────────────────────────────────────────────────────────────────────────

def _carregar_config_inicio() -> bool:
    global FILTRO_LOTERICA, ROTULO_ARQUIVO, ROTULO_NOME
    cached = _carregar_config_cache()
    if not cached:
        return False
    FILTRO_LOTERICA, _mod_cache = cached
    ROTULO_ARQUIVO = None
    ROTULO_NOME = 'modalidade atual'
    return bool(FILTRO_LOTERICA)


def configurar_loterica() -> bool:
    global FILTRO_LOTERICA, ROTULO_ARQUIVO, ROTULO_NOME
    try:
        FILTRO_LOTERICA, ROTULO_ARQUIVO = ler_config_extracao()
        ROTULO_NOME = _rotulo_nome()
        if not FILTRO_LOTERICA or not (FILTRO_LOTERICA.termo or '').strip():
            print('\n>>> Lotérica inválida ou vazia.')
            FILTRO_LOTERICA = None
            return False
        print(f'\n>>> Config OK | Lotérica: {FILTRO_LOTERICA.termo} | Modalidade: {ROTULO_NOME}')
        return True
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f'\n>>> ERRO: {exc}')
        traceback.print_exc()
        return False


def _menu_consolidar_capturas() -> None:
    from boloes_consolidar import consolidar_capturas_pasta

    mod_slug = ROTULO_ARQUIVO.slug if ROTULO_ARQUIVO else 'quina'
    path, total = consolidar_capturas_pasta(
        PASTA_CAPTURAS, PASTA_JSON, 'sem-concurso', mod_slug,
        FILTRO_LOTERICA.codigo if FILTRO_LOTERICA else None,
        FILTRO_LOTERICA.qtd_dezenas if FILTRO_LOTERICA else None,
    )
    print(f'\n>>> Consolidado a partir de capturas-api/: {path}')
    print(f'>>> Total único: {total}')


def menu_principal() -> None:
    global FILTRO_LOTERICA, ROTULO_ARQUIVO, ROTULO_NOME

    while True:
        try:
            print('\n' + '=' * 60)
            print('  EXTRATOR DE BOLOES — Caixa (API)')
            print(f'  >>> VERSAO: {VERSAO_EXTRATOR}')
            print('=' * 60)
            _imprimir_status_modalidade()
            _imprimir_tabela_modalidades_resumida()
            print(f'\n  JSON: {PASTA_JSON}')
            print('\n[C] INICIAR EXTRAÇÃO — CICLO COMPLETO  ★')
<<<<<<< HEAD
            print('    = AUTO: cards → SIM → Compre seu bolão → SIM (lista) → JSON')
=======
            print('    = AUTO: cards → Compre seu bolão → JSON (sem SIM/ENTER)')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
            print('[1] EXTRAIR AUTOMATICO (uma modalidade)')
            print('    = lista já aberta | clique Detalhes COM popup')
            print('[2] EXTRAIR MANUAL (ENTER a cada pagina / varios filtros)')
            print('[3] Consolidar capturas-api/')
            print('[M] Tabela completa de modalidades')
            print('[0] Fechar navegador')
            print('-' * 60)
            print('  Opcional: M1-M9 | QSJ | DSP — so para forcar parser')
            print('-' * 60)

            opcao = input('Opção: ').strip().upper()

            if not opcao:
                continue
            if opcao.startswith('M') and len(opcao) == 2 and opcao[1].isdigit():
                if _trocar_modalidade_por_entrada(opcao[1]):
                    continue
            if opcao == 'M':
                imprimir_menu_modalidades()
                continue
            if opcao in TECLAS_ESPECIAIS:
                _trocar_modalidade_por_entrada(opcao)
                continue
            if opcao in ('4', '5', '6', '7', '8', '9'):
                if _trocar_modalidade_por_entrada(opcao):
                    continue
            if opcao not in ('0', '1', '2', '3', 'C', 'I', 'INICIAR', 'M'):
                mod_direto = resolver_modalidade_menu(opcao)
                if mod_direto:
                    _aplicar_modalidade(mod_direto)
                    continue
            if opcao in ('C', 'I', 'INICIAR'):
                extrair_ciclo_completo()
            elif opcao == '1':
                extrair_automatico()
            elif opcao == '2':
                extrair_sessao_multi_filtros()
            elif opcao == '3':
                _menu_consolidar_capturas()
            elif opcao == '0':
                fechar_navegador()
                print('\n>>> Navegador fechado. CTRL+C para sair.')
            else:
                print('\n>>> Opção inválida.')

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f'\n>>> ERRO: {exc}')
            traceback.print_exc()


def main() -> None:
    global FILTRO_LOTERICA, ROTULO_ARQUIVO, ROTULO_NOME
    print('\n' + '#' * 60, flush=True)
    print(f'  VERSAO DO EXTRATOR: {VERSAO_EXTRATOR}', flush=True)
    print('  Se NAO aparecer v3 acima, feche o terminal e abra de novo.', flush=True)
    print('#' * 60 + '\n', flush=True)
    _carregar_config_inicio()
    menu_principal()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\nEncerrado pelo usuário (CTRL+C).')
    finally:
        fechar_navegador()
        print('Fim!')
