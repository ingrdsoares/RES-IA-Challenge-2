import hashlib
import json
import httpx
import pytest
from backend.crawler import distrital_df as df

def law(title="DECRETO Nº 25.508, DE 19 DE JANEIRO DE 2005"):
    return f'<div id="div_texto"><h1>{title}</h1><p>Art. 1º ISS.</p><div class="strike"><p>Art. 2º Redação antiga</p></div><p>ANEXO I</p><table><tr><td>Item</td><td>Alíquota</td></tr><tr><td>1.01</td><td>2%</td></tr></table><p><a href="anexo.html">Anexo</a></p></div>'.encode()

def test_sinj_identity_articles_annex_table_and_strike():
    body,meta=df.parse_html("decreto25508",law())
    assert "## Art. 1º" in body and "## ANEXO I" in body
    assert "~~" in body and "Redação antiga" in body
    assert "| Item | Alíquota |" in body and "2%" in body
    assert "https://www.sinj.df.gov.br/sinj/Norma/46110/anexo.html" in body
    assert meta["tachados"]==1 and meta["tabelas"]==1

def test_wrong_norm_and_error_pages_rejected():
    with pytest.raises(ValueError):df.parse_html("decreto43982",law())
    with pytest.raises(ValueError):df.parse_html("decreto25508",b"Service unavailable")
    wrong=law("DECRETO Nº 99, DE 2005").replace(b"ISS.","DECRETO Nº 25.508, DE 19 DE JANEIRO DE 2005".encode())
    with pytest.raises(ValueError):df.parse_html("decreto25508",wrong)

def test_versions_raw_bytes_and_idempotency(tmp_path):
    raw=law();path=df.ingest("decreto25508",raw,tmp_path);before=path.read_bytes()
    assert path.parent.name==hashlib.sha256(raw).hexdigest()
    assert df.ingest("decreto25508",raw,tmp_path)==path and path.read_bytes()==before
    assert df.ingest("decreto25508",raw+b" ",tmp_path)!=path
    meta=json.loads((path.parent/"metadados.json").read_bytes())
    assert meta["jurisdicao"]=="Distrito Federal" and meta["camada"]=="A"
    assert meta["vigencia"]=="nao_verificada"
    assert (path.parent/"original.html").read_bytes()==raw

def test_pdf_identity_extraction_and_supplier_metadata(tmp_path):
    # Pequeno PDF sintético com texto, sem dependência de biblioteca autora.
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    stream=b"BT /F1 12 Tf 30 700 Td (Manual integracao NFS-e) Tj ET"
    objects.append(b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream")
    raw=b"%PDF-1.4\n";offsets=[]
    for i,obj in enumerate(objects,1):
        offsets.append(len(raw));raw+=str(i).encode()+b" 0 obj\n"+obj+b"\nendobj\n"
    xref=len(raw);raw+=b"xref\n0 6\n0000000000 65535 f \n"+b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)+f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    path=df.ingest("manual-integracao",raw,tmp_path)
    meta=json.loads((path.parent/"metadados.json").read_bytes())
    assert meta["paginas"]==1 and meta["tipo"]=="manual_fornecedor"
    assert meta["catalog_url"]==df.NFSE and "fornecedor" in meta["publicador"]
    assert meta["tabelas"]=="nao_reconstruidas"
    with pytest.raises(ValueError):df.parse_pdf("manual-integracao",b"<html>Error</html>")

def test_http_failure_manifest(tmp_path):
    client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(503,request=req)))
    result=df.collect(tmp_path,["decreto25508"],client)
    assert result["falhas"]==1 and result["extraidos"]==0
    assert json.loads((tmp_path/"manifesto.json").read_bytes())["documentos"][0]["status"]=="erro"


def test_sinj_unclosed_paragraphs_do_not_create_deep_recursion():
    raw=('<div id="div_texto"><h1>DECRETO Nº 25.508, DE 19 DE JANEIRO DE 2005</h1>'+''.join(f'<p>Art. {i} Texto {i}' for i in range(1,500))+'</div>').encode()
    body,stats=df.parse_html("decreto25508",raw)
    assert stats["artigos_anexos"]==499 and "Texto 499" in body
