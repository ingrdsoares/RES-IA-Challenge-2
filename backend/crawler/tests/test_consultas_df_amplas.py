import hashlib
from pathlib import Path
import pytest
from backend.crawler.consultas_df_amplas import ingest, relevant, tarf_links, TARF

def test_tax_scope_rejects_medical_and_substrings():
    assert relevant('Solução de consulta sobre ICMS')
    assert relevant('ISSQN e Simples Nacional')
    assert not relevant('consulta médica comissão de assistência')
    assert not relevant('permissão de uso e omissão administrativa')

def test_tarf_links_dedup():
    raw=b'<a href="http://mobile.receita.fazenda.df.gov.br//aplicacoes/tarf/TelaSaidaAcordao.cfm?Camara=P&Acordao=1&AnoAcordao=2024">1</a>'
    assert tarf_links(raw+raw)==[TARF+'TelaSaidaAcordao.cfm?Camara=P&Acordao=1&AnoAcordao=2024']

def test_preservation_cache_and_hash(tmp_path):
    raw=('<html><body>CONSULTA N 1/2025 ICMS '+('regra tributária '*30)+'</body></html>').encode()
    meta=ingest(raw,'https://ww1.receita.fazenda.df.gov.br/test',tmp_path,'consulta_tributaria',{'data_publicacao':'01/01/2025'})
    assert Path(meta['originais'][0]['arquivo']).read_bytes()==raw
    assert ingest(raw,meta['source_url'],tmp_path,'consulta_tributaria')==meta
    Path(meta['markdown_arquivo']).write_text('corrupt')
    with pytest.raises(ValueError,match='Cache'):ingest(raw,meta['source_url'],tmp_path,'consulta_tributaria')

def test_reject_generic_and_out_of_scope(tmp_path):
    with pytest.raises(ValueError):ingest(b'<body>Login</body>','https://www.receita.fazenda.df.gov.br/test',tmp_path,'jurisprudencia_tarf')
    raw=('<body>Consulta médica '+('saúde '*100)+'</body>').encode()
    with pytest.raises(ValueError,match='fora_escopo'):ingest(raw,'https://www.receita.fazenda.df.gov.br/test',tmp_path,'consulta_tributaria')


def test_tarf_decision_requires_tax_scope_and_marks_view(tmp_path):
    raw=("<body>ACÓRDÃO EMENTA ICMS DECISÃO "+("regra tributária "*40)+"</body>").encode("cp1252")
    meta=ingest(raw,TARF+"TelaSaidaAcordao.cfm?Camara=P&Acordao=1&AnoAcordao=2024",tmp_path,"jurisprudencia_tarf")
    assert meta["tipo"]=="jurisprudencia_tarf"
    assert "não equivale ao inteiro teor" in Path(meta["markdown_arquivo"]).read_text(encoding="utf-8")

def test_reject_external_origin(tmp_path):
    with pytest.raises(ValueError,match="origem oficial"):
        ingest(b"anything","https://www.receita.fazenda.df.gov.br.evil.test/a",tmp_path,"consulta_tributaria")
