import hashlib
import json
from pathlib import Path
import pytest
from backend.refino.pipeline import identity,normalize_text,classify,load_policy,run


def test_identity_preserves_annexes_queries_and_authorities():
    assert identity('https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/145726/visao/original')==identity('https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/145726/visao/multivigente')
    assert identity('https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/145726/anexo/80140')!=identity('https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/145726/visao/multivigente')
    assert identity('https://example.gov.br/doc?id=1')!=identity('https://example.gov.br/doc?id=2')
    assert identity('https://example.gov.br/doc#art1')!=identity('https://example.gov.br/doc#art2')
    assert identity('https://a.gov.br/doc')!=identity('https://b.gov.br/doc')


def test_normalization_preserves_legal_content():
    body='# Lei\nArt. 1.000 — R$ 1.000,00, 10%. ~~Revogado~~\n| Faixa | Valor |\n| 1 | 100 |\n'
    wrapped='---\nsource_url: https://example.gov.br\nsha256: abc\ncoletado_em: 2026\n---\n'+body
    assert normalize_text(wrapped)==normalize_text(body)
    assert 'R$ 1.000,00, 10%. ~~Revogado~~' in normalize_text(wrapped)
    assert normalize_text(body)!=normalize_text(body.replace('100 |','101 |'))
    assert normalize_text('---\nregra: preservar\n---\n'+body).startswith('---')


def make_input(root,items):
    snapshots=[]
    for name,url,text,front,*extra in items:
        folder=root/front/name;folder.mkdir(parents=True)
        md=folder/'documento.md';md.write_text(text,encoding='utf8')
        raw=b'same raw primary';meta=dict(source_url=url,source_id=name,titulo='Documento',sha256=hashlib.sha256(raw).hexdigest(),coletado_em='2026-11-05',tipo='legislacao',status='extraido',markdown_arquivo='documento.md',markdown_sha256=hashlib.sha256(md.read_bytes()).hexdigest())
        if extra:meta.update(extra[0])
        mp=folder/'metadados.json';mp.write_text(json.dumps(meta),encoding='utf8')
        snapshots.append(dict(diretorio=folder.relative_to(root).as_posix(),metadados=mp.relative_to(root).as_posix(),origem=url,problemas=[]))
    catalog=root/'catalogo.json';catalog.write_text(json.dumps(dict(snapshots=snapshots,executado_em='2026-11-05')),encoding='utf8');return catalog


def read_rows(folder,name):return [json.loads(line) for line in (folder/name).read_text(encoding='utf8').splitlines()]


def test_same_raw_different_views_are_versions_and_sources_survive(tmp_path):
    root=tmp_path/'raw';url='https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/145726/visao/multivigente'
    catalog=make_input(root,[('one',url,'# Simples Nacional\nArt. 1 Texto.','legislacao'),('two',url,'# Simples Nacional\nArt. 1 Texto.\n## Visão original\nTexto adicional.','retencoes-defesa-setores'),('three',url,'# Simples Nacional\nArt. 1 Texto.','consultas-rfb')])
    before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    report=run(root,catalog,tmp_path/'refined');folder=tmp_path/'refined'/report['run_id']
    assert report['ocorrencias']==3 and report['documentos_logicos']==1 and report['versoes']==2 and report['conteudos_unicos']==2
    assert len(read_rows(folder,'ocorrencias.jsonl'))==3
    assert len(read_rows(folder,'indice_nucleo.jsonl'))==1
    assert {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}==before
    assert run(root,catalog,tmp_path/'refined')==report
    content=next((folder/'conteudos').glob('*.md'));content.write_text('alterado',encoding='utf8')
    with pytest.raises(ValueError,match='corrompida'):run(root,catalog,tmp_path/'refined')


def test_shared_text_does_not_merge_different_documents_and_dataset_not_rag(tmp_path):
    root=tmp_path/'raw';catalog=make_input(root,[('a','https://a.gov.br/law','# Simples Nacional\nLei A','legislacao'),('b','https://b.gov.br/law','# Simples Nacional\nLei A','legislacao'),('cnpj','https://example.gov.br/cnpj','# Empresas\nTabela parcial','cnpj-df-censo')])
    report=run(root,catalog,tmp_path/'refined');folder=tmp_path/'refined'/report['run_id']
    assert report['documentos_logicos']==3 and report['conteudos_unicos']==1
    assert len(read_rows(folder,'datasets.jsonl'))==1
    assert len(read_rows(folder,'indice_nucleo.jsonl'))==2


def test_relevance_does_not_assume_old_law_revoked():
    policy=load_policy(profile='mei_simples_df')
    category,reasons=classify({'tipo':'legislacao','data':'2006-12-14'},'legislacao','# LC 123\nSimples Nacional',policy)
    assert category=='nucleo'
    category,reasons=classify({'tipo':'agenda_diaria_historica','periodo':'2020-01'},'historico-competencias','Simples Nacional',policy)
    assert category=='historico'
    category,reasons=classify({'tipo':'lei'},'desconhecido','Texto amplo sem classificação temática',policy)
    assert category=='revisao'


def test_all_regimes_df_includes_federal_irpj_without_simples_keyword():
    policy=load_policy()
    assert policy['perfil']=='tributario_df'
    assert classify({'tipo':'legislacao'},'tributacao-lucro','Regras de apuração do IRPJ e CSLL.',policy)[0]=='nucleo'
    assert classify({'tipo':'consulta_tributaria','jurisdicao':'DF'},'consultas-df-amplas','ISS distrital.',policy)[0]=='nucleo'
    assert classify({'tipo':'modelo_peticao_sem_forca_normativa'},'sumulas-classificacao','Modelo de pedido',policy)[0]=='complementar'


def test_personnel_type_is_not_promoted_by_simples_keyword():
    assert classify({'tipo':'legislacao','tipo_ato_fonte':{'siglaTipoAto':'Port. Pes.'}},'retencoes-defesa-setores','Designa membros do Simples Nacional.',load_policy())[0]=='complementar'


def test_dataset_different_slices_same_raw_remain_distinct_versions(tmp_path):
    root=tmp_path/'raw';catalog=make_input(root,[('small','https://example.gov.br/cnpj','Amostra pequena','cnpj-df'),('large','https://example.gov.br/cnpj','Amostra maior','cnpj-df')])
    a=root/'cnpj-df'/'small'/'metadados.json';b=root/'cnpj-df'/'large'/'metadados.json'
    for p,n in ((a,10),(b,100)):
        meta=json.loads(p.read_bytes());meta['registros']=n;p.write_text(json.dumps(meta),encoding='utf8')
    report=run(root,catalog,tmp_path/'refined')
    assert report['documentos_logicos']==1 and report['versoes']==2 and report['datasets']==2

def test_metadata_cannot_escape_input_root(tmp_path):
    root=tmp_path/'raw';root.mkdir()
    other=tmp_path/'outside.json';other.write_text('{}')
    catalog=root/'catalogo.json';catalog.write_text(json.dumps({'snapshots':[{'metadados':'../outside.json'}]}))
    with pytest.raises(ValueError,match='fora da camada'):run(root,catalog,tmp_path/'refined')


def test_changed_catalog_audit_cannot_reuse_stale_core(tmp_path):
    root=tmp_path/'raw';catalog=make_input(root,[('a','https://a.gov.br/law','# Simples Nacional\nLei A','legislacao')])
    first=run(root,catalog,tmp_path/'refined');old=tmp_path/'refined'/first['run_id']
    old_manifest=(old/'manifesto.json').read_bytes()
    source=json.loads(catalog.read_bytes());source['snapshots'][0]['problemas']=['hash_divergente']
    catalog.write_text(json.dumps(source),encoding='utf8')
    second=run(root,catalog,tmp_path/'refined');new=tmp_path/'refined'/second['run_id']
    assert first['run_id']!=second['run_id']
    assert first['indices_documentos']['nucleo']==1 and second['indices_documentos']['nucleo']==0
    assert second['ocorrencias_com_erros']==1
    assert (old/'manifesto.json').read_bytes()==old_manifest
    meta=json.loads((new/'manifesto.json').read_bytes());meta['politica_sha256']='0'*64
    (new/'manifesto.json').write_text(json.dumps(meta),encoding='utf8')
    with pytest.raises(ValueError,match='incompatível'):run(root,catalog,tmp_path/'refined')


LEI='Lei nº 8.212, de 24 de julho de 1991'
RFB='https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/%s/visao/multivigente'


def refine(tmp_path,items):
    root=tmp_path/'raw';catalog=make_input(root,items)
    report=run(root,catalog,tmp_path/'refined');return tmp_path/'refined'/report['run_id'],report


def test_mesma_lei_camara_e_planalto_vira_um_documento(tmp_path):
    leg=dict(natureza_documental='legislacao',titulo=LEI)
    folder,report=refine(tmp_path,[('c','https://www2.camara.leg.br/legin/fed/lei-8212','# Lei\nArt. 1 A.','legislacao',leg),('p','https://www.planalto.gov.br/ccivil_03/leis/l8212.htm','# Lei\nArt. 1 B.','legislacao',leg)])
    docs=read_rows(folder,'documentos.jsonl')
    assert report['documentos_logicos']==1 and docs[0]['chave_origem']=='norma:federal:lei:-:8212:1991'


def test_lei_federal_e_df_mesmo_numero_continuam_separadas(tmp_path):
    leg=dict(natureza_documental='legislacao',titulo='Lei nº 123, de 14 de dezembro de 2006')
    folder,report=refine(tmp_path,[('f','https://www.planalto.gov.br/l123.htm','# Lei\nFederal.','legislacao',leg),('d','https://www.sinj.df.gov.br/sinj/Norma/123','# Lei\nDistrital.','legislacao',leg)])
    keys={d['chave_origem'] for d in read_rows(folder,'documentos.jsonl')}
    assert keys=={'norma:federal:lei:-:123:2006','norma:df:lei:-:123:2006'}


def test_atos_rfb_com_texto_quase_igual_continuam_separados_por_ato(tmp_path):
    body='# Ineficácia\n'+'\n'.join('Linha %d do texto.'%i for i in range(50))
    folder,report=refine(tmp_path,[('a',RFB%'1',body+'\nfim 19','consultas-rfb',dict(titulo='Solução de Ineficácia nº 19/2019')),('b',RFB%'2',body+'\nfim 20','consultas-rfb',dict(titulo='Solução de Ineficácia nº 20/2019'))])
    assert report['documentos_logicos']==2 and len(read_rows(folder,'indice_nucleo.jsonl'))==2


def test_consulta_rfb_mantem_identidade_por_ato(tmp_path):
    meta=dict(natureza_documental='legislacao',titulo='Instrução Normativa RFB nº 1.500, de 29 de outubro de 2014')
    folder,_=refine(tmp_path,[('a',RFB%'111','# IN\nTexto.','legislacao',meta)])
    assert read_rows(folder,'documentos.jsonl')[0]['chave_origem']=='rfb:ato:111'


def citada(name,visao,text,**more):
    return (name,'https://x.gov.br/'+name,text,'normas-citadas',dict(norma_chave='federal:lei:-:9:2000',visao_fonte=visao,natureza_documental='legislacao',titulo='Lei nº 9/2000',**more))


def versions_by_visao(folder):return {v['visao']:v for v in read_rows(folder,'versoes.jsonl')}


def test_compilada_e_preferida_e_original_fica_fora_do_indice(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(20))
    folder,_=refine(tmp_path,[citada('o','original',base+'\nArt. 99 Só no original.\n'+'x'*500),citada('c','multivigente',base)])
    vs=versions_by_visao(folder);row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert set(vs)=={'compilada','original'}
    assert row['versoes']==[vs['compilada']['id']] and row['representacao_preferida']==vs['compilada']['id']
    assert read_rows(folder,'documentos.jsonl')[0]['chave_origem']=='norma:federal:lei:-:9:2000'


def test_sem_compilada_original_e_indexada(tmp_path):
    folder,_=refine(tmp_path,[citada('o','original','# Lei\nArt. 1.')])
    vs=versions_by_visao(folder)
    assert read_rows(folder,'indice_nucleo.jsonl')[0]['versoes']==[vs['original']['id']]


def test_extracao_com_visao_extra_nao_perde_conteudo(tmp_path):
    comp='# Ato\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('c','multivigente',comp),citada('u','unica',comp+'\nAnexo I\nTabela A\nTabela B'),citada('o','original',comp+'\nRedação original\nOutra'),citada('p','exclusiva',comp+'\nUma linha a mais')])
    vs={v['id']:v for v in read_rows(folder,'versoes.jsonl')}
    row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert len(vs)==4
    assert sorted(vs[i]['visao'] for i in row['versoes'])==['compilada','unica']
    assert vs[row['representacao_preferida']]['visao']=='compilada'


def test_familia_normas_citadas_entra_no_nucleo():
    assert 'normas-citadas' in load_policy()['familias_nucleo']


def test_leis_com_texto_quase_igual_e_numeros_diferentes_continuam_separadas(tmp_path):
    body='# Lei\n'+'\n'.join('Linha %d do texto.'%i for i in range(50))
    leg=lambda n:dict(natureza_documental='legislacao',titulo='Lei nº %d, de 1 de março de 2019'%n)
    folder,report=refine(tmp_path,[('a','https://www.planalto.gov.br/l19.htm',body+'\nfim 19','legislacao',leg(19)),('b','https://www.planalto.gov.br/l20.htm',body+'\nfim 20','legislacao',leg(20))])
    assert report['documentos_logicos']==2
    assert {d['chave_origem'] for d in read_rows(folder,'documentos.jsonl')}=={'norma:federal:lei:-:19:2019','norma:federal:lei:-:20:2019'}


def test_chave_legada_so_para_tipos_unicos_com_ano_e_host_conhecido(tmp_path):
    leg=lambda t:dict(natureza_documental='legislacao',titulo=t)
    folder,_=refine(tmp_path,[
        ('p1','https://www.sinj.df.gov.br/sinj/Norma/1','# P\nA.','legislacao',leg('Portaria SEF nº 10, de 2 de maio de 2020')),
        ('p2','https://www.sinj.df.gov.br/sinj/Norma/2','# P\nB.','legislacao',leg('Portaria SEEC nº 10, de 2 de maio de 2020')),
        ('sa','https://www.planalto.gov.br/semano.htm','# L\nC.','legislacao',leg('Lei nº 77')),
        ('hd','https://exemplo.org/lei','# L\nD.','legislacao',leg('Lei nº 78, de 1 de março de 2019'))])
    keys={d['chave_origem'] for d in read_rows(folder,'documentos.jsonl')}
    assert len(keys)==4 and all(k.startswith('url:') for k in keys)


def test_stub_compilado_nao_vence_texto_integral_mas_fica_no_indice(tmp_path):
    full='# Lei\n'+'\n'.join('Art. %d Texto integral.'%i for i in range(60))
    folder,_=refine(tmp_path,[citada('s','multivigente','# Lei\nResumo sem números.'),citada('f','unica',full)])
    vs=versions_by_visao(folder);row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert row['representacao_preferida']==vs['unica']['id']
    assert set(row['versoes'])=={vs['unica']['id'],vs['compilada']['id']}
    assert read_rows(folder,'documentos.jsonl')[0]['representacao_preferida']==vs['unica']['id']


def test_forma_da_in_2119_original_integral_vence_stub_compilado(tmp_path):
    big='# Instrução Normativa\n'+'\n'.join('Art. %d '%i+'texto '*20 for i in range(700))
    assert len(big)>80000
    folder,_=refine(tmp_path,[citada('s','multivigente','# IN\n(Republicação sem corpo)'),citada('o','original',big)])
    vs=versions_by_visao(folder);row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert row['representacao_preferida']==vs['original']['id']
    assert vs['compilada']['id'] in row['versoes']


def test_toda_versao_esta_no_indice_ou_tem_motivo(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('c','multivigente',base),citada('o','original',base+'\nRedação original'),citada('u','unica',base.rsplit('\n',1)[0])])
    row=read_rows(folder,'indice_nucleo.jsonl')[0]
    motivos={f['versao']:f['motivo'] for f in row['fora_do_indice']}
    assert set(motivos.values())=={'original_com_compilada','versao_sem_conteudo_novo'}
    ids={v['id'] for v in read_rows(folder,'versoes.jsonl')}
    assert ids==set(row['versoes'])|set(motivos) and not set(row['versoes'])&set(motivos)
    assert 'permanecem em' in read_rows(folder,'documentos.jsonl')[0]['criterio_representacao']


def test_valor_alterado_em_uma_linha_mantem_versao_no_indice(tmp_path):
    lines=['Art. %d Texto.'%i for i in range(99)]
    a='# Lei\n'+'\n'.join(lines+['Alíquota de 5%'])
    b='# Lei\n'+'\n'.join(lines+['Alíquota de 7%'])
    folder,_=refine(tmp_path,[citada('c','multivigente',a),citada('u','unica',b)])
    assert len(read_rows(folder,'indice_nucleo.jsonl')[0]['versoes'])==2


def test_marcador_de_omissao_nao_conta_como_conteudo_novo(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('c','multivigente',base),citada('u','unica',base+'\n(...)\n[...]\n...\n(…)')])
    assert len(read_rows(folder,'indice_nucleo.jsonl')[0]['versoes'])==1


def test_original_limpo_vence_compilada_com_ressalva_e_compilada_vira_extra(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('c','multivigente',base+'\nNota um\nNota dois\nNota tres',status='parcial'),citada('o','original',base)])
    vs=versions_by_visao(folder);row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert row['representacao_preferida']==vs['original']['id']
    assert vs['compilada']['id'] in row['versoes']


def all_rows(folder):
    return [r for n in ('indice_nucleo','indice_complementar','indice_historico','fila_revisao') for r in read_rows(folder,n+'.jsonl')]


def test_toda_versao_de_todo_documento_esta_indexada_ou_tem_motivo(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    items=[citada('c','multivigente',base),citada('o','original',base+'\nRedação original'),
        ('e','https://x.gov.br/e','','normas-citadas',dict(norma_chave='federal:lei:-:9:2000',visao_fonte='unica',natureza_documental='legislacao',titulo='Lei nº 9/2000')),
        ('r','https://x.gov.br/r','# Lei\nFalha.','normas-citadas',dict(norma_chave='federal:lei:-:9:2000',visao_fonte='exclusiva',natureza_documental='legislacao',titulo='Lei nº 9/2000',status='erro'))]
    folder,_=refine(tmp_path,items)
    covered=set()
    for r in all_rows(folder):
        covered|=set(r['versoes'])|{f['versao'] for f in r['fora_do_indice']}
    doc=read_rows(folder,'documentos.jsonl')[0]
    motivos={f['versao']:f['motivo'] for f in doc['fora_do_indice']}
    assert {v['id'] for v in read_rows(folder,'versoes.jsonl')}<=covered|set(motivos)
    assert set(motivos.values())=={'sem_texto_extraido','em_revisao'}


def test_stub_sozinho_em_categoria_nao_vira_preferida_e_linha_fica_parcial(tmp_path):
    full='# Lei\n'+'\n'.join('Art. %d Texto integral.'%i for i in range(60))
    items=[citada('f','unica',full,jurisdicao='DF'),citada('s','multivigente','# Lei\nResumo.')]
    # o stub é de outra categoria: perfil/jurisdição explícita fora do foco o torna complementar
    items[1][4]['jurisdicao']='SP'
    folder,_=refine(tmp_path,items)
    vs=versions_by_visao(folder);doc=read_rows(folder,'documentos.jsonl')[0]
    assert doc['representacao_preferida']==vs['unica']['id']
    row=read_rows(folder,'indice_complementar.jsonl')[0]
    assert row['apenas_versao_parcial'] is True and row['representacao_preferida']==vs['compilada']['id']
    assert read_rows(folder,'indice_nucleo.jsonl')[0]['apenas_versao_parcial'] is False


def test_original_sem_compilada_tem_motivo_de_conteudo_nao_novo(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('u','unica',base),citada('o','original',base.rsplit('\n',1)[0])])
    row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert [f['motivo'] for f in row['fora_do_indice']]==['versao_sem_conteudo_novo']


def norma_citada(name,texto,**more):
    return (name,'https://x.gov.br/'+name,texto,'normas-citadas',dict(natureza_documental='legislacao',titulo='Lei nº 9.985, de 18 de julho de 2000',**more))


def test_relacionada_recebe_etiqueta_e_fica_no_indice(tmp_path):
    # Norma citada cujo título e ementa não têm termo tributário: etiqueta relacionada, sem sair do índice.
    folder,_=refine(tmp_path,[norma_citada('p','# Lei\nInstitui o Sistema Nacional de Unidades de Conservação.\nArt. 1 Texto.')])
    row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert row['etiquetas']==['relacionada'] and row['versoes']
    assert read_rows(folder,'documentos.jsonl')[0]['etiquetas']==['relacionada']


def test_relacionada_nao_marca_norma_com_termo_tributario_na_ementa(tmp_path):
    folder,_=refine(tmp_path,[norma_citada('t','# Lei\nDispõe sobre o Simples Nacional e o imposto de renda.\nArt. 1 Texto.')])
    assert read_rows(folder,'indice_nucleo.jsonl')[0]['etiquetas']==[]


def test_revogada_so_com_informacao_da_fonte(tmp_path):
    # situacao_fonte só existe quando a fonte informa; ausência ou "não consta" não gera etiqueta.
    folder,_=refine(tmp_path,[
        norma_citada('r','# Lei\nArt. 1 A.',situacao_fonte='Revogada'),
        norma_citada('s','# Lei\nArt. 1 B.'),
        norma_citada('n','# Lei\nArt. 1 C.',situacao_fonte='Não consta revogação expressa')])
    by_url={r['source_url']:r for r in read_rows(folder,'ocorrencias.jsonl')}
    docs={d['chave_origem']:d for d in read_rows(folder,'documentos.jsonl')}
    etiquetas={r['chave_origem']:r['etiquetas'] for r in read_rows(folder,'documentos.jsonl')}
    assert len(by_url)==3 and len(docs)==3
    assert etiquetas['url:https://x.gov.br/r']==['relacionada','revogada']
    assert sum('revogada' in v for v in etiquetas.values())==1
    assert by_url['https://x.gov.br/r']['situacao_fonte']=='Revogada'
    assert len(read_rows(folder,'indice_nucleo.jsonl'))==3


def test_toda_ocorrencia_e_rastreavel(tmp_path):
    root=tmp_path/'raw';base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    catalog=make_input(root,[citada('c','multivigente',base),citada('o','original',base+'\nRedação original'),norma_citada('x','# Lei\nOutra norma.')])
    report=run(root,catalog,tmp_path/'refined');folder=tmp_path/'refined'/report['run_id']
    ocorrencias=read_rows(folder,'ocorrencias.jsonl')
    assert len(ocorrencias)==3
    docs={d['id']:d for d in read_rows(folder,'documentos.jsonl')}
    versoes={v['id']:v for v in read_rows(folder,'versoes.jsonl')}
    for oc in ocorrencias:
        assert oc['source_url'].startswith('https://') and oc['versao_id'] in versoes and oc['documento_id'] in docs
        assert oc['id'] in versoes[oc['versao_id']]['ocorrencias'] and oc['id'] in docs[oc['documento_id']]['ocorrencias']
        raw=(root/oc['metadados_ref']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==oc['hash_metadados']
    assert sorted(o for d in docs.values() for o in d['ocorrencias'])==sorted(o['id'] for o in ocorrencias)


def test_toda_saida_do_indice_tem_motivo(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[
        citada('c','multivigente',base),citada('o','original',base+'\nRedação original'),
        ('e','https://x.gov.br/e','','normas-citadas',dict(norma_chave='federal:lei:-:9:2000',visao_fonte='unica',natureza_documental='legislacao',titulo='Lei nº 9/2000')),
        ('k','https://x.gov.br/k','# Catálogo\nResumo técnico.','catalogo-tecnico-x',dict(tipo='catalogo_tecnico',titulo='Catálogo técnico'))])
    motivos_validos={'original_com_compilada','versao_sem_conteudo_novo','sem_texto_extraido','em_revisao','categoria_sem_indice'}
    indexadas=set()
    for r in all_rows(folder):indexadas|=set(r['versoes'])
    for r in all_rows(folder):
        for f in r['fora_do_indice']:assert f['motivo'] in motivos_validos
    fora={f['versao']:f['motivo'] for d in read_rows(folder,'documentos.jsonl') for f in d['fora_do_indice']}
    fora.update({f['versao']:f['motivo'] for r in all_rows(folder) for f in r['fora_do_indice']})
    versoes={v['id'] for v in read_rows(folder,'versoes.jsonl')}
    assert versoes==indexadas|set(fora) and not indexadas&set(fora)
    assert set(fora.values())>={'sem_texto_extraido','categoria_sem_indice'}


def test_antes_depois_compara_indice_bytes_normas_e_parcial(tmp_path):
    from backend.refino.pipeline import antes_depois
    full='# Lei\n'+'\n'.join('Art. %d Texto integral.'%i for i in range(60))
    base_dir=tmp_path/'base';atual_dir=tmp_path/'atual'
    base_folder,base_report=refine(base_dir,[citada('f','unica',full,jurisdicao='DF')])
    atual_folder,atual_report=refine(atual_dir,[citada('f','unica',full,jurisdicao='DF'),citada('s','multivigente','# Lei\nResumo.',jurisdicao='SP'),
        ('o','https://x.gov.br/o','# Outra\nTexto de outra norma.','normas-citadas',dict(natureza_documental='legislacao',titulo='Lei nº 77, de 1 de janeiro de 2001'))])
    normas=tmp_path/'normas.json';normas.write_text(json.dumps({'normas':{'x':{'situacao':'nao_encontrada'},'y':{'situacao':'bloqueada'},'z':{'situacao':'manual'},'w':{'situacao':'coletada'}}}),encoding='utf8')
    out=antes_depois(atual_folder,base_folder,normas_atual=normas,normas_base=None)
    saida=json.loads((atual_folder/'antes_depois.json').read_bytes())
    assert saida==out
    assert saida['atual']['documentos_no_indice']==len({r['documento_id'] for f in atual_folder.glob('indice_*.jsonl') for r in read_rows(atual_folder,f.name)})
    assert saida['base']['documentos_no_indice']==len({r['documento_id'] for f in base_folder.glob('indice_*.jsonl') for r in read_rows(base_folder,f.name)})
    assert saida['delta']['documentos_no_indice']==saida['atual']['documentos_no_indice']-saida['base']['documentos_no_indice']
    assert saida['atual']['bytes_textuais_entrada']==atual_report['bytes_textuais_entrada'] and saida['base']['bytes_conteudos_unicos']==base_report['bytes_conteudos_unicos']
    assert saida['atual']['apenas_versao_parcial']['count']==1 and saida['base']['apenas_versao_parcial']['count']==0
    assert saida['atual']['normas']=={'ausentes':1,'bloqueadas_ou_manuais':2,'situacoes':{'nao_encontrada':1,'bloqueada':1,'manual':1,'coletada':1}}
    assert saida['base']['normas'] is None
    assert saida['atual']['extracao_curta']==sum('extracao_curta' in r['problemas'] for r in read_rows(atual_folder,'auditoria_extracao.jsonl'))


def planalto(ementa,corpo=''):
    """Forma real do Planalto coletado: frontmatter, título, citação, cabeçalho, links e ementa numa célula."""
    return ('---\nsource_url: https://www.planalto.gov.br/ccivil_03/leis/l8212compilado.htm\nsha256: abc\ncoletado_em: 2026-11-06\nvigencia: nao_verificada\n---\n\n'
        '# Lei nº 8212/1991\n\n[Arquivo original](original.html)\n\n'
        '> Coletado para pesquisa. A data de coleta não comprova vigência; a situação declarada pela fonte consta em metadados.json.\n\n'
        '|  |  |\n| --- | --- |\n|  | **Presidência da República   Casa Civil   Subchefia para Assuntos Jurídicos** |\n\n'
        '**[LEI Nº 8.212, DE 24 DE JULHO DE 1991](https://legislacao.planalto.gov.br/x?OpenDocument)**\n\n'
        '|  |  |\n| --- | --- |\n'
        '| [Texto compilado](https://www.planalto.gov.br/L.htm) [Mensagem de veto](https://x) [Vide Lei n° 15.371, de 2026](https://x) [Vigência](https://x) | '+ementa+' |\n\n'
        'O PRESIDENTE DA REPÚBLICA Faço saber que o Congresso Nacional decreta e eu sanciono a seguinte Lei:\n\n'+corpo)


def test_ementa_vem_da_celula_da_tabela_e_ignora_linhas_vazias_e_autoria():
    from backend.refino.pipeline import ementa, normalize_text
    assert ementa(normalize_text(planalto('Dispõe sobre a organização da Seguridade Social, institui Plano de Custeio.')))=='Dispõe sobre a organização da Seguridade Social, institui Plano de Custeio.'
    assert ementa('|  |  |\n| --- | --- |\n|  |  |\n(Autoria do Projeto: Poder Executivo)\n\nReestrutura a Carreira de Auditoria Tributária do DF.')=='Reestrutura a Carreira de Auditoria Tributária do DF.'


def test_lei_8212_com_muitos_termos_no_corpo_nao_e_relacionada(tmp_path):
    corpo='\n'.join('A contribuição social do empregador, art. %d.'%i for i in range(10))
    folder,_=refine(tmp_path,[('8212','https://www.planalto.gov.br/ccivil_03/leis/l8212compilado.htm',planalto('Dispõe sobre a organização da Seguridade Social, institui Plano de Custeio.',corpo),'normas-citadas',dict(natureza_documental='legislacao',titulo='Lei nº 8212/1991'))])
    oc=read_rows(folder,'ocorrencias.jsonl')[0]
    assert oc['ementa'].startswith('Dispõe sobre a organização') and oc['termos_no_corpo']>=5
    assert read_rows(folder,'indice_nucleo.jsonl')[0]['etiquetas']==[]


def test_leis_10833_e_9718_com_ementa_tributaria_nao_sao_relacionadas(tmp_path):
    folder,_=refine(tmp_path,[
        ('10833','https://www.planalto.gov.br/ccivil_03/leis/2003/L10833.htm',planalto('Altera a Legislação Tributária Federal e dá outras providências.'),'normas-citadas',dict(natureza_documental='legislacao',titulo='Lei nº 10833/2003')),
        ('9718','https://www.planalto.gov.br/ccivil_03/leis/L9718.htm',planalto('Altera a Legislação Tributária Federal.'),'normas-citadas',dict(natureza_documental='legislacao',titulo='Lei nº 9718/1998'))])
    assert [r['etiquetas'] for r in read_rows(folder,'indice_nucleo.jsonl')]==[[],[]]


def test_codigo_civil_com_poucos_termos_e_relacionada_e_continua_no_indice(tmp_path):
    folder,_=refine(tmp_path,[('cc','https://www.planalto.gov.br/ccivil_03/leis/2002/L10406.htm',planalto('Institui o Código Civil.','Art. 1 Texto. Contribuição, uma vez.'),'normas-citadas',dict(natureza_documental='legislacao',titulo='Lei nº 10406/2002'))])
    row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert row['etiquetas']==['relacionada'] and row['versoes']


def test_situacao_conflitante_entre_versoes_nao_e_resolvida_e_etiqueta_segue_preferida(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('c','multivigente',base,situacao_fonte='Vigente'),citada('o','original',base+'\nRedação original',situacao_fonte='Revogado')])
    vs=versions_by_visao(folder);row=read_rows(folder,'indice_nucleo.jsonl')[0]
    assert row['representacao_preferida']==vs['compilada']['id'] and 'revogada' not in row['etiquetas']
    assert row['situacao_por_versao'][vs['compilada']['id']]==dict(zip(vs['compilada']['ocorrencias'],['Vigente']))
    assert row['situacao_por_versao'][vs['original']['id']]==dict(zip(vs['original']['ocorrencias'],['Revogado']))
    assert vs['original']['etiquetas']==['revogada'] and vs['compilada']['etiquetas']==[]


def test_revogada_da_versao_preferida_entra_na_etiqueta_do_indice(tmp_path):
    base='# Lei\n'+'\n'.join('Art. %d Texto.'%i for i in range(40))
    folder,_=refine(tmp_path,[citada('c','multivigente',base,situacao_fonte='Revogado'),citada('o','original',base+'\nRedação original',situacao_fonte='Vigente')])
    assert read_rows(folder,'indice_nucleo.jsonl')[0]['etiquetas']==['relacionada','revogada']


def test_negacao_so_vale_ate_pontuacao():
    from backend.refino.pipeline import revogada, load_policy
    cfg=load_policy()['etiquetas']['revogada']
    assert revogada('Não consta revogação, mas foi revogada pela Lei X',cfg)
    assert revogada('Revogada',cfg) and not revogada('Não revogada',cfg)
    assert not revogada('Não consta revogação expressa',cfg)


def test_apenas_versao_parcial_conta_documento_unico(tmp_path):
    from backend.refino.pipeline import antes_depois
    pasta=tmp_path/'run';pasta.mkdir()
    (pasta/'manifesto.json').write_text(json.dumps(dict(run_id='r',indices_documentos={},bytes_textuais_entrada=0,bytes_conteudos_unicos=0,bytes_busca=0)),encoding='utf8')
    (pasta/'auditoria_extracao.jsonl').write_text('',encoding='utf8')
    linhas=[dict(documento_id='d1',apenas_versao_parcial=True),dict(documento_id='d1',apenas_versao_parcial=True),dict(documento_id='d2',apenas_versao_parcial=False)]
    (pasta/'indice_nucleo.jsonl').write_text('\n'.join(json.dumps(l) for l in linhas)+'\n',encoding='utf8')
    out=antes_depois(pasta,pasta)
    assert out['atual']['apenas_versao_parcial']['count']==1 and out['atual']['apenas_versao_parcial']['documentos']==['d1']
