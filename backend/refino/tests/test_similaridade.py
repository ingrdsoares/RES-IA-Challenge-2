import hashlib
import json
from pathlib import Path

import pytest

from backend.refino import similaridade
from backend.refino.pipeline import run
from backend.refino.similaridade import comparar, suspeitos

PARAMS = json.loads((Path(__file__).resolve().parents[1] / 'politica.json').read_bytes())['similaridade']


def palavras(n, prefixo='pal'):
    return [prefixo + chr(97 + i // 26) + chr(97 + i % 26) for i in range(n)]


def escrever(tmp_path, nome, texto):
    p = tmp_path / (nome + '.md')
    p.write_text(texto, encoding='utf8')
    return p


def test_so_numeros_e_classificado(tmp_path):
    base = ' '.join(palavras(80))
    textos = {'a': escrever(tmp_path, 'a', base + ' 100 reais'), 'b': escrever(tmp_path, 'b', base + ' 200 reais')}
    pares = comparar(textos, params=PARAMS, workers=1)
    assert len(pares) == 1
    par = pares[0]
    assert (par.a, par.b) == ('a', 'b')
    assert par.jaccard >= 0.6
    assert par.classe == 'so_numeros'
    assert par.n_dif == 2
    assert set(par.tokens_dif) == {'100', '200'}


def test_so_formatacao_entre_documentos_diferentes_vira_suspeito(tmp_path):
    base = palavras(80)
    textos = {'a': escrever(tmp_path, 'a', ' '.join(base)), 'b': escrever(tmp_path, 'b', '. '.join(base) + '.')}
    pares = comparar(textos, params=PARAMS, workers=1, documentos={'a': {'doc1'}, 'b': {'doc2'}})
    assert len(pares) == 1
    assert pares[0].classe == 'so_formatacao'
    assert pares[0].n_dif == 0
    assert pares[0].relacao == 'documentos_diferentes'
    assert suspeitos(pares) == pares

    mesmo = comparar(textos, params=PARAMS, workers=1, documentos={'a': {'doc1'}, 'b': {'doc1'}})
    assert mesmo[0].relacao == 'mesmo_documento'


def test_resultado_e_deterministico(tmp_path):
    base = palavras(120)
    textos = {}
    for i in range(6):
        corpo = list(base)
        corpo[i * 10] = 'troca' + chr(97 + i)
        textos[f'c{i}'] = escrever(tmp_path, f'c{i}', ' '.join(corpo))
    textos['outro'] = escrever(tmp_path, 'outro', ' '.join(palavras(120, 'zzz')))
    primeiro = comparar(textos, params=PARAMS, workers=1)
    assert primeiro
    assert all(p.jaccard >= 0.6 for p in primeiro)
    assert not any('outro' in (p.a, p.b) for p in primeiro)
    assert comparar(textos, params=PARAMS, workers=1) == primeiro
    assert comparar(textos, params=PARAMS, workers=2) == primeiro


def test_texto_curto_nao_quebra(tmp_path):
    textos = {
        'vazio': escrever(tmp_path, 'vazio', ''),
        'curto': escrever(tmp_path, 'curto', 'um dois tres'),
        'curto2': escrever(tmp_path, 'curto2', 'um dois tres'),
        'normal': escrever(tmp_path, 'normal', ' '.join(palavras(80))),
    }
    pares = comparar(textos, params=PARAMS, workers=1)
    assert isinstance(pares, list)
    assert not any(({p.a, p.b} & {'vazio', 'curto', 'curto2'}) for p in pares)


def test_conjunto_com_mais_de_50_iguais_nao_explode(tmp_path):
    base = palavras(200)
    textos = {f'v{i}': escrever(tmp_path, f'v{i}', ' '.join(base + ['fim' + chr(97 + i // 26) + chr(97 + i % 26)])) for i in range(60)}
    pares = comparar(textos, params=PARAMS, workers=1)
    assert pares
    assert all(p.jaccard >= 0.6 for p in pares)
    assert len(pares) < 60 * 59 // 2


def test_textos_nao_sao_relidos_a_cada_par(tmp_path, monkeypatch):
    base = palavras(80)
    n = 300
    textos = {f'd{i:03d}': escrever(tmp_path, f'd{i:03d}', ' '.join(base + ['fim' + chr(97 + i // 26) + chr(97 + i % 26)])) for i in range(n)}
    chamadas = []
    original = similaridade.tokens

    def contado(texto):
        chamadas.append(1)
        return original(texto)

    monkeypatch.setattr(similaridade, 'tokens', contado)
    pares = comparar(textos, params=PARAMS, workers=1)
    assert len(pares) > n
    assert len(chamadas) <= 2 * n  # uma leitura para assinatura e uma para classificar; sem releitura por par


def test_similaridade_nao_altera_indice_nem_documentos(tmp_path, monkeypatch):
    base = ' '.join(palavras(80))
    items = [('a', 'https://a.gov.br/law', '# Lei A\n' + base + ' 100 reais', 'legislacao'),
             ('b', 'https://b.gov.br/law', '# Lei B\n' + base + ' 200 reais', 'legislacao')]
    root = tmp_path / 'raw'
    catalog = corpus(root, items)

    com = run(root, catalog, tmp_path / 'com')
    pasta_com = tmp_path / 'com' / com['run_id']
    assert (pasta_com / 'similaridade.jsonl').read_text(encoding='utf8').strip()
    assert (pasta_com / 'suspeitos.jsonl').is_file()

    monkeypatch.setattr(similaridade, 'comparar', lambda *a, **k: [])
    sem = run(root, catalog, tmp_path / 'sem')
    pasta_sem = tmp_path / 'sem' / sem['run_id']
    assert com['run_id'] == sem['run_id']
    assert (pasta_sem / 'similaridade.jsonl').read_text(encoding='utf8') == ''
    for nome in ('indice_nucleo.jsonl', 'documentos.jsonl', 'versoes.jsonl', 'ocorrencias.jsonl', 'conteudos.jsonl'):
        assert (pasta_com / nome).read_bytes() == (pasta_sem / nome).read_bytes(), nome


def test_familias_de_dados_ficam_fora(tmp_path):
    base = ' '.join(palavras(80))
    items = [('a', 'https://a.gov.br/law', '# Lei A\n' + base, 'legislacao'),
             ('b', 'https://b.gov.br/law', '# Lei B\n' + base + ' extra', 'legislacao'),
             ('cnpj', 'https://example.gov.br/cnpj', '# Empresas\n' + base, 'cnpj-df-censo')]
    root = tmp_path / 'raw'
    catalog = corpus(root, items)
    report = run(root, catalog, tmp_path / 'out')
    pasta = tmp_path / 'out' / report['run_id']
    cid = {r['source_url']: r['conteudo_id'] for r in rows(pasta / 'ocorrencias.jsonl')}
    assert cid['https://example.gov.br/cnpj'] is None
    pares = rows(pasta / 'similaridade.jsonl')
    assert len(pares) == 1
    assert {pares[0]['a'], pares[0]['b']} == {cid['https://a.gov.br/law'], cid['https://b.gov.br/law']}


def test_cnpj_com_status_erro_nao_entra_na_similaridade(tmp_path):
    base = ' '.join(palavras(80))
    items = [('a', 'https://a.gov.br/law', '# Lei A\n' + base, 'legislacao'),
             ('b', 'https://b.gov.br/law', '# Lei B\n' + base + ' extra', 'legislacao'),
             ('cnpj', 'https://example.gov.br/cnpj', '# Empresas\n' + base + ' extra', 'cnpj-df-censo', {'status': 'erro'})]
    root = tmp_path / 'raw'
    report = run(root, corpus(root, items), tmp_path / 'out')
    pasta = tmp_path / 'out' / report['run_id']
    cid = {r['source_url']: r['conteudo_id'] for r in rows(pasta / 'ocorrencias.jsonl')}
    assert cid['https://example.gov.br/cnpj'] is not None  # o texto existe no refino; a similaridade não pode vê-lo
    pares = rows(pasta / 'similaridade.jsonl')
    assert len(pares) == 1
    assert {pares[0]['a'], pares[0]['b']} == {cid['https://a.gov.br/law'], cid['https://b.gov.br/law']}


def test_chave_de_parametros_ausente_falha_alto(tmp_path):
    base = ' '.join(palavras(80))
    items = [('a', 'https://a.gov.br/law', '# Lei A\n' + base, 'legislacao')]
    root = tmp_path / 'raw'
    politica = json.loads((Path(__file__).resolve().parents[1] / 'politica.json').read_bytes())
    del politica['similaridade']
    politica_sem = tmp_path / 'politica.json'
    politica_sem.write_text(json.dumps(politica), encoding='utf8')
    with pytest.raises(KeyError, match='similaridade'):
        run(root, corpus(root, items), tmp_path / 'out', policy_path=politica_sem)


def corpus(root, items):
    snapshots = []
    for name, url, text, front, *extra in items:
        pasta = root / front / name
        pasta.mkdir(parents=True)
        md = pasta / 'documento.md'
        md.write_text(text, encoding='utf8')
        meta = dict(source_url=url, source_id=name, titulo='Documento', sha256=hashlib.sha256(url.encode()).hexdigest(),
                    coletado_em='2026-11-05', tipo='legislacao', status='extraido', markdown_arquivo='documento.md',
                    markdown_sha256=hashlib.sha256(md.read_bytes()).hexdigest())
        meta.update(extra[0] if extra else {})
        mp = pasta / 'metadados.json'
        mp.write_text(json.dumps(meta), encoding='utf8')
        snapshots.append(dict(diretorio=pasta.relative_to(root).as_posix(), metadados=mp.relative_to(root).as_posix(), origem=url, problemas=[]))
    catalog = root / 'catalogo.json'
    catalog.write_text(json.dumps(dict(snapshots=snapshots, executado_em='2026-11-05')), encoding='utf8')
    return catalog


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line]
