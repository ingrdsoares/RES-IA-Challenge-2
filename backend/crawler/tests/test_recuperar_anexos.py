import hashlib
import pytest
from backend.crawler.recuperar_anexos import render, verify


def test_converted_table_and_ocr_are_explicit(tmp_path):
    html=b'<html><body><h1>Anexo</h1><table><tr><td>Faixa</td><td>Valor</td></tr><tr><td>1</td><td>1000</td></tr></table></body></html>'
    text,stats=render(html,'word','https://example.gov.br/anexo')
    assert '| Faixa | Valor |' in text and stats['tabelas']==1
    text,stats=render('Anexo valor 1.000,00'.encode(),'ocr','u')
    assert 'OCR' in text and '1.000,00' in text
    with pytest.raises(ValueError):render(b'','ocr','u')
    p=tmp_path/'documento.md';p.write_bytes(b'valid')
    meta={'markdown_sha256':hashlib.sha256(b'valid').hexdigest(),'artefatos_sha256':{'documento.md':hashlib.sha256(b'valid').hexdigest()}}
    verify(tmp_path,meta)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError):verify(tmp_path,meta)


def test_both_collections_reuse_cache_and_deduplicate_versions(tmp_path):
    import json
    from backend.crawler.recuperar_anexos import collect
    raw=tmp_path/'attachment.doc';raw.write_bytes(b'original')
    checksum=hashlib.sha256(raw.read_bytes()).hexdigest()
    original={'arquivo':str(raw.resolve()),'sha256':checksum,'bytes':8,'source_url':'https://example.gov.br/anexo'}
    output=tmp_path/'output';target=output/'42-attachment'/checksum;target.mkdir(parents=True)
    (target/'documento.md').write_bytes(b'converted')
    meta={'source_id':'42-attachment','sha256':checksum,'originais':[original],'origem_metadados':'source','extrator':'Microsoft Word HTML filtrado','artefatos_sha256':{'documento.md':hashlib.sha256(b'converted').hexdigest()}}
    (target/'metadados.json').write_text(json.dumps(meta))
    for collection in ('reforma-historico','retencoes-defesa-setores'):
        for version in ('old','new'):
            folder=tmp_path/collection/version;folder.mkdir(parents=True)
            (folder/'metadados.json').write_text(json.dumps({'source_id':42,'coletado_em':'2026-01-01','originais':[original]}))
    result=collect(output,tmp_path)
    assert result['extraidos']==result['total']==1
    assert result['falhas']==[]
    assert raw.read_bytes()==b'original'


def test_reuses_conversion_and_ignores_decorative_empty_ocr(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    from backend.crawler import recuperar_anexos as module
    raw=tmp_path/'attachment.doc';raw.write_bytes(b'original')
    checksum=hashlib.sha256(raw.read_bytes()).hexdigest()
    folder=tmp_path/'retencoes-defesa-setores';folder.mkdir()
    item={'arquivo':str(raw.resolve()),'sha256':checksum,'bytes':8,'source_url':'https://example.gov.br/anexo'}
    (folder/'metadados.json').write_text(json.dumps({'source_id':42,'coletado_em':'2026-01-01','originais':[item]}))
    output=tmp_path/'output';target=output/'42-attachment'/checksum;target.mkdir(parents=True)
    html=target/'convertido.html';html.write_text('<body>Substantive original document text<img src="logo.png"></body>')
    (target/'logo.png').write_bytes(b'image');(target/'ocr-imagem-001.txt').write_bytes(b'')
    (output/'conversao.json').write_text(json.dumps([{'id':'42-attachment','status':'convertido','output':str(html.resolve())}]))
    calls=[]
    def native(args,**kwargs):
        calls.append(args)
        assert 'ocr-suporte-jobs.json' in ' '.join(args)
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(module.subprocess,'run',native)
    result=module.collect(output,tmp_path)
    assert result['extraidos']==1 and not result['falhas']
    assert result['documentos'][0]['imagens_sem_texto_ocr']==1
    assert 'Substantive original' in (target/'documento.md').read_text(encoding='utf-8')
    assert len(calls)==0
