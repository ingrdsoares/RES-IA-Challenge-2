# Plano de refino inicial

- [x] Diagnosticar equivalências reais e riscos de perda de versões.
- [x] Definir modelo, política e arquitetura preservando os originais.
- [x] Implementar backend/refino com identidade, normalização, classificação e registro de datasets.
- [x] Adicionar contrato PostgreSQL e documentação de uso, sem executar migração sem ambiente existente.
- [x] Testar casos de versões/rasuras/valores, identidade, proveniência, datasets e retomada.
- [x] Executar no catálogo inteiro e verificar todas as ocorrências e hashes da saída.
- [x] Revisar a arquitetura/implementação e registrar resultados e limites.

## Resultado da primeira etapa

Perfil confirmado: todos os regimes tributários, foco DF. Entrada preservada: 7.213 ocorrências. Resultado: 6.291 documentos lógicos, 7.040 versões, 6.877 conteúdos únicos, 225 repetições textuais evitadas e 922 ocorrências agrupadas por identidade. Núcleo candidato: 5.024 documentos; 37 datasets registrados. Todas as ocorrências e fontes permaneceram rastreáveis. Executada e validada a retomada com cache; catálogo e código participam da chave da execução.

Execução autoritativa: 42519bf3b85704f26362ac4da9011c963a880a89400be8298432d8adb895d3f6. Conferidos 6.889 artefatos, zero erros. Testes: 344 coletores/refino e um API. O contrato PostgreSQL foi documentado, não aplicado ao servidor. Relevância é candidata; permanecem revisão semântica, fragmentação e integração PostgreSQL.

Continuidade independente de modelo: handoff/refino/CONTINUAR.md e estado.json; exportador backend/refino/exportar.py. ZIP contém código, contexto, índices, referências e snapshot textual refinado; originais brutos ficam externos. Registra também a instrução de parar ao atingir o limite da sessão.
