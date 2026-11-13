# -*- coding: utf-8 -*-
"""
Orquestrador [C] — ciclo AUTOMÁTICO pelas cards de #/inicio-bolao.

Fluxo:
  1) Login 1× (Entrar automático após senha)
  2) Abre inicio-bolao e LÊ os cards (modalidade + concurso)
<<<<<<< HEAD
  3) UM SIM — a partir daí o ciclo não pede outra confirmação
  4) Para cada modalidade: Detalhes de todos os bolões da página, grava, próxima página
  5) O site troca de estado sozinho nessa paginação; acabou a lista → próxima modalidade
=======
  3) Sem confirmação — clica "Compre seu bolão" e extrai até o fim
  4) Aviso sonoro/voz → próxima modalidade (sem SIM / ENTER)
  5) Grava 1 JSON por modalidade — sem misturar
  6) Cada modalidade: SP → demais UFs → só para no último estado
  7) Relatório + Excel + JSON consolidado só após a última modalidade
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from boloes_cards_inicio import (
    URL_INICIO_BOLAO,
    abrir_lista_do_card,
    ir_para_inicio_bolao,
    listar_cards_modalidades,
    ordenar_cards_por_prioridade,
)
from boloes_checkpoint_ciclo import (
    STATUS_AGUARDANDO,
    STATUS_ANDAMENTO,
    STATUS_CICLO_OK,
    STATUS_CICLO_PAUSA,
    STATUS_CICLO_EXEC,
    STATUS_CONCLUIDO,
    STATUS_ERRO,
    STATUS_PAUSADO,
    STATUS_PENDENTE,
    STATUS_VAZIO,
    atualizar_modalidade,
    atualizar_uf,
    calcular_resumo,
    hidratar_ciclo_com_jsons,
    modalidade_concluida_pelas_ufs,
    normalizar_ufs_do_ciclo,
    novo_ciclo,
    resolver_retomada_ciclo_automatica,
    salvar_ciclo,
    set_operacao,
    ufs_concluidas_da_modalidade,
    STATUS_CICLO_OCORRENCIAS,
)
<<<<<<< HEAD
from boloes_estados import estados_varredura
from boloes_modalidades import MODALIDADES_MENU, modalidade_por_slug

UNIDADE_LISTA = 'LISTA'
_STATUS_UF_FECHADA = (STATUS_CONCLUIDO, STATUS_VAZIO)
=======
from boloes_estados import estados_varredura, siglas_varredura
from boloes_modalidades import MODALIDADES_MENU, modalidade_por_slug

>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
LogFn = Callable[[str], None]


def _siglas_brasil() -> List[str]:
    return [e.sigla for e in estados_varredura('SP')]


def _slots_uf(mod: Dict[str, Any]) -> Dict[str, Any]:
    """UFs reais (AC..TO). Ignora a unidade legada LISTA."""
    out: Dict[str, Any] = {}
    for sigla, slot in (mod.get('ufs') or {}).items():
        chave = str(sigla or '').upper()
        if chave == UNIDADE_LISTA or len(chave) != 2:
            continue
        out[chave] = slot
    return out


def _ufs_fechadas(ciclo: Dict[str, Any], slug: str) -> bool:
    mod = (ciclo.get('modalidades') or {}).get(slug) or {}
    slots = _slots_uf(mod)
    if len(slots) < len(_siglas_brasil()):
        return False
    return all(str(s.get('status') or '') in _STATUS_UF_FECHADA for s in slots.values())


def _contagem_ufs(mod: Dict[str, Any]) -> tuple:
    slots = _slots_uf(mod)
    ok = sum(1 for s in slots.values() if str(s.get('status') or '') in _STATUS_UF_FECHADA)
    n = sum(int(s.get('boloes') or 0) for s in slots.values())
    total = len(_siglas_brasil())
    return ok, total, n


def _barra(pct: float, largura: int = 20) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    cheios = int(round(largura * pct / 100.0))
    return '█' * cheios + '░' * (largura - cheios)


def _ufs_dos_boloes(boloes: list) -> List[str]:
    return sorted({
        str(b.get('uf') or '').upper()
        for b in (boloes or [])
        if str(b.get('uf') or '').strip()
    })


def _boloes_desta_uf(boloes: list, sigla: str) -> List[dict]:
    alvo = (sigla or '').upper()
    out = []
    for b in boloes or []:
        marca = str(b.get('uf_varredura') or '').upper()
        uf = str(b.get('uf') or '').upper()
        if marca == alvo or (not marca and uf == alvo):
            out.append(b)
    return out


def imprimir_painel_ciclo(ciclo: Dict[str, Any], out_fn: LogFn = print, ordem_slugs: Optional[List[str]] = None) -> None:
    res = ciclo.get('resumo') or calcular_resumo(ciclo)
    mods = ciclo.get('modalidades') or {}
    total = len(mods) or 1
    feitos = sum(
        1 for m in mods.values()
        if str(m.get('status') or '') in (STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO)
    )
    pct = 100.0 * feitos / total

    out_fn('')
    out_fn('=' * 64)
    out_fn('  CICLO COMPLETO — AUTOMÁTICO (cards inicio-bolao)')
    out_fn('  Ordem: 1º Dia de Sorte → 2º maior premiação nos cards')
<<<<<<< HEAD
    out_fn('  1 JSON por modalidade | Detalhes + próxima página | SEM POPUP')
=======
    out_fn('  1 JSON por modalidade | 27 UFs (SP → último estado) | SEM POPUP')
    out_fn('  Excel/consolidado só no fim de TODAS as modalidades')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    out_fn('=' * 64)
    out_fn(f'  Status     : {ciclo.get("status")}')
    out_fn(f'  Modalidade : {ciclo.get("modalidade_atual") or "—"}')
    out_fn(f'  UF atual   : {ciclo.get("uf_atual") or "—"}')
    out_fn(f'  Operação   : {ciclo.get("operacao") or "—"}')
    out_fn(f'  Progresso  : {_barra(pct)} {pct:.0f}%  ({feitos}/{total} modalidades)')
    out_fn(f'  Bolões≈    : {res.get("boloes_total", 0)} | Erros: {res.get("erros", 0)}')
    out_fn('-' * 64)
    slugs = list(ordem_slugs) if ordem_slugs else list(mods.keys())
    fila_ufs = siglas_varredura('SP')
    for slug in slugs:
        if slug not in mods:
            continue
        mod = mods[slug]
        st = str(mod.get('status') or STATUS_AGUARDANDO)
        label = mod.get('label') or slug
<<<<<<< HEAD
        conc = mod.get('concurso') or ''
        ufs_txt = mod.get('ufs_encontradas') or ''
        extra = f'conc {conc}' if conc else 'paginação do site'
        if ufs_txt:
            extra += f' | UFs no JSON: {ufs_txt}'
=======
        ufs_map = mod.get('ufs') or {}
        ufs_ok = sum(
            1 for s in fila_ufs
            if str((ufs_map.get(s) or {}).get('status') or '') in (
                STATUS_CONCLUIDO, STATUS_VAZIO,
            )
        )
        uf_atual = ''
        pag = 0
        n = 0
        for s in fila_ufs:
            slot = ufs_map.get(s) or {}
            st_uf = str(slot.get('status') or '')
            if st_uf not in (STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO):
                uf_atual = s
                pag = int(slot.get('pagina_atual') or 0)
                n = int(slot.get('boloes') or 0)
                break
        if not uf_atual:
            n = sum(int((ufs_map.get(s) or {}).get('boloes') or 0) for s in fila_ufs)
        conc = mod.get('concurso') or ''
        ufs_txt = mod.get('ufs_encontradas') or ''
        extra = f'UF {uf_atual or "—"} {ufs_ok}/{len(fila_ufs)}'
        if pag:
            extra += f' | pág {pag}'
        if n:
            extra += f' | {n} bolões'
        if conc:
            extra += f' | conc {conc}'
        if ufs_txt:
            extra += f' | no JSON: {ufs_txt}'
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        out_fn(f'  {label:<28} {st:<14} {extra}')
    out_fn('=' * 64)


def imprimir_resumo_final(ciclo: Dict[str, Any], out_fn: LogFn = print) -> None:
    res = calcular_resumo(ciclo)
    inicio = ciclo.get('inicio') or ''
    fim = ciclo.get('fim') or ''
    out_fn('')
    out_fn('=' * 64)
    out_fn('  EXTRAÇÃO COMPLETA — RESUMO')
    out_fn('=' * 64)
    out_fn(f'  Início : {inicio}')
    out_fn(f'  Fim    : {fim}')
    if inicio and fim:
        try:
            t0 = datetime.strptime(inicio, '%Y-%m-%d %H:%M:%S')
            t1 = datetime.strptime(fim, '%Y-%m-%d %H:%M:%S')
            secs = int((t1 - t0).total_seconds())
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            out_fn(f'  Duração: {h:02d}:{m:02d}:{s:02d}')
        except Exception:
            pass
    out_fn(f'  Modalidades concluídas : {res.get("modalidades_ok")}')
    out_fn(f'  Bolões                 : {res.get("boloes_total")}')
    out_fn(f'  Erros / pendências     : {res.get("erros")} / {res.get("ufs_pendente")}')
    out_fn('=' * 64)


<<<<<<< HEAD
def _slot_uf_novo() -> Dict[str, Any]:
    return {
        'status': STATUS_AGUARDANDO,
        'pagina_atual': 0,
        'total_paginas': 0,
        'boloes': 0,
        'tentativas': 0,
        'erro': '',
        'atualizado_em': '',
    }


def _garantir_unidade_lista(ciclo: Dict[str, Any], slug: str, label: str) -> None:
    """Garante a modalidade e um slot por UF. Não apaga progresso já gravado."""
=======
def _garantir_ufs_modalidade(ciclo: Dict[str, Any], slug: str, label: str) -> None:
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    mods = ciclo.setdefault('modalidades', {})
    if slug not in mods:
        mods[slug] = {
            'label': label,
            'status': STATUS_AGUARDANDO,
            'concurso': '',
            'arquivo_base': '',
            'ufs': {},
            'ufs_encontradas': '',
            'inicio': '',
            'fim': '',
        }
    else:
        mods[slug]['label'] = label or mods[slug].get('label') or slug
<<<<<<< HEAD
    ufs = mods[slug].setdefault('ufs', {})
    ufs.pop(UNIDADE_LISTA, None)
    for sigla in _siglas_brasil():
        ufs.setdefault(sigla, _slot_uf_novo())
=======
        mods[slug].setdefault('ufs_encontradas', '')
    normalizar_ufs_do_ciclo(ciclo)
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257


def _mod_de_card(card: dict):
    mod = card.get('mod')
    if mod is not None:
        return mod
    return modalidade_por_slug(str(card.get('slug') or ''))


<<<<<<< HEAD
def _ja_baixada(ciclo: Dict[str, Any], slug: str) -> bool:
    """Modalidade marcada como baixada no checkpoint do ciclo. Não recomeça.

    CONCLUÍDO com só 1 UF (ex.: só SP) NÃO conta — a paginação do site deve
    percorrer todos os estados; reabre no Continuar.
    """
    mod = (ciclo.get('modalidades') or {}).get(slug, {}) or {}
    st = str(mod.get('status') or '')
    if st == STATUS_VAZIO:
        return True
    if st != STATUS_CONCLUIDO:
        return False
    ufs_txt = str(mod.get('ufs_encontradas') or '')
    ufs = [u.strip().upper() for u in ufs_txt.replace(';', ',').split(',') if u.strip()]
    if len(ufs) <= 1:
        return False
    return True


def _ordenar_continuar(cards: List[dict], ciclo: Dict[str, Any]) -> List[dict]:
    """
    Continuar: não põe o Dia de Sorte na frente se ele já foi baixado.
    Primeiro a modalidade do checkpoint que ainda falta; o restante pendente;
    as já baixadas ficam no fim (o loop só as anuncia e pula).
    """
    def feita(card: dict) -> bool:
        return _ja_baixada(ciclo, str(card.get('slug') or ''))

    pendentes = [c for c in cards if not feita(c)]
    feitas = [c for c in cards if feita(c)]
    atual = str(ciclo.get('modalidade_atual') or '')
    if atual and not _ja_baixada(ciclo, atual):
        pendentes = [c for c in pendentes if c.get('slug') == atual] + [
            c for c in pendentes if c.get('slug') != atual
        ]
    return pendentes + feitas
=======
def _proximo_card_pendente(cards: List[dict], ciclo: Dict[str, Any], idx_atual: int):
    for card in cards[idx_atual:]:
        mod = _mod_de_card(card)
        if mod is None:
            continue
        st = str((ciclo.get('modalidades') or {}).get(mod.slug, {}).get('status') or '')
        if st not in (STATUS_CONCLUIDO, STATUS_VAZIO):
            return mod
    return None


def _avisar_inicio_modalidade(label: str, out_fn: LogFn) -> None:
    try:
        from boloes_avisos import avisar_nova_modalidade
        avisar_nova_modalidade(label, out_fn=out_fn)
    except Exception:
        out_fn(f'\n  🔔 NOVA MODALIDADE — {label}')


def _avisar_fim_modalidade(label: str, out_fn: LogFn) -> None:
    try:
        from boloes_avisos import avisar_modalidade_concluida
        avisar_modalidade_concluida(label, out_fn=out_fn)
    except Exception:
        out_fn(f'\n  🔔 MODALIDADE CONCLUÍDA — {label}')


def _continuar_apos_falha(label: str, out_fn: LogFn, motivo: str = '') -> None:
    out_fn(f'  [ERRO] {label}')
    if motivo:
        out_fn(f'  [ERRO] {motivo}')
    out_fn('  [AVISO] Modalidade não concluída.')
    out_fn('  [INFO] Continuando para a próxima modalidade.')
    try:
        from boloes_avisos import avisar_modalidade_erro
        avisar_modalidade_erro(label, out_fn=out_fn)
    except Exception:
        pass


def _imprimir_resumo_da_modalidade(ciclo: Dict[str, Any], slug: str, pasta: str, out_fn: LogFn) -> None:
    try:
        from boloes_relatorio_execucao import coletar_linhas_modalidades, imprimir_resumo_modalidade
        linhas = coletar_linhas_modalidades(ciclo, pasta, [slug])
        if linhas:
            imprimir_resumo_modalidade(linhas[0], out_fn=out_fn)
    except Exception as exc:
        out_fn(f'  [RELATÓRIO] Aviso ao montar resumo da modalidade: {exc}')


def _gerar_entregaveis(ciclo: Dict[str, Any], pasta: str, ordem_slugs: List[str], out_fn: LogFn, pausado: bool) -> None:
    try:
        from boloes_relatorio_execucao import gerar_entregaveis_finais
        gerar_entregaveis_finais(
            pasta, ciclo, ordem_slugs, out_fn=out_fn, pausado=pausado,
        )
    except Exception as exc:
        out_fn(f'  [RELATÓRIO] Falha ao gerar Excel/consolidado: {exc}')
        imprimir_resumo_final(ciclo, out_fn)
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257


def executar_ciclo_completo(
    api,
    *,
    modalidades_slugs: Optional[List[str]] = None,
    out_fn: LogFn = print,
) -> Dict[str, Any]:
    """
<<<<<<< HEAD
    Login 1× → lê cards → UM SIM → cada modalidade percorre as 27 UFs.
=======
    Login 1× → lê cards → abre lista e extrai até o fim (sem SIM/ENTER).
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    """
    pasta = api.PASTA_JSON
    wanted = None
    if modalidades_slugs:
        wanted = {s.strip().lower() for s in modalidades_slugs if s and str(s).strip()}

    continuar, ciclo_existente = resolver_retomada_ciclo_automatica(pasta, out_fn=out_fn)

    if continuar and ciclo_existente:
        ciclo = ciclo_existente
        ciclo['status'] = STATUS_CICLO_EXEC
    else:
        out_fn('')
        out_fn('  CICLO AUTOMÁTICO (sem intervenção):')
        out_fn('  — App abre inicio-bolao e lê os cards (modalidade + concurso)')
<<<<<<< HEAD
        out_fn('  — UM SIM: começa no Dia de Sorte')
        out_fn('  — Em cada página: Detalhes de todos, grava o JSON, próxima página')
        out_fn('  — O site troca de estado na paginação; acabou a lista, vai a próxima modalidade')
        out_fn('  — 1 JSON por modalidade | sem misturar')
=======
        out_fn('  — Clica Compre seu bolão e extrai até o fim')
        out_fn('  — Ao terminar uma modalidade, inicia a próxima sozinho')
        out_fn('  — 1 JSON por modalidade | sem misturar | sem SIM/ENTER')
        out_fn('  — Cada modalidade: SP → demais UFs → só para no último estado')
        out_fn('  — Excel/consolidado só depois da última modalidade')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        # Placeholder; modalidades reais vêm dos cards após login
        seed = list(MODALIDADES_MENU)
        ciclo = novo_ciclo(
            [{'slug': m.slug, 'label': m.label} for m in seed],
<<<<<<< HEAD
            _siglas_brasil(),
=======
            siglas_varredura('SP'),
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        )
        ciclo['modo'] = 'cards-auto'
        ciclo['concurso_inicial'] = ''

    hidratar_ciclo_com_jsons(pasta, ciclo, out_fn=out_fn)
    salvar_ciclo(pasta, ciclo)

    if getattr(api, 'driver', None) is None:
        if not api.iniciar_navegador():
            ciclo['status'] = STATUS_CICLO_PAUSA
            set_operacao(ciclo, operacao='Falha ao abrir navegador')
            salvar_ciclo(pasta, ciclo)
            return ciclo

    from boloes_pasta_bds import detectar_lista_boloes_aberta
    lista_inicio = detectar_lista_boloes_aberta(api.driver)

    # Continuar com a lista já aberta: NÃO volta ao hub (senão perde a página e mistura arquivo)
    if continuar and lista_inicio and lista_inicio.get('slug'):
        out_fn(
            f'  [CICLO] Continuar: site já em {lista_inicio["label"]} '
            f'conc {lista_inicio.get("concurso") or "?"} — mantém esta lista.'
        )
        cards = []
    else:
        # 1) Hub de cards (Bolões) — ainda SEM extrair
        try:
            if not ir_para_inicio_bolao(api.driver, log_fn=out_fn, espera=3.0):
                api.driver.get(getattr(api, 'URL_BOLOES', URL_INICIO_BOLAO))
                time.sleep(2)
        except Exception:
            pass
        cards = listar_cards_modalidades(api.driver, log_fn=out_fn)

    if wanted:
        cards = [c for c in cards if c['slug'] in wanted or c.get('parser_slug') in wanted]
    if not cards and ciclo.get('modalidades'):
        for slug, m in (ciclo.get('modalidades') or {}).items():
            cards.append({
                'slug': slug,
                'label': m.get('label') or slug,
                'concurso': str(m.get('concurso') or ''),
            })
        if cards:
            out_fn('  [CICLO] Cards do checkpoint (lista já estava aberta ou hub vazio).')
    # Ordem de prioridade (Dia de Sorte → maior premiação), sem mudar o fluxo
    if cards:
        cards = ordenar_cards_por_prioridade(cards)
<<<<<<< HEAD
    if continuar and cards:
        cards = _ordenar_continuar(cards, ciclo)
    if lista_inicio and lista_inicio.get('slug') and not (
        continuar and _ja_baixada(ciclo, str(lista_inicio.get('slug') or ''))
    ):
        # Continuar: mantém a lista já aberta na frente só se ela ainda não foi baixada
=======
    if lista_inicio and lista_inicio.get('slug'):
        # Continuar: mantém a lista já aberta na frente; o restante segue a prioridade
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        slug_pri = lista_inicio['slug']
        cards = [c for c in cards if c.get('slug') == slug_pri] + [
            c for c in cards if c.get('slug') != slug_pri
        ]
        if lista_inicio.get('concurso'):
            atualizar_modalidade(ciclo, slug_pri, concurso=str(lista_inicio['concurso']))
    if not cards:
        out_fn('  [CICLO] Nenhum card reconhecido em inicio-bolao.')
        out_fn('  Abra Bolões no Edge (inicio-bolao) ou a lista da modalidade e rode [C] de novo.')
        ciclo['status'] = STATUS_CICLO_PAUSA
        set_operacao(ciclo, operacao='Sem cards')
        salvar_ciclo(pasta, ciclo)
        return ciclo

    ordem_slugs: List[str] = []
    for card in cards:
        slug = card['slug']
        label = card['label']
        ordem_slugs.append(slug)
        _garantir_ufs_modalidade(ciclo, slug, label)
        if card.get('concurso'):
            atualizar_modalidade(ciclo, slug, concurso=str(card['concurso']))
    if not continuar:
        extras = [s for s in list((ciclo.get('modalidades') or {}).keys()) if s not in ordem_slugs]
        for s in extras:
            ciclo['modalidades'].pop(s, None)

    salvar_ciclo(pasta, ciclo)
    imprimir_painel_ciclo(ciclo, out_fn, ordem_slugs=ordem_slugs)

<<<<<<< HEAD
    # 3) PAUSA — operador pode mexer no Caixa; nada baixa antes do SIM
    api.SESSAO_AUTORIZADA = False
    out_fn('\n  ⏸⏸⏸  PAUSA ÚNICA — cards já detectados.')
    out_fn('  Digite SIM para começar.')
    out_fn('  Continuar lê o checkpoint: modalidade já baixada é pulada.')
    out_fn('  O site percorre os estados. No fim da lista, vai à próxima modalidade.')
    if not api.aguardar_site_pronto(modo_ciclo=True):
=======
    # 3) Sem confirmação — cards já detectados, segue sozinho
    out_fn('\n  [AUTO] Cards detectados — iniciando extração sem SIM/ENTER.')
    if not api.garantir_sessao_ciclo(out_fn):
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        ciclo['status'] = STATUS_CICLO_PAUSA
        set_operacao(ciclo, operacao='Sessão/login indisponível no início do ciclo')
        salvar_ciclo(pasta, ciclo)
        return ciclo
    api.SESSAO_AUTORIZADA = False

    from boloes_pasta_bds import detectar_lista_boloes_aberta
    lista_aberta = detectar_lista_boloes_aberta(api.driver)
    if lista_aberta and lista_aberta.get('slug') and continuar:
        out_fn(
            f'  [CICLO] Lista já aberta no site: {lista_aberta["label"]} '
            f'conc {lista_aberta.get("concurso") or "?"} — continua neste JSON, sem voltar ao hub.'
        )
        slug_pri = lista_aberta['slug']
        cards = ordenar_cards_por_prioridade(cards)
<<<<<<< HEAD
        if _ja_baixada(ciclo, str(slug_pri)):
            out_fn(
                f'  [CHECKPOINT] {lista_aberta.get("label") or slug_pri} já está marcada '
                f'como baixada. Não recomeça nela.'
            )
            cards = _ordenar_continuar(cards, ciclo)
        else:
            cards = [c for c in cards if c.get('slug') == slug_pri] + [
                c for c in cards if c.get('slug') != slug_pri
            ]
=======
        cards = [c for c in cards if c.get('slug') == slug_pri] + [
            c for c in cards if c.get('slug') != slug_pri
        ]
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        ordem_slugs = [c['slug'] for c in cards]
        if lista_aberta.get('concurso'):
            atualizar_modalidade(ciclo, slug_pri, concurso=str(lista_aberta['concurso']))
        salvar_ciclo(pasta, ciclo)
    else:
        # Volta ao hub (usuário pode ter navegado no Edge durante a pausa)
        if not ir_para_inicio_bolao(api.driver, log_fn=out_fn, espera=2.0):
            ciclo['status'] = STATUS_CICLO_PAUSA
<<<<<<< HEAD
            set_operacao(ciclo, operacao='Falha ao reabrir inicio-bolao após SIM')
            salvar_ciclo(pasta, ciclo)
            return ciclo

        # Re-lê cards após SIM (site pode ter mudado enquanto esperava)
=======
            set_operacao(ciclo, operacao='Falha ao reabrir inicio-bolao')
            salvar_ciclo(pasta, ciclo)
            return ciclo

        # Re-lê cards no hub (site pode ter mudado)
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        cards_pos = listar_cards_modalidades(api.driver, log_fn=out_fn)
        if wanted and cards_pos:
            cards_pos = [c for c in cards_pos if c['slug'] in wanted or c.get('parser_slug') in wanted]
        if cards_pos:
            cards = cards_pos
            ordem_slugs = []
            for card in cards:
                slug = card['slug']
                label = card['label']
                ordem_slugs.append(slug)
<<<<<<< HEAD
                _garantir_unidade_lista(ciclo, slug, label)
=======
                _garantir_ufs_modalidade(ciclo, slug, label)
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
                if card.get('concurso'):
                    atualizar_modalidade(ciclo, slug, concurso=str(card['concurso']))
            salvar_ciclo(pasta, ciclo)

<<<<<<< HEAD
    out_fn('\n  ✔ SIM OK — Detalhes, grava, próxima página. Sem filtro de estado.')
=======
    out_fn('\n  [AUTO] Clicando Compre seu bolão e extraindo automaticamente...')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    imprimir_painel_ciclo(ciclo, out_fn, ordem_slugs=ordem_slugs)

    pausado = False
    total = len(cards)
<<<<<<< HEAD
    ordem_cards = list(cards)
    _pos_ciclo = 0
    _segunda_passagem = False
    while not pausado:
        if _pos_ciclo >= len(ordem_cards):
            if _segunda_passagem:
                break
            faltam_cards = []
            for card_f in cards:
                st_f = str(
                    (ciclo.get('modalidades') or {}).get(card_f.get('slug'), {}).get('status') or ''
                )
                if st_f not in (STATUS_CONCLUIDO, STATUS_VAZIO):
                    faltam_cards.append(card_f)
            if not faltam_cards:
                break
            _segunda_passagem = True
            nomes = ', '.join(str(c.get('label') or c.get('slug')) for c in faltam_cards)
            out_fn('')
            out_fn(
                '  [CICLO] Checkpoint — voltando às modalidades que ainda não '
                f'esgotaram a paginação: {nomes}'
            )
            ordem_cards = faltam_cards
            _pos_ciclo = 0
            total = len(ordem_cards)
            continue
        idx = _pos_ciclo + 1
        card = ordem_cards[_pos_ciclo]
        _pos_ciclo += 1
=======
    fila_estados = estados_varredura('SP')
    ultima_sigla = fila_estados[-1].sigla if fila_estados else ''

    def _uf_corrente(slug_mod: str):
        ufs_map = (ciclo.get('modalidades') or {}).get(slug_mod, {}).get('ufs') or {}
        for est in fila_estados:
            slot = ufs_map.get(est.sigla) or {}
            if str(slot.get('status') or '') not in (
                STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO,
            ):
                return est.sigla, slot
        return (fila_estados[0].sigla if fila_estados else 'SP'), {}

    for idx, card in enumerate(cards, start=1):
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        if pausado:
            break
        mod = _mod_de_card(card)
        if mod is None:
            out_fn(f'  [CICLO] Card sem modalidade: {card!r}')
            continue
        slug = mod.slug
<<<<<<< HEAD
        _garantir_unidade_lista(ciclo, slug, mod.label)
        st_mod = str(ciclo['modalidades'][slug].get('status') or '')
        if _ja_baixada(ciclo, slug):
            out_fn(
                f'  [CHECKPOINT] {mod.label} já baixada ({st_mod}). '
                f'Não abre de novo e não volta para a página 2.'
            )
=======
        _garantir_ufs_modalidade(ciclo, slug, mod.label)
        sigla0, slot0 = _uf_corrente(slug)
        st_mod = str(ciclo['modalidades'][slug].get('status') or '')
        pag0 = int(slot0.get('pagina_atual') or 0)
        tot0 = int(slot0.get('total_paginas') or 0)
        if (
            st_mod == STATUS_CONCLUIDO
            and pag0 > 0
            and tot0 > 0
            and pag0 < tot0
        ):
            out_fn(
                f'  [CICLO] {mod.label} estava CONCLUÍDO cedo demais '
                f'(UF {sigla0} pág. {pag0}/{tot0}) — reabre para continuar.'
            )
            atualizar_uf(
                ciclo, slug, sigla0,
                status=STATUS_PENDENTE, pagina_atual=pag0,
                total_paginas=tot0,
                erro='parcial — wrap/fim aparente com páginas restantes',
            )
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            ciclo['modalidades'][slug]['fim'] = ''
            salvar_ciclo(pasta, ciclo)
            st_mod = STATUS_PENDENTE
        if st_mod in (STATUS_CONCLUIDO, STATUS_VAZIO) and modalidade_concluida_pelas_ufs(ciclo, slug):
            out_fn(f'  [CICLO] {mod.label} já ok (todas as UFs) — pulando.')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
            continue

        conc_mod = str(card.get('concurso') or ciclo['modalidades'][slug].get('concurso') or '')
        if conc_mod:
            atualizar_modalidade(ciclo, slug, concurso=conc_mod)

        atualizar_modalidade(ciclo, slug, status=STATUS_ANDAMENTO, marcar_inicio=True)
        set_operacao(
            ciclo,
            modalidade=slug,
<<<<<<< HEAD
            uf='',
            operacao=f'Auto card — {mod.label} ({idx}/{total})',
=======
            uf=sigla0,
            operacao=f'Auto card — {mod.label} ({idx}/{total}) | UF {sigla0}',
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        )
        salvar_ciclo(pasta, ciclo)
        imprimir_painel_ciclo(ciclo, out_fn, ordem_slugs=ordem_slugs)

        out_fn('')
        out_fn('=' * 64)
<<<<<<< HEAD
        out_fn(f'  {idx}/{total} — {mod.label} | conc {conc_mod or "?"} | AUTO')
=======
        out_fn(
            f'  {idx}/{total} — {mod.label} | conc {conc_mod or "?"} | '
            f'{len(fila_estados)} UFs (SP → {ultima_sigla})'
        )
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        from boloes_modalidades import nome_arquivo_sessao
        arq_prev = nome_arquivo_sessao(conc_mod or 'sem-concurso', mod)
        out_fn(f'  Arquivo destino: json-boloes/{arq_prev}.json')
        out_fn('=' * 64)
<<<<<<< HEAD

        # Troca de modalidade: Caixa costuma expirar / Edge cair após longas extrações.
        out_fn('  [SESSÃO] Conferindo Edge/login antes de abrir o card...')
        if not api.garantir_sessao_ciclo(out_fn):
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            set_operacao(ciclo, operacao=f'Checkpoint — sessão ao abrir {mod.label}')
            salvar_ciclo(pasta, ciclo)
            out_fn(
                f'  [SESSÃO] Não recuperou login agora em {mod.label}. '
                f'Fica no checkpoint. Segue para a próxima e volta depois.'
            )
            continue

        ok_lista = False
        try:
            ok_lista = abrir_lista_do_card(
                api.driver,
                label=mod.label,
                concurso=conc_mod,
                slug=slug,
                log_fn=out_fn,
            )
        except Exception as exc_abrir:
            out_fn(f'  [SESSÃO] Erro ao abrir lista: {exc_abrir}')
            if api._erro_indica_janela_morta(exc_abrir) or not api._janela_edge_viva():
                out_fn('  [SESSÃO] Edge morreu ao abrir lista — recuperando e tentando de novo...')
                if api.garantir_sessao_ciclo(out_fn):
                    try:
                        ok_lista = abrir_lista_do_card(
                            api.driver,
                            label=mod.label,
                            concurso=conc_mod,
                            slug=slug,
                            log_fn=out_fn,
                        )
                    except Exception as exc2:
                        out_fn(f'  [SESSÃO] 2ª tentativa falhou: {exc2}')
                        ok_lista = False

        if not ok_lista:
            out_fn(
                f'  [SESSÃO] Lista de {mod.label} não abriu (0 Detalhes / sessão). '
                f'Recuperando login e tentando 1×...'
            )
            if api.garantir_sessao_ciclo(out_fn):
                try:
                    ok_lista = abrir_lista_do_card(
                        api.driver,
                        label=mod.label,
                        concurso=conc_mod,
                        slug=slug,
                        log_fn=out_fn,
                    )
                except Exception as exc_retry:
                    out_fn(f'  [SESSÃO] Retry falhou: {exc_retry}')
                    ok_lista = False

        if not ok_lista:
            # PENDENTE (não ERRO): [C] Continuar reabre estas modalidades.
            janela_ok = api._janela_edge_viva()
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            salvar_ciclo(pasta, ciclo)
            if not janela_ok:
                set_operacao(ciclo, operacao=f'Checkpoint — Edge fechou em {mod.label}')
                salvar_ciclo(pasta, ciclo)
                out_fn(
                    f'  [CICLO] Edge fechado — {mod.label} PENDENTE. '
                    f'Relogin na próxima modalidade (não para o ciclo).'
                )
                api.garantir_sessao_ciclo(out_fn)
                continue
            out_fn(f'  [CICLO] Não abriu lista de {mod.label} — fica PENDENTE; próxima.')
            continue

        conferida = detectar_lista_boloes_aberta(api.driver)
        if conferida and conferida.get('slug') and conferida['slug'] != slug:
            out_fn(
                f'  [CICLO] Site está em {conferida["label"]}, esperado {mod.label}. '
                f'Não extrai — evitaria gravar no arquivo errado.'
            )
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            salvar_ciclo(pasta, ciclo)
            continue

        from boloes_modalidades import nome_arquivo_sessao
        arq_mod = nome_arquivo_sessao(conc_mod or 'sem-concurso', mod)
        out_fn(
            f'\n  ✔ Lista aberta: {mod.label} conc {conc_mod or "?"}. '
            f'Detalhes de cada bolão da página, grava e vai à próxima.'
        )
        out_fn('  Sem filtro de estado. A paginação do site é que troca a UF.')
        out_fn(f'  Arquivo: json-boloes/{arq_mod}.json')
        api.SESSAO_AUTORIZADA = True
        set_operacao(
            ciclo,
            modalidade=slug,
            uf='',
            operacao=f'Detalhes + próxima página — {mod.label}',
        )
        salvar_ciclo(pasta, ciclo)

        try:
            boloes_final, ab, painel = api._extrair_como_opcao_1(
                mod,
                conc_mod,
                rodada_filtro=idx,
                forcar_pagina_inicial=1,
                sem_popup=True,
            )
        except Exception as exc:
            if api._erro_indica_janela_morta(exc) or not api._janela_edge_viva():
                atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
                set_operacao(ciclo, operacao=f'Checkpoint — Edge caiu em {mod.label}')
                salvar_ciclo(pasta, ciclo)
                out_fn(
                    f'  [SESSÃO] Edge/sessão caiu em {mod.label}. '
                    f'Checkpoint guardado. Relogin e segue para a próxima.'
                )
                api.SESSAO_AUTORIZADA = False
                api.garantir_sessao_ciclo(out_fn)
                continue
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            salvar_ciclo(pasta, ciclo)
            out_fn(f'  [CICLO] Erro em {mod.label}: {exc} — próxima.')
            api.SESSAO_AUTORIZADA = False
            continue

        painel = painel or {}
        if ab:
            atualizar_modalidade(ciclo, slug, arquivo_base=ab)
        conc = painel.get('concurso_alvo') or conc_mod
        if conc:
            atualizar_modalidade(ciclo, slug, concurso=conc)

        paginas = int(painel.get('paginas_processadas') or 0)
        path_json = os.path.join(pasta, f'{(ab or arq_mod)}.json')
        disco = []
        try:
            from boloes_consolidar import carregar_json_boloes
            disco = carregar_json_boloes(path_json)
        except Exception:
            disco = list(boloes_final or [])
        n_boloes = len(disco or boloes_final or [])
        ufs_found = _ufs_dos_boloes(disco or boloes_final)
        if ufs_found:
            ciclo['modalidades'][slug]['ufs_encontradas'] = ', '.join(ufs_found)

        if painel.get('pausado_operador'):
            atualizar_modalidade(ciclo, slug, status=STATUS_PAUSADO)
=======
        _avisar_inicio_modalidade(mod.label, out_fn)

        out_fn('  [SESSÃO] Conferindo Edge/login antes de abrir o card...')
        if not api.garantir_sessao_ciclo(out_fn):
            atualizar_uf(
                ciclo, slug, sigla0,
                status=STATUS_PENDENTE, pagina_atual=pag0,
                boloes=int(slot0.get('boloes') or 0),
                erro='sessão Caixa/Edge indisponível na troca de modalidade',
            )
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
            ciclo['status'] = STATUS_CICLO_PAUSA
            set_operacao(ciclo, operacao='Pausa — sessão expirada (troca de modalidade)')
            salvar_ciclo(pasta, ciclo)
            out_fn(
                '  [SESSÃO] Não recuperou login/Edge. '
                'Ciclo PAUSADO (PENDENTE). Rode [C] → Continuar após login.'
            )
            pausado = True
            break

<<<<<<< HEAD
        meta_pag = painel.get('paginacao_api') or {}
        pa_api = int(meta_pag.get('pagina_atual') or 0)
        up_api = int(meta_pag.get('ultima_pagina') or 0)
        # Só SP (ou 1 UF) + API ainda com páginas = NÃO concluído (bug antigo encerrava cedo).
        incompleto_ufs = (
            bool(painel.get('chegou_ao_fim') or painel.get('uf_concluida'))
            and len(ufs_found) <= 1
            and up_api > 0
            and pa_api > 0
            and pa_api < up_api
            and not painel.get('fim_lista_confirmado')
        )
        if incompleto_ufs:
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            set_operacao(
                ciclo,
                operacao=(
                    f'Checkpoint — {mod.label} incompleto '
                    f'(UF={",".join(ufs_found) or "?"} API {pa_api}/{up_api})'
                ),
            )
            salvar_ciclo(pasta, ciclo)
            out_fn(
                f'\n  [CICLO] {mod.label} NÃO concluída — só UF '
                f'{", ".join(ufs_found) or "?"} e API ainda em {pa_api}/{up_api}. '
                f'Fica PENDENTE para Continuar paginar todos os estados.'
            )
            api.SESSAO_AUTORIZADA = False
            continue

        if painel.get('uf_concluida') or painel.get('chegou_ao_fim'):
            st = STATUS_VAZIO if (paginas <= 0 and n_boloes <= 0) else STATUS_CONCLUIDO
            atualizar_modalidade(ciclo, slug, status=st, marcar_fim=True)
            out_fn(
                f'\n  [OK] {mod.label} concluída pela paginação '
                f'({n_boloes} bolões | UFs: {", ".join(ufs_found) or "—"}).'
            )
=======
        ok_lista = False
        try:
            ok_lista = abrir_lista_do_card(
                api.driver,
                label=mod.label,
                concurso=conc_mod,
                slug=slug,
                log_fn=out_fn,
            )
        except Exception as exc_abrir:
            out_fn(f'  [SESSÃO] Erro ao abrir lista: {exc_abrir}')
            if api._erro_indica_janela_morta(exc_abrir) or not api._janela_edge_viva():
                out_fn('  [SESSÃO] Edge morreu ao abrir lista — recuperando e tentando de novo...')
                if api.garantir_sessao_ciclo(out_fn):
                    try:
                        ok_lista = abrir_lista_do_card(
                            api.driver,
                            label=mod.label,
                            concurso=conc_mod,
                            slug=slug,
                            log_fn=out_fn,
                        )
                    except Exception as exc2:
                        out_fn(f'  [SESSÃO] 2ª tentativa falhou: {exc2}')
                        ok_lista = False

        if not ok_lista:
            out_fn(
                f'  [SESSÃO] Lista de {mod.label} não abriu (0 Detalhes / sessão). '
                f'Recuperando login e tentando 1×...'
            )
            if api.garantir_sessao_ciclo(out_fn):
                try:
                    ok_lista = abrir_lista_do_card(
                        api.driver,
                        label=mod.label,
                        concurso=conc_mod,
                        slug=slug,
                        log_fn=out_fn,
                    )
                except Exception as exc_retry:
                    out_fn(f'  [SESSÃO] Retry falhou: {exc_retry}')
                    ok_lista = False

        if not ok_lista:
            janela_ok = api._janela_edge_viva()
            atualizar_uf(
                ciclo, slug, sigla0,
                status=STATUS_PENDENTE, pagina_atual=pag0,
                boloes=int(slot0.get('boloes') or 0),
                erro='falha ao abrir lista (sessão/site)',
            )
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            salvar_ciclo(pasta, ciclo)
            if not janela_ok:
                ciclo['status'] = STATUS_CICLO_PAUSA
                set_operacao(ciclo, operacao='Pausa — Edge fechou na troca de modalidade')
                salvar_ciclo(pasta, ciclo)
                out_fn(
                    f'  [CICLO] Edge fechado — {mod.label} PENDENTE. '
                    f'Ciclo PAUSADO (não marca as demais como ERRO).'
                )
                pausado = True
                break
            _continuar_apos_falha(mod.label, out_fn, 'falha ao abrir lista (sessão/site)')
            continue

        conferida = detectar_lista_boloes_aberta(api.driver)
        if conferida and conferida.get('slug') and conferida['slug'] != slug:
            out_fn(
                f'  [CICLO] Site está em {conferida["label"]}, esperado {mod.label}. '
                f'Não extrai — evitaria gravar no arquivo errado.'
            )
            atualizar_uf(
                ciclo, slug, sigla0,
                status=STATUS_PENDENTE, pagina_atual=pag0,
                boloes=int(slot0.get('boloes') or 0),
                erro='lista de outra modalidade aberta',
            )
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            salvar_ciclo(pasta, ciclo)
            _continuar_apos_falha(mod.label, out_fn, 'lista de outra modalidade aberta')
            continue

        out_fn(
            f'\n  [AUTO] Lista aberta: {mod.label} conc {conc_mod or "?"} — '
            f'varre SP → {ultima_sigla} (só para no último estado).'
        )
        api.SESSAO_AUTORIZADA = True

        from boloes_modalidades import nome_arquivo_sessao
        from boloes_checkpoint import decidir_pagina_inicial
        from boloes_consolidar import carregar_json_boloes
        arq_mod = nome_arquivo_sessao(conc_mod or 'sem-concurso', mod)
        path_mod = os.path.join(pasta, f'{arq_mod}.json')

        for i_uf, estado in enumerate(fila_estados, start=1):
            if pausado:
                break
            sigla = estado.sigla
            slot = ciclo['modalidades'][slug]['ufs'].get(sigla) or {}
            st_uf = str(slot.get('status') or '')
            if st_uf in (STATUS_CONCLUIDO, STATUS_VAZIO):
                out_fn(f'  [UF] {sigla} já ok — próxima UF.')
                continue

            pag_uf = int(slot.get('pagina_atual') or 0)
            atualizar_uf(ciclo, slug, sigla, status=STATUS_ANDAMENTO, incrementar_tentativa=True)
            set_operacao(
                ciclo,
                modalidade=slug,
                uf=sigla,
                operacao=f'{mod.label} | UF {sigla} ({i_uf}/{len(fila_estados)})',
            )
            salvar_ciclo(pasta, ciclo)
            out_fn('')
            out_fn('-' * 64)
            out_fn(
                f'  [UF] {i_uf}/{len(fila_estados)} {estado.nome} ({sigla}) — '
                f'{"último estado" if sigla == ultima_sigla else "depois segue a fila"}'
            )

            existentes_mod: list = []
            n_arq = 0
            kb_arq = 0.0
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
            try:
                if os.path.isfile(path_mod):
                    kb_arq = os.path.getsize(path_mod) / 1024
                    existentes_mod = carregar_json_boloes(path_mod)
                    n_arq = len(existentes_mod)
            except Exception:
<<<<<<< HEAD
                pass
        else:
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            set_operacao(ciclo, operacao=f'Checkpoint — {mod.label} pág. {paginas}')
            salvar_ciclo(pasta, ciclo)
            out_fn(
                f'\n  [CICLO] {mod.label} parou na pág. {paginas} '
                f'({n_boloes} bolões). Checkpoint guardado. '
                f'Segue para a próxima modalidade e volta nesta depois.'
            )
            api.SESSAO_AUTORIZADA = False
            continue
=======
                existentes_mod = []
                n_arq = 0
            existentes_uf = [
                b for b in existentes_mod
                if str(b.get('uf') or '').upper() == sigla
            ]
            pagina_ini, n_ck = decidir_pagina_inicial(
                pasta, arq_mod, existentes_uf, pagina_ciclo=pag_uf, uf=sigla,
            )
            if pagina_ini > 1:
                out_fn(
                    f'  [CHECKPOINT] {sigla}: {len(existentes_uf) or n_ck} bolões desta UF '
                    f'| JSON {n_arq} reg. | {kb_arq:.1f} KB '
                    f'→ retoma na pág. {pagina_ini} (não na 1).'
                )
            else:
                out_fn(
                    f'  [UF] {sigla} começa na pág. 1 — '
                    + (
                        f'JSON já tem {n_arq} reg. de outras UFs.'
                        if n_arq and not existentes_uf
                        else ('arquivo será criado agora.' if n_arq == 0 else f'{len(existentes_uf)} desta UF.')
                    )
                )

            try:
                boloes_final, ab, painel = api._extrair_como_opcao_1(
                    mod,
                    conc_mod,
                    rodada_filtro=idx,
                    forcar_pagina_inicial=pagina_ini,
                    sem_popup=True,
                    estado=estado,
                    ufs_concluidas=ufs_concluidas_da_modalidade(ciclo, slug),
                    aplicar_filtro_uf=True,
                )
            except Exception as exc:
                if api._erro_indica_janela_morta(exc) or not api._janela_edge_viva():
                    atualizar_uf(
                        ciclo, slug, sigla,
                        status=STATUS_PENDENTE, pagina_atual=pag_uf,
                        boloes=int(slot.get('boloes') or 0),
                        erro=f'Edge/sessão caiu: {exc}',
                    )
                    atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
                    ciclo['status'] = STATUS_CICLO_PAUSA
                    set_operacao(ciclo, operacao='Pausa — Edge fechou durante extração')
                    salvar_ciclo(pasta, ciclo)
                    out_fn(
                        f'  [SESSÃO] Edge/sessão caiu em {mod.label}/{sigla}. '
                        f'Ciclo PAUSADO (PENDENTE). [C] → Continuar após login.'
                    )
                    api.SESSAO_AUTORIZADA = False
                    pausado = True
                    break
                atualizar_uf(ciclo, slug, sigla, status=STATUS_ERRO, erro=str(exc))
                salvar_ciclo(pasta, ciclo)
                out_fn(f'  [UF] {sigla} com erro — segue para o próximo estado.')
                continue

            if ab:
                atualizar_modalidade(ciclo, slug, arquivo_base=ab)
            conc = (painel or {}).get('concurso_alvo') or conc_mod
            if conc:
                atualizar_modalidade(ciclo, slug, concurso=conc)

            paginas = int((painel or {}).get('paginas_processadas') or 0)
            total_pag = int(((painel or {}).get('paginacao_api') or {}).get('ultima_pagina') or 0)
            path_json = os.path.join(pasta, f'{(ab or arq_mod)}.json')
            n_boloes_uf = len(existentes_uf)
            n_boloes_total = n_arq
            try:
                disco = carregar_json_boloes(path_json)
                n_boloes_total = max(n_boloes_total, len(disco))
                n_boloes_uf = sum(
                    1 for b in disco if str(b.get('uf') or '').upper() == sigla
                )
                ufs_found = _ufs_dos_boloes(disco or boloes_final)
            except Exception:
                ufs_found = _ufs_dos_boloes(boloes_final)
            if ufs_found:
                ciclo['modalidades'][slug]['ufs_encontradas'] = ', '.join(ufs_found)

            if (painel or {}).get('erro_filtro_uf'):
                atualizar_uf(
                    ciclo, slug, sigla,
                    status=STATUS_PENDENTE, pagina_atual=pag_uf,
                    boloes=n_boloes_uf,
                    erro=f'filtro UF {sigla} não aplicado no site',
                )
                atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
                salvar_ciclo(pasta, ciclo)
                out_fn(
                    f'  [UF] {sigla} não selecionado — não baixa de novo a lista errada. '
                    f'Segue para o próximo estado.'
                )
                continue

            if bool((painel or {}).get('abortar_retomada')) or bool((painel or {}).get('pausado_retomada')):
                atualizar_uf(
                    ciclo, slug, sigla,
                    status=STATUS_PENDENTE,
                    pagina_atual=max(int(pag_uf or 0), 0),
                    boloes=n_boloes_uf,
                    erro='retomada: site não chegou na página do JSON',
                )
                atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
                ciclo['status'] = STATUS_CICLO_PAUSA
                set_operacao(ciclo, operacao=f'Pausa — alinha página {sigla} no site (Seguinte)')
                salvar_ciclo(pasta, ciclo)
                out_fn(
                    f'  [CICLO] {mod.label}/{sigla} continua PENDENTE — '
                    f'NÃO vai para a próxima modalidade. '
                    f'NÃO vai para o próximo estado. '
                    f'Rode [C] de novo para alinhar a página.'
                )
                pausado = True
                break

            if bool((painel or {}).get('pausado_operador')):
                atualizar_uf(
                    ciclo, slug, sigla,
                    status=STATUS_PAUSADO, pagina_atual=paginas,
                    total_paginas=total_pag, boloes=n_boloes_uf,
                )
                atualizar_modalidade(ciclo, slug, status=STATUS_PAUSADO)
                ciclo['status'] = STATUS_CICLO_PAUSA
                set_operacao(ciclo, operacao='Pausado pelo operador')
                salvar_ciclo(pasta, ciclo)
                pausado = True
                break

            if (painel or {}).get('uf_concluida') or (painel or {}).get('chegou_ao_fim'):
                st_uf_fim = STATUS_VAZIO if (paginas <= 0 and n_boloes_uf <= 0) else STATUS_CONCLUIDO
                atualizar_uf(
                    ciclo, slug, sigla,
                    status=st_uf_fim, pagina_atual=paginas,
                    total_paginas=total_pag, boloes=n_boloes_uf,
                )
                out_fn(
                    f'  [OK] UF {sigla} encerrada ({n_boloes_uf} bolões desta UF | '
                    f'{n_boloes_total} no JSON).'
                )
                if sigla == ultima_sigla:
                    out_fn(f'  [UF] Último estado ({ultima_sigla}) atingido — fecha a modalidade.')
                else:
                    out_fn('  [UF] Ainda há estados na fila — NÃO fecha a modalidade.')
            elif paginas <= 0 and n_boloes_uf <= 0:
                atualizar_uf(
                    ciclo, slug, sigla,
                    status=STATUS_VAZIO, pagina_atual=0, boloes=0,
                    erro='lista vazia nesta UF',
                )
                out_fn(f'  [UF] {sigla} sem bolões — marca VAZIO e segue.')
            else:
                atualizar_uf(
                    ciclo, slug, sigla,
                    status=STATUS_PENDENTE, pagina_atual=paginas,
                    total_paginas=total_pag, boloes=n_boloes_uf,
                    erro='parcial',
                )
                atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
                out_fn(
                    f'  [UF] {sigla} parcial — NÃO fecha a modalidade. '
                    f'Segue tentando os demais estados.'
                )

            salvar_ciclo(pasta, ciclo)
            imprimir_painel_ciclo(ciclo, out_fn, ordem_slugs=ordem_slugs)

        if pausado:
            break

        if modalidade_concluida_pelas_ufs(ciclo, slug):
            st_mod_fim = STATUS_CONCLUIDO
            atualizar_modalidade(ciclo, slug, status=st_mod_fim, marcar_fim=True)
            out_fn(f'\n  [OK] {mod.label} concluída — todas as UFs até {ultima_sigla}.')
            _imprimir_resumo_da_modalidade(ciclo, slug, pasta, out_fn)
            _avisar_fim_modalidade(mod.label, out_fn)
        else:
            atualizar_modalidade(ciclo, slug, status=STATUS_PENDENTE)
            out_fn(
                f'  [CICLO] {mod.label} ainda tem UF pendente — '
                f'não gera Excel/consolidado. Próxima modalidade segue.'
            )
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257

        salvar_ciclo(pasta, ciclo)
        imprimir_painel_ciclo(ciclo, out_fn, ordem_slugs=ordem_slugs)
        api.SESSAO_AUTORIZADA = False

<<<<<<< HEAD
        # Limpa capturas da modalidade anterior (evita misturar +Milionária etc.)
=======
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        try:
            from boloes_api_caixa import limpar_capturas_api
            limpar_capturas_api(api.driver)
        except Exception:
            pass

<<<<<<< HEAD
        # Volta ao hub com sessão viva antes da próxima modalidade
        out_fn('  [SESSÃO] Voltando ao hub / conferindo login para a próxima...')
        if not api.garantir_sessao_ciclo(out_fn):
            set_operacao(ciclo, operacao='Checkpoint — sessão caiu após modalidade')
            salvar_ciclo(pasta, ciclo)
            out_fn(
                '  [SESSÃO] Sessão caiu após a modalidade. '
                'Segue para a próxima (relogin de novo, sem parar o ciclo).'
            )
            continue
=======
        out_fn('  [SESSÃO] Voltando ao hub / conferindo login para a próxima...')
        if not api.garantir_sessao_ciclo(out_fn):
            ciclo['status'] = STATUS_CICLO_PAUSA
            set_operacao(ciclo, operacao='Pausa — sessão caiu após modalidade')
            salvar_ciclo(pasta, ciclo)
            out_fn(
                '  [SESSÃO] Sessão caiu após a modalidade. '
                'Ciclo PAUSADO — [C] Continuar após login.'
            )
            pausado = True
            break
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        try:
            ir_para_inicio_bolao(api.driver, log_fn=out_fn, espera=2.0)
        except Exception as exc_hub:
            out_fn(f'  [SESSÃO] Aviso ao voltar ao hub: {exc_hub}')
            if api._erro_indica_janela_morta(exc_hub) or not api._janela_edge_viva():
                if not api.garantir_sessao_ciclo(out_fn):
<<<<<<< HEAD
                    set_operacao(ciclo, operacao='Checkpoint — Edge fechou no hub')
                    salvar_ciclo(pasta, ciclo)
                    out_fn('  [SESSÃO] Edge fechou no hub. A próxima modalidade tenta de novo.')
                    continue
=======
                    ciclo['status'] = STATUS_CICLO_PAUSA
                    set_operacao(ciclo, operacao='Pausa — Edge fechou no hub')
                    salvar_ciclo(pasta, ciclo)
                    pausado = True
                    break
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
                try:
                    ir_para_inicio_bolao(api.driver, log_fn=out_fn, espera=2.0)
                except Exception:
                    pass

    if not pausado:
        todas_ok = True
        for slug in ordem_slugs:
            st = str(ciclo['modalidades'].get(slug, {}).get('status') or '')
        if st != STATUS_CONCLUIDO:
            todas_ok = False
        from boloes_checkpoint_ciclo import agora_iso
        ciclo['fim'] = agora_iso()
        ciclo['status'] = STATUS_CICLO_OK if todas_ok else STATUS_CICLO_OCORRENCIAS
        set_operacao(ciclo, modalidade='', uf='', operacao='Finalizado')
        salvar_ciclo(pasta, ciclo)
        _gerar_entregaveis(ciclo, pasta, ordem_slugs, out_fn, pausado=False)
        try:
            from boloes_avisos import avisar_ciclo_finalizado
            avisar_ciclo_finalizado(ciclo.get('status') or '', out_fn=out_fn)
        except Exception:
            pass
    else:
        from boloes_checkpoint_ciclo import agora_iso
        ciclo['fim'] = ''
        set_operacao(ciclo, operacao=ciclo.get('operacao') or 'Pausado — extração incompleta')
        salvar_ciclo(pasta, ciclo)
        out_fn('')
        out_fn('  [CICLO] PAUSADO — extração ainda NÃO terminou.')
        out_fn('  [CICLO] Excel e JSON consolidado NÃO serão gerados agora.')
        out_fn('  [CICLO] Rode [C] de novo: continua a UF atual e só para no último estado.')
        out_fn('  [CICLO] Relatório final sai só depois da última modalidade.')

    return ciclo
