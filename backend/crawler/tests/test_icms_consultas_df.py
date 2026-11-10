import hashlib
import json
import pytest
from backend.crawler.icms_consultas_df import canonical, discover, ingest, parse, SEEDS

RAW=b'<html><head><title>Lei 1254 de 08/11/1996</title></head><body><div id="div_texto"><h1>Lei 1254 de 08/11/1996</h1><p>Art. 1 ICMS '+b'regra tributaria '*20+b'</p><table><tr><td>valor</td></tr></table></div></body></html>'

def test_boundary():
    assert canonical(SEEDS[0]+'#art1')==SEEDS[0]
    for u in ['https://www.sinj.df.gov.br.evil.test/sinj/Norma/1/a.html','http://www.sinj.df.gov.br/sinj/Norma/1/a.html','https://www.sinj.df.gov.br/login','file:///sinj/Norma/1/a.html']:
        assert canonical(u) is None

def test_discovery_deduplicates_and_bounds():
    raw=b'<a href="/sinj/Norma/1/a.html#x">a</a><a href="/sinj/Norma/1/a.html#y">b</a><a href="https://evil.test/a.html">x</a>'
    assert discover(raw,SEEDS[0])==['https://www.sinj.df.gov.br/sinj/Norma/1/a.html']

def test_reject_shell_and_mismatched_identity():
    with pytest.raises(ValueError):parse(b'<html><title>Error</title><body>Access denied</body></html>',SEEDS[0])
    with pytest.raises(ValueError):parse(RAW.replace(b'<title>Lei 1254 de 08/11/1996</title>',b'<title>Lei 999 de 01/01/2000</title>'),SEEDS[0])

def test_cache_hash_and_original(tmp_path):
    result=ingest(RAW,SEEDS[0],tmp_path)
    assert ingest(RAW,SEEDS[0],tmp_path)==result
    target=(tmp_path/result['markdown']).parent
    assert (target/'original.html').read_bytes()==RAW
    assert result['original']=='original.html'
    assert result['sha256']==hashlib.sha256(RAW).hexdigest()
    (target/'documento.md').write_text('corrupt')
    with pytest.raises(ValueError):ingest(RAW,SEEDS[0],tmp_path)


def test_wrong_seed_identity(tmp_path):
    with pytest.raises(ValueError):ingest(RAW.replace(b"1254",b"9999"),SEEDS[0],tmp_path)


def test_leading_zero_identity():
    raw=RAW.replace(b'<h1>Lei 1254 de 08/11/1996</h1>',b'<h1>LEI N 01.254 DE 8 DE NOVEMBRO DE 1996</h1>')
    assert parse(raw,SEEDS[0])[0].startswith('LEI')


def test_legacy_portaria_header():
    raw=RAW.replace(b'<title>Lei 1254 de 08/11/1996</title>',b'<title>Portaria 42 de 07/03/2016</title>').replace(b'<h1>Lei 1254 de 08/11/1996</h1>','<p>PORTARIA Nº 42 DE 07 DE MARÇO DE 2016</p>'.encode())
    assert parse(raw,SEEDS[0])[0].startswith('PORTARIA')


def test_pdf_expected_decree_identity(monkeypatch):
    from backend.crawler import icms_consultas_df as collector
    class Page:
        def get_textpage(self):return self
        def get_text_range(self):return 'DECRETO Nº 18.107, DE 19 DE MARÇO DE 1997. Art. 1 regra'
        def close(self):pass
    class Document:
        def __init__(self,raw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def __len__(self):return 1
        def __getitem__(self,i):return Page()
    monkeypatch.setattr(collector.pypdfium2,'PdfDocument',Document)
    assert parse(b'%PDF-test','https://www.sinj.df.gov.br/sinj/Norma/31519/test.pdf')[2]['paginas']==1
    with pytest.raises(ValueError):parse(b'%PDF-test','https://www.sinj.df.gov.br/sinj/Norma/32566/test.pdf')


def test_unrelated_consulta_is_not_tax_consultation():
    from backend.crawler.icms_consultas_df import classify_diary
    assert classify_diary('CONSULTA MÉDICA PSIQUIATRIA. ACÓRDÃO TARF. ICMS.')=='diario_com_jurisprudencia_tributaria'
    assert classify_diary('Consulta médica. ICMS.')=='diario_geral'
    assert classify_diary('SOLUÇÃO DE CONSULTA Nº 27/2024 ICMS. Lei 5005')=='diario_com_consulta_tributaria'
    assert classify_diary('DECLARAÇÃO DE INEFICÁCIA DE CONSULTA Nº 12/2025 PROCESSO ICMS.')=='diario_com_consulta_tributaria'
