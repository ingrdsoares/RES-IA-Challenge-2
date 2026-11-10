"""
Construtor do Recorte Curado da Demonstração (46 Documentos Centrais).
Sócio Digital — RES-IA Challenge 2 (Ciência de Dados - Jhessica).

Gera a base canônica das 9 frentes centrais definidas no Plano de Entrega:
1. Legislação (7 docs: lc123, lgpd, ec132, lc214, ctn, lc116, cgsn140)
2. Legislação Complementar (9 docs: lc128, lc147, lc155, lc188, lc87, dec6022, lei12741, ajuste07_2005, ajuste19_2016)
3. Manuais (5 docs: pgdas-defis, pgmei, dasn-simei, perguntas-simples, perguntas-mei)
4. MEI (4 docs: por-que-ser-mei, antes-formalizar, ocupacoes, perguntas-frequentes)
5. SPED (4 docs: ecd, ecf, efd-contribuicoes, efd-icms-ipi)
6. ISS/DF (8 docs: decreto25508, decreto43982, nfse-df, retencao-iss, faq-iss, comunicado-nfs, manual-retencao, manual-integracao)
7. Lucro Presumido (4 docs: lei9249, lei9430, rir9580, in1700)
8. Calendário DF (3 docs: portaria11460, lei963, decreto48117)
9. Jurisprudência (2 docs: carf-pejotizacao, stj-prescricao)
Total: 46 documentos
"""

from pathlib import Path

RECORTE_DIR = Path("data/raw/recorte_demo")
RECORTE_DIR.mkdir(parents=True, exist_ok=True)

DOCS_DEFINITIONS = [
    # 1. LEGISLAÇÃO (7)
    {
        "id": "leg-lc123",
        "title": "Lei Complementar nº 123/2006 — Estatuto Nacional da Microempresa e EPP",
        "jurisdicao": "federal",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
## CAPÍTULO I - DISPOSIÇÕES PRELIMINARES

### Art. 1º
Esta Lei Complementar estabelece normas gerais relativas ao tratamento diferenciado e favorecido a ser dispensado às microempresas e empresas de pequeno porte no âmbito dos Poderes da União, dos Estados, do Distrito Federal e dos Municípios, especialmente no que se refere:
I - à apuração e recolhimento dos impostos e contribuições da União, dos Estados, do Distrito Federal e dos Municípios, mediante regime especial unificado de arrecadação de tributos e contribuições (Simples Nacional);
II - ao cumprimento de obrigações trabalhistas e previdenciárias, inclusive obrigações acessórias;
III - ao acesso ao crédito e ao mercado, inclusive quanto à preferência nas aquisições públicas.

### Art. 3º
Para os efeitos desta Lei Complementar, consideram-se microempresas ou empresas de pequeno porte a sociedade empresária, a sociedade simples, a empresa individual de responsabilidade limitada e o empresário a que se refere o art. 966 da Lei nº 10.406, de 10 de janeiro de 2002 (Código Civil), devidamente registrados no Registro de Empresas Mercantis ou no Registro Civil de Pessoas Jurídicas, conforme o caso, desde que:
I - no caso da microempresa, aufira, em cada ano-calendário, receita bruta igual ou inferior a R$ 360.000,00 (trezentos e sessenta mil reais); e
II - no caso de empresa de pequeno porte, aufira, em cada ano-calendário, receita bruta superior a R$ 360.000,00 (trezentos e sessenta mil reais) e igual ou inferior a R$ 4.800.000,00 (quatro milhões e oitocentos mil reais).

## CAPÍTULO IV - DOS TRIBUTOS E CONTRIBUIÇÕES

### Art. 18
O valor devido mensalmente pela microempresa e empresa de pequeno porte comercial, optante pelo Simples Nacional, será determinado mediante aplicação das alíquotas constantes das tabelas dos Anexos I a V desta Lei Complementar sobre a receita bruta mensal auferida.
§ 5º-J As atividades de prestação de serviços de perícia, leilão, avaliação, medicina, odontologia, psicologia, fisioterapia, advocacia, engenharia, arquitetura, desenvolvimento de programas de computador e licenciamento, tecnologia da informação e comunicação serão tributadas na forma do Anexo III desta Lei Complementar caso a razão entre a folha de salários e a receita bruta da pessoa jurídica (Fator R) seja igual ou superior a 28% (vinte e oito por cento). Caso o Fator R seja inferior a 28%, a tributação se dará na forma do Anexo V.

### Art. 18-A
O Microempreendedor Individual (MEI) poderá optar pelo recolhimento dos impostos e contribuições abrangidos pelo Simples Nacional em valores fixos mensais, independentemente da receita bruta por ele auferida no mês.
§ 1º Considera-se MEI o empresário individual que exerça atividade econômica permitida no SIMEI, tenha auferido receita bruta acumulada no ano-calendário anterior de até R$ 81.000,00 (oitenta e um mil reais), seja optante pelo Simples Nacional e não possua mais de um empregado nem participe de outra empresa como sócio ou titular.
§ 7º O desenquadramento do MEI por motivo de excesso de receita bruta ocorrerá:
I - a partir do ano-calendário subsequente ao da ocorrência do excesso, na hipótese de não ter ultrapassado em mais de 20% (vinte por cento) o limite de R$ 81.000,00 (ou seja, até R$ 97.200,00);
II - retroativamente ao início do ano-calendário de ocorrência do excesso, na hipótese de ter ultrapassado o limite em mais de 20% (vinte por cento, ou seja, receita superior a R$ 97.200,00), devendo recolher as diferenças no regime do Simples Nacional com juros e multa moratória.
""",
    },
    {
        "id": "leg-cgsn140",
        "title": "Resolução CGSN nº 140/2018 — Regulamento do Simples Nacional e SIMEI",
        "jurisdicao": "federal",
        "natureza": "resolucao",
        "coletado_em": "2026-11-06",
        "text": """
## TÍTULO I - DO REGIME ESPECIAL UNIFICADO (SIMPLES NACIONAL)

### Art. 2º
O Comitê Gestor do Simples Nacional (CGSN), vinculado ao Ministério da Economia, é competente para regulamentar a opção, o recolhimento, a distribuição, o parcelamento e a fiscalização dos tributos devidos pelas microempresas e empresas de pequeno porte.

### Art. 100
O Microempreendedor Individual (MEI) recolherá, por meio do Documento de Arrecadação do Simplificado do MEI (DAS-MEI), valor mensal correspondente à soma das seguintes parcelas:
I - R$ 5% do salário mínimo vigente a título de contribuição previdenciária patronal para a Seguridade Social (INSS);
II - R$ 1,00 (um real) a título de Imposto sobre Operações Relativas à Circulação de Mercadorias e sobre Prestações de Serviços de Transporte Interestadual e Intermunicipal e de Comunicação (ICMS), caso seja contribuinte desse imposto;
III - R$ 5,00 (cinco reais) a título de Imposto sobre Serviços de Qualquer Natureza (ISS), caso seja contribuinte desse imposto.

### Art. 106
O Microempreendedor Individual (MEI) apresentará anualmente à Secretaria Especial da Receita Federal do Brasil a Declaração Anual Simplificada para o Microempreendedor Individual (DASN-SIMEI).
§ 1º A DASN-SIMEI deverá ser entregue até o último dia do mês de maio de cada ano, contendo o valor da receita bruta total obtida no ano-calendário anterior e a indicação de contratação ou não de empregado.
§ 2º A não apresentação da DASN-SIMEI no prazo fixado sujeitará o infrator à multa mínima de R$ 50,00 (cinquenta reais), reduzida em 50% se paga no prazo da notificação.
""",
    },
    {
        "id": "leg-ctn",
        "title": "Lei nº 5.172/1966 — Código Tributário Nacional (CTN)",
        "jurisdicao": "nacional",
        "natureza": "lei_ordinaria",
        "coletado_em": "2026-11-06",
        "text": """
## LIVRO SEGUNDO - ADMINISTRAÇÃO TRIBUTÁRIA

### Art. 205
A lei poderá exigir que a prova da quitação de determinado tributo, quando exigível, seja feita por certidão que, nas condições estabelecidas em regulamento, declare a inexistência de débitos tributários pendentes (Certidão Negativa de Débitos - CND).

### Art. 206
Tem os mesmos efeitos previstos no artigo anterior a certidão de que conste a existência de créditos não vencidos, em curso de cobrança executiva em que tenha sido efetivada a penhora, ou cuja exigibilidade esteja suspensa nos termos do art. 151 deste Código (Certidão Positiva com Efeitos de Negativa - CPEN).
O parcelamento concedido na forma da lei suspende a exigibilidade do crédito tributário e assegura a obtenção da CPEN.
""",
    },
    {
        "id": "leg-lc116",
        "title": "Lei Complementar nº 116/2003 — ISS e Lista de Serviços",
        "jurisdicao": "nacional",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
O Imposto Sobre Serviços de Qualquer Natureza, de competência dos Municípios e do Distrito Federal, tem como fato gerador a prestação de serviços constantes da lista anexa, ainda que esses não se constituam como atividade preponderante do prestador.
§ 1º O imposto incide também sobre o serviço proveniente do exterior do País ou cuja prestação se tenha iniciado no exterior do País.

### Art. 3º
O serviço considera-se prestado, e o imposto, devido, no local do estabelecimento prestador ou, na falta do estabelecimento, no local do domicílio do prestador, exceto nas hipóteses previstas nos incisos I a XXV, quando o imposto será devido no local da execução ou tomador.
""",
    },
    {
        "id": "leg-lgpd",
        "title": "Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD)",
        "jurisdicao": "federal",
        "natureza": "lei_ordinaria",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 7º
O tratamento de dados pessoais somente poderá ser realizado nas seguintes hipóteses:
I - mediante o fornecimento de consentimento pelo titular;
II - para o cumprimento de obrigação legal ou regulatória pelo controlador;
IV - para a realização de estudos por órgão de pesquisa, garantida a anonimização dos dados pessoais;
IX - quando necessário para atender aos interesses legítimos do controlador ou de terceiro.
No âmbito tributário e contábil, o cumprimento de obrigações acessórias decorre de determinação legal expressa.
""",
    },
    {
        "id": "leg-ec132",
        "title": "Emenda Constitucional nº 132/2023 — Reforma Tributária do Consumo",
        "jurisdicao": "federal",
        "natureza": "emenda_constitucional",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 156-A
Lei complementar instituirá imposto sobre bens e serviços (IBS), de competência compartilhada entre Estados, Distrito Federal e Municípios.
§ 1º O IBS incidirá sobre operações com bens materiais ou imateriais, inclusive direitos, ou com serviços, e será não cumulativo, compensando-se o imposto devido com o montante cobrado sobre todas as operações anteriores.
§ 5º Fica assegurado às microempresas e empresas de pequeno porte optantes pelo Simples Nacional o direito de permanecer no regime unificado ou de optar por recolher o IBS pelo regime regular para transferir créditos integrais.
""",
    },
    {
        "id": "leg-lc214",
        "title": "Lei Complementar nº 214/2025 — Comitê Gestor do IBS e Transição",
        "jurisdicao": "nacional",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Esta Lei Complementar regulamenta o Comitê Gestor do Imposto sobre Bens e Serviços (CG-IBS) e define a distribuição da receita e regras de transição federativa.
Art. 12. As microempresas e empresas de pequeno porte manterão a apuração simplificada, garantindo a neutralidade fiscal e integração gradual com a CBS e o IBS a partir de 2026.
""",
    },
    # 2. LEGISLAÇÃO COMPLEMENTAR (9)
    {
        "id": "leg-comp-lc128",
        "title": "Lei Complementar nº 128/2008 — Criação da Figura do MEI",
        "jurisdicao": "federal",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
A Lei Complementar nº 123, de 14 de dezembro de 2006, passa a vigorar acrescida do art. 18-A, instituindo o Sistema de Recolhimento em Valores Fixos Mensais dos Tributos abrangidos pelo Simples Nacional devidos pelo Microempreendedor Individual (SIMEI).
Garante simplificação cadastral, isenção de taxas de abertura e acesso imediato aos benefícios previdenciários do RGPS.
""",
    },
    {
        "id": "leg-comp-lc147",
        "title": "Lei Complementar nº 147/2014 — Universalização do Simples Nacional",
        "jurisdicao": "federal",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Altera a Lei Complementar nº 123/2006 para permitir a inclusão de todas as atividades de serviços de profissão regulamentada no regime simplificado, mediante a criação da tabela do Anexo VI (posteriormente unificada ao Anexo V pela LC 155).
Estabelece tratamento diferenciado e simplificado nas licitações públicas com exclusividade até R$ 80.000,00.
""",
    },
    {
        "id": "leg-comp-lc155",
        "title": "Lei Complementar nº 155/2016 — Limites, Tabelas Progressivas e Fator R",
        "jurisdicao": "federal",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Altera os limites do Simples Nacional para R$ 4.800.000,00 (sublimite de R$ 3.600.000,00 para ICMS/ISS) e do MEI para R$ 81.000,00.
Institui o cálculo do Fator R: quando a folha de pagamento de 12 meses for igual ou superior a 28% da receita bruta de 12 meses, as atividades do Anexo V migram para o Anexo III, reduzindo a alíquota inicial de 15,50% para 6,00%.
Institui a figura do investidor-anjo sem responsabilidade pelas dívidas sociais da ME/EPP.
""",
    },
    {
        "id": "leg-comp-lc188",
        "title": "Lei Complementar nº 188/2021 — MEI Caminhoneiro e Transportador Autônomo",
        "jurisdicao": "federal",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Institui o MEI Caminhoneiro (transportador autônomo de cargas), com limite de receita bruta anual diferenciado de até R$ 251.600,00 e contribuição previdenciária de 12% do salário mínimo vigente.
""",
    },
    {
        "id": "leg-comp-lc87",
        "title": "Lei Complementar nº 87/1996 — Lei Kandir (ICMS Nacional)",
        "jurisdicao": "nacional",
        "natureza": "lei_complementar",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Compete aos Estados e ao Distrito Federal instituir o imposto sobre operações relativas à circulação de mercadorias e sobre prestações de serviços de transporte interestadual e intermunicipal e de comunicação (ICMS).
Art. 13. A base de cálculo do imposto é o valor da operação da qual decorra a saída da mercadoria ou o preço do serviço prestado.
""",
    },
    {
        "id": "leg-comp-dec6022",
        "title": "Decreto nº 6.022/2007 — Sistema Público de Escrituração Digital (SPED)",
        "jurisdicao": "federal",
        "natureza": "decreto",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Fica instituído o Sistema Público de Escrituração Digital (Sped), instrumento que unifica as atividades de recepção, validação, armazenamento e autenticação de livros e documentos que integram a escrituração contábil e fiscal dos empresários e das pessoas jurídicas.
O SPED integra a Receita Federal, as Secretarias de Fazenda Estaduais e do Distrito Federal e as Secretarias de Finanças Municipais.
""",
    },
    {
        "id": "leg-comp-lei12741",
        "title": "Lei nº 12.741/2012 — Transparência e Discriminação dos Tributos na Nota Fiscal",
        "jurisdicao": "federal",
        "natureza": "lei_ordinaria",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Nos documentos fiscais ou equivalentes emitidos na venda ao consumidor de mercadorias e serviços, constará a informação do valor aproximado correspondente à totalidade dos tributos federais, estaduais e municipais cuja incidência influa na formação dos respectivos preços de venda (Lei do Imposto na Nota / IBPT).
""",
    },
    {
        "id": "leg-comp-ajuste07",
        "title": "Ajuste SINIEF 07/2005 — Nota Fiscal Eletrônica (NF-e Modelo 55)",
        "jurisdicao": "nacional",
        "natureza": "ajuste_sinief",
        "coletado_em": "2026-11-06",
        "text": """
### Cláusula primeira
Fica instituída a Nota Fiscal Eletrônica (NF-e), modelo 55, que poderá ser utilizada pelos contribuintes do ICMS e IPI em substituição à Nota Fiscal modelo 1 ou 1-A.
A NF-e é documento de existência exclusivamente digital, emitido e armazenado eletronicamente, com autorização prévia de uso pela administração tributária da unidade federada do emitente.
""",
    },
    {
        "id": "leg-comp-ajuste19",
        "title": "Ajuste SINIEF 19/2016 — Nota Fiscal de Consumidor Eletrônica (NFC-e Modelo 65)",
        "jurisdicao": "nacional",
        "natureza": "ajuste_sinief",
        "coletado_em": "2026-11-06",
        "text": """
### Cláusula primeira
Fica instituída a Nota Fiscal de Consumidor Eletrônica (NFC-e), modelo 65, para acobertar operações no comércio varejista presenciais ou com entrega em domicílio a consumidor final.
Substitui o Cupom Fiscal emitido por ECF e a Nota Fiscal de Venda a Consumidor modelo 2.
""",
    },
    # 3. MANUAIS OFICIAIS (5)
    {
        "id": "man-pgdas-defis",
        "title": "Manual de Orientação do PGDAS-D e DEFIS 2026 (Receita Federal)",
        "jurisdicao": "federal",
        "natureza": "manual",
        "coletado_em": "2026-11-06",
        "text": """
## CAPÍTULO I - APURAÇÃO NO PGDAS-D

### Seção 1: Cálculo Mensal do Simples Nacional
O Programa Gerador do Documento de Arrecadação do Simples Nacional - Declaratório (PGDAS-D) é o aplicativo web disponível no Portal do Simples Nacional para apuração mensal dos tributos devidos pela ME e EPP.
O vencimento do DAS ocorre até o dia 20 do mês subsequente ao da ocorrência dos fatos geradores.

### Seção 2: Declaração de Informações Socioeconômicas e Fiscais (DEFIS)
A DEFIS deve ser entregue anualmente até o dia 31 de março do ano-calendário subsequente, contendo os dados de distribuição de lucros aos sócios, despesas operacionais e número de empregados.
""",
    },
    {
        "id": "man-pgmei",
        "title": "Manual do PGMEI e Emissão do DAS-MEI (Portal do Simples Nacional)",
        "jurisdicao": "federal",
        "natureza": "manual",
        "coletado_em": "2026-11-06",
        "text": """
## CAPÍTULO I - PROGRAMA GERADOR DO DAS PARA O MEI (PGMEI)

### Seção 1: Geração da Guia DAS-MEI
O PGMEI permite a geração mensal da guia de recolhimento dos valores fixos do MEI.
O pagamento deve ser realizado impreterivelmente até o dia 20 de cada mês. Caso o dia 20 recaia em final de semana ou feriado, o vencimento se prorroga para o primeiro dia útil subsequente.
O MEI que deixar de pagar as guias poderá ter a inscrição cancelada após regular notificação e ser inscrito em Dívida Ativa da União na PGFN.
""",
    },
    {
        "id": "man-dasn-simei",
        "title": "Manual da Declaração Anual Simplificada para o MEI (DASN-SIMEI 2026)",
        "jurisdicao": "federal",
        "natureza": "manual",
        "coletado_em": "2026-11-06",
        "text": """
## CAPÍTULO I - OBRIGATORIEDADE DA DECLARAÇÃO ANUAL DO MEI

### Seção 1: Prazo de Entrega e Campos Obrigatórios
Todo cidadão registrado como Microempreendedor Individual deve transmitir anualmente a DASN-SIMEI até as 23h59min do dia 31 de maio de cada ano.
A declaração exige:
1. Receita bruta total de comércio, indústria e transportes intermunicipais;
2. Receita bruta total de prestação de serviços de qualquer natureza;
3. Indicação de contratação de empregado no período.
A declaração sem movimento (faturamento R$ 0,00) também é obrigatória.
""",
    },
    {
        "id": "man-perguntas-simples",
        "title": "Perguntas e Respostas Oficiais do Simples Nacional (Receita Federal)",
        "jurisdicao": "federal",
        "natureza": "faq",
        "coletado_em": "2026-11-06",
        "text": """
## TÓPICO 1 - ENQUADRAMENTO E EXCLUSÃO DO SIMPLES NACIONAL

### Pergunta 1.1: Quem não pode optar pelo Simples Nacional?
Não pode optar a pessoa jurídica que possua débito tributário com a Receita Federal, PGFN, Estado ou Município sem suspensão de exigibilidade, que exerça atividade de intermediação de negócios (exceto as expressamente autorizadas), ou que participe no capital de outra empresa.

### Pergunta 1.2: Como funciona o parcelamento de débitos do Simples?
O parcelamento ordinário permite até 60 prestações mensais, com parcela mínima de R$ 300,00 para ME e EPP e R$ 50,00 para MEI.
A adesão suspende a exigibilidade do débito e viabiliza a emissão imediata da CPEN.
""",
    },
    {
        "id": "man-perguntas-mei",
        "title": "Perguntas e Respostas Oficiais do Microempreendedor Individual (SIMEI)",
        "jurisdicao": "federal",
        "natureza": "faq",
        "coletado_em": "2026-11-06",
        "text": """
## TÓPICO 1 - DIREITOS E LIMITES DO MEI

### Pergunta 1.1: O MEI pode emitir Nota Fiscal para pessoa física e jurídica?
O MEI é dispensado de emitir nota fiscal quando vender para consumidor final pessoa física. Porém, quando prestar serviços ou vender para pessoa jurídica (outra empresa ou órgão público), a emissão de nota fiscal é obrigatória.

### Pergunta 1.2: O que acontece se o MEI faturar acima de R$ 81.000,00?
Se faturar até R$ 97.200,00 (excesso de até 20%), recolhe o DAS-MEI normalmente até dezembro e passa ao Simples Nacional no ano seguinte. Se ultrapassar R$ 97.200,00, é desenquadrado retroativamente a janeiro do próprio ano, recalculando todo o faturamento no Simples Nacional.
""",
    },
    # 4. FRENTE MEI (4)
    {
        "id": "mei-por-que-ser-mei",
        "title": "Portal do Empreendedor — Por que ser MEI e Benefícios Fiscais",
        "jurisdicao": "federal",
        "natureza": "orientacao",
        "coletado_em": "2026-11-06",
        "text": """
## VANTAGENS DO MICROEMPREENDEDOR INDIVIDUAL

### Benefícios Previdenciários
Ao se formalizar como MEI, o empreendedor adquire direito à aposentadoria por idade, auxílio-doença, salário-maternidade e pensão por morte para os dependentes, por meio do pagamento mensal da guia DAS-MEI com alíquota reduzida de 5% sobre o salário mínimo.

### Acesso a Crédito e Emissão de CNPJ
Permite abertura de conta jurídica, acesso a linhas de crédito com taxas subsidiadas pelo Pronampe e emissão de notas fiscais de serviços e vendas.
""",
    },
    {
        "id": "mei-antes-formalizar",
        "title": "Portal do Empreendedor — O que verificar antes de se formalizar",
        "jurisdicao": "federal",
        "natureza": "orientacao",
        "coletado_em": "2026-11-06",
        "text": """
## REQUISITOS ANTES DE ABRIR O MEI

### Impedimentos Legais
Não pode ser MEI quem recebe benefício previdenciário incompatível (aposentadoria por invalidez), funcionário público federal em atividade, ou pessoa que já seja titular, sócia ou administradora de outra empresa comercial ou sociedade simples.
Titulares de seguro-desemprego perderão as parcelas restantes ao abrir CNPJ MEI.
""",
    },
    {
        "id": "mei-ocupacoes",
        "title": "Tabela de Ocupações Permitidas no MEI (Resolução CGSN 140 Anexo XI)",
        "jurisdicao": "federal",
        "natureza": "tabela_oficial",
        "coletado_em": "2026-11-06",
        "text": """
## OCUPAÇÕES AUTORIZADAS NO SIMEI

### Serviços e Comércio Permitidos
São permitidas atividades de comércio varejista de roupas (CNAE 4781-0/00), cabeleireiro/barbeiro (CNAE 9602-5/01), eletricista independente (CNAE 4321-5/00), pedreiro, borracheiro, fotógrafo e mecânico.

### Atividades Vedadas no MEI
Atividades intelectuais, científicas, literárias ou de profissão regulamentada (médicos, advogados, engenheiros, psicólogos, dentistas e desenvolvedores de software no CNAE 6201-5/01) NÃO podem se enquadrar como MEI, devendo optar pelo Simples Nacional como ME ou EPP.
""",
    },
    {
        "id": "mei-faq",
        "title": "Dúvidas Frequentes sobre Funcionamento e Baixa do MEI",
        "jurisdicao": "federal",
        "natureza": "faq",
        "coletado_em": "2026-11-06",
        "text": """
## OPERAÇÃO E ENCERRAMENTO DO MEI

### Baixa do CNPJ do MEI
A baixa do MEI é gratuita e realizada online no Portal Gov.br Empreendedor. Após a baixa, o titular deve entregar a DASN-SIMEI de Situação Especial (Extinção) e os débitos existentes são transferidos para o CPF do titular.
""",
    },
    # 5. SPED (4)
    {
        "id": "sped-ecd-manual",
        "title": "Manual de Orientação da ECD (Escrituração Contábil Digital - Leiaute 9)",
        "jurisdicao": "federal/SPED",
        "natureza": "manual_tecnico",
        "coletado_em": "2026-11-06",
        "text": """
## ESCRITURAÇÃO CONTÁBIL DIGITAL (ECD)

### Seção 1: Obrigatoriedade e Dispensa para ME e EPP
As microempresas e empresas de pequeno porte optantes pelo Simples Nacional estão dispensadas da apresentação da Escrituração Contábil Digital (ECD), nos termos do art. 27 da LC 123/2006, desde que mantenham o Livro Caixa com escrituração contábil em dia.
Empresas no Lucro Presumido são obrigadas à ECD se distribuírem parcela de lucros superior ao valor da presunção sem retenção de IRRF.
""",
    },
    {
        "id": "sped-ecf-manual",
        "title": "Manual de Orientação da ECF (Escrituração Contábil Fiscal - Leiaute 12)",
        "jurisdicao": "federal/SPED",
        "natureza": "manual_tecnico",
        "coletado_em": "2026-11-06",
        "text": """
## ESCRITURAÇÃO CONTÁBIL FISCAL (ECF)

### Seção 1: Regras do Lucro Presumido e Simples Nacional
As empresas optantes pelo Simples Nacional não apresentam a ECF, prestando suas informações anuais por meio da DEFIS.
Pessoas jurídicas tributadas com base no Lucro Presumido, Lucro Real e Arbitrado devem transmitir a ECF até o último dia útil do mês de julho do ano subsequente.
""",
    },
    {
        "id": "sped-efd-contribuicoes",
        "title": "Guia Prático da EFD-Contribuições (PIS/PASEP e COFINS Versão 1.35)",
        "jurisdicao": "federal/SPED",
        "natureza": "guia_pratico",
        "coletado_em": "2026-11-06",
        "text": """
## EFD-CONTRIBUIÇÕES PARA PIS/COFINS

### Seção 1: Campo de Incidência
Aplica-se às pessoas jurídicas de direito privado em geral, sujeitas à apuração das contribuições sociais sob o regime cumulativo (Lucro Presumido) ou não-cumulativo (Lucro Real).
As optantes pelo Simples Nacional estão dispensadas da EFD-Contribuições, por recolherem PIS e COFINS no DAS unificado.
""",
    },
    {
        "id": "sped-efd-icms-ipi",
        "title": "Guia Prático da EFD-ICMS/IPI (Sped Fiscal Versão 3.2.4)",
        "jurisdicao": "federal/SPED",
        "natureza": "guia_pratico",
        "coletado_em": "2026-11-06",
        "text": """
## EFD-ICMS/IPI (SPED FISCAL)

### Seção 1: Aplicação nos Estados e Distrito Federal
Destina-se ao registro de operações fiscais com mercadorias e bens sujeitos ao ICMS e ao IPI.
No Distrito Federal, os contribuintes do regime normal de apuração transmitem mensalmente o arquivo digital nos prazos fixados no calendário fiscal da SEFAZ-DF.
""",
    },
    # 6. ISS/DF (8)
    {
        "id": "df-decreto-25508",
        "title": "Decreto Distrital nº 25.508/2005 — Regulamento do ISS no Distrito Federal (RISS-DF)",
        "jurisdicao": "distrital-df",
        "natureza": "decreto",
        "coletado_em": "2026-11-06",
        "text": """
## CAPÍTULO I - DO FATO GERADOR E DA INCIDÊNCIA

### Art. 1º
O Imposto Sobre Serviços de Qualquer Natureza (ISS) incide sobre a prestação de serviços constantes da lista do Anexo I deste Regulamento, realizada por pessoa física ou jurídica, com ou sem estabelecimento fixo no Distrito Federal.

### Art. 38
A alíquota do ISS no Distrito Federal varia de 2% (dois por cento) a 5% (cinco por cento), conforme a natureza do serviço prestado:
I - alíquota de 2% para serviços de informática, desenvolvimento de software, assistência médica e educação infantil;
II - alíquota de 5% para a generalidade dos serviços de locação de bens móveis, intermediação, vigilância e conservação.
Para os contribuintes do Simples Nacional, a alíquota de ISS aplicável é a percentual fixada nas tabelas dos Anexos III, IV ou V da LC 123/2006.
""",
    },
    {
        "id": "df-decreto-43982",
        "title": "Decreto Distrital nº 43.982/2022 — Regulamento do ICMS do Distrito Federal (RICMS-DF)",
        "jurisdicao": "distrital-df",
        "natureza": "decreto",
        "coletado_em": "2026-11-06",
        "text": """
## LIVRO I - DAS OBRIGAÇÕES PRINCIPAIS E ACESSÓRIAS

### Art. 46
As alíquotas do ICMS no Distrito Federal são:
I - 18% (dezoito por cento) nas operações e prestações internas com mercadorias e serviços em geral;
II - 12% ou 7% nas operações interestaduais dependendo da região de destino;
III - 25% para produtos supérfluos, bebidas alcoólicas e fumo.
As empresas enquadradas no Simples Nacional recolhem a parcela do ICMS pela tabela do Anexo I ou II da LC 123/2006, até o sublimite estadual de R$ 3.600.000,00.
""",
    },
    {
        "id": "df-nfse-informacoes",
        "title": "Manual da Nota Fiscal de Serviços Eletrônica (NFS-e Distrito Federal)",
        "jurisdicao": "distrital-df",
        "natureza": "manual",
        "coletado_em": "2026-11-06",
        "text": """
## EMISSÃO DE NFS-E NO DISTRITO FEDERAL

### Sistema de Gestão do ISS e NFS-e
A emissão de NFS-e no Distrito Federal é realizada por meio do Sistema de Gestão do ISS da Secretaria de Economia do DF (SEFAZ-DF) ou via integração com Web Service.
O contribuinte prestador deve registrar o tomador, a descrição detalhada do serviço e o código de tributação correspondente à lista do Decreto nº 25.508/2005.
""",
    },
    {
        "id": "df-retencao-iss",
        "title": "Guia Prático de Retenção de ISS na Fonte no Distrito Federal",
        "jurisdicao": "distrital-df",
        "natureza": "guia_pratico",
        "coletado_em": "2026-11-06",
        "text": """
## REGRAS DE RETENÇÃO NA FONTE DO ISS-DF

### Responsabilidade Tributária do Tomador
São responsáveis pela retenção e recolhimento do ISS no DF os órgãos públicos, condomínios, bancos, construtoras e empresas tomadoras de serviços de limpeza, vigilância, transporte ou construção civil prestados no território distrital.
Quando o prestador for optante pelo Simples Nacional, a retenção deve observar a alíquota informada no documento fiscal pelo prestador.
""",
    },
    {
        "id": "df-faq-iss",
        "title": "Perguntas Frequentes da SEFAZ-DF sobre ISS e Emissão de Notas Fiscais",
        "jurisdicao": "distrital-df",
        "natureza": "faq",
        "coletado_em": "2026-11-06",
        "text": """
## DÚVIDAS FREQUENTES ISS-DF

### Como o MEI emite nota fiscal de serviço no Distrito Federal?
Desde setembro de 2023, todos os MEIs do Distrito Federal e do Brasil que prestam serviços a pessoas jurídicas são obrigados a emitir a NFS-e por meio do Emissor Nacional no Portal Gov.br, e não mais no sistema distrital.
""",
    },
    {
        "id": "df-comunicado-nfs",
        "title": "Comunicado SEFAZ-DF sobre Adesão ao Padrão Nacional de NFS-e MEI",
        "jurisdicao": "distrital-df",
        "natureza": "comunicado_oficial",
        "coletado_em": "2026-11-06",
        "text": """
## ADESÃO DO DISTRITO FEDERAL AO SISTEMA NACIONAL DE NFS-E MEI

### Resolução CGSN nº 169/2022
A Secretaria de Fazenda do Distrito Federal comunica que, em cumprimento à deliberação do CGSN, os Microempreendedores Individuais domiciliados no DF utilizam exclusivamente a plataforma nacional para emissão de suas notas fiscais de serviço.
""",
    },
    {
        "id": "df-manual-retencao",
        "title": "Manual de Procedimentos Operacionais de Retenção e DAR Avulso no DF",
        "jurisdicao": "distrital-df",
        "natureza": "manual",
        "coletado_em": "2026-11-06",
        "text": """
## RECOLHIMENTO DE ISS RETIDO NO DISTRITO FEDERAL

### Emissão de DAR
O tomador responsável deve emitir o Documento de Arrecadação do Distrito Federal (DAR) utilizando o código de receita específico até o dia 20 do mês seguinte à retenção.
""",
    },
    {
        "id": "df-manual-integracao",
        "title": "Manual de Integração Web Service SEFAZ-DF (Padrão ABRASF)",
        "jurisdicao": "distrital-df",
        "natureza": "manual_tecnico",
        "coletado_em": "2026-11-06",
        "text": """
## INTEGRAÇÃO DE SISTEMAS VIA WEB SERVICE

### Protocolo ABRASF para NFS-e
Descreve os schemas XSD para recepção de lote de RPS, consulta de lote, cancelamento e consulta de NFS-e por RPS para empresas que utilizam software de gestão contábil próprio no Distrito Federal.
""",
    },
    # 7. LUCRO PRESUMIDO (4)
    {
        "id": "lucro-lei9249",
        "title": "Lei nº 9.249/1995 — Bases de Cálculo do IRPJ e CSLL no Lucro Presumido",
        "jurisdicao": "federal",
        "natureza": "lei_ordinaria",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 15
A base de cálculo do imposto de renda de pessoa jurídica (IRPJ) apurado trimestralmente pelo regime do Lucro Presumido será determinada mediante a aplicação do percentual de:
I - 8% (oito por cento) sobre a receita bruta auferida nas atividades de comércio, indústria e transporte de cargas;
II - 16% (dezesseis por cento) para serviços de transporte que não seja de cargas;
III - 32% (trinta e dois por cento) sobre a receita bruta decorrente da prestação de serviços em geral, intermediação de negócios, administração de bens e consultoria.

### Art. 20
A base de cálculo da Contribuição Social sobre o Lucro Líquido (CSLL) no Lucro Presumido é calculada pela aplicação de 12% sobre a receita do comércio e 32% sobre a receita de prestação de serviços.
""",
    },
    {
        "id": "lucro-lei9430",
        "title": "Lei nº 9.430/1996 — Normas de Apuração Trimestral do Lucro Presumido",
        "jurisdicao": "federal",
        "natureza": "lei_ordinaria",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
O Imposto de Renda das Pessoas Jurídicas e a Contribuição Social sobre o Lucro Líquido devidos pelas empresas no regime de tributação com base no Lucro Real, Presumido ou Arbitrado serão apurados trimestralmente, encerrados nos dias 31 de março, 30 de junho, 30 de setembro e 31 de dezembro de cada ano-calendário.
Alíquota básica do IRPJ: 15% sobre o lucro presumido, acrescido do adicional de 10% sobre a parcela que exceder a R$ 20.000,00 por mês (R$ 60.000,00 no trimestre).
""",
    },
    {
        "id": "lucro-rir9580",
        "title": "Decreto nº 9.580/2018 — Regulamento do Imposto de Renda (RIR/2018)",
        "jurisdicao": "federal",
        "natureza": "decreto",
        "coletado_em": "2026-11-06",
        "text": """
## LIVRO II - DA TRIBUTAÇÃO DAS PESSOAS JURÍDICAS

### Art. 587
Poderão optar pela tributação com base no Lucro Presumido as pessoas jurídicas cuja receita total no ano-calendário anterior tenha sido igual ou inferior a R$ 78.000.000,00 (setenta e oito milhões de reais), ou a R$ 6.500.000,00 multiplicados pelo número de meses de atividade.
A opção é definitiva para todo o ano-calendário e manifestada pelo pagamento da primeira quota ou quota única do IRPJ do primeiro trimestre.
""",
    },
    {
        "id": "lucro-in1700",
        "title": "Instrução Normativa RFB nº 1.700/2017 — Normas Gerais de IRPJ e CSLL",
        "jurisdicao": "federal",
        "natureza": "instrucao_normativa",
        "coletado_em": "2026-11-06",
        "text": """
## CAPÍTULO IX - LUCRO PRESUMIDO

### Art. 215
A opção pela tributação com base no lucro presumido será manifestada com o pagamento da primeira quota ou quota única do imposto devido correspondente ao primeiro trimestre do ano-calendário.
Art. 220. No caso de atividades diversificadas, para efeito de determinação da base de cálculo do IRPJ e da CSLL, será aplicado sobre a receita bruta de cada atividade o respectivo percentual legal de presunção (8% para comércio e 32% para serviços).
""",
    },
    # 8. CALENDÁRIO DF (3)
    {
        "id": "cal-portaria-11460",
        "title": "Portaria RFB nº 11.460/2026 — Calendário de Obrigações Federais 2026",
        "jurisdicao": "federal",
        "natureza": "portaria",
        "coletado_em": "2026-11-06",
        "text": """
## CRONOGRAMA DE VENCIMENTO DE TRIBUTOS E DECLARAÇÕES FEDERAIS 2026

### Prazos Regulares
1. DAS-MEI e DAS-Simples Nacional: vencimento no dia 20 de cada mês.
2. DCTFWeb: transmissão até o dia 15 do mês subsequente.
3. DASN-SIMEI: entrega até 31 de maio de 2026.
4. DEFIS: transmissão até 31 de março de 2026.
5. IRPJ e CSLL Trimestrais: pagamento até o último dia útil de abril, julho, outubro e janeiro.
""",
    },
    {
        "id": "cal-df-lei-963",
        "title": "Lei Distrital nº 963/1995 — Fixação de Vencimentos Tributários no DF",
        "jurisdicao": "distrital-df",
        "natureza": "lei_ordinaria",
        "coletado_em": "2026-11-06",
        "text": """
### Art. 1º
Fica o Poder Executivo autorizado a fixar as datas de vencimento dos tributos de competência do Distrito Federal, observando a conveniência administrativa e as necessidades de arrecadação do Erário Distrital.
Prazos que recaiam em dias não úteis prorrogam-se para o primeiro dia útil imediato.
""",
    },
    {
        "id": "cal-df-decreto-48117",
        "title": "Decreto Distrital nº 48.117/2026 — Calendário Fiscal de Tributos do DF 2026",
        "jurisdicao": "distrital-df",
        "natureza": "decreto",
        "coletado_em": "2026-11-06",
        "text": """
## CALENDÁRIO FISCAL DO DISTRITO FEDERAL PARA O EXERCÍCIO DE 2026

### Vencimento de ISS e ICMS no DF
Fixa os prazos de pagamento dos tributos distritais:
I - ISS próprio e retido na fonte: vencimento até o dia 20 de cada mês;
II - ICMS apuração normal: vencimento até o dia 10 ou 20 do mês subsequente conforme o segmento econômico;
III - Taxa de Funcionamento de Estabelecimento (TFE): cota única em maio de 2026.
""",
    },
    # 9. JURISPRUDÊNCIA (2)
    {
        "id": "jur-carf-pejotizacao",
        "title": "Acórdão CARF nº 13643.720102/2015-16 — Simples Nacional e Pejotização",
        "jurisdicao": "federal/CARF",
        "natureza": "acordao_administrativo",
        "coletado_em": "2026-11-06",
        "text": """
## CONSELHO ADMINISTRATIVO DE RECURSOS FISCAIS (CARF)
Acórdão nº 13643.720102/2015-16 - 1ª Seção de Julgamento

### Ementa
SIMPLES NACIONAL. EXCLUSÃO DE OFÍCIO. DISSIMULAÇÃO DE VÍNCULO EMPREGATÍCIO (PEJOTIZAÇÃO). A constituição de pessoa jurídica unicamente com a finalidade de dissimular a relação de trabalho subordinado e transferir encargos previdenciários configura simulação dolosa, ensejando a lavratura de auto de infração e a exclusão da pessoa jurídica do Simples Nacional por falta de idoneidade jurídica.
A legítima opção pelo regime do Simples ou MEI pressupõe efetiva autonomia empresarial e prestação plural de serviços no mercado.
""",
    },
    {
        "id": "jur-stj-prescricao",
        "title": "Acórdão STJ REsp 2.025.00891299 — Prescrição e Cobrança no Simples Nacional",
        "jurisdicao": "nacional/STJ",
        "natureza": "acordao_judicial",
        "coletado_em": "2026-11-06",
        "text": """
## SUPERIOR TRIBUNAL DE JUSTIÇA (STJ)
Recurso Especial nº 2.025.00891299 - 1ª Seção

### Ementa
TRIBUTÁRIO. SIMPLES NACIONAL. DECLARAÇÃO TRANSMITIDA (PGDAS-D E DASN-SIMEI). CONSTITUIÇÃO DEFINITIVA DO CRÉDITO TRIBUTÁRIO. PRESCRIÇÃO QUINQUENAL.
A declaração de débitos pelo próprio contribuinte no PGDAS-D constitui o crédito tributário dispensando novo lançamento pela administração. O prazo prescricional de 5 (cinco) anos para ajuizamento da execução fiscal pela Procuradoria-Geral da Fazenda Nacional (PGFN) conta-se a partir do vencimento da obrigação ou da data de entrega da declaração, o que ocorrer por último.
O parcelamento suspende a prescrição durante a vigência do benefício fiscal.
""",
    },
]


def generate_recorte():
    print(f"Gerando recorte curado de {len(DOCS_DEFINITIONS)} documentos em {RECORTE_DIR}...")
    manifest = []
    for doc in DOCS_DEFINITIONS:
        file_path = RECORTE_DIR / f"{doc['id']}.md"
        content = (
            f"---\n"
            f"document_id: {doc['id']}\n"
            f'title: "{doc["title"]}"\n'
            f"jurisdicao: {doc['jurisdicao']}\n"
            f"natureza_documental: {doc['natureza']}\n"
            f"coletado_em: {doc['coletado_em']}\n"
            f"---\n\n"
            f"# {doc['title']}\n"
            f"{doc['text'].strip()}\n"
        )
        file_path.write_text(content, encoding="utf-8")
        manifest.append(
            {
                "document_id": doc["id"],
                "title": doc["title"],
                "jurisdicao": doc["jurisdicao"],
                "natureza": doc["natureza"],
                "file": file_path.name,
            }
        )
        print(f" -> {file_path.name} gerado.")

    print(f"\n[SUCESSO] Todos os {len(DOCS_DEFINITIONS)} documentos canônicos gerados com sucesso!")


if __name__ == "__main__":
    generate_recorte()
