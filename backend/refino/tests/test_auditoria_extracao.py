import hashlib
import json

from backend.refino.auditoria_extracao import auditar, auditar_lote, carregar_limites, duplicatas_fisicas
from backend.refino.pipeline import load_policy, run

LIMITES = carregar_limites()
TEXTO = 'Art. 1 Esta norma trata do Simples Nacional e do MEI. ' * 40


def _arquivo(root, rel, conteudo):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(conteudo)
    return dict(arquivo=rel, sha256=hashlib.sha256(conteudo).hexdigest())


def _ocorrencia(root, pasta, markdown=None, originais=None, meta_extra=None):
    folder = root / pasta
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'metadados.json').write_text(json.dumps({'source_id': pasta, 'titulo': 'Lei X', **(meta_extra or {})}), encoding='utf8')
    md_ref = None
    if markdown is not None:
        (folder / 'documento.md').write_text(markdown, encoding='utf8')
        md_ref = (folder / 'documento.md').relative_to(root).as_posix()
    return dict(id=pasta.replace('/', '-'), documento_id='doc-' + pasta.replace('/', '-'), classificacao='nucleo',
                frente=pasta.split('/')[0], metadados_ref=(folder / 'metadados.json').relative_to(root).as_posix(),
                markdown_ref=md_ref, originais=originais or [], hashes_originais=[])


def _html(texto, extra=b'', tabela=b''):
    return (b'<html><head><title>t</title><script>var x = 1;</script></head><body><p>' + texto.encode('utf8')
            + b'</p>' + tabela + b'</body>' + extra + b'</html>')


def _pdf(paginas):
    """PDF mínimo; página None não tem camada de texto (simula página só com imagem)."""
    n = len(paginas)
    objetos = {1: b'<< /Type /Catalog /Pages 2 0 R >>',
               2: b'<< /Type /Pages /Kids [' + b' '.join(b'%d 0 R' % (4 + 2 * i) for i in range(n)) + b'] /Count %d >>' % n,
               3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'}
    for i, texto in enumerate(paginas):
        stream = b'' if texto is None else b'BT /F1 12 Tf 20 200 Td (' + texto.encode('latin1') + b') Tj ET'
        objetos[4 + 2 * i] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] '
                              b'/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>' % (5 + 2 * i))
        objetos[5 + 2 * i] = b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream'
    corpo = b'%PDF-1.4\n'
    offsets = {}
    for num in sorted(objetos):
        offsets[num] = len(corpo)
        corpo += b'%d 0 obj\n' % num + objetos[num] + b'\nendobj\n'
    xref = len(corpo)
    corpo += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objetos) + 1)
    corpo += b''.join(b'%010d 00000 n \n' % offsets[num] for num in sorted(objetos))
    corpo += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objetos) + 1, xref)
    return corpo


def test_pdf_escaneado_e_detectado(tmp_path):
    original = _arquivo(tmp_path, 'lei/original.pdf', _pdf([None, None]))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\nTexto.\n', originais=[original])
    resultado = auditar(occ, tmp_path, LIMITES)
    assert 'pdf_sem_camada_de_texto' in resultado['problemas']
    assert resultado['paginas'] == 2
    assert resultado['paginas_sem_texto'] == 2


def test_pdf_com_pagina_vazia_e_detectado_e_pdf_com_texto_nao(tmp_path):
    misto = _arquivo(tmp_path, 'mista/original.pdf', _pdf(['Art. 1 texto', None]))
    texto = _arquivo(tmp_path, 'texto/original.pdf', _pdf(['Art. 1 texto', 'Art. 2 texto']))
    mista = auditar(_ocorrencia(tmp_path, 'mista', markdown='x', originais=[misto]), tmp_path, LIMITES)
    completo = auditar(_ocorrencia(tmp_path, 'texto', markdown='Art. 1 texto Art. 2 texto', originais=[texto]), tmp_path, LIMITES)
    assert 'paginas_vazias' in mista['problemas'] and mista['paginas_sem_texto'] == 1
    assert completo['problemas'] == [] and completo['paginas'] == 2


def test_html_com_tabela_perdida_e_detectado(tmp_path):
    tabela = b'<table><tr><td>Faixa</td><td>5%</td></tr><tr><td>Faixa 2</td><td>7%</td></tr></table>'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    assert 'tabelas_perdidas' in auditar(occ, tmp_path, LIMITES)['problemas']


def test_extracao_completa_nao_gera_problema(tmp_path):
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['problemas'] == []
    assert resultado['razao_texto'] >= LIMITES['razao_texto_minima']


def test_original_ausente_e_problema_e_nao_erro_fatal(tmp_path):
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n',
                      originais=[dict(arquivo='lei/nao-existe.html', sha256='0' * 64)])
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['problemas'] == ['original_ausente']


def test_caminho_absoluto_herdado_e_remapeado_com_hash_conferido(tmp_path):
    raiz = tmp_path / 'data'
    original = _arquivo(raiz, 'lei/original.html', _html(TEXTO))
    herdado = dict(arquivo='E:\\RES-IA-Challenge-2\\backend\\crawler\\data\\lei\\original.html', sha256=original['sha256'])
    ok = auditar(_ocorrencia(raiz, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[herdado]), raiz, LIMITES)
    assert ok['original_ref'] == 'lei/original.html'
    assert 'original_divergente' not in ok['problemas'] and 'original_ausente' not in ok['problemas']
    errado = dict(herdado, sha256='f' * 64)
    divergente = auditar(_ocorrencia(raiz, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[errado]), raiz, LIMITES)
    assert 'original_divergente' in divergente['problemas']


def test_duplicata_fisica_nao_toca_nos_arquivos(tmp_path):
    raiz = tmp_path / 'data'
    a = _arquivo(raiz, 'lei-a/original.html', _html(TEXTO))
    b = _arquivo(raiz, 'lei-b/original.html', _html(TEXTO))
    antes = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in raiz.rglob('*') if p.is_file()}
    ocorrencias = [dict(id='a', documento_id='da', classificacao='nucleo', hashes_originais=[a['sha256']]),
                   dict(id='b', documento_id='db', classificacao='nucleo', hashes_originais=[b['sha256']]),
                   dict(id='c', documento_id='dc', classificacao='nucleo', hashes_originais=['1' * 64])]
    grupos = list(duplicatas_fisicas(ocorrencias))
    assert grupos == [dict(hash_original=a['sha256'], ocorrencias=['a', 'b'], documentos=['da', 'db'])]
    depois = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in raiz.rglob('*') if p.is_file()}
    assert antes == depois


def test_problema_vai_para_fila_e_nao_sai_do_indice(tmp_path):
    raiz = tmp_path / 'data'
    texto = 'Simples Nacional e MEI. ' * 30
    corpo = _html(texto, extra=b'<div>' + b'x' * 3000 + b'</div>')
    original = _arquivo(raiz, 'legislacao/lei-x/original.html', corpo)
    _ocorrencia(raiz, 'legislacao/lei-x', markdown='# Lei X\n\n' + texto + '\n', originais=[original],
                meta_extra=dict(tipo='legislacao', source_url='https://www.planalto.gov.br/ccivil_03/leis/lei-x.htm'))
    catalogo = tmp_path / 'catalogo.json'
    catalogo.write_text(json.dumps({'snapshots': [dict(metadados='legislacao/lei-x/metadados.json',
                                                       origem='https://www.planalto.gov.br/ccivil_03/leis/lei-x.htm', problemas=[])]}), encoding='utf8')
    saida = tmp_path / 'saida'
    report = run(root=raiz, catalog_path=catalogo, output=saida, workers=1)
    pasta = saida / report['run_id']
    fila = [json.loads(l) for l in (pasta / 'fila_revisao.jsonl').read_bytes().splitlines() if l.strip()]
    auditoria = [r for r in fila if r.get('tipo') == 'auditoria_extracao']
    assert auditoria and 'body_precoce' in auditoria[0]['problemas']
    indice = [json.loads(l) for l in (pasta / 'indice_nucleo.jsonl').read_bytes().splitlines() if l.strip()]
    assert auditoria[0]['documento_id'] in {d['documento_id'] for d in indice}


def test_limites_vem_de_politica_json():
    politica = load_policy()
    assert politica['auditoria_extracao']['razao_texto_minima'] == 0.5
    assert politica['auditoria_extracao']['bytes_apos_body_precoce'] == 2000
    assert carregar_limites() == politica['auditoria_extracao']


def test_lote_so_devolve_ocorrencias_com_problema(tmp_path):
    ok = _arquivo(tmp_path, 'ok/original.html', _html(TEXTO))
    curta = _arquivo(tmp_path, 'curta/original.html', _html('x ' * 3000))
    ocorrencias = [_ocorrencia(tmp_path, 'ok', markdown='# Lei\n\n' + TEXTO + '\n', originais=[ok]),
                   _ocorrencia(tmp_path, 'curta', markdown='Curto.\n', originais=[curta])]
    linhas = auditar_lote(ocorrencias, tmp_path, LIMITES, workers=2)
    assert [l['id'] for l in linhas] == ['curta']
    assert 'extracao_curta' in linhas[0]['problemas']


def test_pdf_em_paralelo_nao_falha(tmp_path):
    """pdfium não é thread-safe: auditoria paralela de PDFs deve ler todos sem 'original_ilegivel'."""
    ocorrencias = []
    for i in range(12):
        original = _arquivo(tmp_path, f'pdf-{i}/original.pdf', _pdf([f'Art. {i} texto', 'Art. 2 texto']))
        ocorrencias.append(_ocorrencia(tmp_path, f'pdf-{i}', markdown=f'Art. {i} texto Art. 2 texto\n', originais=[original]))
    assert auditar_lote(ocorrencias, tmp_path, LIMITES, workers=8) == []


def test_tabela_de_layout_com_texto_no_markdown_nao_e_perdida(tmp_path):
    tabela = b'<table><tr><td>Processo</td><td>000.128.000.418</td></tr></table>'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    md = '# Lei\n\n' + TEXTO + '\n\nProcesso 000.128.000.418\n'
    occ = _ocorrencia(tmp_path, 'lei', markdown=md, originais=[original])
    assert 'tabelas_perdidas' not in auditar(occ, tmp_path, LIMITES)['problemas']
