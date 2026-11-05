import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.crawler import reforma_historico as mod

class ReformaTests(unittest.TestCase):
    def test_repeated_identity_rejected(self):
        with self.assertRaises(ValueError):
            mod.parse_search(json.dumps({'atos':[{'idAto':1},{'idAto':1}], 'quantidadeTotal':2, 'quantidadePaginas':1}))

    def test_two_views_and_original_identity(self):
        def cached(client, path, method, url, **kwargs):
            view = url.rsplit('/',1)[-1]
            data = {'idAto':1, 'visao':view, 'ementas':[], 'outrosSegmentos':[{'idSegmento':2,'ordemSegmentoAto':1,'versaoSegmento':1,'textoIntegra':'<p>Art. 1º Texto histórico.</p>'}], 'epigrafe':{}, 'historico':[]}
            path.parent.mkdir(parents=True,exist_ok=True)
            raw=json.dumps(data).encode()
            path.write_bytes(raw)
            mod.rfb.save_json(path.with_suffix('.json.receipt.json'), {'coletado_em':'2026-11-04T00:00:00+00:00'})
            return raw
        with tempfile.TemporaryDirectory() as root, patch.object(mod.rfb,'cached',side_effect=cached):
            meta=mod.ingest(None,Path(root),{'row':{'idAto':1,'tipoAto':{'siglaTipoAto':'Resol.'},'numeroAto':'1','anoAto':'2007'},'temas':['historico-cgsn']})
            self.assertEqual(len(meta['visoes_fonte']),2)
            self.assertEqual(meta['vigencia'],'nao_verificada')
            self.assertEqual(Path(meta['originais'][0]['arquivo']).name,'multivigente.json')
            self.assertEqual(meta['markdown_sha256'],mod.rfb.digest((Path(root)/'1'/'documento.md').read_bytes()))
            self.assertEqual(meta['coletado_em'],'2026-11-04T00:00:00+00:00')
            (Path(root)/'1'/'documento.md').write_text('corrupted',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Markdown em cache divergente'):
                mod.ingest(None,Path(root),{'row':{'idAto':1},'temas':[]})

    def test_cached_wrong_identity_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'x.json'
            path.write_bytes(b'{}')
            mod.rfb.save_json(path.with_suffix('.json.receipt.json'), {'sha256':'invalid','source_url':'https://official','request':None})
            with self.assertRaises(ValueError):
                mod.rfb.cached(None,path,'GET','https://official')
