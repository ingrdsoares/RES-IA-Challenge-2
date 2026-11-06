"""Sumarização descritiva e referências exaustivas dos snapshots e recibos locais."""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from urllib.parse import quote,urlsplit
from .catalogo import collect as catalog,frontmatter,Hasher,FRONTES,walk_files
from .anexos import _cell,_write_atomic

DATA=Path(__file__).resolve().parent/'data'
DOCS=Path(__file__).resolve().parents[2]/'docs'
SCOPES={
 'legislacao':'Núcleo jurídico do Simples Nacional: textos legais, dispositivos e versões publicados nas fontes oficiais. O acervo serve à fundamentação; a coleta não certifica vigência ou interpretação aplicável a cada contribuinte.',
 'anexos-cgsn140':'Anexos publicados da regulamentação do Simples, com tabelas e conteúdos auxiliares. A numeração, as versões e a integridade devem ser mantidas ao estruturar regras de enquadramento e cálculo.',
 'manuais':'Manuais de apuração e declaração do Simples e MEI, incluindo PGDAS-D/DEFIS, PGMEI e DASN-SIMEI. Contêm procedimentos, telas, tabelas e exemplos operacionais; textos extraídos não substituem a revisão do PDF.',
 'mei':'Orientações públicas sobre ocupações, enquadramento, obrigações e situações do MEI. Critérios de elegibilidade precisam ser relacionados à competência, à atividade efetiva e às normas correspondentes.',
 'cnae':'Códigos, descrições e hierarquia de atividades econômicas do IBGE. CNAE descreve atividade; isoladamente não determina anexo tributário, enquadramento ou elegibilidade MEI.',
 'notas-cnae':'Notas explicativas da CNAE/CONCLA, incluindo alcance, inclusões e exclusões de atividades. A versão da publicação é parte da informação e deve acompanhar qualquer cruzamento com códigos.',
 'cnpj':'Dados cadastrais e tabelas auxiliares oficiais da Receita. Códigos, portes e naturezas são mantidos como texto. Capital declarado não é faturamento e códigos de município da Receita não equivalem automaticamente aos do IBGE.',
 'cnpj-ampliado':'Cruzamentos amostrais iniciais de empresas, estabelecimentos e opções Simples/MEI. São amostras de conveniência, sem representatividade estatística; preservadas para rastrear a evolução da coleta.',
 'cnpj-df':'Amostra de empresas ativas com estabelecimento no DF, cruzada com opções públicas Simples/MEI. Ausência no arquivo de opções permanece distinta de opção literal N.',
 'cnpj-df-censo':'Recorte dos dez lotes de estabelecimentos, dez de empresas e arquivo Simples da competência 2026-10. Contém 413.539 empresas de portes 01/03 com estabelecimento ativo no DF, uma linha por raiz. Não inclui todos os portes nem todas as filiais; 195.132.919 linhas brutas foram percorridas nos três conjuntos.',
 'consultas-rfb':'Soluções de Consulta e Divergência recuperadas por buscas temáticas sobre Simples, MEI, Fator R e segregação de receitas. Ementas e integrais disponíveis são identificados; interpretações administrativas não são leis de aplicação universal.',
 'obrigacoes':'Agendas e orientações declaratórias da Receita: prazos publicados, PGDAS-D, DEFIS e DASN-SIMEI. A exigibilidade depende do perfil empresarial, da competência e das condições da obrigação.',
 'obrigacoes-avancadas':'Documentação DCTFWeb, eSocial e EFD-Reinf: manuais, eventos, leiautes e schemas. Disponibilidade documental não implica que toda obrigação se aplique a MEIs ou microempresas.',
 'calendario-df':'Agenda federal de 2026 e atos sobre feriados, pontos facultativos e alterações no DF e na administração federal. Versões documentais e registros sobrepostos são preservados; pontos facultativos não deslocam automaticamente vencimentos fiscais.',
 'distrital-df':'Legislação e orientações locais de ISS, retenções e NFS-e no Distrito Federal. Manuais do fornecedor vinculados pela administração são distinguidos de textos normativos. Normas municipais de outras localidades não são aplicadas ao DF.',
 'icms-consultas-df':'Regulamento ICMS/DF, Lei 1.254 e normas relacionadas descobertas a partir das fontes sementes. Inclui quatro diários com consultas tributárias e um com jurisprudência TARF; documentos integrais podem conter outras matérias. Não equivale a todo o acervo local.',
 'consultas-df-amplas':'Consultas tributárias com texto integral publicadas de 2010 a 2026 e páginas TARF contendo ementa e decisão. A seleção do TARF é limitada por tema/paginação e não representa votos integrais nem todos os julgados.',
 'documentos-fiscais':'Documentação inicial de NF-e/NFS-e e padrões de integração. São referências técnicas para futura leitura e conferência; não constituem autorização de emissão ou acesso a documentos de terceiros.',
 'notas-tecnicas-fiscais':'Notas técnicas, classificações e planilhas de documentos fiscais, incluindo informações relacionadas à reforma e correlações publicadas. Tabelas extraídas preservam estrutura disponível, mas não certificam cálculos nem aplicabilidade universal.',
 'xmls-exemplo':'Exemplos oficiais municipais de São Paulo e pacotes nacionais examinados. Schemas não são instâncias XML; os exemplos de São Paulo não comprovam compatibilidade com o DF. Permanecem lacunas de instâncias nacionais e distritais.',
 'documentos-jurisprudencia':'Ampliação de manuais, notas, eventos, schemas e planilhas NF-e/NFS-e, mais consultas CARF e conteúdo editorial do STJ. Ementas/editoriais são distinguidos de julgados em inteiro teor; dependências de schemas e falhas remotas são explícitas.',
 'fontes-recuperadas':'Tentativas de recuperação de fontes antes indisponíveis por caminhos oficiais públicos. A resolução é registrada separadamente das falhas históricas e não envolve contorno de autenticação, captcha ou restrições.',
 'sped-complementar':'Manuais e catálogos oficiais ECD, ECF, EFD-Contribuições e EFD-ICMS/IPI, identificados por versão. A extração textual mantém páginas; imagens e organização visual de tabelas devem ser conferidas nos originais.',
 'tributacao-lucro':'Leis 9.249/1995 e 9.430/1996, IN RFB 1.700/2017 e RIR/Decreto 9.580/2018. Visões publicadas, versões e marcadores históricos são preservados; não foi implementado cálculo tributário nem inferida vigência.',
 'reforma-historico':'Marcos normativos da reforma do consumo e histórico CGSN/MEI, com respostas das visões solicitadas e efetivamente retornadas pela API. Reúne EC 132, LC 214, LC 227, Decreto 12.955 e atos encontrados por CBS/IBS/CGSN. Linha do tempo publicada não equivale a datas de produção de efeitos verificadas.',
 'reforma':'Documentação inicial de implantação da reforma tributária do consumo, cronogramas e orientações. Deve ser lida por versão e competência, em conjunto com o núcleo normativo ampliado.',
 'retencoes-defesa-setores':'Atos e interpretações sobre ISS e retenções federais/previdenciárias, tributação fora do DAS e substituição tributária; fiscalização, multas, impugnação e recursos; restituição e compensação. Inclui buscas setoriais em tecnologia/software, saúde, construção, alimentação e comércio. A pertinência é recuperada literalmente pela busca, não certifica regras completas de cada setor.',
 'sumulas-classificacao':'Quadros de súmulas CARF, referências textuais a precedentes, atos administrativos relacionados, compêndios NESH/Ceclam/OMA/Mercosul e tabela NCM. A NCM contém nós hierárquicos e códigos finais distintos; referências a acórdãos não equivalem a integrais coletadas e modelos de petição não têm força normativa.',
 'historico-competencias':'Agendas federais históricas em HTML/PDF e disponibilidade de competências no compartilhamento CNPJ. Índices vazios, formatos antigos e meses ausentes são distinguidos de falhas. A listagem de competências não significa que os respectivos cadastros antigos tenham sido baixados.',
 'anexos-recuperados':'Conversão local de anexos Word e reconhecimento OCR em português de imagens, incluindo imagens incorporadas. Os bytes oficiais originais permanecem preservados. Texto OCR, tabelas e formatação exigem revisão humana; a recuperação complementa pendências registradas em versões anteriores.',
 'casos-oficiais':'Trechos literais candidatos a exemplos encontrados em manuais existentes, com linhas e páginas quando identificadas. São enriquecimentos derivados, não documentos oficiais novos nem casos de cálculo certificados.',
 'legislacao-complementar':'Leis e atos complementares ao núcleo inicial, incluindo alterações do Simples, ICMS, escrituração e documentos fiscais. Cada texto é tratado por identidade, origem e versão, sem consolidar automaticamente regras vigentes.',
 'regularizacao-fiscal':'Orientações públicas da Receita e PGFN sobre parcelamentos, dívida ativa, situação fiscal e certidões. Não inclui acesso a contas fiscais, dados privados, emissão ou adesão a negociações.',
 'indicadores-empresariais':'Publicações Mapa de Empresas, JUCIS-DF e indicadores públicos Sebrae. Estoques, aberturas, fechamentos, empresas e MEIs mantêm suas definições e datas próprias; não são somados automaticamente.',
 'ibge-indicadores':'Séries e indicadores públicos do IBGE úteis ao contexto empresarial. Conceitos, unidades e períodos da fonte devem acompanhar as observações.',
 'sebrae':'Conteúdo público de orientação empresarial. É distinguido de norma jurídica; indisponibilidades de painéis e alternativas oficiais coletadas permanecem registradas.',
 'complemento-contabil':'Normas e materiais contábeis complementares para micro e pequenas empresas. Referências contábeis não substituem a identificação do regime tributário nem revisão profissional.',
 'contabilidade':'Referências contábeis iniciais do projeto, preservadas com origem e versão. O inventário individual descreve os artefatos disponíveis.',
 'economia':'Dados e referências econômicas iniciais para contexto, com períodos e unidades da fonte. Não são indicadores de faturamento privado das empresas cadastradas.',
 'tabelas-fiscais':'Tabelas e códigos fiscais auxiliares, preservando identificação e versão. Códigos e correlações não estabelecem, isoladamente, a tributação de uma operação.'}


def valid_url(value):
    return isinstance(value,str) and urlsplit(value).scheme in ('http','https') and bool(urlsplit(value).netloc)


def build_index(root,inventory):
    root=Path(root).resolve();entries=[];refs={};errors=[]
    cachefile=root/'catalogo'/'hash-cache.json'
    cache=json.loads(cachefile.read_bytes()) if cachefile.exists() else {}
    hasher=Hasher(cache)
    def add(url,kind,entry=None,file=None,checksum=None,date=None,front=None):
        if not valid_url(url):return
        r=refs.setdefault(url,dict(url=url,categorias=set(),entradas=set(),arquivos=set(),sha256=set(),datas=set(),frentes=set()))
        r['categorias'].add(kind)
        for key,value in [('entradas',entry),('arquivos',file),('sha256',checksum),('datas',date),('frentes',front)]:
            if value is not None:
                if key=='arquivos':
                    path=Path(value)
                    if path.is_absolute():
                        try:value=path.relative_to(root).as_posix()
                        except ValueError:value=str(path)
                    else:value=path.as_posix()
                r[key].add(str(value))
    def read_metadata(snapshot):
        mp=root/snapshot['metadados']
        try:return (json.loads(mp.read_bytes()) if mp.suffix=='.json' else frontmatter(mp.read_text(encoding='utf-8-sig'))),None
        except (ValueError,OSError) as exc:return None,dict(arquivo=snapshot['metadados'],erro=str(exc))
    with ThreadPoolExecutor(max_workers=8) as pool:metadata=list(pool.map(read_metadata,inventory['snapshots']))
    for number,(snapshot,(meta,error)) in enumerate(zip(inventory['snapshots'],metadata),1):
        mp=root/snapshot['metadados']
        if error:errors.append(error);continue
        directory=snapshot['diretorio'];front=directory.split('/')[0]
        urls=set();source=snapshot.get('origem')
        add(source,'origem_declarada',number,date=snapshot.get('coletado_em'),front=front)
        if valid_url(source):urls.add(source)
        for item in meta.get('originais',[]) or []:
            url=item.get('source_url')
            add(url,'original_referenciado',number,file=item.get('arquivo'),checksum=item.get('sha256'),date=snapshot.get('coletado_em'),front=front)
            if valid_url(url):urls.add(url)
        for check in snapshot['verificacoes']:
            if check.get('tipo')=='derivado_markdown':continue
            url=check.get('source_url') or source
            add(url,'arquivo_auditado',number,file=check['arquivo'],checksum=check.get('sha256_calculado'),date=snapshot.get('coletado_em'),front=front)
            if valid_url(url):urls.add(url)
        for key in ('catalog_url','consulta_url','api_url'):
            url=meta.get(key);add(url,'referencia_contextual',number,front=front)
            if valid_url(url):urls.add(url)
        title=str(meta.get('titulo') or meta.get('title') or meta.get('source_id') or directory)
        kind=str(meta.get('natureza_documental') or meta.get('tipo') or meta.get('kind') or 'artefato_documental')
        themes=meta.get('temas',[]);themes=themes if isinstance(themes,list) else [str(themes)]
        description='Tipo: '+kind+'.'
        if themes:description+=' Temas de recuperação: '+', '.join(str(t) for t in themes)+'.'
        for key,label in [('paginas','Páginas'),('paginas_pdf','Páginas PDF'),('registros','Registros'),('arquivos_xsd','XSD'),('candidatos','Trechos candidatos')]:
            value=meta.get(key)
            if type(value) is int:description+=f' {label}: {value}.'
        version=meta.get('versao_documental') or meta.get('versao')
        if version and isinstance(version,(str,int,float)):description+=' Versão declarada: '+str(version)+'.'
        entries.append(dict(id=number,frente=front,titulo=title,tipo=kind,resumo=description,source_urls=sorted(urls),diretorio=directory,
            metadados=snapshot['metadados'],markdown=meta.get('markdown_arquivo') or meta.get('markdown_file') or next((p.name for p in mp.parent.glob('*.md') if p.name not in ('indice.md','tabelas.md')),None),
            coletado_em=snapshot.get('coletado_em'),status=snapshot.get('status_fonte'),revisao=snapshot.get('revisao_humana'),problemas=snapshot.get('problemas',[]),sha256=snapshot.get('sha256')))
    receipts=[p for p in walk_files(root) if p.name.endswith('.receipt.json') and not any(x in ('catalogo','estatisticas','__pycache__') for x in p.relative_to(root).parts)]
    def check_receipt(receipt):
        try:
            meta=json.loads(receipt.read_bytes());raw=receipt.with_name(receipt.name[:-len('.receipt.json')])
            if not isinstance(meta,dict) or not valid_url(meta.get('source_url')):return None,None,None
            if not raw.is_file() or hasher.digest(raw)!=meta.get('sha256'):raise ValueError('Recibo sem arquivo íntegro correspondente')
            return meta,raw,None
        except (ValueError,OSError,TypeError) as exc:return None,None,dict(arquivo=receipt.relative_to(root).as_posix(),erro=str(exc))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for meta,raw,error in pool.map(check_receipt,receipts):
            if error:errors.append(error)
            elif meta:add(meta['source_url'],'requisicao_com_recibo',file=raw.relative_to(root).as_posix(),checksum=meta['sha256'],date=meta.get('coletado_em'),front=raw.relative_to(root).parts[0])
    cachefile.parent.mkdir(parents=True,exist_ok=True)
    _write_atomic(cachefile,json.dumps(hasher.cache,ensure_ascii=False,indent=2)+'\n')
    return dict(entradas=entries,referencias=[{k:sorted(v) if isinstance(v,set) else v for k,v in r.items()} for url,r in sorted(refs.items())],erros=errors)


def href(url):return quote(str(url),safe=":/?#[]@!$&'*+,;=%")


def local(path,base):return Path(os.path.relpath(path,base)).as_posix()


def generate(root=DATA,docs=DOCS,inventory=None,statistics=None):
    root=Path(root).resolve();docs=Path(docs).resolve();docs.mkdir(parents=True,exist_ok=True);appendices=docs/'referencias-acervo';appendices.mkdir(exist_ok=True)
    inventory=catalog(root) if inventory is None else inventory
    if statistics is None:
        statistics=json.loads((root/'estatisticas'/'totais.json').read_bytes()) if (root/'estatisticas'/'totais.json').exists() else {}
    if statistics.get('snapshots') is not None and statistics['snapshots']!=len(inventory['snapshots']):raise ValueError('Estatísticas desatualizadas: execute estatisticas antes da sumarização')
    index=build_index(root,inventory);entries=index['entradas'];refs=index['referencias'];byfront=defaultdict(list)
    for r in entries:byfront[r['frente']].append(r)
    for ref in refs:
        for front in ref['frentes']:byfront.setdefault(front,[])
    names={v:k for k,v in FRONTES.items()}
    main=['# Sumarização integral do acervo tributário','', 'Gerado em '+datetime.now(timezone.utc).isoformat()+'. Catálogo auditado em '+str(inventory.get('executado_em','não informado'))+'. Documento descritivo da coleta local; não é parecer jurídico nem certificação de vigência.','',
          'O acervo reúne legislação, anexos, manuais, interpretações administrativas, jurisprudência selecionada, classificações, cadastros e indicadores. Brasília/DF é o foco local. As descrições por frente sintetizam o assunto e a utilidade; os anexos inventariam cada versão e sua natureza documental, sem transformar uma ementa, modelo ou orientação em norma.','',
          '## Dimensão e unidades','', '| Medida | Total |','|---|---:|']
    for key,label in [('snapshots','Snapshots/versões'),('originais_conteudos_distintos','Conteúdos originais distintos por hash'),('markdown_arquivos','Arquivos Markdown'),('paginas_pdf_distintas','Páginas físicas de PDFs distintos'),('xsd_conteudos_distintos','Conteúdos XSD distintos'),('empresas_raizes_distintas','Empresas distintas por raiz'),('gib_em_disco','Volume local (GiB)')]:
        if key in statistics:main.append(f'| {label} | {statistics[key]} |')
    main+=['',f'Este inventário descreve **{len(entries)} entradas catalogadas** e **{len(refs)} URLs distintas**. URLs de consulta/catálogo são referências contextuais; referências com arquivo auditado ou recibo indicam a evidência local. Arquivos em cache sem snapshot semântico ficam nas referências, sem aumentar a contagem de documentos.','',
           'As medidas não são somadas: uma norma pode ter duas visões, vários anexos, diversas páginas e múltiplas versões. A tabela NCM contém níveis hierárquicos; empresas são deduplicadas por raiz. Páginas físicas não garantem texto integral extraído.','',
           '## Mapa completo do conteúdo','', '| Frente | Entradas | Referências | Inventário e fontes |','|---|---:|---:|---|']
    for front,items in sorted(byfront.items()):
        references=[r for r in refs if front in r['frentes']];name=names.get(front,front)
        main.append('| '+_cell(name)+f' | {len(items)} | {len(references)} | [Descrições e links](referencias-acervo/{front}.md) |')
        text=['# '+name,'',SCOPES.get(front,'Artefatos auxiliares ou referências preservadas nesta pasta. As descrições abaixo identificam tipo, versão e procedência de cada entrada efetivamente catalogada.'),'',f'Entradas: {len(items)}. URLs distintas vinculadas: {len(references)}.','',
              '## Entradas e descrições','', '| ID | Título | Descrição e situação | Origem | Arquivos locais |','|---|---|---|---|---|']
        navigation=[]
        for filename,label in [('indice.md','Índice da coleta'),('manifesto.json','Manifesto, limites e falhas')]:
            path=root/front/filename
            if path.is_file():navigation.append('['+label+']('+local(path,appendices)+')')
        if navigation:text[2:2]=[' · '.join(navigation),'']
        for r in items:
            origin='; '.join(f'[Fonte {i}]({href(u)})' for i,u in enumerate(r['source_urls'],1))
            links='[Metadados]('+local(root/r['metadados'],appendices)+')'
            if r['markdown']:links+=' · [Conteúdo]('+local(root/r['diretorio']/r['markdown'],appendices)+')'
            desc=r['resumo']+' Estado: '+str(r['status'])+'. Revisão: '+str(r['revisao'])+'. Coleta: '+str(r['coletado_em'])+'.'
            if r['problemas']:desc+=' Integridade: '+', '.join(r['problemas'])+'.'
            text.append('| '+str(r['id'])+' | '+_cell(r['titulo'])+' | '+_cell(desc)+' | '+origin+' | '+links+' |')
        text+=['','## Todas as referências desta frente','','Cada URL aparece uma vez nesta lista, com todas as entradas vinculadas. As versões e os arquivos correspondentes estão no JSON integral.','']
        for ref in references:
            text+=['- [Referência oficial/declarada]('+href(ref['url'])+') — '+', '.join(ref['categorias'])+'; entradas: '+(', '.join(str(i) for i in ref['entradas']) or 'somente cache/descoberta')+'.']
        (appendices/(front+'.md')).write_bytes(('\n'.join(text)+'\n').encode())
        main+=[]
    main+=['','## Síntese por frente','']
    for front in sorted(byfront):main+=['### '+names.get(front,front),'',SCOPES.get(front,'Pasta auxiliar com referências de coleta ou descoberta; não foi atribuída aplicação tributária sem metadados.'),'',f'Consulte [todas as entradas e fontes desta frente](referencias-acervo/{front}.md).','']
    main+=['## Cobertura das nove expansões','',
           '1. Recuperação de anexos: conversão Word e OCR com originais preservados, complementando pendências históricas.','2. Súmulas/precedentes: quadros, atos e referências textuais; quantidade de identificadores não significa íntegra disponível ou vigência.','3. Mercadorias: NCM hierárquica e compêndios de classificação; classificar um produto exige aplicar regras e verificar o caso concreto.','4. Distrito Federal: consultas integrais e páginas TARF; seleções e limites por busca estão nos manifestos.','5. Retenções/fora do DAS: corpus temático de normas e interpretações.','6. Fiscalização/defesa: penalidades, procedimentos, impugnações e recursos recuperados por buscas explícitas.','7. Restituição/compensação: atos e orientações sobre pagamentos e créditos, sem acesso a contas privadas.','8. Setores: recortes de tecnologia, saúde, construção, alimentação e comércio, sem presumir regras únicas por CNAE.','9. Histórico: agendas e versões publicadas por competência, com índices vazios, ausências e falhas identificados.','',
           '## Limites e leitura jurídica','',
           'Integridade de bytes não certifica vigência, completude jurídica, aplicabilidade, força vinculante, qualidade de OCR ou exatidão de tabelas. Consultas e decisões se referem a contextos próprios. As notas técnicas e schemas não são notas fiscais reais nem prova de validação fiscal. Modelos de petição são materiais operacionais sem força normativa.','',
           'Persistem fontes bloqueadas/indisponíveis e referências a julgados sem inteiro teor; não houve contorno de captcha, autenticação ou restrições. Dependências XSD ausentes, páginas sem texto e anexos ainda sem conversão são listados nos manifestos. Pendências de versões anteriores podem ter recuperação em outra frente, sem apagar o histórico.','',
           'A lista integral e mecanicamente verificável está em [referencias-acervo/inventario-integral.json](referencias-acervo/inventario-integral.json). A navegação dos conteúdos locais pressupõe que a pasta backend/crawler/data esteja disponível; os links oficiais continuam independentes dessa pasta.','',
           '## Reprodução','', '`python -m backend.crawler.estatisticas` atualiza as contagens. Depois, `python -m backend.crawler.sumarizacao` recompõe este documento e todos os anexos de referências.','']
    if index['erros']:main+=['## Pendências técnicas do inventário','']+['- '+str(e) for e in index['erros']]
    (docs/'sumarizacao-acervo-tributario.md').write_bytes(('\n'.join(main)+'\n').encode())
    (appendices/'inventario-integral.json').write_bytes(json.dumps(index,ensure_ascii=False,indent=2).encode())
    report=dict(entradas=len(entries),urls=len(refs),frentes=len(byfront),erros=index['erros'],documento=str(docs/'sumarizacao-acervo-tributario.md'))
    (appendices/'verificacao.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode());return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=DATA);p.add_argument('--docs',type=Path,default=DOCS);a=p.parse_args()
    cached_catalog=a.data/'catalogo'/'catalogo.json'
    inventory=json.loads(cached_catalog.read_bytes()) if cached_catalog.exists() else None
    print(json.dumps(generate(a.data,a.docs,inventory=inventory),ensure_ascii=False,indent=2))
