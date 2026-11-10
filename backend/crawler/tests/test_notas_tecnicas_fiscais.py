import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import httpx
from backend.crawler.notas_tecnicas_fiscais import discover,selected,parse_xlsx,ingest,collect


def workbook():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="NBS" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/sharedStrings.xml','<sst><si><t>001.01</t></si></sst>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="A2" t="s"><v>0</v></c><c r="C2" t="inlineStr"><is><t>Descrição</t></is></c></row></sheetData><mergeCells><mergeCell ref="A2:B3"/></mergeCells></worksheet>')
    return out.getvalue()

class NotasTecnicasTests(unittest.TestCase):
    def test_catalog_uses_system_route_and_latest_selection(self):
        raw=b'''<a href="#" onclick="download_arquivo_estatico('DFE', 16, 'it.pdf');">IT 2025.002 RT Tabela v1.71</a>'''
        link=discover(raw,'https://dfe-portal.svrs.rs.gov.br/Nfe/Documentos')[0]
        self.assertIn('/DFE/DownloadArquivoEstatico/',link['url'])
        self.assertTrue(selected('nfe',link))
        self.assertFalse(selected('nfe',{'url':'','titulo':'Nota Técnica 2025.002 v1.52'}))

    def test_coordinates_leading_zero_and_merged_cells_preserved(self):
        sheets=parse_xlsx(workbook());s=sheets[0]
        self.assertEqual(s['mesclagens'],['A2:B3'])
        self.assertEqual(s['linhas'][0]['celulas'],[{'celula':'A2','valor':'001.01'},{'celula':'C2','valor':'Descrição'}])
        with self.assertRaises(ValueError):parse_xlsx(b'<html>login</html>')

    def test_hash_origin_original_and_idempotency(self):
        raw=workbook();item={'source_id':'test','url':'https://www.gov.br/test.xlsx','titulo':'Anexo B v1.01','catalog_url':'https://www.gov.br/catalog'}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);a=ingest(item,raw,out);b=ingest(item,raw,out)
            self.assertEqual(a['markdown'],b['markdown']);self.assertEqual(a['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(a['source_url'],item['url']);self.assertEqual(a['vigencia'],'nao_verificada')
            self.assertEqual((out/a['markdown']).with_name('original.xlsx').read_bytes(),raw)
            self.assertEqual(len(list((out/'test').iterdir())),1)

    def test_rejects_html_masquerading_as_pdf_and_invalid_nbs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for url in ['https://www.gov.br/a.pdf','https://www.gov.br/nbs2-0.csv']:
                with self.assertRaises(ValueError):ingest({'source_id':'x','url':url,'titulo':'x'},b'<html>login</html>',Path(tmp))

    def test_catalog_failures_are_visible(self):
        def fail(req):return httpx.Response(503,request=req)
        with tempfile.TemporaryDirectory() as tmp,httpx.Client(transport=httpx.MockTransport(fail)) as client:
            report=collect(Path(tmp),client)
            self.assertEqual(len(report['catalogos']),4)
            self.assertTrue(all(c['status']=='erro' for c in report['catalogos']))
            self.assertEqual(json.loads((Path(tmp)/'manifesto.json').read_text(encoding='utf8'))['total'],0)

if __name__=='__main__':unittest.main()

def test_snapshot_metadata_is_immutable_and_corruption_rejected(tmp_path):
    import pytest
    raw=workbook();item={'source_id':'test','url':'https://www.gov.br/test.xlsx','titulo':'Anexo B','catalog_url':'https://www.gov.br/catalog'}
    first=ingest(item,raw,tmp_path);second=ingest(item,raw,tmp_path)
    assert first==second
    (tmp_path/first['markdown']).with_name('original.xlsx').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='incompleta ou divergente'):ingest(item,raw,tmp_path)

def test_empty_pdf_is_not_accepted_because_of_generated_header(tmp_path):
    import pytest,pypdfium2
    doc=pypdfium2.PdfDocument.new();page=doc.new_page(200,200);page.close();stream=io.BytesIO();doc.save(stream);doc.close()
    item={'source_id':'blank','url':'https://www.gov.br/blank.pdf','titulo':'Manual fiscal sem texto '+('classificações e correlações oficiais '*10),'catalog_url':'https://www.gov.br/catalog'}
    with pytest.raises(ValueError,match='sem texto'):ingest(item,stream.getvalue(),tmp_path)
