import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import httpx
from backend.crawler.indicadores_empresariais import extract_indicators,extract_df_summary,extract_mapa_summary,snapshot,collect,UFS

def sample():
    props={'stats':{'companies':{'value':'28.4M','year':'out/2026'},'employees':{'value':'60.7M','year':2025}},'stateStats':{'53':{'companies':{'value':482623,'year':'out/2026'},'employees':{'value':1000,'year':2025}},'93':{'companies':{'value':1,'year':2026}}}}
    props['stateStats']={code:dict(props['stateStats']['53']) for code in UFS}
    props['stateStats']['93']={'companies':{'value':1,'year':2026}}
    return ('<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':props}})+'</script>').encode()

class IndicadoresEmpresariaisTests(unittest.TestCase):
    def test_periods_rounding_and_df_without_regional_double_count(self):
        rows,_=extract_indicators(sample());self.assertEqual(len(rows),56)
        self.assertEqual(rows[0]['valor'],'28.4M');self.assertEqual(rows[0]['periodo'],'out/2026');self.assertEqual(rows[-2]['territorio'],'DF');self.assertEqual(rows[-2]['valor'],482623)
        self.assertTrue(all('source_url' in r and 'json_path' in r for r in rows))

    def test_shell_and_missing_period_rejected(self):
        with self.assertRaises(ValueError):extract_indicators(b'<html>Data Explorer</html>')
        with self.assertRaises(ValueError):extract_indicators(sample().replace(b'out/2026',b''))

    def test_hash_original_and_idempotency(self):
        info={'url':'https://observatorio.sebrae.com.br/','titulo':'Observatório','kind':'indicadores'};raw=sample()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);a=snapshot('obs',info,raw,200,out);b=snapshot('obs',info,raw,200,out)
            self.assertEqual(a['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(a,b)
            self.assertEqual((out/a['markdown']).with_name(a['original']).read_bytes(),raw);self.assertEqual(a['indicadores'],56)

    def test_pdf_html_and_http403_preserved_as_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            info={'url':'https://www.gov.br/test.pdf','titulo':'Boletim','kind':'pdf','periodo':'2025'};out=Path(tmp)
            for code in [200,403]:
                meta=snapshot('pdf',info,b'<html>backend unavailable</html>',code,out)
                self.assertEqual(meta['status'],'indisponivel');self.assertEqual(meta['indicadores'],0);self.assertTrue((out/meta['markdown']).with_name(meta['original']).exists())

    def test_df_summary_identity_and_exact_evidence(self):
        pages=['']*39;pages[37]='Cadastro Estadual de Empresas 01/07/2025';pages[4]='Distrito Federal possui 431.090 empresas ativas. MEIs, são 241.030 na capital. foram constituídas 8.992 empresas; foram 25.236 aberturas; sendo 227.482 se considerado apenas a atividade principal, e 272.270 levando em consideração atividade principal e secundária.'
        rows=extract_df_summary(pages,'https://jucis.df.gov.br/test.pdf');self.assertEqual(len(rows),6);self.assertEqual(rows[0]['valor'],431090);self.assertEqual(rows[2]['periodo'],'2025-01/2025-04');self.assertTrue(all(r['pagina']==5 for r in rows))
        pages[37]='outro relatório'
        with self.assertRaises(ValueError):extract_df_summary(pages,'test')

    def test_mapa_summary_keeps_period_page_and_source(self):
        pages=['Relatório do 2º quadrimestre de 2025','','O segundo quadrimestre registrou 24.213.445 empresas ativas','parcela significativa (12.660.170). No segundo quadrimestre foram abertas 1.668.753 empresas; foram fechadas 942.049 empresas. Desse montante 1.257.036 são MEIs. Saldo positivo: 726.704 empresas','A média de tempo de abertura de empresas no país foi de 21 horas']
        rows=extract_mapa_summary(pages,{'url':'https://www.gov.br/test.pdf','periodo':'2025-05/2025-08'})
        self.assertEqual(len(rows),7);self.assertEqual(rows[0]['valor'],24213445);self.assertEqual(rows[0]['pagina'],3);self.assertEqual(rows[-1]['unidade'],'horas');self.assertEqual(rows[-1]['valor'],21)
        self.assertTrue(all(r['periodo']=='2025-05/2025-08' for r in rows))
        pages[0]='outro documento'
        with self.assertRaises(ValueError):extract_mapa_summary(pages,{'url':'test','periodo':'2025'})

    def test_requires_all_27_states(self):
        raw=sample().replace(b'"11":',b'"99":')
        with self.assertRaises(ValueError):extract_indicators(raw)

    def test_existing_corrupt_original_is_not_overwritten(self):
        info={'url':'https://observatorio.sebrae.com.br/','titulo':'Observatório','kind':'indicadores'}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);meta=snapshot('obs',info,sample(),200,out);original=(out/meta['markdown']).with_name(meta['original']);original.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):snapshot('obs',info,sample(),200,out)
            self.assertEqual(original.read_bytes(),b'corrupt')

    def test_network_rerun_preserves_last_success_and_reports_attempt(self):
        info={'url':'https://observatorio.sebrae.com.br/','titulo':'Observatório','kind':'indicadores'}
        def handler(req):raise httpx.ConnectError('indisponível',request=req)
        with tempfile.TemporaryDirectory() as tmp,httpx.Client(transport=httpx.MockTransport(handler)) as c:
            out=Path(tmp);snapshot('observatorio-sebrae',info,sample(),200,out);report=collect(out,c)
            self.assertEqual(report['indicadores'],56);source=report['fontes'][0];self.assertTrue(source['dados_preservados_de_execucao_anterior']);self.assertEqual(source['ultima_tentativa']['status'],'erro')

    def test_network_failures_in_manifest(self):
        def handler(req):raise httpx.ConnectError('indisponível',request=req)
        with tempfile.TemporaryDirectory() as tmp,httpx.Client(transport=httpx.MockTransport(handler)) as c:
            report=collect(Path(tmp),c);self.assertEqual(report['total_fontes'],6);self.assertEqual(report['indicadores'],0);self.assertTrue(all(x['status']=='erro' for x in report['fontes']))

if __name__=='__main__':unittest.main()
