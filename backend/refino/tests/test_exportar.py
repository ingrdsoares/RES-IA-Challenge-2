import json
import hashlib
import zipfile
import pytest
from backend.refino.exportar import package

def test_portable_bundle_hashes_and_no_secrets_or_raw(tmp_path):
    repo=tmp_path/'repo';(repo/'handoff/refino').mkdir(parents=True)
    state=repo/'handoff/refino/estado.json';state.write_text(json.dumps({'run_id':'abc'}))
    (repo/'handoff/refino/CONTINUAR.md').write_text('Continue aqui')
    run=repo/'backend/refino/data/abc';run.mkdir(parents=True);(run/'manifesto.json').write_text('{}')
    (run/'conteudos').mkdir();(run/'conteudos/raw.md').write_text('included')
    (run/'manifesto.json').write_text(json.dumps({'run_id':'abc','artefatos_sha256':{'conteudos/raw.md':hashlib.sha256(b'included').hexdigest()}}))
    (repo/'.env').write_text('DO_NOT_EXPORT')
    (repo/'README.md').write_text('Projeto')
    report=package(repo,tmp_path/'bundle.zip',state)
    with zipfile.ZipFile(report['arquivo']) as z:
        assert 'handoff/refino/CONTINUAR.md' in z.namelist()
        assert 'backend/refino/data/abc/manifesto.json' in z.namelist()
        assert not any('.env' in n for n in z.namelist())
        assert 'backend/refino/data/abc/conteudos/raw.md' in z.namelist()
        manifest=json.loads(z.read('MANIFESTO-HANDOFF.json'))
        assert manifest['dados_brutos_incluidos'] is False and manifest['textos_refinados_incluidos'] is True
    assert report['verificado'] and (tmp_path/'bundle.zip.sha256').exists()
    with pytest.raises(FileExistsError):package(repo,tmp_path/'bundle.zip',state)


def test_incomplete_refined_snapshot_fails_before_creating_zip(tmp_path):
    repo=tmp_path/'repo';(repo/'handoff/refino').mkdir(parents=True)
    state=repo/'handoff/refino/estado.json';state.write_text(json.dumps({'run_id':'abc'}))
    run=repo/'backend/refino/data/abc';run.mkdir(parents=True)
    (run/'manifesto.json').write_text(json.dumps({'run_id':'abc','artefatos_sha256':{'conteudos/missing.md':'0'*64}}))
    with pytest.raises(ValueError,match='incompleto/corrompido'):package(repo,tmp_path/'bundle.zip',state)
    assert not (tmp_path/'bundle.zip').exists()


def test_busca_derivada_fica_fora_do_pacote_sem_quebrar_verificacao(tmp_path):
    repo=tmp_path/'repo';(repo/'handoff/refino').mkdir(parents=True)
    state=repo/'handoff/refino/estado.json';state.write_text(json.dumps({'run_id':'abc'}))
    (repo/'handoff/refino/CONTINUAR.md').write_text('Continue aqui')
    run=repo/'backend/refino/data/abc';(run/'conteudos').mkdir(parents=True);(run/'busca').mkdir()
    (run/'conteudos/raw.md').write_text('texto integral')
    (run/'busca/raw.md').write_text('texto integral limpo')
    (run/'manifesto.json').write_text(json.dumps({'run_id':'abc','artefatos_sha256':{'conteudos/raw.md':hashlib.sha256(b'texto integral').hexdigest(),'busca/raw.md':hashlib.sha256(b'texto integral limpo').hexdigest()}}))
    (repo/'README.md').write_text('Projeto')
    report=package(repo,tmp_path/'bundle.zip',state)
    with zipfile.ZipFile(report['arquivo']) as z:
        names=z.namelist()
        assert 'backend/refino/data/abc/conteudos/raw.md' in names
        assert not any('/busca/' in n for n in names)
        manifest=json.loads(z.read('MANIFESTO-HANDOFF.json'))
        assert not any('/busca/' in n for n in manifest['arquivos'])
    assert report['verificado']
