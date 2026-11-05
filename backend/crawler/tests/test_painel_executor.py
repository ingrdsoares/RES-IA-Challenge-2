import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from backend.crawler.painel.executor import Executor, RodadaAtiva, _encerrar_arvore, comando_sonda, ultimas_execucoes
from backend.crawler.painel.frentes import Frente
from backend.crawler.painel.sonda import SAIDA_EXCECAO

FRENTES = (Frente('a', 'pasta-a'), Frente('b', 'pasta-b'))
PRE = '''
import json, os, pathlib, subprocess, sys, time
def ev(tipo, url, **k):
    with open(os.environ['PAINEL_EVENTOS'], 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': 'x', 'modulo': MODULO, 'tipo': tipo, 'url': url, **k}) + '\\n')
def espera(p):
    fim = time.time() + 20
    while not os.path.exists(p):
        if time.time() > fim:
            sys.exit(99)
        time.sleep(0.01)
'''


def catalogo(*pastas, origens=(), situacao=None, pendencias=0):
    snapshots = [{'diretorio': f'{p}/{i}', 'origem': o, 'coletado_em': '2026-01-01'}
                 for p in pastas for i, o in enumerate(origens or [None])]
    cobertura = [{'pasta': p, 'snapshots': len(origens or [None]), 'situacao': situacao,
                  'erros_manifesto_mais_recente': pendencias, 'pendencias_extracao': 0} for p in pastas]
    return {'snapshots': snapshots, 'cobertura_frentes': cobertura}


def vivo(pid: int) -> bool:
    if os.name == 'nt':
        saida = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout
        return str(pid) in saida
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.tmp = Path(self._dir.name)
        self.painel = self.tmp / 'painel'
        self.data = self.tmp / 'data'
        self.ordem = self.tmp / 'ordem.txt'
        self.solta = self.tmp / 'solta'
        self.scripts = {}
        self.catalogo_final = catalogo('pasta-a', 'pasta-b')

    def script(self, modulo, corpo='', saida=0):
        self.scripts[modulo] = (f'{PRE}\nMODULO = {modulo!r}\n'
                                f'with open({str(self.ordem)!r}, "a", encoding="utf-8") as f:\n'
                                f'    f.write(MODULO + "\\n")\n{corpo}\nsys.exit({saida})\n')

    def comando(self, modulo):
        if modulo == 'catalogo' and modulo not in self.scripts:
            destino = self.data / 'catalogo' / 'catalogo.json'
            self.script('catalogo', f'd = pathlib.Path({str(destino)!r}); d.parent.mkdir(parents=True, exist_ok=True)\n'
                                    f'd.write_text(json.dumps({self.catalogo_final!r}), encoding="utf-8")')
        return [sys.executable, '-c', self.scripts[modulo]]

    def executor(self, frentes=FRENTES):
        e = Executor(self.painel, self.data, frentes=frentes, comando=self.comando, tempo_limite=0.5, intervalo=0.02)
        self.addCleanup(self._encerrar, e)
        return e

    def _encerrar(self, e):
        self.solta.touch()
        e.parar()
        e.aguardar(30)

    def gravar_catalogo(self, dados):
        destino = self.data / 'catalogo' / 'catalogo.json'
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados), encoding='utf-8')

    def gravar_historico(self, *linhas):
        self.painel.mkdir(parents=True, exist_ok=True)
        (self.painel / 'historico.jsonl').write_text(''.join(linhas), encoding='utf-8')

    def esperar(self, condicao, timeout=15):
        fim = time.monotonic() + timeout
        while time.monotonic() < fim:
            if condicao():
                return
            time.sleep(0.01)
        self.fail('condição não atendida a tempo')

    def rodada(self, e, selecionadas=('a', 'b'), refazer=(), finais=()):
        e.iniciar(set(selecionadas), set(refazer), set(finais))
        e.aguardar(30)
        return e.estado()

    def ordem_rodada(self):
        return self.ordem.read_text(encoding='utf-8').split()

    @staticmethod
    def linha(estado, modulo):
        return next(f for f in estado['frentes'] if f['modulo'] == modulo)

    def test_roda_em_ordem_e_atualiza_catalogo_no_fim(self):
        self.script('a')
        self.script('b')
        estado = self.rodada(self.executor())
        self.assertEqual(self.ordem_rodada(), ['a', 'b', 'catalogo'])
        self.assertFalse(estado['rodando'])
        self.assertEqual(estado['etapa'], 'ocioso')
        self.assertEqual((estado['feitas'], estado['total']), (2, 2))
        self.assertIsNotNone(estado['fim'])
        self.assertEqual(self.linha(estado, 'a')['estado'], 'concluida')
        self.assertEqual(self.linha(estado, 'a')['itens'], 1)  # recarregado do catálogo novo
        ultima = ultimas_execucoes(self.painel / 'historico.jsonl')['a']
        self.assertEqual(ultima['resultado'], 'concluida')
        self.assertEqual(ultima['requisicoes'], 0)
        self.assertFalse(ultima['forcada'])
        self.assertGreater(ultima['duracao_s'], 0)

    def test_falha_nao_interrompe_as_seguintes(self):
        self.script('a', saida=1)
        self.script('b')
        estado = self.rodada(self.executor())
        self.assertEqual(self.linha(estado, 'a')['estado'], 'erro')
        self.assertEqual(self.linha(estado, 'a')['saida'], 1)
        self.assertEqual(self.linha(estado, 'b')['estado'], 'concluida')

    def test_excecao_nao_vira_parcial(self):
        self.catalogo_final = catalogo('pasta-a', situacao='coletada_com_pendencias', pendencias=1)
        self.script('a', saida=SAIDA_EXCECAO)
        estado = self.rodada(self.executor(), ['a'])
        self.assertEqual(self.linha(estado, 'a')['estado'], 'erro')

    def test_parcial_vem_do_catalogo_mesmo_com_saida_1(self):
        self.catalogo_final = catalogo('pasta-a', situacao='coletada_com_pendencias', pendencias=3)
        self.script('a', saida=1)
        estado = self.rodada(self.executor(), ['a'])
        self.assertEqual(self.linha(estado, 'a')['estado'], 'parcial')
        self.assertEqual(self.linha(estado, 'a')['pendencias'], 3)
        self.assertIsNone(estado['aviso'])

    def test_catalogo_falha_mostra_aviso_e_classifica_pelo_processo(self):
        self.gravar_catalogo(catalogo('pasta-a', situacao='coletada_com_pendencias', pendencias=3))
        self.script('a')
        self.script('b', saida=1)
        self.script('catalogo', saida=1)
        estado = self.rodada(self.executor(), refazer=['a'])
        self.assertEqual(estado['aviso'], 'Não foi possível atualizar o catálogo; pendências podem estar desatualizadas')
        self.assertEqual(self.linha(estado, 'a')['estado'], 'concluida')
        self.assertEqual(self.linha(estado, 'b')['estado'], 'erro')

    def test_eventos_alimentam_linha(self):
        origens = ['https://x.gov.br/1', 'https://x.gov.br/2']
        self.gravar_catalogo(catalogo('pasta-a', origens=origens))
        self.catalogo_final = catalogo('pasta-a', origens=origens)
        self.script('a', f"""
ev('resposta', 'https://x.gov.br/0', url_final='https://x.gov.br/1', status=200, bytes=5, ms=1)
ev('resposta', 'https://y.gov.br/z', url_final='https://y.gov.br/z', status=200, bytes=7, ms=1)
with open(os.environ['PAINEL_EVENTOS'], 'a') as f:
    f.write('lixo\\n{{"cortada')
espera({str(self.solta)!r})""")
        e = self.executor()
        e.iniciar({'a'}, {'a'}, set())
        self.esperar(lambda: self.linha(e.estado(), 'a')['requisicoes'] == 2)
        estado = e.estado()
        json.dumps(estado)  # o servidor serializa o estado
        linha = self.linha(estado, 'a')
        self.assertEqual((linha['feitos'], linha['total'], linha['fracao'], linha['base']), (1, 2, 0.5, 2))
        self.assertEqual(linha['bytes'], 12)
        self.assertEqual(linha['bytes_item'], 7)
        self.assertEqual(linha['item_atual'], 'https://y.gov.br/z')
        self.assertEqual(linha['fonte'], 'y.gov.br')
        self.assertEqual(linha['estado'], 'coletando')
        self.assertEqual(estado['itens'], 1)
        self.solta.touch()
        e.aguardar(30)
        self.assertEqual(self.linha(e.estado(), 'a')['fonte'], 'x.gov.br')  # parada: predominante no catálogo

    def test_base_1_conta_requisicoes_na_linha_e_itens_no_topo(self):
        self.gravar_catalogo(catalogo('pasta-a', origens=['https://x.gov.br/1', 'https://x.gov.br/2']))
        self.gravar_historico(json.dumps({'evento': 'fim', 'modulo': 'a', 'resultado': 'concluida', 'requisicoes': 4,
                                          'duracao_s': 100.0}) + '\n')
        self.script('a', f"""
ev('resposta', 'https://y.gov.br/1', url_final='https://y.gov.br/1', status=200, bytes=1, ms=1)
ev('resposta', 'https://y.gov.br/2', url_final='https://y.gov.br/2', status=200, bytes=1, ms=1)
espera({str(self.solta)!r})""")
        e = self.executor()
        e.iniciar({'a'}, {'a'}, set())
        self.esperar(lambda: self.linha(e.estado(), 'a')['requisicoes'] == 2)
        estado = e.estado()
        linha = self.linha(estado, 'a')
        self.assertEqual((linha['feitos'], linha['total'], linha['fracao'], linha['base']), (2, 4, 0.5, 1))
        self.assertEqual(estado['itens'], 0)  # requisição não é item
        self.assertGreater(linha['restante_s'], 0)
        self.assertEqual(estado['restante_s'], linha['restante_s'])

    def test_estimativa_soma_e_conta_frentes_sem_base(self):
        self.gravar_catalogo({'cobertura_frentes': [{'pasta': 'pasta-b', 'snapshots': 2}]})
        self.gravar_historico(json.dumps({'evento': 'fim', 'modulo': 'a', 'resultado': 'concluida', 'duracao_s': 500.0}) + '\n')
        self.script('a', f'espera({str(self.solta)!r})')
        self.script('b')
        self.script('c')
        e = self.executor((Frente('a', 'pasta-a'), Frente('b', 'pasta-b'), Frente('c', 'pasta-c')))
        e.iniciar({'a', 'b', 'c'}, {'b'}, set())
        estado = e.estado()
        self.assertEqual(estado['sem_estimativa'], 2)  # b e c na fila, ainda sem s/item
        self.assertGreater(estado['restante_s'], 400)

    def test_s_por_item_vem_das_finalizadas_da_rodada(self):
        self.gravar_catalogo(catalogo('pasta-a', 'pasta-b'))
        self.script('a')
        self.script('b', f'espera({str(self.solta)!r})')
        e = self.executor()
        e.iniciar({'a', 'b'}, {'a', 'b'}, set())
        self.esperar(lambda: self.linha(e.estado(), 'b')['estado'] == 'coletando')
        estado = e.estado()
        self.assertEqual(estado['feitas'], 1)
        self.assertEqual(self.linha(estado, 'a')['estado'], 'verificando')
        self.assertEqual(estado['sem_estimativa'], 0)
        self.assertEqual(estado['itens'], 1)
        self.assertGreater(self.linha(estado, 'b')['restante_s'], 0)

    def test_parada_suave_nao_inicia_seguintes(self):
        self.script('a', "espera(os.environ['PAINEL_PARAR'])")
        self.script('b')
        e = self.executor()
        e.iniciar({'a', 'b'}, set(), set())
        self.esperar(self.ordem.exists)
        e.parar()
        self.assertEqual(self.linha(e.estado(), 'b')['estado'], 'nao_iniciada')
        e.aguardar(30)
        estado = e.estado()
        self.assertEqual(self.linha(estado, 'a')['estado'], 'interrompida')
        self.assertFalse(self.linha(estado, 'a')['forcada'])
        self.assertEqual(self.linha(estado, 'b')['estado'], 'nao_iniciada')
        self.assertEqual(self.ordem_rodada(), ['a', 'catalogo'])
        ultimas = ultimas_execucoes(self.painel / 'historico.jsonl')
        self.assertEqual(ultimas['a']['resultado'], 'interrompida')
        self.assertNotIn('b', ultimas)

    def test_parada_forcada_encerra_arvore(self):
        arquivo_pid = self.tmp / 'pid'
        filho = "import os, pathlib, time; pathlib.Path(os.environ['ALVO']).write_text(str(os.getpid())); time.sleep(30)"
        self.script('a', f"""
os.environ['ALVO'] = {str(arquivo_pid)!r}
subprocess.Popen([sys.executable, '-c', {filho!r}])
time.sleep(30)""")
        self.script('b')
        e = self.executor()
        e.iniciar({'a', 'b'}, set(), set())
        self.esperar(lambda: arquivo_pid.exists() and arquivo_pid.read_text())
        pid = int(arquivo_pid.read_text())
        self.assertTrue(vivo(pid))
        e.parar()
        self.assertEqual(self.linha(e.estado(), 'a')['estado'], 'parando')
        self.assertEqual(e.estado()['etapa'], 'parando')
        e.aguardar(30)
        linha = self.linha(e.estado(), 'a')
        self.assertEqual(linha['estado'], 'interrompida')
        self.assertTrue(linha['forcada'])
        self.assertEqual(self.ordem_rodada(), ['a', 'catalogo'])
        self.assertTrue(ultimas_execucoes(self.painel / 'historico.jsonl')['a']['forcada'])
        self.esperar(lambda: not vivo(pid))

    def test_forcar_encerra_filho_e_neto_sem_esperar_o_prazo(self):
        arquivo_pid = self.tmp / 'pid'
        filho = "import os, pathlib, time; pathlib.Path(os.environ['ALVO']).write_text(str(os.getpid())); time.sleep(30)"
        self.script('a', f"""
os.environ['ALVO'] = {str(arquivo_pid)!r}
subprocess.Popen([sys.executable, '-c', {filho!r}])
time.sleep(30)""")
        self.script('b')
        e = Executor(self.painel, self.data, frentes=FRENTES, comando=self.comando, tempo_limite=60, intervalo=0.02)
        self.addCleanup(self._encerrar, e)
        e.iniciar({'a', 'b'}, set(), set())
        self.esperar(lambda: arquivo_pid.exists() and arquivo_pid.read_text())
        pid = int(arquivo_pid.read_text())
        e.forcar()
        e.aguardar(10)
        self.assertFalse(e.estado()['rodando'])
        linha = self.linha(e.estado(), 'a')
        self.assertEqual((linha['estado'], linha['forcada']), ('interrompida', True))
        self.assertEqual(self.linha(e.estado(), 'b')['estado'], 'nao_iniciada')
        self.esperar(lambda: not vivo(pid))

    def test_forcar_durante_catalogo_encerra_a_rodada(self):
        self.script('a')
        self.script('catalogo', f"espera({str(self.solta)!r})")
        self.script('estatisticas')
        e = Executor(self.painel, self.data, frentes=FRENTES, comando=self.comando, tempo_limite=60, intervalo=0.02)
        self.addCleanup(self._encerrar, e)
        e.iniciar({'a'}, set(), {'estatisticas'})
        self.esperar(lambda: e.estado()['etapa'] == 'catalogo')
        e.forcar()
        e.aguardar(10)
        estado = e.estado()
        self.assertFalse(estado['rodando'])
        self.assertEqual(estado['finais'][0]['estado'], 'nao_iniciada')
        self.assertNotIn('estatisticas', self.ordem_rodada())

    def test_forcar_nao_lanca_catalogo_nem_finais(self):
        self.script('a', "espera(os.environ['PAINEL_PARAR'])")
        self.script('estatisticas')
        e = Executor(self.painel, self.data, frentes=FRENTES, comando=self.comando, tempo_limite=60, intervalo=0.02)
        self.addCleanup(self._encerrar, e)
        e.iniciar({'a'}, set(), {'estatisticas'})
        self.esperar(self.ordem.exists)
        e.forcar()
        e.aguardar(10)
        estado = e.estado()
        self.assertEqual(self.ordem_rodada(), ['a'])
        self.assertIsNone(estado['aviso'])
        self.assertEqual(estado['finais'][0]['estado'], 'nao_iniciada')
        self.assertEqual(self.linha(estado, 'a')['estado'], 'interrompida')

    def test_encerrar_arvore_sobrevive_a_ctrl_c_no_taskkill(self):
        alvo = 'subprocess.run' if os.name == 'nt' else 'os.killpg'
        for efeitos in ([KeyboardInterrupt, None], [KeyboardInterrupt, KeyboardInterrupt]):
            with self.subTest(efeitos=efeitos), mock.patch(alvo, side_effect=efeitos) as encerrar:
                proc = mock.Mock(pid=1)
                _encerrar_arvore(proc)
                self.assertEqual(encerrar.call_count, 2)
                proc.kill.assert_called_once_with()

    def test_forcar_sem_rodada_nao_faz_nada(self):
        e = self.executor()
        e.forcar()
        self.assertFalse(e.estado()['rodando'])

    def test_parar_durante_catalogo_nao_o_encerra_e_cancela_finais(self):
        terminou = self.tmp / 'catalogo-terminou'
        self.script('a')
        self.script('catalogo', f"espera({str(self.solta)!r})\npathlib.Path({str(terminou)!r}).touch()")
        self.script('estatisticas')
        e = self.executor()
        e.iniciar({'a'}, set(), {'estatisticas'})
        self.esperar(lambda: e.estado()['etapa'] == 'catalogo')
        e.parar()
        self.assertEqual(e.estado()['etapa'], 'catalogo')
        time.sleep(0.7)  # passa do tempo_limite: o catálogo não pode ser forçado
        self.solta.touch()
        e.aguardar(30)
        self.assertTrue(terminou.exists())
        self.assertEqual(e.estado()['finais'][0]['estado'], 'nao_iniciada')
        self.assertNotIn('estatisticas', self.ordem_rodada())

    def test_historico_e_interrupcao_por_queda(self):
        self.gravar_catalogo(catalogo('pasta-a'))
        self.catalogo_final = catalogo('pasta-a')
        self.gravar_historico(
            json.dumps({'evento': 'fim', 'modulo': 'a', 'resultado': 'concluida', 'requisicoes': 9}) + '\n',
            json.dumps({'evento': 'inicio', 'modulo': 'a', 't': 'x'}) + '\n',
            '{"mod')
        historico = self.painel / 'historico.jsonl'
        self.assertEqual(ultimas_execucoes(historico)['a'], {'resultado': 'interrompida'})
        self.assertEqual(ultimas_execucoes(self.tmp / 'nao-existe'), {})
        self.script('a')
        e = self.executor()
        self.assertEqual(self.linha(e.estado(), 'a')['estado'], 'interrompida')
        self.assertEqual(e.previa({'a'}, set())[0]['acao'], 'rodar')
        estado = self.rodada(e, ['a'])
        self.assertEqual(self.linha(estado, 'a')['estado'], 'concluida')
        self.assertEqual(ultimas_execucoes(historico)['a']['resultado'], 'concluida')
        self.assertIn('{"mod\n', historico.read_text(encoding='utf-8'))  # linha nova não cola na cortada

    def test_execucao_sem_requisicoes_nao_e_base_1(self):
        self.gravar_catalogo(catalogo('pasta-a'))
        self.gravar_historico(json.dumps({'evento': 'fim', 'modulo': 'a', 'resultado': 'concluida', 'requisicoes': 0}) + '\n')
        self.script('a', f'espera({str(self.solta)!r})')
        e = self.executor()
        e.iniciar({'a'}, {'a'}, set())
        self.esperar(self.ordem.exists)
        linha = self.linha(e.estado(), 'a')
        self.assertEqual(linha['estado'], 'coletando')
        self.assertIsNone(linha['fracao'])
        self.assertIsNone(linha['base'])
        self.assertIsNone(linha['total'])

    def test_saida_com_acentos_em_utf8(self):
        self.script('a', "print('ação €')")
        e = self.executor()
        estado = self.rodada(e, ['a'])
        self.assertEqual(self.linha(estado, 'a')['saida'], 0)
        self.assertIn('ação €', e.log('a'))
        self.assertIn('ação €', self.executor().log('a'))  # outro executor acha o log da última rodada

    def test_log_recusa_modulo_desconhecido(self):
        self.assertEqual(self.executor().log('../../segredo'), '')

    def test_segunda_rodada_recusada(self):
        self.script('a', f'espera({str(self.solta)!r})')
        e = self.executor()
        e.iniciar({'a'}, set(), set())
        with self.assertRaises(RodadaAtiva):
            e.iniciar({'a'}, set(), set())
        with self.assertRaises(RodadaAtiva):
            self.executor().iniciar({'a'}, set(), set())
        self.assertTrue(e.estado()['rodando'])

    def test_trava_liberada_ao_terminar(self):
        self.script('a')
        e = self.executor()
        self.rodada(e, ['a'], ['a'])
        self.rodada(e, ['a'], ['a'])
        self.rodada(self.executor(), ['a'], ['a'])
        self.assertEqual(self.ordem_rodada().count('a'), 3)

    def test_etapas_finais_rodam_depois_do_catalogo(self):
        self.script('a')
        self.script('estatisticas')
        self.script('sumarizacao', saida=1)
        estado = self.rodada(self.executor(), ['a'], finais=['sumarizacao', 'estatisticas'])
        self.assertEqual(self.ordem_rodada(), ['a', 'catalogo', 'estatisticas', 'sumarizacao'])
        finais = {f['modulo']: f for f in estado['finais']}
        self.assertEqual(finais['estatisticas']['estado'], 'concluida')
        self.assertEqual(finais['sumarizacao']['estado'], 'erro')
        self.assertEqual(finais['sumarizacao']['saida'], 1)
        self.assertIsNotNone(finais['sumarizacao']['fim'])

    def test_pulada_e_panorama(self):
        self.gravar_catalogo({'snapshots': [], 'cobertura_frentes': [
            {'pasta': 'pasta-a', 'snapshots': 2},
            {'pasta': 'pasta-c', 'snapshots': 1, 'situacao': 'coletada_com_pendencias'}]})
        e = self.executor((Frente('a', 'pasta-a'), Frente('b', 'pasta-b'), Frente('c', 'pasta-c')))
        estado = e.estado()
        self.assertEqual([f['estado'] for f in estado['frentes']], ['ja_coletada', 'sem_dados', 'parcial'])
        self.assertEqual(estado['etapa'], 'ocioso')
        self.assertIsNone(estado['restante_s'])
        estado = self.rodada(e, ['a'])  # só pulada: nada roda, nem o catálogo
        self.assertFalse(self.ordem.exists())
        self.assertEqual(self.linha(estado, 'a')['estado'], 'pulada')
        self.assertEqual(self.linha(estado, 'a')['itens'], 2)
        self.assertEqual((estado['feitas'], estado['total']), (0, 0))

    def test_parar_durante_etapa_final_interrompe_e_pula_as_demais(self):
        self.script('a')
        self.script('estatisticas', "espera(os.environ['PAINEL_PARAR'])")
        self.script('sumarizacao')
        e = self.executor()
        e.iniciar({'a'}, set(), {'estatisticas', 'sumarizacao'})
        self.esperar(lambda: self.ordem.exists() and 'estatisticas' in self.ordem_rodada())
        self.assertEqual(e.estado()['etapa'], 'finais')
        e.parar()
        e.aguardar(30)
        self.assertEqual([f['estado'] for f in e.estado()['finais']], ['interrompida', 'nao_iniciada'])
        self.assertEqual(self.linha(e.estado(), 'a')['estado'], 'concluida')  # terminou antes de Parar

    def test_sonda_de_verdade_com_modulo_inexistente_vira_erro(self):
        def comando(modulo):
            return self.comando(modulo) if modulo == 'catalogo' else comando_sonda(modulo)
        e = Executor(self.painel, self.data, frentes=(Frente('nao_existe_xyz', 'pasta-a'),), comando=comando,
                     tempo_limite=0.5, intervalo=0.02)
        estado = self.rodada(e, ['nao_existe_xyz'])
        self.assertEqual(self.linha(estado, 'nao_existe_xyz')['saida'], SAIDA_EXCECAO)
        self.assertEqual(self.linha(estado, 'nao_existe_xyz')['estado'], 'erro')
        self.assertIn('nao_existe_xyz', e.log('nao_existe_xyz'))

    def test_url_invalida_em_evento_nao_derruba_a_rodada(self):
        self.script('a', f"""
ev('pedido', 'http://[bad')
ev('resposta', 'http://[bad', url_final='http://[bad', status=200, bytes=3, ms=1)
ev('resposta', 'https://y.gov.br/1', url_final=['nao', 'hashavel'], status=200, bytes='x', ms=1)
ev('resposta', 'https://y.gov.br/2', url_final='https://y.gov.br/2', status=200, bytes=4, ms=1)
espera({str(self.solta)!r})""")
        e = self.executor()
        e.iniciar({'a'}, set(), set())
        self.esperar(lambda: self.linha(e.estado(), 'a')['fonte'] == 'y.gov.br')
        self.assertTrue(e.estado()['rodando'])
        self.assertEqual(self.linha(e.estado(), 'a')['estado'], 'coletando')
        self.solta.touch()
        e.aguardar(30)
        estado = e.estado()
        self.assertIsNone(estado['aviso'])
        self.assertEqual(self.linha(estado, 'a')['estado'], 'concluida')
        self.assertEqual(self.linha(estado, 'a')['bytes'], 7)

    def test_falha_interna_nao_deixa_processo_vivo(self):
        arquivo_pid = self.tmp / 'pid'
        self.script('a', f"""
pathlib.Path({str(arquivo_pid)!r}).write_text(str(os.getpid()))
time.sleep(30)""")
        self.script('b')
        e = self.executor()

        def falha(_modulo):
            if arquivo_pid.exists() and arquivo_pid.read_text():
                raise RuntimeError('quebrou')
        e._ler_eventos = falha
        with contextlib.redirect_stderr(io.StringIO()):  # a falha interna imprime o traceback de propósito
            e.iniciar({'a', 'b'}, set(), set())
            e.aguardar(30)
        estado = e.estado()
        self.assertFalse(estado['rodando'])
        self.assertIn('quebrou', estado['aviso'])
        self.assertFalse(vivo(int(arquivo_pid.read_text())))
        self.assertEqual(self.linha(estado, 'a')['estado'], 'interrompida')
        self.assertEqual(self.linha(estado, 'b')['estado'], 'nao_iniciada')

    def test_execucao_truncada_nao_serve_de_base_nem_estimativa(self):
        for resultado in ('interrompida', 'erro'):
            with self.subTest(resultado=resultado):
                self.solta.unlink(missing_ok=True)
                self.ordem.unlink(missing_ok=True)
                self.gravar_historico(json.dumps({'evento': 'fim', 'modulo': 'a', 'resultado': resultado,
                                                  'requisicoes': 2, 'duracao_s': 3.0}) + '\n')
                self.script('a', f"""
ev('resposta', 'https://y.gov.br/1', url_final='https://y.gov.br/1', status=200, bytes=1, ms=1)
ev('resposta', 'https://y.gov.br/2', url_final='https://y.gov.br/2', status=200, bytes=1, ms=1)
espera({str(self.solta)!r})""")
                e = self.executor()
                e.iniciar({'a'}, set(), set())
                self.esperar(lambda: self.linha(e.estado(), 'a')['requisicoes'] == 2)
                estado = e.estado()
                linha = self.linha(estado, 'a')
                self.assertEqual((linha['fracao'], linha['base'], linha['total']), (None, None, None))
                self.assertIsNone(linha['restante_s'])
                self.assertEqual(estado['sem_estimativa'], 1)
                self.solta.touch()
                e.aguardar(30)

    def test_execucao_parcial_serve_de_base(self):
        self.gravar_historico(json.dumps({'evento': 'fim', 'modulo': 'a', 'resultado': 'parcial',
                                          'requisicoes': 4, 'duracao_s': 100.0}) + '\n')
        self.script('a', f'espera({str(self.solta)!r})')
        e = self.executor()
        e.iniciar({'a'}, set(), set())
        self.esperar(self.ordem.exists)
        linha = self.linha(e.estado(), 'a')
        self.assertEqual((linha['total'], linha['base']), (4, 1))
        self.assertGreater(linha['restante_s'], 0)

    def test_queda_depois_da_primeira_frente_preserva_o_resultado_dela(self):
        self.gravar_catalogo(catalogo('pasta-a', 'pasta-b'))
        self.script('a')
        self.script('b', f'espera({str(self.solta)!r})')
        e = self.executor()
        e.iniciar({'a', 'b'}, {'a', 'b'}, set())
        self.esperar(lambda: self.linha(e.estado(), 'b')['estado'] == 'coletando')
        # o histórico neste instante é o que sobraria de uma queda da máquina
        ultimas = ultimas_execucoes(self.painel / 'historico.jsonl')
        self.assertEqual(ultimas['a']['resultado'], 'concluida')
        self.assertEqual(ultimas['b'], {'resultado': 'interrompida'})
        self.assertEqual(e.previa({'a'}, set())[0]['acao'], 'pular')

    def fins_no_historico(self, modulo):
        linhas = (json.loads(b) for b in (self.painel / 'historico.jsonl').read_text(encoding='utf-8').splitlines())
        return [x['resultado'] for x in linhas if x['evento'] == 'fim' and x['modulo'] == modulo]

    def test_catalogo_corrige_resultado_do_processo_no_historico(self):
        self.catalogo_final = catalogo('pasta-a', situacao='coletada_com_pendencias', pendencias=3)
        self.script('a', saida=1)
        self.rodada(self.executor(), ['a'])
        self.assertEqual(self.fins_no_historico('a'), ['erro', 'parcial'])
        self.assertEqual(ultimas_execucoes(self.painel / 'historico.jsonl')['a']['resultado'], 'parcial')

    def test_resultado_igual_nao_repete_linha_no_historico(self):
        self.script('a')
        self.rodada(self.executor(), ['a'])
        self.assertEqual(self.fins_no_historico('a'), ['concluida'])

    def test_etapa_final_roda_sem_frente_executada_e_sem_catalogo(self):
        self.script('estatisticas')
        estado = self.rodada(self.executor(), (), finais=['estatisticas'])
        self.assertEqual(self.ordem_rodada(), ['estatisticas'])
        self.assertEqual(estado['finais'][0]['estado'], 'concluida')
        self.assertEqual(estado['finais'][1]['estado'], 'nao_iniciada')
