import hashlib
import json
import httpx
import pytest
from backend.crawler import legislacao_complementar as lc
from backend.crawler.legislacao import SOURCES as ORIGINAL_SOURCES

def document(source="lc128", text="Texto", extra=""):
    title=lc.SOURCES[source]["title"].split(" —")[0]
    return f'<html><h1>{title}</h1><div class="textoNorma"><p>Art. 1º {text}</p>{extra}</div></html>'.encode("utf-8")

def test_identity_and_no_global_mutation():
    original=dict(ORIGINAL_SOURCES)
    assert "## Art. 1º" in lc.parse("lc128", document())
    with pytest.raises(ValueError, match="Identidade"):
        lc.parse("lc147",document())
    assert ORIGINAL_SOURCES == original

@pytest.mark.parametrize("raw", [b"<html>Service unavailable</html>", b"<html>404 Not Found</html>"])
def test_error_page_rejected(raw):
    with pytest.raises(ValueError): lc.parse("lc128",raw)

def test_struck_text_links_and_articles():
    raw=document(extra='<p>Art. 2º <strike>Antigo</strike> <a href="outra.html">Alteração</a></p>')
    body=lc.parse("lc128",raw)
    assert "~~Antigo~~" in body
    assert "## Art. 2º" in body
    assert "https://www2.camara.leg.br/legin/fed/leicom/2008/outra.html" in body

def test_versions_and_idempotency(tmp_path):
    raw=document()
    path=lc.ingest("lc128",raw,tmp_path)
    assert path.parent.name == hashlib.sha256(raw).hexdigest()
    before=path.read_bytes()
    assert lc.ingest("lc128",raw,tmp_path)==path
    assert before==path.read_bytes()
    second=lc.ingest("lc128",document(text="Alterado"),tmp_path)
    assert second!=path and path.is_file()
    assert (path.parent/"original.html").read_bytes()==raw
    assert "vigencia: nao_verificada" in before.decode()

def test_http_failure_manifest(tmp_path):
    client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(503,request=req)))
    result=lc.collect(tmp_path,["lc128"],client)
    assert result["falhas"]==1 and result["coletados"]==0
    assert json.loads((tmp_path/"manifesto.json").read_bytes())["total"]==1

def test_confaz_clause_and_correct_identity():
    raw='<div id="content-core"><p>AJUSTE SINIEF 19/16, DE 9 DE DEZEMBRO DE 2016</p><p>Cláusula primeira Institui NFC-e.</p></div>'.encode()
    assert "## Cláusula primeira" in lc.parse("ajuste19_2016",raw)
    with pytest.raises(ValueError): lc.parse("ajuste07_2005",raw)


def test_real_camara_dir_boundary_and_duplicate_article_heading():
    # Câmara LC188: Art.2 é texto solto após </dir>; Art.3 já está em <p>.
    raw='''<h1>Lei Complementar nº 188, de 31 de dezembro de 2021</h1>
    <div class="textoNorma"><div class="texto">Art. 1º A Lei Complementar passa a vigorar:
    <dir>"Art. 2º Redação interna da LC123." (NR)</dir>     Art. 2º A Lei Complementar passa a vigorar:
    <dir>"Art. 18-A. Texto citado."</dir><p>Art. 3º Esta Lei Complementar entra em vigor na data de sua publicação.</p>
    </div></div>'''.encode()
    text=lc.parse('lc188',raw)
    assert [line for line in text.splitlines() if line.startswith('## Art.')]==[
        '## Art. 1º','## Art. 2º','## Art. 3º']
    assert '> "Art. 2º Redação interna' in text
    assert '## Art. 18-A' not in text
    assert text.count('Art. 3º Esta Lei')==1


@pytest.mark.parametrize('corruption',['missing','sha256','source_url','source_id'])
def test_resume_rejects_missing_or_divergent_metadata(tmp_path,corruption):
    raw=document();path=lc.ingest('lc128',raw,tmp_path)
    metadata=path.parent/'metadados.json'
    if corruption=='missing':metadata.unlink()
    else:
        meta=json.loads(metadata.read_bytes());meta[corruption]='divergente'
        metadata.write_text(json.dumps(meta),encoding='utf-8')
    with pytest.raises(ValueError,match='incompleta ou divergente'):
        lc.ingest('lc128',raw,tmp_path)
