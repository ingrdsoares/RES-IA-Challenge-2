import hashlib
import json
from pathlib import Path

from backend.refino.pipeline import classify, load_policy, run
from backend.refino.ruido import carregar_regras, limpar, sugerir

REGRAS = carregar_regras()
ASSINATURA = 'AUDITOR-FISCAL DA RECEITA FEDERAL DO BRASIL'
BANNER = '> Revisão humana pendente. Vigência e aplicabilidade não verificadas. TARF: ementa e decisão disponibilizadas pelo catálogo; não equivale ao inteiro teor do voto.'
STUB = (
    '# Conteúdo Restrito\n\n'
    'Fonte: https://www.gov.br/carf/x.pdf\n\n'
    '> Súmulas, precedentes e atos normativos. Vigência exige revisão.\n\n'
    'Info\n\n'
    '# Conteúdo Restrito\n\n'
    'É necessário autenticar para visualizar essa página. Se você acredita que está recebendo essa mensagem incorretamente, por favor contate a\n'
    '[administração do site](https://www.gov.br/carf/canais).\n\n'
    '[Ir para a página inicial](https://www.gov.br/carf)\n'
)
CARF_COM_TEXTO = '# Súmula CARF 1\n\nO conteúdo deste acórdão não fica restrito ao contribuinte; o texto integral está disponível.\nArt. 2º Valor de R$ 10,00 em 01/02/2020.\n'


def make_input(root, items):
    snapshots = []
    for name, url, text, front, *extra in items:
        folder = root / front / name
        folder.mkdir(parents=True)
        md = folder / 'documento.md'
        md.write_text(text, encoding='utf8')
        raw = b'same raw primary'
        meta = dict(source_url=url, source_id=name, titulo='Documento', sha256=hashlib.sha256(raw).hexdigest(), coletado_em='2026-11-05', tipo='legislacao', status='extraido', markdown_arquivo='documento.md', markdown_sha256=hashlib.sha256(md.read_bytes()).hexdigest())
        if extra:
            meta.update(extra[0])
        mp = folder / 'metadados.json'
        mp.write_text(json.dumps(meta), encoding='utf8')
        snapshots.append(dict(diretorio=folder.relative_to(root).as_posix(), metadados=mp.relative_to(root).as_posix(), origem=url, problemas=[]))
    catalog = root / 'catalogo.json'
    catalog.write_text(json.dumps(dict(snapshots=snapshots, executado_em='2026-11-05')), encoding='utf8')
    return catalog


def read_rows(folder, name):
    return [json.loads(line) for line in (folder / name).read_text(encoding='utf8').splitlines()]


def test_remove_so_o_que_esta_na_lista():
    texto = 'Art. 1º Texto.\n' + BANNER + '\nFundamentos\nArt. 2º Texto.\nFundamentos\n'
    saida, aplicadas = limpar(texto, REGRAS)
    assert BANNER not in saida
    assert saida == 'Art. 1º Texto.\nFundamentos\nArt. 2º Texto.\nFundamentos\n'
    assert aplicadas == ['revisao-tarf']
    assert limpar('Fundamentos\nRelatório\nFundamentos\n', REGRAS) == ('Fundamentos\nRelatório\nFundamentos\n', [])


def test_regra_casa_linha_inteira():
    paragrafo = 'Art. 3º Fica mantido o aviso: Revisão humana pendente. Texto legal permanece.\nOutro trecho.\n'
    assert limpar(paragrafo, REGRAS) == (paragrafo, [])
    assert limpar('Texto antes ' + BANNER + '\n', REGRAS) == ('Texto antes ' + BANNER + '\n', [])


def test_preserva_artigos_valores_datas_tabelas_rasuras():
    legal = ['Art. 1.000 Pagamento de R$ 1.000,00, alíquota 10%.', '01/01/2020 vencimento em 31/12/2026.', '| Faixa | Valor |', '| 1 | 100,00 |', '~~Revogado~~ texto tachado mantido.', 'Parágrafo único. Ver item 3.2.1.']
    texto = '\n'.join(legal) + '\n' + BANNER + '\n'
    saida, aplicadas = limpar(texto, REGRAS)
    assert saida == '\n'.join(legal) + '\n'
    assert aplicadas == ['revisao-tarf']


def test_assinatura_frequente_nao_sai_por_frequencia(tmp_path):
    textos = {}
    for i in range(30):
        p = tmp_path / ('t%d.md' % i)
        p.write_text('Texto %d\n%s\n' % (i, ASSINATURA), encoding='utf8')
        textos['t%d' % i] = p
    sugestoes = sugerir(textos, minimo_textos=10)
    assert any(s['texto'] == ASSINATURA and s['textos'] == 30 for s in sugestoes)
    assert limpar(ASSINATURA + '\n', REGRAS) == (ASSINATURA + '\n', [])


def test_conteudo_original_nao_muda(tmp_path):
    root = tmp_path / 'raw'
    catalog = make_input(root, [('a', 'https://a.gov.br/doc', '# Lei\nArt. 1º Texto.\n> Fotografia das visões da fonte. Não inferir vigência nem datas de produção de efeitos. Revisão humana pendente.\n', 'legislacao')])
    report = run(root, catalog, tmp_path / 'refined')
    folder = tmp_path / 'refined' / report['run_id']
    conteudo = next((folder / 'conteudos').glob('*.md'))
    busca = folder / 'busca' / conteudo.name
    assert 'Fotografia das visões' in conteudo.read_text(encoding='utf8')
    assert 'Fotografia das visões' not in busca.read_text(encoding='utf8')
    assert 'Art. 1º Texto.' in busca.read_text(encoding='utf8')


def test_agenda_e_conteudo_restrito_viram_apoio():
    policy = load_policy()
    assert classify({'natureza_documental': 'agenda_diaria'}, 'calendario-df', '# Agenda\nDia 10', policy)[0] == 'apoio'
    assert classify({'natureza_documental': 'agenda_mes'}, 'obrigacoes', '# Agenda do mês\nDia 10', policy)[0] == 'apoio'
    assert classify({'natureza_documental': 'agenda_indice'}, 'obrigacoes', '# Agenda\nÍndice', policy)[0] == 'apoio'
    assert classify({'natureza_documental': 'ato_normativo_administrativo'}, 'sumulas-classificacao', STUB, policy)[0] == 'apoio'
    assert classify({'natureza_documental': 'ato_normativo_administrativo'}, 'legislacao', STUB, policy)[0] == 'apoio'
    assert classify({'tipo': 'agenda_diaria_historica', 'periodo': '2020-01'}, 'historico-competencias', 'Simples Nacional', policy)[0] == 'historico'
    assert classify({'natureza_documental': 'legislacao'}, 'legislacao', '# Lei\nArt. 1º Texto.', policy)[0] == 'nucleo'
    corpo_so_aviso = 'É necessário autenticar para visualizar essa página. Por favor contate a\n[administração do site](https://www.gov.br/carf/canais).\n\n[Ir para a página inicial](https://www.gov.br/carf)\n'
    assert classify({'natureza_documental': 'ato_normativo_administrativo'}, 'legislacao', corpo_so_aviso, policy)[0] == 'apoio'


def test_pagina_oficial_e_orientacao_do_calendario_nao_viram_apoio():
    policy = load_policy()
    lei = '# Lei 963\n\nArt. 1º Fica instituído o programa; R$ 100,00.\n'
    assert classify({'natureza_documental': 'pagina_oficial'}, 'calendario-df', lei, policy)[0] == 'nucleo'
    assert classify({'natureza_documental': 'orientacao_declaracao'}, 'calendario-df', '# DASN-SIMEI\n\nPrazo 31 de maio.\n', policy)[0] == 'nucleo'


def test_documento_com_texto_e_palavra_restrito_no_corpo_nao_vira_apoio():
    policy = load_policy()
    assert classify({'natureza_documental': 'ato_normativo_administrativo'}, 'sumulas-classificacao', CARF_COM_TEXTO, policy)[0] != 'apoio'


def test_apoio_fica_fora_do_nucleo_e_acessivel(tmp_path):
    root = tmp_path / 'raw'
    catalog = make_input(root, [
        ('lei', 'https://a.gov.br/lei', '# Simples Nacional\nArt. 1º Lei do Simples.', 'legislacao'),
        ('agenda', 'https://a.gov.br/agenda', '# Agenda de outubro\nDia 10: DASN-SIMEI.', 'calendario-df', dict(natureza_documental='agenda_diaria')),
    ])
    report = run(root, catalog, tmp_path / 'refined')
    folder = tmp_path / 'refined' / report['run_id']
    nucleo = read_rows(folder, 'indice_nucleo.jsonl')
    apoio = read_rows(folder, 'indice_apoio.jsonl')
    assert len(nucleo) == 1 and len(apoio) == 1
    assert nucleo[0]['documento_id'] != apoio[0]['documento_id']
    assert report['indices_documentos']['apoio'] == 1
    ocorrencia = next(r for r in read_rows(folder, 'ocorrencias.jsonl') if r['documento_id'] == apoio[0]['documento_id'])
    assert ocorrencia['classificacao'] == 'apoio'
    versao = next(v for v in read_rows(folder, 'versoes.jsonl') if v['id'] == apoio[0]['representacao_preferida'])
    assert 'Dia 10: DASN-SIMEI.' in (folder / 'busca' / (versao['conteudo_id'] + '.md')).read_text(encoding='utf8')
