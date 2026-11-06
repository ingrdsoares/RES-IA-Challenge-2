import hashlib
import json

from backend.refino.auditoria_extracao import auditar, auditar_lote, carregar_limites, duplicatas_fisicas
from backend.refino.pipeline import load_policy, run

LIMITES = carregar_limites()
TEXTO = 'Art. 1 Esta norma trata do Simples Nacional e do MEI. ' * 40
RECEITA = 'https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/126880/visao/multivigente'


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


def _html(texto, extra=b'', tabela=b'', antes=b''):
    return (b'<html><head><title>t</title><script>var x = 1;</script></head><body>' + antes + b'<p>' + texto.encode('utf8')
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
    tabela = b'<table><tr><td>Aliquota</td><td>5%</td></tr><tr><td>Faixa 2</td><td>7%</td></tr></table>'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    assert 'tabelas_perdidas' in auditar(occ, tmp_path, LIMITES)['problemas']


def test_tabela_real_presente_no_markdown_nao_e_flagrada(tmp_path):
    """Forma real de consultas-df-amplas: tabela NCM com células que aparecem no Markdown."""
    tabela = ('<table><tr><th>Item</th><th>NCM/SH</th><th>Descrição das mercadorias</th></tr>'
              '<tr><td>1</td><td>3816.00.1 3824.50.00</td><td>Argamassas</td></tr>'
              '<tr><td>VI</td><td>2707, 2713</td><td>Produtos impermeabilizantes</td></tr></table>').encode('utf8')
    md = '# Lei\n\n' + TEXTO + '\n\n| Item | NCM/SH | Descrição das mercadorias |\n| 1 | 3816.00.1 3824.50.00 | Argamassas |\n| VI | 2707, 2713 | Produtos impermeabilizantes |\n'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    occ = _ocorrencia(tmp_path, 'lei', markdown=md, originais=[original])
    assert 'tabelas_perdidas' not in auditar(occ, tmp_path, LIMITES)['problemas']


def test_tabela_widget_com_valores_nulos_e_ignorada(tmp_path):
    """Widget de visitantes do DOU: rótulos com valores null não são conteúdo."""
    widget = ('<table><tr><td>Páginas vistas</td><td>null null  null</td></tr>'
              '<tr><td>Visitantes únicos</td><td>null null  null</td></tr></table>').encode('utf8')
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=widget))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    assert 'tabelas_perdidas' not in auditar(occ, tmp_path, LIMITES)['problemas']


def test_tabela_sem_markdown_vira_sem_markdown_e_nao_perda(tmp_path):
    tabela = b'<table><tr><td>Aliquota</td><td>5%</td></tr></table>'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    occ = _ocorrencia(tmp_path, 'lei', markdown=None, originais=[original])
    problemas = auditar(occ, tmp_path, LIMITES)['problemas']
    assert problemas.count('sem_markdown') == 1
    assert 'tabelas_perdidas' not in problemas


def test_extracao_completa_nao_gera_problema(tmp_path):
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['problemas'] == []
    assert resultado['razao_texto'] >= LIMITES['razao_texto_minima']


def test_extracao_curta_ignora_navegacao_no_denominador(tmp_path):
    nav = b'<nav>' + b'Menu principal Entrar Cadastre-se Portal ' * 200 + b'</nav>'
    rodape = b'<footer>' + b'Rodape institucional de contato ' * 200 + b'</footer>'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, antes=nav, extra=rodape))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    resultado = auditar(occ, tmp_path, LIMITES)
    assert 'extracao_curta' not in resultado['problemas']
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
    corpo = _html(texto, extra=b'<div>' + b'Conteudo novo sem registro no Markdown ' * 100 + b'</div>')
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


def test_extracao_curta_nao_entra_na_fila_nem_sai_do_indice(tmp_path):
    raiz = tmp_path / 'data'
    texto = 'Simples Nacional e MEI. ' * 30
    nav = b'<nav>' + b'Menu principal Entrar Cadastre-se Portal ' * 300 + b'</nav>'
    original = _arquivo(raiz, 'legislacao/lei-y/original.html', _html(texto, antes=nav))
    _ocorrencia(raiz, 'legislacao/lei-y', markdown='# Lei Y\n\nCurto.\n', originais=[original],
                meta_extra=dict(tipo='legislacao', source_url='https://www.planalto.gov.br/ccivil_03/leis/lei-y.htm'))
    catalogo = tmp_path / 'catalogo.json'
    catalogo.write_text(json.dumps({'snapshots': [dict(metadados='legislacao/lei-y/metadados.json',
                                                       origem='https://www.planalto.gov.br/ccivil_03/leis/lei-y.htm', problemas=[])]}), encoding='utf8')
    report = run(root=raiz, catalog_path=catalogo, output=tmp_path / 'saida', workers=1)
    pasta = tmp_path / 'saida' / report['run_id']
    auditoria = [json.loads(l) for l in (pasta / 'auditoria_extracao.jsonl').read_bytes().splitlines() if l.strip()]
    assert any('extracao_curta' in r['problemas'] for r in auditoria)
    fila = [json.loads(l) for l in (pasta / 'fila_revisao.jsonl').read_bytes().splitlines() if l.strip()]
    assert not any(r.get('tipo') == 'auditoria_extracao' for r in fila)
    indice = [json.loads(l) for l in (pasta / 'indice_nucleo.jsonl').read_bytes().splitlines() if l.strip()]
    assert any(d['documento_id'] in {r['documento_id'] for r in auditoria} for d in indice)


def test_body_precoce_so_com_conteudo_ausente_do_markdown(tmp_path):
    rodape = b'<footer>' + b'Ouvidoria e politica de privacidade do portal ' * 200 + b'</footer>'
    presente = b'<div>' + TEXTO.encode('utf8') + b'</div>'
    ausente = b'<div>' + b'Dispositivo exclusivo do original fora do Markdown ' * 100 + b'</div>'
    md = '# Lei\n\n' + TEXTO + '\n'
    so_rodape = _arquivo(tmp_path, 'a/original.html', _html(TEXTO, extra=rodape))
    so_presente = _arquivo(tmp_path, 'b/original.html', _html(TEXTO, extra=presente + b' ' * 3000))
    perdido = _arquivo(tmp_path, 'c/original.html', _html(TEXTO, extra=ausente))
    assert 'body_precoce' not in auditar(_ocorrencia(tmp_path, 'a', markdown=md, originais=[so_rodape]), tmp_path, LIMITES)['problemas']
    assert 'body_precoce' not in auditar(_ocorrencia(tmp_path, 'b', markdown=md, originais=[so_presente]), tmp_path, LIMITES)['problemas']
    assert 'body_precoce' in auditar(_ocorrencia(tmp_path, 'c', markdown=md, originais=[perdido]), tmp_path, LIMITES)['problemas']


def test_segmentos_receita_perdidos_e_detectados(tmp_path):
    segmentos = [f'Art. {i} O benefício fiscal número {i} aplica-se às receitas do contribuinte.' for i in range(20)]
    conteudo = json.dumps({'ementas': [], 'outrosSegmentos': [{'textoIntegra': f'<p>{s}</p>'} for s in segmentos]}).encode('utf8')
    original = _arquivo(tmp_path, 'ok/original.json', conteudo)
    cheio = _ocorrencia(tmp_path, 'ok', markdown='\n'.join(segmentos) + '\n', originais=[original], meta_extra=dict(source_url=RECEITA))
    assert 'segmentos_perdidos' not in auditar(cheio, tmp_path, LIMITES)['problemas']
    original2 = _arquivo(tmp_path, 'falha/original.json', conteudo)
    faltando = _ocorrencia(tmp_path, 'falha', markdown='\n'.join(segmentos[:18]) + '\n', originais=[original2], meta_extra=dict(source_url=RECEITA))
    assert 'segmentos_perdidos' in auditar(faltando, tmp_path, LIMITES)['problemas']


def test_json_fora_da_receita_so_conta_sem_verificacao(tmp_path):
    original = _arquivo(tmp_path, 'x/original.json', json.dumps({'texto': 'algo qualquer grande o bastante'}).encode('utf8'))
    occ = _ocorrencia(tmp_path, 'x', markdown='algo', originais=[original], meta_extra=dict(source_url='https://www.gov.br/x'))
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['sem_verificacao'] is True
    assert 'segmentos_perdidos' not in resultado['problemas']


def test_tabelas_json_corrompido_vira_problema_e_nao_aborta(tmp_path):
    tabela = b'<table><tr><td>Aliquota</td><td>5%</td></tr></table>'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    (tmp_path / 'lei' / 'tabelas.json').write_text('[{"truncado": ', encoding='utf8')
    resultado = auditar(occ, tmp_path, LIMITES)
    assert 'tabelas_json_corrompido' in resultado['problemas']


def test_limites_vem_de_politica_json():
    politica = load_policy()
    assert politica['auditoria_extracao']['razao_texto_minima'] == 0.5
    assert politica['auditoria_extracao']['bytes_apos_body_precoce'] == 2000
    assert carregar_limites() == politica['auditoria_extracao']


def test_lote_devolve_todas_as_linhas_com_problemas_marcados(tmp_path):
    ok = _arquivo(tmp_path, 'ok/original.html', _html(TEXTO))
    curta = _arquivo(tmp_path, 'curta/original.html', _html('x ' * 3000))
    ocorrencias = [_ocorrencia(tmp_path, 'ok', markdown='# Lei\n\n' + TEXTO + '\n', originais=[ok]),
                   _ocorrencia(tmp_path, 'curta', markdown='Curto.\n', originais=[curta])]
    linhas = {l['id']: l for l in auditar_lote(ocorrencias, tmp_path, LIMITES, workers=2)}
    assert linhas['ok']['problemas'] == []
    assert 'extracao_curta' in linhas['curta']['problemas']


def test_pdf_em_paralelo_nao_falha(tmp_path):
    """pdfium não é thread-safe: auditoria paralela de PDFs deve ler todos sem 'original_ilegivel'."""
    ocorrencias = []
    for i in range(12):
        original = _arquivo(tmp_path, f'pdf-{i}/original.pdf', _pdf([f'Art. {i} texto', 'Art. 2 texto']))
        ocorrencias.append(_ocorrencia(tmp_path, f'pdf-{i}', markdown=f'Art. {i} texto Art. 2 texto\n', originais=[original]))
    assert [l for l in auditar_lote(ocorrencias, tmp_path, LIMITES, workers=8) if l['problemas']] == []


def test_rodape_conhecido_depois_do_body_nao_e_perda(tmp_path):
    """Aviso padrão do portal fora de <footer> é boilerplate, não conteúdo perdido."""
    aviso = ('<div>Este conteúdo não substitui a publicação oficial na versão certificada. '
             'Este canal se destina a receber apenas manifestações relativas a falhas e inconsistências. ' * 20 + '</div>').encode('utf8')
    original = _arquivo(tmp_path, 'a/original.html', _html(TEXTO, extra=aviso + b' ' * 3000))
    occ = _ocorrencia(tmp_path, 'a', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    assert 'body_precoce' not in auditar(occ, tmp_path, LIMITES)['problemas']


def test_segmento_com_link_no_markdown_conta_como_presente(tmp_path):
    """Link no Markdown insere URL no meio do segmento; início e fim do segmento bastam para presença."""
    segmento = 'Art. 3 O benefício fiscal aplica-se às receitas do contribuinte optante pelo regime especial, nos termos do inciso II, ' * 3
    conteudo = json.dumps({'outrosSegmentos': [{'textoIntegra': segmento}]}).encode('utf8')
    original = _arquivo(tmp_path, 'l/original.json', conteudo)
    meio = segmento[:len(segmento) // 2]
    fim = segmento[len(segmento) // 2:]
    md = meio + ' [Art. 3](https://www.receita.fazenda.gov.br/legislacao/art3) ' + fim + '\n'
    occ = _ocorrencia(tmp_path, 'l', markdown=md, originais=[original], meta_extra=dict(source_url=RECEITA))
    assert 'segmentos_perdidos' not in auditar(occ, tmp_path, LIMITES)['problemas']


def test_anexo_nao_e_comparado_com_markdown_do_documento_principal(tmp_path):
    """Original principal é o indicado em metadados['original']; anexo HTML não entra na razão nem nos segmentos."""
    segmentos = [f'Art. {i} O benefício fiscal número {i} aplica-se às receitas do contribuinte.' for i in range(20)]
    conteudo = json.dumps({'outrosSegmentos': [{'textoIntegra': s} for s in segmentos]}).encode('utf8')
    principal = _arquivo(tmp_path, 'r/multivigente.json', conteudo)
    anexo = _arquivo(tmp_path, 'r/anexo-1.html', _html('Anexo com tabela extensa de alíquotas ' * 2000))
    occ = _ocorrencia(tmp_path, 'r', markdown='\n'.join(segmentos) + '\n', originais=[anexo, principal],
                      meta_extra=dict(source_url=RECEITA, original='multivigente.json'))
    assert auditar(occ, tmp_path, LIMITES)['problemas'] == []


def test_classe_de_pagina_nao_remove_o_documento_inteiro(tmp_path):
    """<body class="default-header-template"> não é cabeçalho: o conteúdo continua no denominador."""
    corpo = _html(TEXTO).replace(b'<body>', b'<body class="default-header-template portal-institucional">')
    original = _arquivo(tmp_path, 'lei/original.html', corpo)
    occ = _ocorrencia(tmp_path, 'lei', markdown='# Lei\n\n' + TEXTO + '\n', originais=[original])
    resultado = auditar(occ, tmp_path, LIMITES)
    assert resultado['razao_texto'] is not None
    assert resultado['problemas'] == []


def test_espaco_nao_separavel_do_original_nao_conta_como_diferenca(tmp_path):
    """&nbsp; no JSON da Receita vira U+00A0; espaço não é letra e não pode quebrar a presença do segmento."""
    segmentos = [f'Nota {i} Este documento foi tornado público em cumprimento à Lei de Acesso à Informação.' for i in range(20)]
    conteudo = json.dumps({'outrosSegmentos': [{'textoIntegra': s + '&nbsp;&nbsp;'} for s in segmentos]}).encode('utf8')
    original = _arquivo(tmp_path, 'n/original.json', conteudo)
    occ = _ocorrencia(tmp_path, 'n', markdown='\n'.join(segmentos) + '\n', originais=[original], meta_extra=dict(source_url=RECEITA))
    assert 'segmentos_perdidos' not in auditar(occ, tmp_path, LIMITES)['problemas']


def test_celula_com_caractere_substituto_do_original_nao_e_perdida(tmp_path):
    """Original com bytes corrompidos (descri��o) e Markdown correto (descrição): o substituto casa qualquer letra."""
    tabela = b'<table><tr><td>Descri\xef\xbf\xbd\xef\xbf\xbdo</td><td>Valor integral</td></tr><tr><td>Faixa</td><td>Contribuicao</td></tr></table>'
    md = '# Lei\n\n' + TEXTO + '\n\nDescrição Valor integral\n\nFaixa Contribuicao\n'
    original = _arquivo(tmp_path, 'lei/original.html', _html(TEXTO, tabela=tabela))
    occ = _ocorrencia(tmp_path, 'lei', markdown=md, originais=[original])
    assert 'tabelas_perdidas' not in auditar(occ, tmp_path, LIMITES)['problemas']
