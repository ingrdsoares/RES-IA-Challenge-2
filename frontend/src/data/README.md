# Localidades

Lista incorporada ao frontend a partir da API de Localidades do IBGE em 17/11/2026.
Contém as 27 UFs e os 5.571 nomes retornados pelo catálogo, agrupados pela UF da região imediata.

Fontes:
- https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome
- https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome

O cadastro usa a cópia local para evitar dependência da API externa durante o preenchimento.
A seleção é declarada pelo usuário e não representa consulta cadastral de CNPJ.
Ao atualizar a lista, preserve nomes com acentos e verifique que todos os registros retornados pertencem a uma das 27 UFs.
