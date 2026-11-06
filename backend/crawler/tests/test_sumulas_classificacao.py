import json
import hashlib
import io
import zipfile
from pathlib import Path
import tempfile
import unittest
from backend.crawler.sumulas_classificacao import ingest, links, CARF, RFB, NCM, extract_docx, enrich_metadata
from backend.crawler.catalogo import audit_snapshot, Hasher

class SumulasClassificacaoTests(unittest.TestCase):
    def test_editorial_bounds_and_normalization(self):
        raw=f'<nav><a href="{CARF}noise">noise</a></nav><main><a href="ato.pdf/view#x">Ato</a><a href="https://example.com/file.pdf">external</a></main>'.encode()
        self.assertEqual(links(raw,CARF+'catalogo'),{CARF+'ato.pdf':'Ato'})
    def test_snapshot_immutable_and_audited(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=b'<h1>Sumula</h1><main><p>Texto oficial</p><table><tr><td>1</td><td>2</td></tr></table></main>'
            m=ingest(CARF+'a',raw,root)
            p=next(root.glob('snapshots/*/*/metadados.json'))
            self.assertEqual(audit_snapshot(m,p,root,Hasher())['problemas'],[])
            self.assertEqual(m,ingest(CARF+'a',raw,root))
            (p.parent/'documento.md').write_text('modified')
            with self.assertRaises(ValueError):ingest(CARF+'a',raw,root)
    def test_ncm_json_rows_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            raw=json.dumps({'Nomenclaturas':[{'Codigo':'01','Descricao':'Capitulo'},{'Codigo':'0101.21.00','Descricao':'Animais'}],'Data_Ultima_Atualizacao':'2026-11-04'}).encode()
            m=ingest(NCM,raw,Path(d))
            self.assertEqual(m['original'],'original.json')
            self.assertEqual(m['ncm_registros_hierarquicos'],2)
            self.assertEqual(m['ncm_codigos_oito_digitos'],1)
            self.assertEqual(m['ncm_niveis_intermediarios'],1)
            self.assertIn('0101.21.00',next(Path(d).glob('snapshots/*/*/documento.md')).read_text(encoding='utf8'))
    def test_docx_paragraph_and_table(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('[Content_Types].xml','<Types/>')
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Peticao</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Celula</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        text=extract_docx(stream.getvalue())
        self.assertIn('Peticao',text)
        self.assertIn('Celula',text)
        with tempfile.TemporaryDirectory() as d:
            m=ingest(RFB+'/modelo.docx',stream.getvalue(),Path(d))
            self.assertEqual(m['natureza_documental'],'modelo_peticao_sem_forca_normativa')
            self.assertEqual(m['tipo'],m['natureza_documental'])
            self.assertEqual(m,ingest(RFB+'/modelo.docx',stream.getvalue(),Path(d)))
    def test_dou_followed_once(self):
        url='https://www.in.gov.br/web/dou/-/portaria-123'
        raw=('<main><a href="'+url+'">ato</a></main>').encode()
        self.assertIn(url,links(raw,CARF+'sumulas'))
        self.assertNotIn(url,links(raw,url))
    def test_pdf_blank_page_marks_partial(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'documento.md').write_text('## Página 1\n\nTexto\n\n## Página 2\n\n',encoding='utf8')
            old={'source_url':RFB+'/nesh.pdf','original':'original.pdf','markdown_arquivo':'documento.md','coletado_em':'2020-01-01','sha256':'originalhash','status':'extraido'}
            m=enrich_metadata(old,p)
            self.assertEqual(m['paginas_sem_texto'],[2])
            self.assertEqual(m['status'],'parcial')
            self.assertTrue(m['ocr_revisao_pendente'])
            self.assertEqual(m['coletado_em'],old['coletado_em'])
            self.assertEqual(m['sha256'],old['sha256'])
    def test_verified_blank_page_clears_ocr_only_with_matching_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'documento.md').write_text('## Página 1\n\n',encoding='utf8')
            image=p/'blank.png';image.write_bytes(b'rendered page evidence')
            old={'source_url':RFB+'/nesh.pdf','original':'original.pdf','markdown_arquivo':'documento.md','sha256':'pdfhash','status':'parcial','paginas_em_branco_verificadas':[{'pagina':1,'pdf_sha256':'pdfhash','imagem_arquivo':str(image),'imagem_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}]}
            m=enrich_metadata(old,p)
            self.assertEqual(m['paginas_sem_texto'],[1])
            self.assertEqual(m['paginas_ocr_pendentes'],[])
            self.assertFalse(m['ocr_revisao_pendente'])
            self.assertEqual(m['status'],'extraido')
            self.assertEqual(m,enrich_metadata(m,p))
            image.write_bytes(b'changed evidence')
            self.assertEqual(enrich_metadata(m,p)['paginas_ocr_pendentes'],[1])
    def test_authority_persisted_and_cached(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);raw=b'<h1>Portaria</h1><main>Norma administrativa</main>'
            m=ingest(CARF+'portaria-383.pdf',raw,p)
            self.assertEqual(m['tipo'],'ato_normativo_administrativo')
            side=next(p.glob('snapshots/*/*/metadados.json'))
            stored=json.loads(side.read_bytes())
            self.assertEqual(stored['natureza_documental'],m['natureza_documental'])
            self.assertEqual(m,ingest(CARF+'portaria-383.pdf',raw,p))
            self.assertEqual(audit_snapshot(m,side,p,Hasher())['problemas'],[])
    def test_blocked_html_not_document(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):ingest(RFB,b'<h1>Access denied</h1>',Path(d))

if __name__=='__main__':unittest.main()
