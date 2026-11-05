import json
import tempfile
import unittest
from pathlib import Path

from backend.crawler.catalogo import FRONTES
from backend.crawler.painel.frentes import (ETAPAS_FINAIS, FRENTES, MODULO_CATALOGO,
                                            carregar_catalogo, resumir_catalogo)

FERRAMENTAS = Path(__file__).resolve().parents[1] / 'ferramentas.json'


class FrentesTests(unittest.TestCase):
    def test_cobre_ferramentas_e_frontes(self):
        declarados = {t['modulo'] for t in json.loads(FERRAMENTAS.read_text('utf8'))['ferramentas']
                      if t['tipo'] != 'biblioteca' and t['modulo'] != 'painel'}
        self.assertEqual(declarados, {f.modulo for f in FRENTES} | set(ETAPAS_FINAIS) | {MODULO_CATALOGO})
        self.assertEqual(set(FRONTES.values()), {f.pasta for f in FRENTES} | {'catalogo'})

    def test_dependencia_vem_antes(self):
        ordem = [f.modulo for f in FRENTES]
        for f in FRENTES:
            for d in f.depende:
                self.assertLess(ordem.index(d), ordem.index(f.modulo))

    def test_nome_legivel(self):
        por_modulo = {f.modulo: f for f in FRENTES}
        self.assertEqual(por_modulo['cnae'].nome, 'CNAE IBGE')

    def test_catalogo_ausente_ou_corrompido(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            self.assertIsNone(carregar_catalogo(data))
            (data / 'catalogo').mkdir()
            (data / 'catalogo' / 'catalogo.json').write_text('{quebrado')
            self.assertIsNone(carregar_catalogo(data))
        self.assertEqual(resumir_catalogo(None), {})

    def test_resumo_por_pasta(self):
        catalogo = {'snapshots': [
            {'diretorio': 'cnae/a', 'origem': 'https://x.gov.br/1', 'coletado_em': '2026-11-01T00:00:00+00:00'},
            {'diretorio': 'cnae/b', 'origem': 'https://x.gov.br/2', 'coletado_em': '2026-11-03T00:00:00+00:00'},
            {'diretorio': 'cnae/c', 'origem': 'https://y.gov.br/3', 'coletado_em': None}],
            'cobertura_frentes': [{'pasta': 'cnae', 'snapshots': 3, 'situacao': 'coletada_com_pendencias',
                                   'erros_manifesto_mais_recente': 2, 'pendencias_extracao': 1}]}
        r = resumir_catalogo(catalogo)['cnae']
        self.assertEqual((r['itens'], r['fonte'], r['pendencias']), (3, 'x.gov.br', 3))
        self.assertEqual(r['ultima_coleta'], '2026-11-03T00:00:00+00:00')
        self.assertEqual(len(r['origens']), 3)
        self.assertEqual(r['situacao'], 'coletada_com_pendencias')


if __name__ == '__main__':
    unittest.main()
