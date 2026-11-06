import json
import os
import threading

import httpx
import pytest

from backend.crawler import normas_citadas as nc
from backend.crawler.fontes_normas import Ambigua, Bloqueada, Candidato, Indisponivel, SemTextoAutomatico

NOME = {'lei': 'LEI', 'decreto': 'DECRETO', 'portaria': 'PORTARIA'}


def html(tipo, numero, ano, extra=''):
    return (f'<html><body><p>{NOME[tipo]} Nº {numero}, DE 1º DE JANEIRO DE {ano}</p><p>Art. 1º Texto.</p>'
            f'{extra}</body></html>').encode('utf-8')


def linha(tipo, numero, ano, jur='federal', citado=1, situacao='pendente', ordem=None, orgao=None, **extra):
    n = {'tipo': tipo, 'numero': numero, 'ano': ano, 'jurisdicao': jur, 'orgao': orgao}
    chave = f"{jur}:{tipo}:{orgao or '-'}:{numero}:{ano or '?'}"
    return {**({'candidata_ordem': ordem} if ordem is not None else {}), 'chave': chave, 'norma': n,
            'citado_em': citado, 'exemplos': [], 'situacao': situacao, 'motivo': None, 'origem': 'citacao',
            'ligacao': 'certa', **extra}


def inventario(tmp, linhas, nome='inventario.json'):
    p = tmp / 'entrada' / nome
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({'run': 'r', 'total': len(linhas), 'linhas': linhas}), encoding='utf-8')
    return p


def cand_padrao(host='a.gov.br', nome='planalto'):
    return lambda n, http: [Candidato(f'https://{host}/{n.tipo}-{n.numero}', nome, 'unica')]


class Stub:
    """Fonte falsa: `ato(norma, http)` devolve lista de Candidato ou levanta."""

    def __init__(self, nome='planalto', tipos=('lei', 'decreto', 'portaria'), ato=None, host='a.gov.br'):
        self.nome, self.tipos = nome, tipos
        self.ato = ato or cand_padrao(host, nome)
        self.chamadas = []

    def aceita(self, norma):
        return norma.tipo in self.tipos

    def localizar(self, norma, http):
        self.chamadas.append(norma.chave)
        return self.ato(norma, http)


def so_jur(stub, jur):
    stub.aceita = lambda n: n.jurisdicao == jur
    return stub


class Rede:
    """MockTransport: rotas url -> (status, corpo). Padrao: documento valido derivado do caminho tipo-numero."""

    def __init__(self, rotas=None, ano=2000):
        self.pedidos, self.rotas, self.ano = [], rotas or {}, ano
        self.client = httpx.Client(transport=httpx.MockTransport(self.handler))

    def handler(self, req):
        url = str(req.url)
        if req.url.path == '/robots.txt':
            return httpx.Response(404)
        self.pedidos.append(url)
        if url in self.rotas:
            st, corpo = self.rotas[url]
            return httpx.Response(st, content=corpo, headers={'content-type': 'text/html'})
        tipo, numero = req.url.path.strip('/').split('-')
        return httpx.Response(200, content=html(tipo, int(numero), self.ano), headers={'content-type': 'text/html'})


def rodar(tmp, linhas, fontes, rede=None, rodada=1, **kw):
    rede = rede or Rede()
    kw.setdefault('workers', 1)
    kw.setdefault('dormir', lambda s: None)
    kw.setdefault('saida', lambda *a: None)
    r = nc.coletar(inventario(tmp, linhas), tmp / 'destino', rodada, fontes, client=rede.client, **kw)
    return r, rede


def frente(tmp):
    return tmp / 'destino' / 'normas-citadas'


def estado(tmp, rodada=1):
    return json.loads((frente(tmp) / f'estado-rodada-{rodada}.json').read_text('utf-8'))['normas']


def test_rodada_invalida_e_recusada(tmp_path):
    with pytest.raises(ValueError):
        nc.coletar(inventario(tmp_path, []), tmp_path / 'd', 3, [])


def test_coleta_simples_grava_documento_e_manifesto(tmp_path):
    r, _ = rodar(tmp_path, [linha('lei', 10, 2000)], [Stub()])
    assert r['contagem'] == {'coletada': 1}
    e = estado(tmp_path)['federal:lei:-:10:2000']
    assert e['situacao'] == 'coletada' and len(e['documentos']) == 1
    assert (frente(tmp_path) / e['documentos'][0]['pasta'] / 'documento.md').is_file()
    man = json.loads((frente(tmp_path) / 'manifesto.json').read_text('utf-8'))
    assert man['normas']['federal:lei:-:10:2000']['situacao'] == 'coletada'


def test_retomada_e_checkpoint_corrompido(tmp_path):
    ls = [linha('lei', 10, 2000), linha('lei', 11, 2000)]
    _, rede = rodar(tmp_path, ls, [Stub()])
    assert len(rede.pedidos) == 2
    _, rede2 = rodar(tmp_path, ls, [Stub()])
    assert rede2.pedidos == []  # 0 downloads
    ck = frente(tmp_path) / 'estado-rodada-1.json'
    ck.write_text('{ invalido', encoding='utf-8')
    with pytest.raises(ValueError, match='corrompido'):
        rodar(tmp_path, ls, [Stub()])
    assert ck.read_text('utf-8') == '{ invalido'


def test_mais_citadas_primeiro(tmp_path):
    ls = [linha('lei', 1, 2000, citado=9), linha('lei', 2, 2000, citado=5), linha('lei', 3, 2000, citado=1)]
    _, rede = rodar(tmp_path, ls, [Stub()])
    assert [u.rsplit('-', 1)[1] for u in rede.pedidos] == ['1', '2', '3']


def test_limite_cap_de_normas_tentadas_e_restantes(tmp_path):
    ls = [linha('lei', n, 2000, citado=10 - n) for n in range(1, 5)]
    r, rede = rodar(tmp_path, ls, [Stub()], limite=2)
    assert len(rede.pedidos) == 2 and r['restantes'] == 2 and r['contagem'] == {'coletada': 2}
    r, rede = rodar(tmp_path, ls, [Stub()], limite=5)  # retoma: so as 2 faltantes
    assert len(rede.pedidos) == 2 and r['restantes'] == 0


def test_fonte_em_falha_passa_para_a_proxima(tmp_path):
    def cai(n, http):
        raise Bloqueada('403 em https://a.gov.br/x')
    rodar(tmp_path, [linha('lei', 10, 2000)], [Stub('planalto', ato=cai), Stub('lexml', host='b.gov.br')])
    e = estado(tmp_path)['federal:lei:-:10:2000']
    assert e['situacao'] == 'coletada' and e['fontes']['planalto']['resultado'] == 'bloqueada'
    assert e['fontes']['lexml']['resultado'] == 'ok'


def test_todas_falham_vira_situacao_final(tmp_path):
    def vazio(n, http):
        return []

    def bloq(n, http):
        raise Bloqueada('robots.txt proibe https://b.gov.br/x')
    rodar(tmp_path, [linha('lei', 1, 2000)], [Stub('planalto', ato=vazio), Stub('lexml', ato=vazio)])
    assert estado(tmp_path)['federal:lei:-:1:2000']['situacao'] == 'nao_encontrada'
    b = tmp_path / 'b'
    rodar(b, [linha('lei', 2, 2000)], [Stub('planalto', ato=vazio), Stub('lexml', ato=bloq)])
    e = estado(b)['federal:lei:-:2:2000']
    assert e['situacao'] == 'bloqueada' and not e.get('repetir')
    assert 'https://b.gov.br/x' in (frente(b) / 'manual.md').read_text('utf-8')


def test_indisponivel_e_repetida_na_proxima_execucao_mas_bloqueada_nao(tmp_path):
    fonte = {'cai': True}

    def instavel(n, http):
        if fonte['cai']:
            raise Indisponivel('503 em https://a.gov.br/x')
        return [Candidato('https://a.gov.br/lei-1', 'planalto', 'unica')]

    def bloq(n, http):
        raise Bloqueada('403 em https://c.gov.br/x')
    ls = [linha('lei', 1, 2000), linha('decreto', 2, 2000)]

    def fontes():
        return [Stub('planalto', tipos=('lei',), ato=instavel), Stub('lexml', tipos=('decreto',), ato=bloq)]
    rodar(tmp_path, ls, fontes())
    e = estado(tmp_path)
    assert e['federal:lei:-:1:2000']['situacao'] == 'bloqueada'
    assert e['federal:lei:-:1:2000']['motivo'] == 'fonte indisponível'
    fonte['cai'] = False
    _, rede = rodar(tmp_path, ls, fontes())
    e = estado(tmp_path)
    assert e['federal:lei:-:1:2000']['situacao'] == 'coletada'
    assert e['federal:decreto:-:2:2000']['situacao'] == 'bloqueada'
    assert len(rede.pedidos) == 1  # so a lei foi tentada de novo


def test_ambigua_manual_e_rejeitada_por_validacao(tmp_path):
    def amb(n, http):
        raise Ambigua('2 registros')

    def sem(n, http):
        raise SemTextoAutomatico('sem texto compilado')
    ls = [linha('lei', 1, 2000), linha('decreto', 2, 2000), linha('portaria', 3, 2000)]
    fontes = [Stub('planalto', tipos=('lei',), ato=amb), Stub('sinj', tipos=('decreto',), ato=sem),
              Stub('planalto', tipos=('portaria',))]
    rodar(tmp_path, ls, fontes, Rede(ano=1999))  # texto de outro ano: identidade nao confere
    e = estado(tmp_path)
    assert e['federal:lei:-:1:2000']['situacao'] == 'ambigua' and '2 registros' in e['federal:lei:-:1:2000']['motivo']
    assert e['federal:decreto:-:2:2000']['situacao'] == 'manual'
    assert e['federal:portaria:-:3:2000']['situacao'] == 'ambigua'
    assert not list((tmp_path / 'destino').rglob('documento.md'))


def test_sem_fonte_aplicavel_e_assunto_viram_manual_sem_rede(tmp_path):
    ls = [linha('ec', 3, 1993), linha('assunto', 0, None, jur='df', assunto='IPTU')]
    _, rede = rodar(tmp_path, ls, [Stub()])
    assert {v['situacao'] for v in estado(tmp_path).values()} == {'manual'} and rede.pedidos == []


def test_compilada_e_original_ambas_salvas_e_404_derivado_nao_falha(tmp_path):
    def tres(n, http):
        return [Candidato('https://a.gov.br/lei-1', 'camara', 'compilada'),
                Candidato('https://a.gov.br/lei-1b', 'camara', 'original'),
                Candidato('https://a.gov.br/lei-1c', 'camara', 'original')]
    rede = Rede({'https://a.gov.br/lei-1b': (200, html('lei', 1, 2000, '<!-- v2 -->')),
                 'https://a.gov.br/lei-1c': (404, b'')})
    rodar(tmp_path, [linha('lei', 1, 2000)], [Stub('camara', ato=tres)], rede)
    e = estado(tmp_path)['federal:lei:-:1:2000']
    assert e['situacao'] == 'coletada' and {d['visao'] for d in e['documentos']} == {'compilada', 'original'}
    assert len({d['sha256'] for d in e['documentos']}) == 2


def test_duas_candidatas_jurisdicao_guardam_identidades_proprias(tmp_path):
    df, fed = linha('lei', 5, 2000, 'df', ordem=0), linha('lei', 5, 2000, 'federal', ordem=1)
    # DF nao encontrada: a federal (listada antes de proposito) e tentada depois
    fontes = [so_jur(Stub('sinj', ato=lambda n, h: []), 'df'), so_jur(Stub('planalto'), 'federal')]
    rodar(tmp_path, [fed, df], fontes)
    e = estado(tmp_path)
    assert e['df:lei:-:5:2000']['situacao'] == 'nao_encontrada' and e['federal:lei:-:5:2000']['situacao'] == 'coletada'
    # DF resolvida: a federal nao e tentada e guarda a identidade propria
    b = tmp_path / 'b'
    _, rede = rodar(b, [df, fed], [so_jur(Stub('sinj'), 'df'), so_jur(Stub('planalto'), 'federal')])
    e = estado(b)
    assert e['df:lei:-:5:2000']['situacao'] == 'coletada'
    assert (e['federal:lei:-:5:2000']['situacao'], e['federal:lei:-:5:2000']['motivo']) == (
        'ambigua', 'resolvida pela candidata de ordem 0')
    assert len(rede.pedidos) == 1
    meta = json.loads(next((b / 'destino').rglob('metadados.json')).read_text('utf-8'))
    assert (meta['norma_chave'], meta['jurisdicao']) == ('df:lei:-:5:2000', 'df')


def test_nao_escreve_fora_do_destino(tmp_path):
    ent = inventario(tmp_path, [linha('lei', 1, 2000), linha('lei', 2, 2000)])
    antes = set(tmp_path.rglob('*'))
    rede = Rede()
    nc.coletar(ent, tmp_path / 'destino', 1, [Stub()], client=rede.client, workers=2, dormir=lambda s: None,
               saida=lambda *a: None)
    novos = set(tmp_path.rglob('*')) - antes
    assert novos and all(tmp_path / 'destino' in p.parents or p == tmp_path / 'destino' for p in novos)
    assert set(ent.parent.iterdir()) == {ent}


def test_nenhum_pendente_no_manifesto(tmp_path):
    ls = [linha('lei', 1, 2000), linha('lei', 2, 2000, situacao='ja_existia'),
          linha('lei', 3, 2000, situacao='ambigua'), linha('ec', 4, 1990)]
    ls[2]['motivo'] = 'ano divergente'
    r, _ = rodar(tmp_path, ls, [Stub()])
    man = json.loads((frente(tmp_path) / 'manifesto.json').read_text('utf-8'))
    assert len(man['normas']) == 4 and 'pendente' not in {v['situacao'] for v in man['normas'].values()}
    assert man['normas']['federal:lei:-:3:2000']['motivo'] == 'ano divergente'
    assert r['contagem'] == {'coletada': 1, 'ja_existia': 1, 'ambigua': 1, 'manual': 1}


def test_disjuntor_de_host_pausa_por_30_minutos(tmp_path):
    t = {'v': 0.0}
    ls = [linha('lei', n, 2000, citado=100 - n) for n in range(1, 31)]
    rede = Rede({f'https://a.gov.br/lei-{n}': (503, b'') for n in range(1, 31)})
    rodar(tmp_path, ls, [Stub()], rede, relogio=lambda: t['v'])
    # 20 normas gastam 2 tentativas cada (5xx e repetido); depois o host e pulado sem rede
    assert len(rede.pedidos) == 40
    assert all(e['situacao'] == 'bloqueada' and e['motivo'] == 'fonte indisponível' for e in estado(tmp_path).values())
    t['v'] = 1801.0  # passou a pausa: o host volta a ser tentado
    rede2 = Rede()
    rodar(tmp_path, ls, [Stub()], rede2, relogio=lambda: t['v'])
    assert len(rede2.pedidos) == 30 and {e['situacao'] for e in estado(tmp_path).values()} == {'coletada'}


def test_hosts_diferentes_andam_em_paralelo_com_um_host_lento(tmp_path):
    livre = threading.Event()

    def devagar(n, http):
        assert livre.wait(5)  # so termina depois que o outro host respondeu
        return []

    def rapido(n, http):
        livre.set()
        return []
    ls = [linha('lei', 1, 2000, citado=9), linha('decreto', 2, 2000, citado=8)]
    r, _ = rodar(tmp_path, ls, [Stub('planalto', tipos=('lei',), ato=devagar),
                                Stub('receita', tipos=('decreto',), ato=rapido, host='b.gov.br')], workers=2)
    assert r['contagem'] == {'nao_encontrada': 2}


def test_checkpoint_atomico_tenta_de_novo_quando_replace_falha(tmp_path, monkeypatch):
    real, falhas = os.replace, {'n': 0}

    def replace(a, b):
        if falhas['n'] < 2:
            falhas['n'] += 1
            raise PermissionError('em uso')
        return real(a, b)
    monkeypatch.setattr(nc.os, 'replace', replace)
    monkeypatch.setattr(nc.time, 'sleep', lambda s: None)
    rodar(tmp_path, [linha('lei', 1, 2000)], [Stub()])
    assert falhas['n'] == 2 and estado(tmp_path)['federal:lei:-:1:2000']['situacao'] == 'coletada'
    assert not list((tmp_path / 'destino').rglob('*.tmp'))


def test_ctrl_c_termina_o_checkpoint_e_sai_limpo(tmp_path):
    def saida(*a):
        raise KeyboardInterrupt

    ls = [linha('lei', n, 2000, citado=10 - n) for n in range(1, 6)]
    r, _ = rodar(tmp_path, ls, [Stub()], saida=saida, a_cada=1)
    assert r['interrompido'] is True and 1 <= len(estado(tmp_path)) < 5
    assert (frente(tmp_path) / 'manifesto.json').is_file()


def test_progresso_a_cada_n_e_status_sem_rede(tmp_path, capsys):
    linhas_ = []
    ls = [linha('lei', n, 2000, citado=100 - n) for n in range(1, 4)]
    rodar(tmp_path, ls, [Stub()], saida=linhas_.append, a_cada=2)
    assert len(linhas_) == 1 and 'coletada=2' in linhas_[0]
    nc.main(['--rodada', '1', '--status', '--destino', str(tmp_path / 'destino')])
    assert 'coletada=3' in capsys.readouterr().out


def test_manual_md_lista_manual_e_bloqueada_com_url_sugerida(tmp_path):
    def sem(n, http):
        raise SemTextoAutomatico('sem texto')

    def bloq(n, http):
        raise Bloqueada('403 em https://z.gov.br/lei-2')
    ls = [linha('lei', 1, 2000), linha('decreto', 2, 2000)]
    rodar(tmp_path, ls, [Stub('sinj', tipos=('lei',), ato=sem), Stub('camara', tipos=('decreto',), ato=bloq)])
    md = (frente(tmp_path) / 'manual.md').read_text('utf-8')
    assert 'federal:lei:-:1:2000' in md and 'federal:decreto:-:2:2000' in md and 'https://z.gov.br/lei-2' in md


def _doc_rodada1(tmp, extra):
    rede = Rede({'https://a.gov.br/lei-1': (200, html('lei', 1, 2000, extra))})
    rodar(tmp, [linha('lei', 1, 2000)], [Stub()], rede)


def test_proxima_rodada_cruza_com_inventario_e_coletadas(tmp_path):
    _doc_rodada1(tmp_path, '<p>Altera a Lei nº 2, de 2000, a Lei nº 3, de 2001 e a Lei nº 1, de 2000.</p>')
    inv = inventario(tmp_path, [linha('lei', 1, 2000), linha('lei', 2, 2000, situacao='ja_existia')])
    p = nc.proxima_rodada(tmp_path / 'destino', inv)
    assert p == frente(tmp_path) / 'inventario-rodada-2.json'
    dados = json.loads(p.read_text('utf-8'))
    assert [l['chave'] for l in dados['linhas']] == ['federal:lei:-:3:2001']
    assert dados['linhas'][0]['situacao'] == 'pendente' and dados['linhas'][0]['citado_em'] == 1


def test_rodada_2_lista_mas_nao_coleta_novas(tmp_path):
    _doc_rodada1(tmp_path, '<p>Veja a Lei nº 3, de 2001.</p>')
    inv2 = nc.proxima_rodada(tmp_path / 'destino', inventario(tmp_path, [linha('lei', 1, 2000)]))
    # o documento da rodada 2 cita a Lei 4/2002, que nao pode ser coletada
    rede = Rede({'https://a.gov.br/lei-3': (200, html('lei', 3, 2001, '<p>Cita a Lei nº 4, de 2002.</p>'))})
    r = nc.coletar(inv2, tmp_path / 'destino', 2, [Stub()], client=rede.client, workers=1,
                   dormir=lambda s: None, saida=lambda *a: None)
    assert rede.pedidos == ['https://a.gov.br/lei-3']  # a Lei 4/2002 nunca e pedida
    fora = json.loads((frente(tmp_path) / 'citadas-fora-do-limite.json').read_text('utf-8'))
    assert [(l['chave'], l['situacao']) for l in fora['linhas']] == [('federal:lei:-:4:2002', 'citada_fora_do_limite')]
    assert r['citadas_fora_do_limite'] == 1
    assert 'federal:lei:-:4:2002' not in estado(tmp_path, 2)
