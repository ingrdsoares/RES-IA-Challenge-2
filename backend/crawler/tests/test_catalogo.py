import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from backend.crawler.catalogo import Hasher,audit_snapshot,collect,frontmatter

class CatalogoTests(unittest.TestCase):
    def test_frontmatter_preserves_url(self):
        data=frontmatter('---\nsource_url: https://example.gov.br/a:b\nsha256: 001\n---\n# Texto')
        self.assertEqual(data['source_url'],'https://example.gov.br/a:b')
        self.assertEqual(data['sha256'],'001')
        self.assertIsNone(frontmatter('# Texto'))

    def test_incorrect_and_missing_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'metadados.json';(root/'original.html').write_bytes(b'raw')
            wrong=audit_snapshot({'sha256':'0'*64,'url':'https://example.gov.br','coletado_em':'2026'},p,root,Hasher())
            self.assertIn('hash_divergente',wrong['problemas'])
            missing=audit_snapshot({},p,root,Hasher())
            self.assertIn('ausente_hash',missing['problemas'])
            self.assertIn('ausente_origem',missing['problemas'])
            self.assertIsNone(missing['verificacoes'][0]['confere'])

    def test_xsd_and_source_zip_have_separate_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'original.xsd').write_bytes(b'xsd');(root/'fonte.zip').write_bytes(b'zip')
            meta={'original':'original.xsd','sha256':hashlib.sha256(b'xsd').hexdigest(),'url':'u','coletado_em':'d','detalhes':{'zip_sha256':hashlib.sha256(b'zip').hexdigest()}}
            result=audit_snapshot(meta,root/'metadados.json',root,Hasher())
            self.assertEqual(result['problemas'],[])
            self.assertEqual(len(result['verificacoes']),2)

    def test_legitimate_duplicates_and_frontmatter_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);digest=hashlib.sha256(b'same').hexdigest()
            for name in ['mei','sebrae']:
                dest=root/name/'snapshot';dest.mkdir(parents=True);(dest/'original.html').write_bytes(b'same')
                (dest/'documento.md').write_text(f'---\nsource_url: https://example.gov.br\ncoletado_em: 2026\nsha256: {digest}\nrevisao_humana: pendente\n---\n',encoding='utf-8')
            result=collect(root)
            self.assertEqual(len(result['snapshots']),2)
            self.assertEqual(len(result['duplicacoes']),1)
            self.assertFalse(any(s['problemas'] for s in result['snapshots']))
            self.assertEqual(result['snapshots'][0]['revisao_humana'],'pendente')
            again=collect(root)
            self.assertEqual(again['arquivos_hasheados_nesta_execucao'],0)

    def test_multi_originals_use_individual_hashes_and_restrict_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'data';root.mkdir()
            original=root/'sample.zip';original.write_bytes(b'zip')
            outside=Path(tmp)/'outside.zip';outside.write_bytes(b'outside')
            meta={'url':'u','coletado_em':'d','sha256':'composite-identity','originais':[{'arquivo':str(original.resolve()),'source_url':'u','sha256':hashlib.sha256(b'zip').hexdigest(),'bytes':3}]}
            result=audit_snapshot(meta,root/'metadados.json',root,Hasher())
            self.assertEqual(result['problemas'],[])
            self.assertTrue(result['verificacoes'][0]['confere'])
            meta['originais'].append({'arquivo':str(outside.resolve()),'sha256':'x'})
            result=audit_snapshot(meta,root/'metadados.json',root,Hasher())
            self.assertIn('original_fora_raiz',result['problemas'])
            self.assertEqual(len(result['verificacoes']),1)
            meta['originais'][0]['sha256']='incorrect'
            result=audit_snapshot(meta,root/'metadados.json',root,Hasher())
            self.assertTrue(any(x.startswith('hash_divergente:') for x in result['problemas']))

    def test_manifest_errors_and_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'mei';folder.mkdir()
            (folder/'manifesto.json').write_text(json.dumps({'fontes':[{'status':'erro','erro':'404'}]}))
            (folder/'original.pdf').write_bytes(b'orphan')
            ignored=root/'inspection';ignored.mkdir();(ignored/'original.pdf').write_bytes(b'ignore')
            result=collect(root)
            self.assertEqual(result['originais_sem_metadados'],['mei/original.pdf'])
            self.assertEqual(result['manifestos_mais_recentes'][0]['quantidade_erros'],1)

if __name__=='__main__':unittest.main()


def test_recovered_manifest_history_is_not_active_failure():
    from backend.crawler.catalogo import manifest_entries
    assert list(manifest_entries({'status':'extraido','historico':[{'erro':'timeout'}]})) == []
    assert len(list(manifest_entries({'status':'erro','erro':'timeout'}))) == 1

def test_catalog_includes_cnae_notes_and_rfb_interpretations(tmp_path):
    from backend.crawler.catalogo import collect
    for category in ('notas-cnae', 'consultas-rfb'):
        dest=tmp_path/category/'snapshot';dest.mkdir(parents=True)
        (dest/'original.json').write_bytes(b'{}')
        meta={'source_url':'https://example.gov.br','coletado_em':'2026-11-04','sha256':hashlib.sha256(b'{}').hexdigest()}
        (dest/'metadados.json').write_text(json.dumps(meta),encoding='utf-8')
    result=collect(tmp_path)
    coverage={entry['pasta']:entry for entry in result['cobertura_sete_frentes']}
    assert coverage['notas-cnae']['snapshots']==1
    assert coverage['consultas-rfb']['snapshots']==1
    assert coverage['mei']['snapshots']==0

def test_catalog_does_not_mark_running_or_partial_collection_complete(tmp_path):
    from backend.crawler.catalogo import collect
    dest=tmp_path/'consultas-rfb'/'1';dest.mkdir(parents=True)
    (dest/'original.json').write_bytes(b'{}')
    meta={'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'{}').hexdigest()}
    (dest/'metadados.json').write_text(json.dumps(meta),encoding='utf-8')
    manifest=dest.parent/'manifesto.json'
    for status,expected in [('em_andamento','coleta_em_andamento'),('parcial','coletada_com_pendencias'),('coleta_concluida','coletada_revisao_pendente')]:
        manifest.write_text(json.dumps({'status':status}),encoding='utf-8')
        result=collect(tmp_path)
        entry=next(x for x in result['cobertura_sete_frentes'] if x['pasta']=='consultas-rfb')
        assert entry['situacao']==expected

def test_catalog_checks_declared_markdown_bytes(tmp_path):
    from backend.crawler.catalogo import audit_snapshot, Hasher
    (tmp_path/'original.json').write_bytes(b'{}')
    (tmp_path/'documento.md').write_bytes(b'# Texto\r\n')
    meta={'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'{}').hexdigest(), 'markdown_sha256':hashlib.sha256(b'# Texto\n').hexdigest()}
    record=audit_snapshot(meta,tmp_path/'metadados.json',tmp_path,Hasher())
    assert 'hash_markdown_divergente' in record['problemas']
    meta['markdown_sha256']=hashlib.sha256((tmp_path/'documento.md').read_bytes()).hexdigest()
    assert audit_snapshot(meta,tmp_path/'metadados.json',tmp_path,Hasher())['problemas']==[]
    (tmp_path/'documento.md').unlink()
    assert 'markdown_ausente' in audit_snapshot(meta,tmp_path/'metadados.json',tmp_path,Hasher())['problemas']

def test_catalog_covers_steps_three_through_eight(tmp_path):
    from backend.crawler.catalogo import collect
    categories=('obrigacoes-avancadas','legislacao-complementar','distrital-df','notas-tecnicas-fiscais','regularizacao-fiscal','indicadores-empresariais')
    for category in categories:
        dest=tmp_path/category/'snapshot';dest.mkdir(parents=True)
        (dest/'original.json').write_bytes(b'{}')
        (dest/'metadados.json').write_text(json.dumps({'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'{}').hexdigest()}),encoding='utf-8')
    result=collect(tmp_path)
    coverage={entry['pasta']:entry for entry in result['cobertura_frentes']}
    assert all(coverage[category]['snapshots']==1 for category in categories)
    assert result['cobertura_sete_frentes']==result['cobertura_frentes']

def test_catalog_reports_extraction_and_schema_pending(tmp_path):
    from backend.crawler.catalogo import collect
    dest=tmp_path/'obrigacoes-avancadas'/'snapshot';dest.mkdir(parents=True)
    (dest/'original.zip').write_bytes(b'zip')
    meta={'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'zip').hexdigest(),'status':'dependencias_pendentes'}
    (dest/'metadados.json').write_text(json.dumps(meta),encoding='utf-8')
    result=collect(tmp_path)
    entry=next(x for x in result['cobertura_frentes'] if x['pasta']=='obrigacoes-avancadas')
    assert entry['pendencias_extracao']==1 and entry['situacao']=='coletada_com_pendencias'
    assert entry['problemas_integridade']==0

def test_recovered_transport_attempt_is_history_not_active_failure():
    from backend.crawler.catalogo import manifest_entries
    for key in ('ultima_tentativa','ultima_tentativa_html'):
        recovered={'status':'coletado',key:{'status':'indisponivel','erro':'backend'}}
        assert list(manifest_entries(recovered))==[]
    assert len(list(manifest_entries({'status':'indisponivel','erro':'HTTP403'})))==1

def test_catalog_includes_high_priority_df_collections(tmp_path):
    from backend.crawler.catalogo import collect
    categories=('cnpj-df','xmls-exemplo','calendario-df')
    for category in categories:
        dest=tmp_path/category/'snapshot';dest.mkdir(parents=True)
        (dest/'original.json').write_bytes(b'{}')
        (dest/'metadados.json').write_text(json.dumps({'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'{}').hexdigest()}),encoding='utf-8')
    result=collect(tmp_path)
    coverage={entry['pasta']:entry for entry in result['cobertura_frentes']}
    assert all(coverage[category]['snapshots']==1 for category in categories)

def test_catalog_includes_sped_and_profit_tax_expansion(tmp_path):
    from backend.crawler.catalogo import collect
    for category in ('sped-complementar','tributacao-lucro'):
        dest=tmp_path/category/'snapshot';dest.mkdir(parents=True)
        (dest/'original.json').write_bytes(b'{}')
        (dest/'metadados.json').write_text(json.dumps({'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'{}').hexdigest()}),encoding='utf-8')
    coverage={entry['pasta']:entry for entry in collect(tmp_path)['cobertura_frentes']}
    assert coverage['sped-complementar']['snapshots']==1
    assert coverage['tributacao-lucro']['snapshots']==1


def test_named_markdown_hash_is_audited(tmp_path):
    raw=b'original'; markdown=b'# Norma'
    (tmp_path/'original.html').write_bytes(raw)
    (tmp_path/'legislacao.md').write_bytes(markdown)
    meta={'source_url':'https://example.gov.br','coletado_em':'2026',
          'sha256':hashlib.sha256(raw).hexdigest(),
          'markdown_arquivo':'legislacao.md','markdown_sha256':hashlib.sha256(markdown).hexdigest()}
    assert audit_snapshot(meta,tmp_path/'metadados.json',tmp_path,Hasher())['problemas']==[]
    (tmp_path/'legislacao.md').write_bytes(b'alterado')
    assert 'hash_markdown_divergente' in audit_snapshot(meta,tmp_path/'metadados.json',tmp_path,Hasher())['problemas']


def test_cached_original_receipt_is_not_semantic_snapshot_or_orphan(tmp_path):
    folder=tmp_path/'cache'/'unselected';folder.mkdir(parents=True)
    raw=folder/'original.json';raw.write_bytes(b'cached')
    receipt=raw.with_name(raw.name+'.receipt.json')
    receipt.write_text(json.dumps({'source_url':'https://example.gov.br','coletado_em':'2026','sha256':hashlib.sha256(b'cached').hexdigest()}))
    result=collect(tmp_path)
    assert result['snapshots']==[] and result['originais_sem_metadados']==[]
    assert len(result['requisicoes_cache_sem_snapshot'])==1
    raw.write_bytes(b'changed')
    result=collect(tmp_path)
    assert result['originais_sem_metadados']==['cache/unselected/original.json'] and result['erros_leitura']
