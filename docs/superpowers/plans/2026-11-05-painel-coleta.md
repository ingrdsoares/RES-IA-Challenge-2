# Painel de coleta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um comando único (`python -m backend.crawler.painel`) que executa as frentes de coleta em sequência e mostra o processo em uma página local.

**Architecture:** Cada módulo roda no próprio processo, por meio de uma sonda que envolve `httpx.Client.send` e grava eventos em JSONL. Um executor em thread consome esses eventos e mantém um estado em memória, que o servidor local entrega por Server-Sent Events a uma página HTML única. Regras de pular, classificar, barra e tempo ficam em funções puras.

**Tech Stack:** Python 3.11, biblioteca padrão (`http.server`, `subprocess`, `runpy`, `threading`), `httpx` já instalado, HTML/CSS/JS sem build, `unittest` executado com `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-05-painel-coleta-design.md`

## Global Constraints

- Nenhum módulo existente é alterado. `python -m backend.crawler.<modulo>` continua igual.
- Sem dependência nova em `backend/crawler/requirements.txt`.
- Servidor escuta apenas em `127.0.0.1`.
- Frentes rodam uma por vez, com argumentos vazios.
- Dados do painel em `backend/crawler/.painel/`, adicionado a `backend/crawler/.gitignore`.
- Tempo limite da parada suave: 60 s, constante no código.
- Sem base para total ou estimativa, a tela diz "total desconhecido" ou "sem estimativa". Nunca inventa número.
- Toda a interface em português. A página funciona por teclado e tem bom contraste.
- Testes não acessam a rede e não leem `backend/crawler/data/`.
- Comandos partem da raiz do repositório. `git add` usa só os caminhos da tarefa, porque há trabalho alheio não commitado na árvore (`normas_id.py`, `citacoes.py`, `docs/`).

## Review Focus

1. `catalogo.json` ausente ou corrompido: a página abre, frentes aparecem como "sem dados" e a coleta pode rodar. Teste na Task 1.
2. Atualização do catálogo falha no fim da rodada: frentes são classificadas só pelo processo e a página mostra aviso. Teste na Task 4.
3. `historico.jsonl` com última linha cortada por queda da máquina: a linha é ignorada e a frente conta como interrompida. Teste na Task 4.
4. Script que imprime acentos com saída redirecionada no Windows (cp1252 derruba `print`): filho roda em UTF-8 e termina normalmente. Teste na Task 4.
5. Segundo painel, ou coleta em terminal, com outra rodada em andamento: recusa com mensagem clara, sem coleta paralela. Testes nas Tasks 4 e 5.

---

## Estrutura de arquivos

```text
backend/crawler/painel/
├── __init__.py      docstring curta
├── __main__.py      linha de comando (Task 5)
├── frentes.py       lista fixa e leitura do catálogo (Task 1)
├── regras.py        funções puras (Task 2)
├── sonda.py         instrumentação do processo filho (Task 3)
├── executor.py      rodada, processos, histórico (Task 4)
├── servidor.py      HTTP e SSE (Task 5)
└── pagina.html      interface (Task 6)
backend/crawler/tests/test_painel_{frentes,regras,sonda,executor,servidor}.py
```

### Task 1: Lista de frentes e leitura do catálogo

**Files:**
- Create: `backend/crawler/painel/__init__.py`, `backend/crawler/painel/frentes.py`
- Modify: `backend/crawler/.gitignore` (acrescentar `.painel/`)
- Test: `backend/crawler/tests/test_painel_frentes.py`

**Interfaces:**
- Produces:
  - `Frente` (dataclass congelada): `modulo: str`, `pasta: str`, `depende: tuple[str, ...] = ()`, `pesada: str | None = None`, `marcas: tuple[str, ...] = ()`; propriedade `nome: str` (nome legível em `FRONTES`).
  - `FRENTES: tuple[Frente, ...]` na ordem de execução; `POR_MODULO: dict[str, Frente]`; `ETAPAS_FINAIS = ('estatisticas', 'sumarizacao')`; `MODULO_CATALOGO = 'catalogo'`.
  - `carregar_catalogo(data: Path) -> dict | None`: `None` se o arquivo faltar ou o JSON for inválido.
  - `resumir_catalogo(catalogo: dict | None) -> dict[str, dict]`, por pasta: `itens: int`, `ultima_coleta: str | None`, `origens: set[str]`, `fonte: str | None` (domínio predominante), `situacao: str | None`, `pendencias: int` (`erros_manifesto_mais_recente + pendencias_extracao`).

- [ ] **Step 1: Write the failing tests**

```python
class FrentesTests(unittest.TestCase):
    def test_cobre_ferramentas_e_frontes(self):
        declarados = {t['modulo'] for t in json.loads(FERRAMENTAS.read_text('utf8'))['ferramentas']
                      if t['tipo'] != 'biblioteca' and t['modulo'] != 'painel'}
        self.assertEqual(declarados, {f.modulo for f in FRENTES} | set(ETAPAS_FINAIS) | {MODULO_CATALOGO})
        self.assertEqual(set(FRONTES.values()), {f.pasta for f in FRENTES} | {'catalogo'})
    def test_dependencia_vem_antes(self):
        ordem = [f.modulo for f in FRENTES]
        for f in FRENTES:
            for d in f.depende:
                self.assertLess(ordem.index(d), ordem.index(f.modulo))
    def test_catalogo_ausente_ou_corrompido(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            self.assertIsNone(carregar_catalogo(data))
            (data / 'catalogo').mkdir()
            (data / 'catalogo' / 'catalogo.json').write_text('{quebrado')
            self.assertIsNone(carregar_catalogo(data))
        self.assertEqual(resumir_catalogo(None), {})
    def test_resumo_por_pasta(self):
        catalogo = {'snapshots': [
            {'diretorio': 'cnae/a', 'origem': 'https://x.gov.br/1', 'coletado_em': '2026-11-01T00:00:00+00:00'},
            {'diretorio': 'cnae/b', 'origem': 'https://x.gov.br/2', 'coletado_em': '2026-11-03T00:00:00+00:00'},
            {'diretorio': 'cnae/c', 'origem': 'https://y.gov.br/3', 'coletado_em': None}],
            'cobertura_frentes': [{'pasta': 'cnae', 'snapshots': 3, 'situacao': 'coletada_com_pendencias',
                                   'erros_manifesto_mais_recente': 2, 'pendencias_extracao': 1}]}
        r = resumir_catalogo(catalogo)['cnae']
        self.assertEqual((r['itens'], r['fonte'], r['pendencias']), (3, 'x.gov.br', 3))
        self.assertEqual(r['ultima_coleta'], '2026-11-03T00:00:00+00:00')
        self.assertEqual(len(r['origens']), 3)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest backend/crawler/tests/test_painel_frentes.py -q`
Expected: FAIL com `ModuleNotFoundError: backend.crawler.painel`

- [ ] **Step 3: Implement `frentes.py`**

Reusar `FRONTES` de `..catalogo`. O nome vem do inverso (pasta → nome). `itens` usa `snapshots` de `cobertura_frentes`; ausente, conta snapshots da pasta. A pasta do snapshot é o primeiro segmento de `diretorio`.

Ordem de `FRENTES`, com a pasta de cada módulo sendo o nome com `-`, salvo `anexos` → `anexos-cgsn140` e `recuperar_anexos` → `anexos-recuperados`:

`cnae, notas_cnae, legislacao, legislacao_complementar, anexos, manuais, mei, complemento_contabil, contabilidade, obrigacoes, obrigacoes_avancadas, calendario_df, documentos_fiscais, notas_tecnicas_fiscais, xmls_exemplo, tabelas_fiscais, sped_complementar, tributacao_lucro, regularizacao_fiscal, distrital_df, icms_consultas_df, consultas_df_amplas, consultas_rfb, sumulas_classificacao, documentos_jurisprudencia, fontes_recuperadas, reforma, reforma_historico, retencoes_defesa_setores, recuperar_anexos, historico_competencias, economia, ibge_indicadores, sebrae, indicadores_empresariais, cnpj, cnpj_ampliado, cnpj_df, cnpj_df_censo, casos_oficiais`

Dependências:
- `anexos` → `legislacao`
- `calendario_df` → `obrigacoes`
- `fontes_recuperadas` → `documentos_jurisprudencia`
- `recuperar_anexos` → `reforma_historico`, `retencoes_defesa_setores`
- `cnpj_df`, `cnpj_df_censo` → `cnpj_ampliado`
- `casos_oficiais` → `complemento_contabil`, `distrital_df`, `manuais`, `mei`, `notas_tecnicas_fiscais`, `obrigacoes_avancadas`

Essas dependências vieram de busca por texto. Confirme lendo cada módulo: nome citado sem leitura de `data/` não é dependência. Se `cnpj_ampliado` lê dados de `cnpj`, inclua.

Marcas (confirme lendo cada módulo):
- `usa cópia local`: `consultas_rfb`, `reforma_historico`, `retencoes_defesa_setores`, `historico_competencias`, `sumulas_classificacao`, `sped_complementar`, `xmls_exemplo`.
- `período fixo: 2026-10`: `cnpj_ampliado`, `cnpj_df`, `cnpj_df_censo`. `período fixo: 2026-11`: `obrigacoes`. `período fixo: até 2026-11-03`: `economia`.
- `reescreve metadados da coleta existente`: `cnpj_ampliado`.

Aviso `pesada`, com texto fiel ao que o módulo faz:
- `cnpj_ampliado`, `cnpj_df`, `cnpj_df_censo`, `historico_competencias`, `consultas_df_amplas`: descrever o volume real.
- `retencoes_defesa_setores`, `consultas_rfb`: avisar sobre tempo de leitura da cópia local, não sobre download.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest backend/crawler/tests/test_painel_frentes.py -q`
Expected: 4 passed. `test_cobre_ferramentas_e_frontes` lê o `ferramentas.json` real.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/painel backend/crawler/tests/test_painel_frentes.py backend/crawler/.gitignore
git commit -m "feat(painel): lista fixa de frentes e leitura do catalogo"
```

### Task 2: Regras de pular, classificar, barra e tempo

**Files:**
- Create: `backend/crawler/painel/regras.py`
- Test: `backend/crawler/tests/test_painel_regras.py`

**Interfaces:**
- Consumes: `Frente`, `FRENTES`, resumo da Task 1.
- Produces (todas puras):
  - `deve_pular(resumo: dict | None, ultima: dict | None, refazer: bool) -> bool`. `ultima` é o registro do histórico, com `resultado`.
  - `planejar(selecionadas: set[str], refazer: set[str], resumos: dict, ultimas: dict) -> list[dict]`: na ordem de `FRENTES`, itens `{'modulo', 'acao': 'rodar'|'pular', 'motivo': str}`. Dependência sem dados entra como `rodar`, com motivo `necessária para <modulo>`.
  - `classificar(saida: int | None, excecao: bool, interrompida: bool, situacao: str | None) -> str`: `'concluida' | 'parcial' | 'erro' | 'interrompida'`.
  - `barra(requisicoes: int, urls_casadas: int, ultimas_requisicoes: int | None, origens: int) -> tuple[float | None, int | None]`: fração e base.
  - `estimar(duracao_anterior: float | None, decorrido: float | None, fracao: float | None, s_por_item: float | None, itens: int) -> float | None`.

- [ ] **Step 1: Write the failing tests**

```python
class RegrasTests(unittest.TestCase):
    def test_pular(self):
        com = {'itens': 3}
        self.assertTrue(deve_pular(com, None, False))
        self.assertTrue(deve_pular(com, {'resultado': 'parcial'}, False))
        self.assertTrue(deve_pular(com, {'resultado': 'concluida'}, False))
        self.assertFalse(deve_pular(com, {'resultado': 'erro'}, False))
        self.assertFalse(deve_pular(com, {'resultado': 'interrompida'}, False))
        self.assertFalse(deve_pular(com, None, True))
        self.assertFalse(deve_pular({'itens': 0}, None, False))
        self.assertFalse(deve_pular(None, None, False))
    def test_classificar(self):
        p = 'coletada_com_pendencias'
        self.assertEqual(classificar(0, False, False, None), 'concluida')
        self.assertEqual(classificar(0, False, False, p), 'parcial')
        self.assertEqual(classificar(1, False, False, p), 'parcial')
        self.assertEqual(classificar(1, False, False, None), 'erro')
        self.assertEqual(classificar(70, True, False, p), 'erro')
        self.assertEqual(classificar(None, False, True, p), 'interrompida')
    def test_barra_bases(self):
        self.assertEqual(barra(5, 1, 10, 100), (0.5, 1))
        self.assertEqual(barra(50, 1, 10, 100), (0.99, 1))
        self.assertEqual(barra(5, 25, 0, 100), (0.25, 2))
        self.assertEqual(barra(5, 25, None, 100), (0.25, 2))
        self.assertEqual(barra(5, 0, None, 0), (None, None))
    def test_estimar(self):
        self.assertEqual(estimar(100, 30, 0.5, None, 0), 30)
        self.assertEqual(estimar(100, None, None, 2, 10), 100)
        self.assertEqual(estimar(None, None, None, 2, 10), 20)
        self.assertEqual(estimar(100, 5, 0, None, 0), 95)
        self.assertEqual(estimar(100, 500, None, None, 0), 0)
        self.assertIsNone(estimar(None, None, None, None, 10))
    def test_planejar_inclui_dependencia_sem_dados(self):
        plano = {p['modulo']: p for p in planejar({'cnpj_df'}, {'cnpj_df'}, {'cnpj-df': {'itens': 1}}, {})}
        self.assertEqual(plano['cnpj_ampliado']['acao'], 'rodar')
        self.assertIn('cnpj_df', plano['cnpj_ampliado']['motivo'])
        self.assertEqual(plano['cnpj_df']['acao'], 'rodar')
    def test_planejar_pula_com_dados(self):
        plano = planejar({'cnae'}, set(), {'cnae': {'itens': 1}}, {})
        self.assertEqual([(p['modulo'], p['acao']) for p in plano], [('cnae', 'pular')])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest backend/crawler/tests/test_painel_regras.py -q`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implement `regras.py`**

Regras de `estimar`, nesta ordem:
1. `decorrido` e `fracao > 0`: `decorrido * (1 - fracao) / fracao`.
2. `duracao_anterior`: `max(duracao_anterior - (decorrido or 0), 0)`.
3. `s_por_item` e `itens`: `s_por_item * itens`.
4. Senão, `None`.

Em `barra`, a base 1 exige `ultimas_requisicoes > 0`. As frações são limitadas a 0,99, porque a linha só chega a 100% ao terminar. Resolva dependências de forma transitiva em `planejar`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest backend/crawler/tests/test_painel_regras.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/painel/regras.py backend/crawler/tests/test_painel_regras.py
git commit -m "feat(painel): regras de pular, classificar, barra e estimativa"
```

### Task 3: Sonda

**Files:**
- Create: `backend/crawler/painel/sonda.py`
- Test: `backend/crawler/tests/test_painel_sonda.py`

**Interfaces:**
- Produces:
  - `python -m backend.crawler.painel.sonda <modulo>`, com variáveis `PAINEL_EVENTOS` (arquivo JSONL) e `PAINEL_PARAR` (arquivo sinal).
  - `SAIDA_EXCECAO = 70`.
  - `ParadaSolicitada(httpx.TransportError)`.
  - `instalar(eventos: Path, parar: Path, modulo: str) -> None`: envolve `httpx.Client.send`.
  - Eventos, um JSON por linha, todos com `t` (ISO UTC) e `modulo`:
    - `{'tipo': 'pedido', 'url'}`
    - `{'tipo': 'resposta', 'url', 'url_final', 'status', 'bytes', 'ms'}`
    - `{'tipo': 'falha', 'url', 'erro'}`

- [ ] **Step 1: Write the failing tests**

Usar `httpx.Client(transport=httpx.MockTransport(...))`. Em `tearDown`, restaurar `httpx.Client.send` original.

```python
def test_registra_pedido_e_resposta_com_redirecionamento(self):
    instalar(self.eventos, self.parar, 'cnae')
    with httpx.Client(transport=self.mock, follow_redirects=True) as c:
        c.get('https://x.gov.br/a')   # mock redireciona para /b e responde 3 bytes
    ev = self.ler()
    self.assertEqual(ev[0]['tipo'], 'pedido')
    self.assertEqual(ev[-1]['url_final'], 'https://x.gov.br/b')
    self.assertEqual((ev[-1]['status'], ev[-1]['bytes'], ev[-1]['modulo']), (200, 3, 'cnae'))
def test_recusa_apos_sinal_de_parada(self):
    instalar(self.eventos, self.parar, 'cnae')
    self.parar.touch()
    with httpx.Client(transport=self.mock) as c, self.assertRaises(httpx.TransportError):
        c.get('https://x.gov.br/a')
    self.assertEqual(self.pedidos_no_mock, 0)
def test_falha_de_gravacao_nao_derruba(self):
    instalar(self.tmp / 'pasta-inexistente' / 'e.jsonl', self.parar, 'cnae')
    with httpx.Client(transport=self.mock) as c:
        self.assertEqual(c.get('https://x.gov.br/b').status_code, 200)
def test_erro_de_rede_propaga(self): ...   # mock levanta ConnectError; c.get levanta; evento 'falha' gravado
def test_threads_nao_misturam_linhas(self): ...  # 8 threads, 50 pedidos; todas as linhas são JSON válido
def test_main_preserva_saida_e_marca_excecao(self):
    # subprocess com PYTHONPATH apontando módulos falsos em pacote temporário:
    # módulo com SystemExit(3) sai 3; com raise ValueError sai SAIDA_EXCECAO
```

Para o último teste, `main(argv)` recebe o nome qualificado completo e usa `backend.crawler.<modulo>` por padrão. Módulos falsos entram por `--pacote <nome>`, usado só em testes.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest backend/crawler/tests/test_painel_sonda.py -q`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implement `sonda.py`**

- Wrapper com a assinatura `send(self, request, **kw)`. Verifica `parar.exists()` antes de cada envio. Na resposta, `bytes` é `Content-Length` em stream e `response.num_bytes_downloaded` no restante.
- `main`: lê variáveis, chama `instalar`, ajusta `sys.argv = [modulo]` e executa `runpy.run_module(nome, run_name='__main__', alter_sys=True)`. `SystemExit` passa intacta. `Exception` imprime traceback e sai com `SAIDA_EXCECAO`. `ParadaSolicitada` não tratada conta como interrupção, pois a classificação usa o sinal de Parar.
- Gravação com `threading.Lock` e `OSError` silenciado.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest backend/crawler/tests/test_painel_sonda.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/painel/sonda.py backend/crawler/tests/test_painel_sonda.py
git commit -m "feat(painel): sonda de requisicoes por processo"
```

### Task 4: Executor

**Files:**
- Create: `backend/crawler/painel/executor.py`
- Test: `backend/crawler/tests/test_painel_executor.py`

**Interfaces:**
- Consumes: `FRENTES`, `carregar_catalogo`, `resumir_catalogo`, `planejar`, `classificar`, `barra`, `estimar`, `SAIDA_EXCECAO`, variáveis da sonda.
- Produces:
  - `Executor(painel: Path, data: Path, frentes=FRENTES, comando=comando_sonda, tempo_limite=60.0, intervalo=0.25)`, em que `comando(modulo) -> list[str]`.
  - `previa(selecionadas: set[str], refazer: set[str]) -> list[dict]`
  - `iniciar(selecionadas, refazer, finais: set[str]) -> None`: levanta `RodadaAtiva` se já houver rodada, inclusive em outro processo.
  - `parar() -> None`, `aguardar(timeout=None) -> None`, `log(modulo: str) -> str` (últimos 64 KB).
  - `estado() -> dict`, com a estrutura:

```python
{'rodando': bool, 'etapa': 'ocioso'|'coletando'|'parando'|'catalogo'|'finais',
 'inicio': str|None, 'fim': str|None, 'restante_s': float|None, 'sem_estimativa': int,
 'feitas': int, 'total': int, 'itens': int, 'aviso': str|None,
 'frentes': [{'modulo','nome','pasta','pesada','marcas','estado','itens','ultima_coleta','fonte','pendencias',
              'inicio','fim','saida','requisicoes','bytes','item_atual','bytes_item','fracao','base','feitos','total',
              'restante_s','forcada'}],
 'finais': [{'modulo','estado','inicio','fim','saida'}]}
```

`estado` de frente: `sem_dados | ja_coletada | parcial | na_fila | coletando | parando | verificando | concluida | pulada | erro | interrompida | nao_iniciada`.

- [ ] **Step 1: Write the failing tests**

Usar frentes falsas de `Frente` e `comando` que roda `sys.executable -c <script>`. Para gerar eventos, o script escreve em `PAINEL_EVENTOS`. Um módulo `catalogo` falso grava `data/catalogo/catalogo.json`. `intervalo=0.02` e `tempo_limite=0.5`.

```python
def test_roda_em_ordem_e_atualiza_catalogo_no_fim(self): ...       # ordem registrada em arquivo: a, b, catalogo
def test_falha_nao_interrompe_as_seguintes(self): ...              # a sai 1, b roda; a='erro', b='concluida'
def test_parcial_vem_do_catalogo_mesmo_com_saida_1(self): ...      # catálogo marca a com pendências
def test_catalogo_falha_mostra_aviso_e_classifica_pelo_processo(self):
    # catalogo sai 1: estado['aviso'] não vazio; a(saida 0)='concluida'; b(saida 1)='erro'
def test_eventos_alimentam_linha(self):
    # 2 'resposta', uma casa com origens: requisicoes==2, feitos==1, fracao==0.5, item_atual é a última URL, fonte é o domínio dela
def test_parada_suave_nao_inicia_seguintes(self):
    # a observa PAINEL_PARAR e sai 0: a='interrompida', forcada False; b='nao_iniciada'; catálogo rodou
def test_parada_forcada_encerra_arvore(self):
    # a ignora sinal e abre filho que grava pid; depois do tempo_limite: a='interrompida', forcada True, filho morto
def test_historico_e_interrupcao_por_queda(self):
    # histórico com linha 'inicio' sem 'fim' + linha final cortada '{"mod'
    # não levanta; ultimas['a']['resultado']=='interrompida'; a roda sem refazer
def test_saida_com_acentos_em_utf8(self):
    # filho: print('ação €'), sem configurar encoding no pai; termina com 0; log(modulo) contém 'ação €'
def test_segunda_rodada_recusada(self):
    # mesmo executor e outro Executor na mesma pasta: RodadaAtiva
def test_trava_liberada_ao_terminar(self): ...
def test_etapas_finais_rodam_depois_do_catalogo(self): ...
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest backend/crawler/tests/test_painel_executor.py -q`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implement processos e histórico**

- `comando_sonda(modulo)`: `[sys.executable, '-m', 'backend.crawler.painel.sonda', modulo]`.
- `Popen` com `cwd=RAIZ` (`Path(__file__).parents[3]`), stdout e stderr no log, e ambiente com `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `PYTHONUNBUFFERED=1`, `PAINEL_EVENTOS`, `PAINEL_PARAR`.
- Grupo próprio: `CREATE_NEW_PROCESS_GROUP` no Windows, `start_new_session=True` em outros sistemas.
- Encerramento forçado: `taskkill /PID <pid> /T /F` no Windows, `os.killpg` em outros. Nunca `os.kill(pid, 0)` no Windows, onde sinal 0 é `CTRL_C_EVENT`.
- Pastas: `painel/historico.jsonl`, `painel/rodadas/<id>/{eventos.jsonl,parar,<modulo>.log}`. `id` é `AAAAMMDD-HHMMSS`.
- Histórico: linha `{'evento': 'inicio', 'modulo', 't'}` ao começar e, após classificar, `{'evento': 'fim', 'modulo', 'inicio', 'fim', 'resultado', 'requisicoes', 'bytes', 'duracao_s', 'forcada'}`. `ultimas_execucoes(path) -> dict[str, dict]` ignora linha inválida. `inicio` sem `fim` posterior vira `{'resultado': 'interrompida'}`.
- Execução sem requisições não fornece base 1: `requisicoes=0` vira `ultimas_requisicoes=None`.
- Trava da rodada: arquivo `painel/rodada.lock` mantido aberto, com `msvcrt.locking` no Windows e `fcntl.flock` em outros. O sistema libera em caso de queda.

- [ ] **Step 4: Implement a rodada**

Thread única. Para cada item `rodar` do plano:
1. Marca `coletando` e grava `inicio` no histórico.
2. Lê novas linhas de `eventos.jsonl` a cada `intervalo`, atualizando `requisicoes`, `bytes`, `item_atual`, `bytes_item` (tamanho declarado na última resposta, mostrado ao lado do item em downloads grandes), `fonte` e `urls_casadas` (URLs distintas, `url` ou `url_final`, presentes em `origens`).
3. Calcula `fracao` e `base` com `barra`. Em processo terminado sem exceção, marca `verificando`.

Depois da última frente, com ao menos uma executada:
- Roda `MODULO_CATALOGO`, inclusive após Parar. Falhou: define `aviso` com o texto "Não foi possível atualizar o catálogo; pendências podem estar desatualizadas".
- Recarrega o resumo, classifica com `classificar`, grava `fim` no histórico. Sem catálogo atualizado, classifica com `situacao=None`.
- Roda `finais` selecionadas, salvo após Parar.

`parar()` cria o sinal, marca a etapa `parando` e, passado `tempo_limite`, força e define `forcada=True`. Frentes que ainda não começaram ficam `nao_iniciada`.

`estado()` copia sob trava e calcula `restante_s` com `estimar`. `s_por_item` é duração ÷ itens das frentes finalizadas nesta rodada. Frentes sem estimativa somam em `sem_estimativa`. `feitas` conta finalizadas, e `total` conta as do plano com `rodar`. `itens` soma `max(itens, feitos)` das finalizadas e `feitos` da atual. Sem rodada, cada frente mostra o panorama do catálogo: `sem_dados`, `ja_coletada` ou `parcial`. `ultima` com `erro` ou `interrompida` tem prioridade.

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest backend/crawler/tests/test_painel_executor.py -q`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add backend/crawler/painel/executor.py backend/crawler/tests/test_painel_executor.py
git commit -m "feat(painel): executor de rodadas com historico e parada em duas etapas"
```

### Task 5: Servidor e linha de comando

**Files:**
- Create: `backend/crawler/painel/servidor.py`, `backend/crawler/painel/__main__.py`
- Test: `backend/crawler/tests/test_painel_servidor.py`

**Interfaces:**
- Consumes: `Executor` da Task 4.
- Produces:
  - `criar_servidor(executor: Executor, porta: int) -> ThreadingHTTPServer`, em `127.0.0.1`. Levanta `OSError` se a porta estiver ocupada.
  - Rotas:
    - `GET /`: página.
    - `GET /estado`: JSON.
    - `GET /eventos`: SSE com `data: <estado>` por segundo.
    - `GET /log?modulo=`: texto.
    - `POST /previa`, `POST /iniciar`: corpo `{'frentes': [], 'refazer': [], 'finais': []}`.
    - `POST /parar`.
  - Linha de comando: `python -m backend.crawler.painel [--porta 8765] [--sem-navegador] [--sem-pagina --frentes a,b [--rodar-de-novo] [--finais estatisticas,sumarizacao]]`.

- [ ] **Step 1: Write the failing tests**

Servidor na porta 0 com executor falso (`estado`, `previa`, `iniciar`, `parar`, `log`, com chamadas registradas). Requisições por `http.client`.

```python
def test_get_estado_e_pagina(self): ...
def test_host_externo_recusado(self):      # Host: evil.com -> 403 em GET /estado (DNS rebinding)
def test_post_origin_externa_recusada(self):
    # Origin: https://evil.com -> 403; executor.iniciar não chamado
def test_post_sem_origin_recusado(self): ...
def test_post_sem_json_recusado(self): ... # Content-Type text/plain -> 415
def test_post_corpo_invalido(self): ...    # JSON quebrado e módulo desconhecido -> 400
def test_iniciar_com_rodada_ativa(self):   # executor levanta RodadaAtiva -> 409 com mensagem
def test_log_modulo_desconhecido(self):    # ?modulo=../../x -> 404; executor.log não chamado
def test_sse_cliente_desconecta(self):     # fecha conexão; rodada segue; servidor responde /estado depois
def test_porta_ocupada(self):              # main(['--porta', str(ocupada), '--sem-navegador']) -> 1 e mensagem com a porta
def test_terminal_saida(self):             # sem-pagina: parcial -> 0; erro -> 1; módulo desconhecido -> 2
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest backend/crawler/tests/test_painel_servidor.py -q`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implement `servidor.py`**

- `BaseHTTPRequestHandler`, sem log por requisição.
- Toda requisição valida `Host` contra `127.0.0.1:<porta>` e `localhost:<porta>`. POST também exige `Origin` igual a `http://` + Host e `Content-Type: application/json`, com corpo limitado a 64 KB.
- `/log` procura o módulo em `POR_MODULO` ou em `ETAPAS_FINAIS`, nunca monta caminho a partir do parâmetro.
- `/eventos`: laço com `wfile.write` e `flush`, encerrando em `BrokenPipeError`, `ConnectionResetError` ou `ConnectionAbortedError`. `daemon_threads = True`. Conjuntos não são serializáveis: `estado()` não os expõe.

- [ ] **Step 4: Implement `__main__.py`**

- `main(argv=None) -> int`. Modo página: cria o servidor antes de abrir o navegador. Porta ocupada: imprime `Porta 8765 em uso. O painel já pode estar aberto em http://127.0.0.1:8765` e retorna 1.
- `KeyboardInterrupt`: `parar()`, `aguardar()`, fecha o servidor. Segundo Ctrl+C durante a espera força o encerramento.
- Modo terminal: uma linha a cada mudança de estado (`hh:mm:ss frente estado detalhes`). Retorna 1 se houver `erro` ou `interrompida`, 2 para argumento inválido, 0 no restante. `RodadaAtiva`: mensagem e retorno 1.
- Caminhos padrão: `painel=crawler/.painel`, `data=crawler/data`.

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest backend/crawler/tests/test_painel_servidor.py -q`
Expected: 11 passed

- [ ] **Step 6: Commit**

```bash
git add backend/crawler/painel/servidor.py backend/crawler/painel/__main__.py backend/crawler/tests/test_painel_servidor.py
git commit -m "feat(painel): servidor local e linha de comando"
```

### Task 6: Página

**Files:**
- Create: `backend/crawler/painel/pagina.html`
- Test: acrescentar em `backend/crawler/tests/test_painel_servidor.py`

**Interfaces:**
- Consumes: rotas e estrutura de `estado` das Tasks 4 e 5.

- [ ] **Step 1: Write the failing test**

```python
def test_pagina_sem_recursos_externos_e_com_rotas(self):
    html = (PAINEL / 'pagina.html').read_text('utf8')
    self.assertNotRegex(html, r'(src|href)="https?://')
    for rota in ('/eventos', '/previa', '/iniciar', '/parar', '/log'):
        self.assertIn(rota, html)
    self.assertIn('total desconhecido', html)
    self.assertIn('sem estimativa', html)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest backend/crawler/tests/test_painel_servidor.py -q -k pagina`
Expected: FAIL com `FileNotFoundError`

- [ ] **Step 3: Implement `pagina.html`**

Layout A do mockup aprovado, em `.superpowers/brainstorm/4450-1793903128/content/layout.html`. Arquivo único, sem bibliotecas e com tema claro e escuro por `prefers-color-scheme`.

- **Coluna esquerda:** lista das 40 frentes com checkbox, opção "rodar de novo" em cada uma, marcar/desmarcar todas, seção "Etapas finais" com `estatisticas` e `sumarizacao` desmarcadas, e botão Iniciar/Parar.
- **Topo:** tempo restante (`~42 min`, `~42 min + 2 frentes sem estimativa`, ou `sem estimativa`), `feitas de total`, itens coletados e `aviso`.
- **Linhas:** uma por frente, com nome, selo de estado, barra, `feitos de total · fonte` (ou `total desconhecido`), horários, tempo restante e `item_atual` em fonte monoespaçada. `fracao` nula usa barra indeterminada com requisições e bytes. Marcas aparecem como etiquetas. Parcial mostra `N pendências`. Frente com `forcada` mostra "Encerrada à força; pode haver arquivo de cache sem recibo". Linha com erro abre o log em `<details>`.
- **Antes de iniciar:** `POST /previa` e diálogo `<dialog>` listando o que roda, o que é pulado e por quê, com avisos de `pesada` e marcas, além de botões Confirmar e Cancelar.
- **Dados:** `EventSource('/eventos')`, com reconexão automática e indicação "Sem conexão com o painel" no erro.
- **Segurança e acessibilidade:** textos de URL via `textContent`, nunca `innerHTML`. Atualizar linhas sem recriar checkboxes, para não perder foco ou marcação. Estado também em texto, não só por cor. `prefers-reduced-motion` desliga animação.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest backend/crawler/tests/test_painel_servidor.py -q`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/painel/pagina.html backend/crawler/tests/test_painel_servidor.py
git commit -m "feat(painel): pagina local no layout de lista de frentes"
```

### Task 7: Documentação e verificação real

**Files:**
- Modify: `backend/crawler/ferramentas.json`, `backend/crawler/FERRAMENTAS.md`, `backend/crawler/README.md`, `backend/README.md`

**Interfaces:**
- Consumes: linha de comando da Task 5.

- [ ] **Step 1: Registrar e documentar**

Em `ferramentas.json`, adicionar `{"modulo": "painel", "arquivo": "painel/__main__.py", "tipo": "coletor/comando", "descricao": "Executor único das coletas com página local de acompanhamento."}`, com linha equivalente em `FERRAMENTAS.md`. No README do crawler, nova seção "Painel de coleta" com comandos, regra de pular, "rodar de novo" não garantir dado novo, e parada em duas etapas. No `backend/README.md`, uma linha com o link.

- [ ] **Step 2: Rodar todos os testes do crawler**

Run: `python -m pytest backend/crawler/tests -q`
Expected: todos passam. Falha fora de `test_painel_*` deve ser relatada, sem ajuste: há trabalho alheio em andamento em `normas_id.py` e `citacoes.py`.

- [ ] **Step 3: Conferir módulos intactos**

Run: `git log --name-only --format= HEAD~6..HEAD`
Expected: só aparecem `backend/crawler/painel/*`, `backend/crawler/tests/test_painel_*` e `backend/crawler/.gitignore`. Nenhum módulo existente foi commitado por este trabalho.

- [ ] **Step 4: Verificação ponta a ponta pelo terminal**

Run: `python -m backend.crawler.painel --sem-pagina --frentes cnae --rodar-de-novo`
Expected: linhas de `coletando` e `concluida`, requisições > 0, catálogo atualizado e saída 0. `git status --short backend/crawler` não mostra nada de `.painel/`. Essa frente faz uma consulta à API do IBGE e só cria versão se o conteúdo mudou.

- [ ] **Step 5: Verificação ponta a ponta pela página**

Run: `python -m backend.crawler.painel`, com `run_in_background`.
Conferir no navegador:
- 40 frentes com contagens do catálogo, sem nada rodando.
- Marcar `mei` com "rodar de novo": prévia mostra o que roda.
- Linha atualiza ao vivo e termina como concluída.
- Selecionar frente coletada sem marcar: aparece como pulada.
- Parar durante `consultas_df_amplas`, depois de marcar "rodar de novo": mostra "parando", termina como interrompida sem aviso de força.
- Encerrar com Ctrl+C.

Registrar resultado real. Sem navegador disponível, dizer que a parte visual não foi conferida.

- [ ] **Step 6: Commit**

```bash
git add backend/crawler/ferramentas.json backend/crawler/FERRAMENTAS.md backend/crawler/README.md backend/README.md
git commit -m "docs(painel): registra comando e uso do painel de coleta"
```
