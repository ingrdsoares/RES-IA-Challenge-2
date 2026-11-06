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


def test_atos_com_texto_quase_igual_continuam_separados(tmp_path):
    body='# Ineficácia\n'+'\n'.join('Linha %d do texto.'%i for i in range(50))
    folder,report=refine(tmp_path,[('a',RFB%'1',body+'\nfim 19','consultas-rfb',dict(titulo='Solução de Ineficácia nº 19/2019')),('b',RFB%'2',body+'\nfim 20','consultas-rfb',dict(titulo='Solução de Ineficácia nº 20/2019'))])
    assert report['documentos_logicos']==2 and len(read_rows(folder,'indice_nucleo.jsonl'))==2


def test_consulta_rfb_mantem_identidade_por_ato(tmp_path):
    meta=dict(natureza_documental='legislacao',titulo='Instrução Normativa RFB nº 1.500, de 29 de outubro de 2014')
    folder,_=refine(tmp_path,[('a',RFB%'111','# IN\nTexto.','legislacao',meta)])
    assert read_rows(folder,'documentos.jsonl')[0]['chave_origem']=='rfb:ato:111'


def citada(name,visao,text):
    return (name,'https://x.gov.br/'+name,text,'normas-citadas',dict(norma_chave='federal:lei:-:9:2000',visao_fonte=visao,natureza_documental='legislacao',titulo='Lei nº 9/2000'))


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
