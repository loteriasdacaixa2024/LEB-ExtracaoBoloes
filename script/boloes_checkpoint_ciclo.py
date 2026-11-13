# -*- coding: utf-8 -*-
"""
Checkpoint GLOBAL do ciclo completo (modalidade × UF × página).

Arquivo: json-boloes/_checkpoint_ciclo.json
Não substitui _checkpoint_extracao.json (página local) — complementa.
"""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

NOME_CHECKPOINT_CICLO = '_checkpoint_ciclo.json'
NOME_CHECKPOINT_CICLO_ESPELHO = 'checkpoint_ciclo.json'
NOMES_CHECKPOINT_CICLO = (NOME_CHECKPOINT_CICLO, NOME_CHECKPOINT_CICLO_ESPELHO)

STATUS_AGUARDANDO = 'AGUARDANDO'
STATUS_ANDAMENTO = 'EM ANDAMENTO'
STATUS_CONCLUIDO = 'CONCLUÍDO'
STATUS_ERRO = 'ERRO'
STATUS_PENDENTE = 'PENDENTE'
STATUS_VAZIO = 'VAZIO'
STATUS_PAUSADO = 'PAUSADO'
STATUS_CICLO_EXEC = 'EM EXECUÇÃO'
STATUS_CICLO_OK = 'EXTRAÇÃO COMPLETA'
STATUS_CICLO_PAUSA = 'PAUSADO'
STATUS_CICLO_OCORRENCIAS = 'CONCLUÍDO COM OCORRÊNCIAS'


def agora_iso() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def caminho_checkpoint_ciclo(pasta_json: str) -> str:
    return os.path.join(pasta_json, NOME_CHECKPOINT_CICLO)


def _atomic_write(path: str, payload: Dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def carregar_ciclo(pasta_json: str) -> Optional[Dict[str, Any]]:
    """Lê _checkpoint_ciclo.json e o espelho sem underscore; fica com o de mais progresso."""
    melhores: List[Dict[str, Any]] = []
    for nome in NOMES_CHECKPOINT_CICLO:
        path = os.path.join(pasta_json, nome)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get('modalidades'):
                melhores.append(data)
        except Exception:
            continue
    if not melhores:
        return None

    def _progresso(ciclo: Dict[str, Any]) -> tuple:
        boloes = 0
        pag = 0
        for m in (ciclo.get('modalidades') or {}).values():
            for u in (m.get('ufs') or {}).values():
                boloes += int(u.get('boloes') or 0)
                pag = max(pag, int(u.get('pagina_atual') or 0))
        return (boloes, pag, str(ciclo.get('atualizado_em') or ''))

    melhores.sort(key=_progresso, reverse=True)
    return melhores[0]


def novo_ciclo(
    modalidades: List[Dict[str, str]],
    ufs: List[str],
    *,
    ciclo_id: str = '',
) -> Dict[str, Any]:
    """
    modalidades: [{'slug','label'}, ...]
    ufs: ['SP','AC', ...]
    """
    cid = ciclo_id or datetime.now().strftime('%Y%m%d-%H%M%S')
    mods: Dict[str, Any] = {}
    for m in modalidades:
        slug = m['slug']
        ufs_map = {
            sigla: {
                'status': STATUS_AGUARDANDO,
                'pagina_atual': 0,
                'total_paginas': 0,
                'boloes': 0,
                'tentativas': 0,
                'erro': '',
                'atualizado_em': '',
            }
            for sigla in ufs
        }
        mods[slug] = {
            'label': m.get('label') or slug,
            'status': STATUS_AGUARDANDO,
            'concurso': '',
            'arquivo_base': '',
            'ufs': ufs_map,
            'inicio': '',
            'fim': '',
        }
    return {
        'versao': 2,
        'ciclo_id': cid,
        'status': STATUS_CICLO_EXEC,
        'inicio': agora_iso(),
        'fim': '',
        'atualizado_em': agora_iso(),
        'modalidade_atual': '',
        'uf_atual': '',
        'operacao': 'Iniciando',
        'modalidades': mods,
        'resumo': {
            'modalidades_ok': 0,
            'ufs_ok': 0,
            'ufs_erro': 0,
            'ufs_vazio': 0,
            'ufs_pendente': 0,
            'boloes_total': 0,
            'erros': 0,
        },
    }


def salvar_ciclo(pasta_json: str, ciclo: Dict[str, Any]) -> str:
    ciclo = dict(ciclo)
    ciclo['atualizado_em'] = agora_iso()
    ciclo['resumo'] = calcular_resumo(ciclo)
    path = _atomic_write(caminho_checkpoint_ciclo(pasta_json), ciclo)
    try:
        _atomic_write(os.path.join(pasta_json, NOME_CHECKPOINT_CICLO_ESPELHO), ciclo)
    except OSError:
        pass
    return path


<<<<<<< HEAD
=======
def _slot_uf_vazio() -> Dict[str, Any]:
    return {
        'status': STATUS_AGUARDANDO,
        'pagina_atual': 0,
        'total_paginas': 0,
        'boloes': 0,
        'tentativas': 0,
        'erro': '',
        'atualizado_em': '',
    }


def normalizar_ufs_do_ciclo(ciclo: Dict[str, Any]) -> bool:
    """
    Garante as 27 UFs (SP primeiro). Migra o slot legado LISTA → SP
    sem apagar progresso. Modalidade já CONCLUÍDA não reabre UFs.
    """
    from boloes_estados import siglas_varredura

    mudou = False
    ordem = siglas_varredura('SP')
    for mod in (ciclo.get('modalidades') or {}).values():
        if not isinstance(mod, dict):
            continue
        ufs = mod.setdefault('ufs', {})
        if not isinstance(ufs, dict):
            continue
        if 'LISTA' in ufs:
            legado = ufs.pop('LISTA') or {}
            dest = ufs.get('SP')
            n_leg = int(legado.get('boloes') or 0)
            n_sp = int((dest or {}).get('boloes') or 0)
            if dest is None or n_leg >= n_sp:
                ufs['SP'] = legado
            mudou = True
        novo: Dict[str, Any] = {}
        for sigla in ordem:
            novo[sigla] = ufs.get(sigla) or _slot_uf_vazio()
        for k, v in ufs.items():
            if k not in novo:
                novo[k] = v
        if list(ufs.keys()) != list(novo.keys()):
            mudou = True
        mod['ufs'] = novo

        st_mod = str(mod.get('status') or '')
        if st_mod == STATUS_CONCLUIDO:
            encontradas = {
                u.strip().upper()
                for u in str(mod.get('ufs_encontradas') or '').split(',')
                if u.strip()
            }
            for sigla, slot in novo.items():
                st = str(slot.get('status') or '')
                if st in (STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO):
                    continue
                if sigla in encontradas or int(slot.get('boloes') or 0) > 0:
                    slot['status'] = STATUS_CONCLUIDO
                else:
                    slot['status'] = STATUS_VAZIO
                mudou = True
    return mudou


>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
def hidratar_ciclo_com_jsons(pasta_json: str, ciclo: Dict[str, Any], out_fn=print) -> bool:
    """
    Se o ciclo diz página 0 mas o JSON da modalidade já tem bolões,
    preenche pagina_atual / arquivo_base a partir do arquivo gravado.
<<<<<<< HEAD
    """
    from boloes_checkpoint import boloes_do_concurso, ultima_pagina_completa_sequencial
    from boloes_consolidar import carregar_json_boloes
    from boloes_modalidades import modalidade_por_slug, nome_arquivo_sessao

    mudou = False
=======
    Conta bolões por UF para não tratar SP como se fosse o país inteiro.
    """
    from boloes_checkpoint import ultima_pagina_completa_sequencial
    from boloes_consolidar import carregar_json_boloes
    from boloes_modalidades import modalidade_por_slug, nome_arquivo_sessao

    mudou = normalizar_ufs_do_ciclo(ciclo)
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    mods = ciclo.setdefault('modalidades', {})
    for slug, mod in list(mods.items()):
        if not isinstance(mod, dict):
            continue
<<<<<<< HEAD
        conc = re.sub(r'\D', '', str(mod.get('concurso') or ''))
        ab = str(mod.get('arquivo_base') or '').removesuffix('.json')
        mobj = modalidade_por_slug(slug)
        # Só o JSON deste concurso. boloes_1300 não retoma o concurso 1332.
        path = ''
        if conc and mobj:
            candidato = os.path.join(pasta_json, f'{nome_arquivo_sessao(conc, mobj)}.json')
            if os.path.isfile(candidato):
                path = candidato
        elif ab and (ab.endswith(f'_{slug}') or f'_{slug}.' in f'{ab}.'):
            candidato = os.path.join(pasta_json, f'{ab}.json')
            if os.path.isfile(candidato):
                path = candidato
=======
        conc = str(mod.get('concurso') or '')
        ab = str(mod.get('arquivo_base') or '').removesuffix('.json')
        candidatos: List[str] = []
        if ab:
            candidatos.append(os.path.join(pasta_json, f'{ab}.json'))
        mobj = modalidade_por_slug(slug)
        if conc and mobj:
            candidatos.append(os.path.join(pasta_json, f'{nome_arquivo_sessao(conc, mobj)}.json'))
        candidatos.extend(sorted(glob.glob(os.path.join(pasta_json, f'boloes_*_{slug}.json'))))
        path = next((p for p in candidatos if p and os.path.isfile(p)), '')
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
        if not path:
            continue
        boloes = carregar_json_boloes(path)
        if not boloes:
            continue
<<<<<<< HEAD
        base = boloes_do_concurso(boloes, conc) if conc else boloes
        ufs = mod.setdefault('ufs', {})
        ufs.pop('LISTA', None)
        mod['arquivo_base'] = os.path.splitext(os.path.basename(path))[0]
        from boloes_estados import estados_varredura
        partes = []
        for est in estados_varredura('SP'):
            subset = [
                b for b in base
                if str(b.get('uf_varredura') or '').upper() == est.sigla
                or (
                    not str(b.get('uf_varredura') or '').strip()
                    and str(b.get('uf') or '').upper() == est.sigla
                )
            ]
            seq = ultima_pagina_completa_sequencial(subset) if subset else 0
            slot = ufs.setdefault(est.sigla, {
                'status': STATUS_AGUARDANDO,
                'pagina_atual': 0,
                'total_paginas': 0,
                'boloes': 0,
                'tentativas': 0,
                'erro': '',
                'atualizado_em': '',
            })
            if seq <= 0:
                continue
            pag_ck = int(slot.get('pagina_atual') or 0)
            if seq > pag_ck or int(slot.get('boloes') or 0) < len(subset):
                slot['pagina_atual'] = max(seq, pag_ck)
                slot['boloes'] = len(subset)
                st = str(slot.get('status') or '')
                if st in ('', STATUS_AGUARDANDO, STATUS_ANDAMENTO, STATUS_CONCLUIDO):
                    # JSON com páginas não prova que a UF acabou (a última pode faltar).
                    slot['status'] = STATUS_PENDENTE
                    slot['erro'] = ''
                mudou = True
                partes.append(f'{est.sigla} pág.{seq} ({len(subset)})')
        if partes:
            st_mod = str(mod.get('status') or '')
            if st_mod in ('', STATUS_AGUARDANDO, STATUS_CONCLUIDO):
                mod['status'] = STATUS_PENDENTE
                mod['fim'] = ''
            mudou = True
            out_fn(
                f'  [CHECKPOINT] {mod.get("label") or slug}: JSON {os.path.basename(path)} '
                f'por UF — ' + ', '.join(partes) + '. Retoma o que faltar.'
            )
=======
        n = len(boloes)
        ufs = mod.setdefault('ufs', {})
        por_uf: Dict[str, List[dict]] = {}
        for b in boloes:
            uf = str(b.get('uf') or '').upper().strip()
            if not uf:
                continue
            por_uf.setdefault(uf, []).append(b)
        if por_uf:
            mod['ufs_encontradas'] = ', '.join(sorted(por_uf.keys()))
        for sigla, itens in por_uf.items():
            slot = ufs.setdefault(sigla, _slot_uf_vazio())
            slot['boloes'] = max(int(slot.get('boloes') or 0), len(itens))
            seq_uf = ultima_pagina_completa_sequencial(itens)
            pag_ck = int(slot.get('pagina_atual') or 0)
            if seq_uf > pag_ck:
                slot['pagina_atual'] = seq_uf
            st = str(slot.get('status') or '')
            st_mod = str(mod.get('status') or '')
            if st_mod != STATUS_CONCLUIDO and st in ('', STATUS_AGUARDANDO):
                slot['status'] = STATUS_PENDENTE
        normalizar_ufs_do_ciclo(ciclo)
        ufs = mod.setdefault('ufs', {})
        st_mod = str(mod.get('status') or '')
        if st_mod != STATUS_CONCLUIDO:
            em_curso = next(
                (
                    s for s, slot in ufs.items()
                    if str(slot.get('status') or '') not in (
                        STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO,
                    ) and int(slot.get('boloes') or 0) > 0
                ),
                '',
            )
            if em_curso:
                seq = ultima_pagina_completa_sequencial(por_uf.get(em_curso) or boloes)
                if st_mod in ('', STATUS_AGUARDANDO):
                    mod['status'] = STATUS_PENDENTE
                mudou = True
                out_fn(
                    f'  [CHECKPOINT] {mod.get("label") or slug}: JSON {os.path.basename(path)} '
                    f'tem {n} bolao(oes) | UF {em_curso} pág. completa={seq} '
                    f'-> retoma na {seq + 1} (demais UFs na fila).'
                )
            elif n > 0:
                mudou = True
                out_fn(
                    f'  [CHECKPOINT] {mod.get("label") or slug}: JSON {os.path.basename(path)} '
                    f'tem {n} bolao(oes) — UFs ainda na fila após SP.'
                )
        if n > 0:
            mod['arquivo_base'] = os.path.splitext(os.path.basename(path))[0]
            mudou = True
>>>>>>> 9b31c3cfb91ce8f2a5d6b33bcd31f23daf18a257
    if mudou:
        ciclo['resumo'] = calcular_resumo(ciclo)
    return mudou


def calcular_resumo(ciclo: Dict[str, Any]) -> Dict[str, int]:
    mods_ok = 0
    ufs_ok = ufs_erro = ufs_vazio = ufs_pend = boloes = erros = 0
    for mod in (ciclo.get('modalidades') or {}).values():
        if str(mod.get('status') or '') == STATUS_CONCLUIDO:
            mods_ok += 1
        for uf in (mod.get('ufs') or {}).values():
            st = str(uf.get('status') or '')
            boloes += int(uf.get('boloes') or 0)
            if st == STATUS_CONCLUIDO:
                ufs_ok += 1
            elif st == STATUS_ERRO:
                ufs_erro += 1
                erros += 1
            elif st == STATUS_VAZIO:
                ufs_vazio += 1
            elif st in (STATUS_PENDENTE, STATUS_AGUARDANDO, STATUS_ANDAMENTO, STATUS_PAUSADO):
                if st == STATUS_PENDENTE:
                    ufs_pend += 1
    return {
        'modalidades_ok': mods_ok,
        'ufs_ok': ufs_ok,
        'ufs_erro': ufs_erro,
        'ufs_vazio': ufs_vazio,
        'ufs_pendente': ufs_pend,
        'boloes_total': boloes,
        'erros': erros,
    }


def set_operacao(
    ciclo: Dict[str, Any],
    *,
    modalidade: str = '',
    uf: str = '',
    operacao: str = '',
) -> None:
    if modalidade:
        ciclo['modalidade_atual'] = modalidade
    if uf:
        ciclo['uf_atual'] = uf
    if operacao:
        ciclo['operacao'] = operacao


def atualizar_uf(
    ciclo: Dict[str, Any],
    slug: str,
    sigla: str,
    *,
    status: str = '',
    pagina_atual: Optional[int] = None,
    total_paginas: Optional[int] = None,
    boloes: Optional[int] = None,
    erro: Optional[str] = None,
    incrementar_tentativa: bool = False,
) -> None:
    mod = (ciclo.get('modalidades') or {}).get(slug)
    if not mod:
        return
    uf = (mod.get('ufs') or {}).get(sigla)
    if not uf:
        return
    if status:
        uf['status'] = status
    if pagina_atual is not None:
        uf['pagina_atual'] = int(pagina_atual)
    if total_paginas is not None:
        uf['total_paginas'] = int(total_paginas)
    if boloes is not None:
        uf['boloes'] = int(boloes)
    if erro is not None:
        uf['erro'] = str(erro)[:500]
    if incrementar_tentativa:
        uf['tentativas'] = int(uf.get('tentativas') or 0) + 1
    uf['atualizado_em'] = agora_iso()


def atualizar_modalidade(
    ciclo: Dict[str, Any],
    slug: str,
    *,
    status: str = '',
    concurso: str = '',
    arquivo_base: str = '',
    marcar_inicio: bool = False,
    marcar_fim: bool = False,
) -> None:
    mod = (ciclo.get('modalidades') or {}).get(slug)
    if not mod:
        return
    if status:
        mod['status'] = status
    if concurso:
        mod['concurso'] = re.sub(r'\D', '', str(concurso)) or mod.get('concurso') or ''
    if arquivo_base:
        mod['arquivo_base'] = str(arquivo_base).removesuffix('.json')
    if marcar_inicio and not mod.get('inicio'):
        mod['inicio'] = agora_iso()
    if marcar_fim:
        mod['fim'] = agora_iso()


def modalidade_concluida_pelas_ufs(ciclo: Dict[str, Any], slug: str) -> bool:
    mod = (ciclo.get('modalidades') or {}).get(slug) or {}
    ufs = mod.get('ufs') or {}
    if not ufs:
        return False
    terminais = {STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO}
    return all(str(u.get('status') or '') in terminais for u in ufs.values())


def proximo_pendente(ciclo: Dict[str, Any]) -> Optional[tuple]:
    """
    Retorna (slug, sigla, pagina_retomar) do próximo item a processar.
    pagina_retomar = pagina_atual+1 se EM ANDAMENTO/PAUSADO com página > 0.
    """
    for slug, mod in (ciclo.get('modalidades') or {}).items():
        st_mod = str(mod.get('status') or '')
        if st_mod == STATUS_CONCLUIDO:
            continue
        for sigla, uf in (mod.get('ufs') or {}).items():
            st = str(uf.get('status') or '')
            if st in (STATUS_CONCLUIDO, STATUS_VAZIO, STATUS_ERRO):
                continue
            pagina = int(uf.get('pagina_atual') or 0)
            if pagina > 0 and st in (
                STATUS_ANDAMENTO, STATUS_PAUSADO, STATUS_PENDENTE, STATUS_AGUARDANDO,
            ):
                return slug, sigla, pagina + 1
            return slug, sigla, 1
    return None


def ufs_concluidas_da_modalidade(ciclo: Dict[str, Any], slug: str) -> List[str]:
    mod = (ciclo.get('modalidades') or {}).get(slug) or {}
    out = []
    for sigla, uf in (mod.get('ufs') or {}).items():
        if str(uf.get('status') or '') in (STATUS_CONCLUIDO, STATUS_VAZIO):
            out.append(sigla)
    return out


def resolver_retomada_ciclo_automatica(
    pasta_json: str,
    *,
    out_fn=print,
) -> tuple:
    """
    Retomada SEM pergunta — usada pelo ciclo automático.

    Ciclo incompleto → continua.
    Ciclo já completo → inicia ciclo novo (não reextrai o que já terminou).
    Sem checkpoint → ciclo novo.
    """
    ciclo = carregar_ciclo(pasta_json)
    if not ciclo:
        return True, None

    hidratar_ciclo_com_jsons(pasta_json, ciclo, out_fn=out_fn)
    status = str(ciclo.get('status') or '')
    if status == STATUS_CICLO_OK:
        out_fn('\n  [CICLO] Último ciclo já está COMPLETO — iniciando ciclo novo automaticamente.')
        return False, None

    nxt = proximo_pendente(ciclo)
    out_fn('')
    out_fn('  [CICLO] Checkpoint incompleto detectado — retomando automaticamente.')
    out_fn(f'  [CICLO] Status={status} | modalidade={ciclo.get("modalidade_atual") or "?"}')
    if nxt:
        out_fn(f'  [CICLO] Próximo: {nxt[0]} / {nxt[1]} pág. {nxt[2]}')
    out_fn('  [CICLO] Sem confirmação (SIM/ENTER) — o fluxo continua sozinho.')
    return True, ciclo


def perguntar_retomada_ciclo(
    pasta_json: str,
    *,
    input_fn=input,
    out_fn=print,
) -> tuple:
    """
    Retorna (continuar: bool, ciclo: dict|None).
    continuar=False + ciclo=None → usuário quer ciclo NOVO (descarta progresso do checkpoint).
    """
    ciclo = carregar_ciclo(pasta_json)
    if not ciclo:
        return True, None

    hidratar_ciclo_com_jsons(pasta_json, ciclo, out_fn=out_fn)

    status = str(ciclo.get('status') or '')
    if status == STATUS_CICLO_OK:
        out_fn('\n  [CICLO] Último ciclo já está COMPLETO.')
        out_fn('  [C] Continuar mesmo assim (revisar pendências/erros)')
        out_fn('  [N] Novo ciclo do zero')
    else:
        nxt = proximo_pendente(ciclo)
        out_fn('')
        out_fn('=' * 60)
        out_fn('  CICLO INCOMPLETO DETECTADO')
        out_fn('=' * 60)
        out_fn(f'  ID        : {ciclo.get("ciclo_id")}')
        out_fn(f'  Status    : {status}')
        out_fn(f'  Início    : {ciclo.get("inicio")}')
        out_fn(f'  Atualizado: {ciclo.get("atualizado_em")}')
        out_fn(f'  Modalidade: {ciclo.get("modalidade_atual") or "?"}')
        out_fn(f'  UF        : {ciclo.get("uf_atual") or "?"}')
        if nxt:
            out_fn(f'  Próximo   : {nxt[0]} / {nxt[1]} pág. {nxt[2]}')
        res = ciclo.get('resumo') or calcular_resumo(ciclo)
        out_fn(
            f'  Resumo    : mods_ok={res.get("modalidades_ok")} | '
            f'ufs_ok={res.get("ufs_ok")} | erros={res.get("erros")} | '
            f'bolões≈{res.get("boloes_total")}'
        )
        out_fn('-' * 60)
        out_fn('  [C] Continuar de onde parou')
        out_fn('  [N] Novo ciclo (NÃO apaga JSONs; reinicia só o checkpoint do ciclo)')
        out_fn('=' * 60)

    try:
        resp = (input_fn('  Escolha [C/N] (Enter=Continuar): ') or '').strip().upper()
    except EOFError:
        resp = 'C'

    if resp in ('N', 'NOVA', 'NEW'):
        out_fn('  >> Novo ciclo a partir da primeira modalidade/UF.')
        return False, None

    out_fn('  >> Continuando o ciclo existente.')
    return True, ciclo
