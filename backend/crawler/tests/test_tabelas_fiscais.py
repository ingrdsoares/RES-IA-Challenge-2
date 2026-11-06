import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from backend.crawler.tabelas_fiscais import parse_ncm, parse_html, parse_xsd, persist

class TabelasFiscaisTests(unittest.TestCase):
    def test_ncm_preserves_leading_zeros_and_validity(self):
        data={'Ato':'Resolução','Nomenclaturas':[{'Codigo':'0101.21.00','Descricao':'Reprodutores','Data_Fim':'31/12/9999'}]}
        rows,meta=parse_ncm(json.dumps(data).encode())
        self.assertEqual(rows[0],data['Nomenclaturas'][0])
        self.assertEqual(meta['Ato'],'Resolução')

    def test_cest_preserves_historical_duplicates_and_ncm(self):
        raw=b'<title>142/18</title><table><tr><td>1</td><td>01.001.00</td><td>01 02</td><td><s>Antigo</s></td></tr><tr><td>1</td><td>01.001.00</td><td>03</td><td>Novo</td></tr></table>'
        rows,_=parse_html(raw,'cest')
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0]['Texto_riscado'])
        self.assertEqual(rows[0]['NCM_SH'],'01 02')

    def test_cfop_keeps_occurrences_and_rejects_login(self):
        rows,_=parse_html(b'<title>03/24</title><p>1.101 - Compra</p><p>1.101 - Retificacao</p>','cfop')
        self.assertEqual(len(rows),2)
        with self.assertRaises(ValueError):parse_html(b'<h1>Login</h1>','cfop')

    def test_xsd_excludes_other_taxes_and_keeps_shared_annotation(self):
        raw=b'''<schema xmlns="http://www.w3.org/2001/XMLSchema"><element name="ICMS"><element name="CST"><annotation><documentation>00 - Integral; 20 - Reduzida</documentation></annotation><enumeration value="00"/><enumeration value="20"/></element></element><element name="PIS"><element name="CST"><enumeration value="99"/></element></element></schema>'''
        rows,_=parse_xsd(raw,'cst')
        self.assertEqual([r['Codigo'] for r in rows],['00','20'])
        self.assertIn('20 - Reduzida',rows[0]['Descricao'])

    def test_persist_original_hash_and_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            raw=b'original'
            entry=persist(Path(d),'cfop',raw,'html','https://example.gov.br','snapshot',[{'Codigo':'1.101','Descricao':'a|b'}],{})
            dest=Path(d)/'cfop'/entry['sha256']
            self.assertEqual(hashlib.sha256((dest/'original.html').read_bytes()).hexdigest(),entry['sha256'])
            self.assertIn('a&#124;b',(dest/'tabela.md').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((dest/'registros.json').read_text(encoding='utf-8'))[0]['Codigo'],'1.101')

if __name__=='__main__':unittest.main()
