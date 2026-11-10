import hashlib
import json
from backend.crawler.estatisticas import collect


def test_counts_units_and_deduplicates(tmp_path):
    a=tmp_path/'frente'/'a';b=tmp_path/'frente'/'b';a.mkdir(parents=True);b.mkdir()
    digest=hashlib.sha256(b'raw').hexdigest()
    for folder in (a,b):
        (folder/'original.json').write_bytes(b'raw')
        (folder/'documento.md').write_text('# Texto',encoding='utf8')
        (folder/'metadados.json').write_text(json.dumps({'source_url':'u','sha256':digest,'coletado_em':'d'}))
    (a/'registros.json').write_text(json.dumps([{'cnpj_basico':'00000001'},{'cnpj_basico':'00000002'}]))
    (b/'registros.json').write_text(json.dumps([{'cnpj_basico':'00000001'}]))
    result=collect(tmp_path)
    assert result['snapshots']==2 and result['originais_conteudos_distintos']==1
    assert result['empresas_raizes_distintas']==2 and result['ocorrencias_empresas_derivados']==3
    assert result['markdown_arquivos']==2 and result['bytes_em_disco']>0


def test_pdf_pages_dedup_and_source_markdown_excluded(tmp_path):
    import io
    import pypdfium2
    doc=pypdfium2.PdfDocument.new();page=doc.new_page(200,200);page.close()
    stream=io.BytesIO();doc.save(stream);doc.close();raw=stream.getvalue()
    digest=hashlib.sha256(raw).hexdigest()
    for n in ('a','b'):
        folder=tmp_path/'frente'/n;folder.mkdir(parents=True)
        pdf=folder/'original.pdf';pdf.write_bytes(raw)
        md=folder/'documento.md';md.write_text('# Texto '+n,encoding='utf8')
        meta={'source_url':'u','coletado_em':'d','sha256':digest,'originais':[
            {'arquivo':str(pdf.resolve()),'source_url':'u','sha256':digest},
            {'arquivo':str(md.resolve()),'source_url':'u','sha256':hashlib.sha256(md.read_bytes()).hexdigest()}]}
        (folder/'metadados.json').write_text(json.dumps(meta))
    result=collect(tmp_path)
    assert result['pdf_arquivos']==2 and result['pdf_conteudos_distintos']==1
    assert result['paginas_pdf_distintas']==1 and result['originais_conteudos_distintos']==1


def test_schema_content_dedup_inside_packages(tmp_path):
    import zipfile
    raw=b'<schema/>'
    for n in ('a','b'):
        with zipfile.ZipFile(tmp_path/(n+'.zip'),'w') as z:z.writestr('nested/schema.xsd',raw)
    (tmp_path/'schema.xsd').write_bytes(raw)
    result=collect(tmp_path)
    assert result['xsd_ocorrencias_arquivos_e_pacotes']==3
    assert result['xsd_conteudos_distintos']==1
