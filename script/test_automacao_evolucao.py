# -*- coding: utf-8 -*-
"""
Testes offline da evolução do ciclo automático (v4.5.0).

Não abre o site da Caixa. Cobre: análise estática do fluxo, paginação,
relatórios, Excel, JSON consolidado, isolamento de erro e avisos.
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _fonte(nome: str) -> str:
    path = os.path.join(SCRIPT_DIR, nome)
    with open(path, encoding='utf-8') as f:
        return f.read()


class Teste1AnaliseFluxoEstatico(unittest.TestCase):
    """TESTE 8 + arquitetura: ciclo automático sem input()/SIM."""

    def test_ciclo_nao_pede_sim_nem_input(self):
        src = _fonte('boloes_ciclo_completo.py')
        self.assertNotIn('aguardar_site_pronto', src)
        self.assertNotIn('aguardar_sim_apos_compre_bolao', src)
        self.assertNotIn('perguntar_retomada_ciclo(', src)
        self.assertIn('resolver_retomada_ciclo_automatica', src)
        tree = ast.parse(src)
        chamadas_input = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'input'
        ]
        self.assertEqual(chamadas_input, [], 'ciclo automático não pode chamar input()')

    def test_ciclo_nao_tem_textos_de_confirmacao(self):
        src = _fonte('boloes_ciclo_completo.py')
        for trecho in ('Digite SIM', 'Pressione ENTER', 'Deseja continuar'):
            self.assertNotIn(trecho, src)

    def test_funcoes_preservadas(self):
        src = _fonte('boloes_ciclo_completo.py')
        for nome in (
            'listar_cards_modalidades',
            'ordenar_cards_por_prioridade',
            'abrir_lista_do_card',
            '_extrair_como_opcao_1',
            'salvar_ciclo',
            'estados_varredura',
            'aplicar_filtro_uf',
        ):
            self.assertIn(nome, src)

    def test_relatorio_nao_sai_na_pausa(self):
        src = _fonte('boloes_ciclo_completo.py')
        self.assertIn('Excel e JSON consolidado NÃO serão gerados agora', src)
        self.assertIn('só para no último estado', src)
        self.assertNotIn('Relatório parcial será gerado', src)

    def test_extrator_ainda_grava_json_e_checkpoint(self):
        src = _fonte('baixar_boloes-API.py')
        self.assertIn('salvar_checkpoint', src)
        self.assertIn('Arquivo:', src)
        self.assertIn('sem_popup', src)
        self.assertIn('formatar_monitor_consistencia', src)
        src_mon = _fonte('boloes_monitor_paginacao.py')
        self.assertIn('linhas_divergencia_paginacao', src_mon)
        # input() do OK/FORCAR só no ramo interativo (não no sem_popup)
        self.assertIn("if sem_popup:", src)
        self.assertIn('>>> OK / FORCAR / Enter:', src)


class Teste2Paginacao(unittest.TestCase):
    """TESTE 2 — divergência visual vs API não é falha."""

    def test_divergencia_detectada_acima_da_pagina_10(self):
        from boloes_monitor_paginacao import divergencia_paginacao, linhas_divergencia_paginacao
        self.assertTrue(divergencia_paginacao(16, 27))
        self.assertFalse(divergencia_paginacao(16, 16))
        self.assertFalse(divergencia_paginacao(None, 27))
        linhas = linhas_divergencia_paginacao(16, 20, 27)
        blob = '\n'.join(linhas)
        self.assertIn('Paginação visual da interface diverge da paginação da API', blob)
        self.assertIn('Extração continuará utilizando a paginação da API', blob)
        self.assertIn('27', blob)
        self.assertIn('16', blob)

    def test_monitor_mostra_fonte_da_verdade(self):
        from boloes_monitor_paginacao import formatar_monitor_consistencia
        linhas = formatar_monitor_consistencia(
            modalidade='Dia de Sorte',
            concurso='1292',
            estado='SP',
            pagina_api=16,
            ultima_api=20,
            registros_recebidos=30,
            total_acumulado=449,
            arquivo='boloes_1292_dia-de-sorte.json',
            tamanho_kb=3000.3,
            pagina_visual=27,
        )
        blob = '\n'.join(linhas)
        self.assertIn('[MODALIDADE] Dia de Sorte', blob)
        self.assertIn('[CONCURSO] 1292', blob)
        self.assertIn('[ESTADO] SP', blob)
        self.assertIn('[API] Página 16/20', blob)
        self.assertIn('[REGISTROS RECEBIDOS] 30', blob)
        self.assertIn('[TOTAL ACUMULADO] 449', blob)
        self.assertIn('[ARQUIVO] boloes_1292_dia-de-sorte.json', blob)
        self.assertIn('3000.3 KB', blob)
        self.assertIn('diverge da paginação da API', blob)


class Teste3EstadosECheckpoint(unittest.TestCase):
    """TESTE 3 e 5 — UFs e checkpoint automático."""

    def test_ufs_de_varios_estados(self):
        from boloes_ciclo_completo import _ufs_dos_boloes
        from boloes_estados import siglas_varredura
        boloes = [
            {'uf': 'SP'}, {'uf': 'BA'}, {'uf': 'RJ'},
            {'uf': 'sp'}, {'uf': ''}, {},
        ]
        self.assertEqual(_ufs_dos_boloes(boloes), ['BA', 'RJ', 'SP'])
        fila = siglas_varredura('SP')
        self.assertEqual(fila[0], 'SP')
        self.assertEqual(len(fila), 27)
        self.assertEqual(fila[-1], 'TO')

    def test_retomada_nao_herda_pagina_de_outra_uf(self):
        from boloes_checkpoint import decidir_pagina_inicial, salvar_checkpoint, STATUS_PAUSADO
        with tempfile.TemporaryDirectory() as tmp:
            ab = 'boloes_3780_lotofacil-independencia'
            salvar_checkpoint(
                tmp, modalidade='lotofacil-independencia',
                modalidade_label='Lotofácil da Independência',
                concurso='3780', arquivo_base=ab,
                pagina_atual=271, total_paginas=845,
                boloes_extraidos=8648, status=STATUS_PAUSADO,
            )
            open(os.path.join(tmp, f'{ab}.json'), 'w', encoding='utf-8').write('[]')
            pagina_ac, _n = decidir_pagina_inicial(tmp, ab, [], pagina_ciclo=0, uf='AC')
            self.assertEqual(pagina_ac, 1)
            sp_boloes = [{'uf': 'SP', 'pagina': p, 'hash_bolao': f'sp{p}-{i}'}
                         for p in range(1, 6) for i in range(20)]
            pagina_sp, n_sp = decidir_pagina_inicial(
                tmp, ab, sp_boloes, pagina_ciclo=5, uf='SP',
            )
            self.assertEqual(n_sp, 100)
            self.assertEqual(pagina_sp, 6)

    def test_normaliza_lista_para_27_ufs(self):
        from boloes_checkpoint_ciclo import (
            STATUS_CONCLUIDO,
            STATUS_PENDENTE,
            STATUS_VAZIO,
            normalizar_ufs_do_ciclo,
            novo_ciclo,
        )
        ciclo = novo_ciclo(
            [
                {'slug': 'dia-de-sorte', 'label': 'Dia de Sorte'},
                {'slug': 'lotofacil-independencia', 'label': 'Lotofácil da Independência'},
            ],
            ['LISTA'],
        )
        ciclo['modalidades']['dia-de-sorte']['status'] = STATUS_CONCLUIDO
        ciclo['modalidades']['dia-de-sorte']['ufs_encontradas'] = 'AC, SP'
        ciclo['modalidades']['dia-de-sorte']['ufs']['LISTA']['status'] = STATUS_CONCLUIDO
        ciclo['modalidades']['dia-de-sorte']['ufs']['LISTA']['boloes'] = 584
        ciclo['modalidades']['lotofacil-independencia']['status'] = STATUS_PENDENTE
        ciclo['modalidades']['lotofacil-independencia']['ufs']['LISTA']['status'] = STATUS_PENDENTE
        ciclo['modalidades']['lotofacil-independencia']['ufs']['LISTA']['boloes'] = 8648
        ciclo['modalidades']['lotofacil-independencia']['ufs']['LISTA']['pagina_atual'] = 271
        normalizar_ufs_do_ciclo(ciclo)
        self.assertNotIn('LISTA', ciclo['modalidades']['lotofacil-independencia']['ufs'])
        self.assertEqual(len(ciclo['modalidades']['lotofacil-independencia']['ufs']), 27)
        self.assertEqual(
            ciclo['modalidades']['lotofacil-independencia']['ufs']['SP']['boloes'], 8648,
        )
        self.assertEqual(
            ciclo['modalidades']['lotofacil-independencia']['ufs']['SP']['pagina_atual'], 271,
        )
        self.assertEqual(
            ciclo['modalidades']['dia-de-sorte']['ufs']['SP']['status'], STATUS_CONCLUIDO,
        )
        self.assertEqual(
            ciclo['modalidades']['dia-de-sorte']['ufs']['AC']['status'], STATUS_CONCLUIDO,
        )
        self.assertEqual(
            ciclo['modalidades']['dia-de-sorte']['ufs']['RJ']['status'], STATUS_VAZIO,
        )

    def test_retomada_ciclo_automatica_continua(self):
        from boloes_checkpoint_ciclo import (
            STATUS_ANDAMENTO,
            STATUS_CICLO_EXEC,
            novo_ciclo,
            resolver_retomada_ciclo_automatica,
            salvar_ciclo,
        )
        with tempfile.TemporaryDirectory() as tmp:
            ciclo = novo_ciclo(
                [{'slug': 'dia-de-sorte', 'label': 'Dia de Sorte'}],
                ['LISTA'],
            )
            ciclo['status'] = STATUS_CICLO_EXEC
            ciclo['modalidades']['dia-de-sorte']['status'] = STATUS_ANDAMENTO
            salvar_ciclo(tmp, ciclo)
            logs = []
            cont, lido = resolver_retomada_ciclo_automatica(tmp, out_fn=logs.append)
            self.assertTrue(cont)
            self.assertIsNotNone(lido)
            self.assertTrue(any('automaticamente' in x.lower() or 'sem confirmação' in x.lower() for x in logs))

    def test_cards_prioridade_preservada(self):
        from boloes_cards_inicio import ordenar_cards_por_prioridade
        cards = [
            {'slug': 'mega-sena', 'label': 'Mega-Sena', 'premio_valor': 70_000_000},
            {'slug': 'dia-de-sorte', 'label': 'Dia de Sorte', 'premio_valor': 100_000},
            {'slug': 'lotofacil-independencia', 'label': 'Lotofácil da Independência', 'premio_valor': 300_000_000},
        ]
        ordem = [c['slug'] for c in ordenar_cards_por_prioridade(cards)]
        self.assertEqual(ordem[0], 'dia-de-sorte')
        self.assertEqual(ordem[1], 'lotofacil-independencia')

    def test_checkpoint_reconhece_json_na_pasta(self):
        from boloes_checkpoint import decidir_pagina_inicial, salvar_checkpoint, STATUS_PAUSADO
        from boloes_consolidar import salvar_json_boloes
        with tempfile.TemporaryDirectory() as tmp:
            ab = 'boloes_3780_lotofacil-independencia'
            boloes = [
                {'hash_bolao': f'h{i}', 'pagina': ((i - 1) // 30) + 1}
                for i in range(1, 91)
            ]
            salvar_json_boloes(os.path.join(tmp, f'{ab}.json'), boloes)
            salvar_checkpoint(
                tmp, modalidade='lotofacil-independencia',
                modalidade_label='Lotofácil da Independência',
                concurso='3780', arquivo_base=ab,
                pagina_atual=3, total_paginas=10,
                boloes_extraidos=90, status=STATUS_PAUSADO,
            )
            pagina, n = decidir_pagina_inicial(tmp, ab, boloes)
            self.assertEqual(n, 90)
            self.assertEqual(pagina, 4)

    def test_checkpoint_confia_arquivo_grande_mesmo_sem_parse(self):
        from boloes_checkpoint import decidir_pagina_inicial, salvar_checkpoint, STATUS_EXECUTANDO
        with tempfile.TemporaryDirectory() as tmp:
            ab = 'boloes_3780_lotofacil-independencia'
            path = os.path.join(tmp, f'{ab}.json')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('[' + ('x' * 3000))
            salvar_checkpoint(
                tmp, modalidade='lotofacil-independencia',
                modalidade_label='Lotofácil da Independência',
                concurso='3780', arquivo_base=ab,
                pagina_atual=181, total_paginas=218,
                boloes_extraidos=5372, status=STATUS_EXECUTANDO,
            )
            pagina, n = decidir_pagina_inicial(tmp, ab, [])
            self.assertEqual(n, 5372)
            self.assertEqual(pagina, 182)

    def test_nao_recomeca_na_pagina_1_se_ciclo_foi_reiniciado(self):
        from boloes_checkpoint import decidir_pagina_inicial, salvar_checkpoint, STATUS_PAUSADO
        from boloes_consolidar import salvar_json_boloes
        with tempfile.TemporaryDirectory() as tmp:
            ab = 'boloes_3780_lotofacil-independencia'
            boloes = [
                {'hash_bolao': f'h{i}', 'pagina': 1 if i <= 8 else 2}
                for i in range(1, 39)
            ]
            salvar_json_boloes(os.path.join(tmp, f'{ab}.json'), boloes)
            salvar_checkpoint(
                tmp, modalidade='lotofacil-independencia',
                modalidade_label='Lotofácil da Independência',
                concurso='3780', arquivo_base=ab,
                pagina_atual=2, boloes_extraidos=38, status=STATUS_PAUSADO,
            )
            pagina, n = decidir_pagina_inicial(tmp, ab, boloes, pagina_ciclo=0)
            self.assertEqual(n, 38)
            self.assertEqual(pagina, 3)

    def test_pagina_incompleta_nao_adianta_checkpoint(self):
        from boloes_checkpoint import ultima_pagina_completa_sequencial
        boloes = [{'pagina': p, 'hash_bolao': f'{p}-{i}'} for p in range(1, 182) for i in range(30)]
        boloes += [{'pagina': 182, 'hash_bolao': f'182-{i}'} for i in range(4)]
        self.assertEqual(ultima_pagina_completa_sequencial(boloes), 181)

    def test_ciclo_nao_pula_pagina_incompleta(self):
        from boloes_checkpoint import decidir_pagina_inicial, ultima_pagina_completa_sequencial
        with tempfile.TemporaryDirectory() as tmp:
            boloes = [{'pagina': p, 'hash_bolao': f'{p}-{i}'} for p in range(1, 182) for i in range(8)]
            boloes += [{'pagina': 182, 'hash_bolao': f'182-{i}'} for i in range(4)]
            self.assertEqual(ultima_pagina_completa_sequencial(boloes), 181)
            pagina, _n = decidir_pagina_inicial(tmp, 'boloes_x', boloes, pagina_ciclo=182)
            self.assertEqual(pagina, 182)

    def test_ciclo_pausa_se_retomada_falha(self):
        src = _fonte('boloes_ciclo_completo.py')
        self.assertIn('abortar_retomada', src)
        self.assertIn('NÃO vai para a próxima modalidade', src)
        from boloes_filtro_loterica import ir_direto_para_pagina_lista
        import inspect
        src = inspect.getsource(ir_direto_para_pagina_lista)
        self.assertIn('_tentar_salto_direto_pagina', src)
        self.assertIn('ALVO ATINGIDO', src)
        src_mod = _fonte('boloes_filtro_loterica.py')
        self.assertIn('Clicando SEGUINTE', src_mod)
        self.assertIn('SALTO DIRETO', src_mod)
        self.assertIn('Salto MENTIU', src_mod)
        self.assertIn('_saltar_digitando_na_barra', src_mod)
        src_api = _fonte('baixar_boloes-API.py')
        self.assertIn('extraindo sem avançar', src_api)
        self.assertIn('Alvo {pagina} atingido — iniciando extração', src_api)
        self.assertIn('[REDE]', src_mod)
        self.assertIn('err_name_not_resolved', src_mod)

    def test_pagina_erro_rede_detecta_dns(self):
        from boloes_filtro_loterica import (
            _excecao_indica_rede,
            _pagina_erro_rede,
            falha_rede_paginacao,
            _marcar_falha_rede,
        )

        class _FakeDns:
            def execute_script(self, *_a, **_k):
                return (
                    'Não consigo chegar a esta página\n'
                    'ERR_NAME_NOT_RESOLVED\n'
                    'O endereço IP do servidor não foi encontrado.'
                )

        class _FakeOk:
            def execute_script(self, *_a, **_k):
                return 'Bolão Caixa\nAnterior 12 Seguinte'

        self.assertTrue(_pagina_erro_rede(_FakeDns()))
        self.assertFalse(_pagina_erro_rede(_FakeOk()))
        self.assertTrue(_excecao_indica_rede(Exception('net::ERR_NAME_NOT_RESOLVED')))
        _marcar_falha_rede(True)
        self.assertTrue(falha_rede_paginacao())
        _marcar_falha_rede(False)
        self.assertFalse(falha_rede_paginacao())


class Teste4RelatoriosExcelConsolidado(unittest.TestCase):
    """TESTES 6, 11, 12 — resumo, Excel e JSON consolidado."""

    def _ciclo_fake(self, pasta: str) -> dict:
        from boloes_checkpoint_ciclo import STATUS_CONCLUIDO, STATUS_ERRO, novo_ciclo
        from boloes_consolidar import salvar_json_boloes

        p1 = os.path.join(pasta, 'boloes_1292_dia-de-sorte.json')
        p2 = os.path.join(pasta, 'boloes_3780_lotofacil-independencia.json')
        salvar_json_boloes(p1, [
            {'hash_bolao': 'a1', 'uf': 'SP', 'modalidade': 'Dia de Sorte', 'concurso': '1292', 'fonte': 'api'},
            {'hash_bolao': 'a2', 'uf': 'BA', 'modalidade': 'Dia de Sorte', 'concurso': '1292', 'fonte': 'api'},
        ])
        salvar_json_boloes(p2, [
            {'hash_bolao': 'b1', 'uf': 'RJ', 'modalidade': 'Lotofácil da Independência', 'concurso': '3780', 'fonte': 'api'},
        ])
        ciclo = novo_ciclo(
            [
                {'slug': 'dia-de-sorte', 'label': 'Dia de Sorte'},
                {'slug': 'lotofacil-independencia', 'label': 'Lotofácil da Independência'},
                {'slug': 'mais-milionaria', 'label': '+Milionária'},
            ],
            ['LISTA'],
        )
        ciclo['inicio'] = '2026-09-07 17:23:00'
        ciclo['fim'] = '2026-09-07 19:10:00'
        ciclo['modalidades']['dia-de-sorte'].update({
            'status': STATUS_CONCLUIDO,
            'concurso': '1292',
            'arquivo_base': 'boloes_1292_dia-de-sorte',
            'ufs_encontradas': 'BA, SP',
            'inicio': '2026-09-07 17:23:00',
            'fim': '2026-09-07 18:10:00',
        })
        ciclo['modalidades']['lotofacil-independencia'].update({
            'status': STATUS_CONCLUIDO,
            'concurso': '3780',
            'arquivo_base': 'boloes_3780_lotofacil-independencia',
            'ufs_encontradas': 'RJ',
            'inicio': '2026-09-07 18:10:00',
            'fim': '2026-09-07 18:50:00',
        })
        ciclo['modalidades']['mais-milionaria'].update({
            'status': STATUS_ERRO,
            'concurso': '388',
            'arquivo_base': '',
            'inicio': '2026-09-07 18:50:00',
            'fim': '2026-09-07 18:51:00',
        })
        ciclo['modalidades']['mais-milionaria']['ufs']['LISTA']['erro'] = 'falha simulada'
        return ciclo

    def test_resumo_modalidade_e_geral(self):
        from boloes_relatorio_execucao import (
            coletar_linhas_modalidades,
            imprimir_relatorio_geral,
            imprimir_resumo_modalidade,
            status_geral_de,
        )
        with tempfile.TemporaryDirectory() as tmp:
            ciclo = self._ciclo_fake(tmp)
            linhas = coletar_linhas_modalidades(ciclo, tmp)
            self.assertEqual(linhas[0]['registros'], 2)
            self.assertIn('SP', linhas[0]['estados'])
            logs = []
            imprimir_resumo_modalidade(linhas[0], out_fn=logs.append)
            self.assertTrue(any('MODALIDADE CONCLUÍDA' in x for x in logs))
            logs = []
            st = status_geral_de(linhas)
            self.assertEqual(st, 'CONCLUÍDO COM OCORRÊNCIAS')
            imprimir_relatorio_geral(ciclo, linhas, status_geral=st, out_fn=logs.append)
            blob = '\n'.join(logs)
            self.assertIn('RELATÓRIO FINAL DA EXTRAÇÃO', blob)
            self.assertIn('Dia de Sorte', blob)
            self.assertIn('+Milionária', blob)
            self.assertIn('CONCLUÍDO COM OCORRÊNCIAS', blob)

    def test_excel_profissional(self):
        from openpyxl import load_workbook
        from boloes_relatorio_execucao import coletar_linhas_modalidades, gerar_excel_relatorio
        with tempfile.TemporaryDirectory() as tmp:
            ciclo = self._ciclo_fake(tmp)
            linhas = coletar_linhas_modalidades(ciclo, tmp)
            path = gerar_excel_relatorio(
                tmp, ciclo, linhas, agora=datetime(2026, 9, 7, 19, 10),
            )
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(os.path.basename(path).startswith('relatorio_extracao_2026-09-07_19-10'))
            wb = load_workbook(path)
            self.assertEqual(wb.sheetnames, ['Resumo Geral', 'Estados', 'Detalhamento'])
            ws = wb['Resumo Geral']
            self.assertEqual(ws['A3'].value, 'Modalidade')
            self.assertEqual(ws.auto_filter.ref[:2], 'A3')
            self.assertEqual(ws.freeze_panes, 'A4')
            self.assertGreaterEqual(ws.column_dimensions['A'].width, 12)
            ufs = [r[2] for r in wb['Estados'].iter_rows(min_row=4, values_only=True) if r[2]]
            self.assertIn('SP', ufs)
            self.assertIn('BA', ufs)

    def test_json_consolidado_preserva_individuais(self):
        from boloes_consolidar import carregar_json_boloes
        from boloes_relatorio_execucao import coletar_linhas_modalidades, gerar_json_consolidado
        with tempfile.TemporaryDirectory() as tmp:
            ciclo = self._ciclo_fake(tmp)
            linhas = coletar_linhas_modalidades(ciclo, tmp)
            path, n = gerar_json_consolidado(tmp, linhas, agora=datetime(2026, 9, 7))
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(os.path.basename(path), 'boloes_consolidado_2026-09-07.json')
            self.assertEqual(n, 3)
            self.assertTrue(os.path.isfile(os.path.join(tmp, 'boloes_1292_dia-de-sorte.json')))
            self.assertTrue(os.path.isfile(os.path.join(tmp, 'boloes_3780_lotofacil-independencia.json')))
            cons = carregar_json_boloes(path)
            self.assertEqual(len(cons), 3)
            self.assertTrue(all(c.get('origem') for c in cons))
            self.assertTrue(all(c.get('origem_arquivo') for c in cons))
            self.assertTrue(all(c.get('modalidade') for c in cons))
            self.assertTrue(all(c.get('concurso') or c.get('uf') for c in cons))


class Teste5ErroNaoDerrubaCiclo(unittest.TestCase):
    """TESTE 13 — falha em uma modalidade não encerra as demais."""

    def test_continuar_apos_falha_mensagens(self):
        from boloes_ciclo_completo import _continuar_apos_falha
        logs = []
        _continuar_apos_falha('+Milionária', logs.append, 'timeout')
        blob = '\n'.join(logs)
        self.assertIn('[ERRO] +Milionária', blob)
        self.assertIn('[AVISO] Modalidade não concluída.', blob)
        self.assertIn('[INFO] Continuando para a próxima modalidade.', blob)

    def test_status_geral_com_ocorrencias(self):
        from boloes_relatorio_execucao import status_geral_de
        linhas = [
            {'status': 'CONCLUÍDO'},
            {'status': 'ERRO'},
            {'status': 'CONCLUÍDO'},
        ]
        self.assertEqual(status_geral_de(linhas), 'CONCLUÍDO COM OCORRÊNCIAS')
        self.assertEqual(status_geral_de([{'status': 'CONCLUÍDO'}]), 'CONCLUÍDO')


class Teste6Avisos(unittest.TestCase):
    """TESTES 9 e 10 — som e voz não bloqueiam e não levantam exceção."""

    def test_avisos_nao_bloqueiam(self):
        from boloes_avisos import (
            aviso_disponivel,
            aviso_sonoro,
            aviso_voz,
            avisar_modalidade_concluida,
            avisar_nova_modalidade,
        )
        info = aviso_disponivel()
        self.assertIn('winsound', info)
        logs = []
        aviso_sonoro('ok')
        aviso_voz('Teste de voz da extração.')
        avisar_modalidade_concluida('Dia de Sorte', out_fn=logs.append)
        avisar_nova_modalidade('Lotofácil', out_fn=logs.append)
        self.assertTrue(any('MODALIDADE CONCLUÍDA' in x for x in logs))
        self.assertTrue(any('NOVA MODALIDADE' in x for x in logs))


class Teste7JsonTempoRealECheckpointTexto(unittest.TestCase):
    """TESTE 4 — persistência incremental ainda existe no extrator."""

    def test_persistencia_incremental_presente(self):
        src = _fonte('baixar_boloes-API.py')
        self.assertIn('def _persistir_json_pagina', src)
        self.assertIn('[CHECKPOINT] Página', src)
        self.assertIn('próximo retomaria', src)


def imprimir_analise_fluxo() -> None:
    linhas = [
        '=' * 64,
        '  ANALISE DO FLUXO ATUAL (antes/depois da evolucao)',
        '=' * 64,
        '  1. Arquivo principal : script/baixar_boloes-API.py  (menu [C]/[1]/[2])',
        '  2. Extracao          : _loop_extracao_paginas / _extrair_como_opcao_1',
        '  3. Paginacao         : API paginaAtual/ultimaPagina + botao Seguinte',
        '                         UI (barra Anterior N Seguinte) e so diagnostico',
        '  4. Cards             : boloes_cards_inicio.listar_cards_modalidades',
        '  5. Selecao           : ordenar_cards_por_prioridade (Dia de Sorte 1o)',
        '  6. Estados           : 27 UFs (SP primeiro; so para no ultimo estado)',
        '  7. JSON              : salvar_json_boloes atomico, 1 arquivo/modalidade',
        '  8. Checkpoint        : _checkpoint_extracao.json + _checkpoint_ciclo.json',
        '  9. Transicao         : ciclo fecha modalidade -> hub -> proximo card',
        ' 10. Confirmacao       : REMOVIDA do [C] (sem SIM / ENTER / input)',
        '  Fonte da extracao    : API + registros recebidos + JSON gravado',
        '  Paginacao visual     : pode divergir (ex. API 16/20 vs UI 27) - NAO e erro',
        '=' * 64,
    ]
    for linha in linhas:
        print(linha)


if __name__ == '__main__':
    imprimir_analise_fluxo()
    unittest.main(verbosity=2)
