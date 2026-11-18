# Design system do Sócio Digital

Os [tokens CSS](src/tokens.css) são a fonte da paleta. A [configuração do Tailwind](tailwind.config.js) expõe as mesmas cores semânticas para os componentes React.

| Cor | Token de paleta | Aplicação |
| --- | --- | --- |
| `#ffb346` | `--palette-apricot` | Botões principais e símbolo da marca |
| `#fcf8ed` | `--palette-cream` | Fundo das páginas e texto sobre a navegação escura |
| `#ffd166` | `--palette-honey` | Seção ativa, seleção e base dos destaques |
| `#ff9f1c` | `--palette-orange` | Botão principal em hover |
| `#118ab2` | `--palette-blue` | Foco em superfícies claras e base das citações e superfícies informativas |
| `#073b4c` | `--palette-navy` | Texto, títulos e navegação |

## Componentes

- **Botões** usam `.primary` para a ação principal e `.secondary` para ações de apoio. O texto sobre laranja e amarelo é azul-petróleo. Áreas escuras usam foco amarelo.
- **Painéis e campos** usam `.panel` e `.field` para espaçamento, bordas e superfícies. Campos inválidos usam borda de erro e mensagem textual.
- **Citações** usam `bg-info text-link` nos links e `bg-highlight text-ink` no trecho destacado.
- **Avisos** usam `.notice` ou `bg-notice text-ink`. O rótulo continua indicando o estado, como “Pagamento não verificado”.
- **Tipografia** usa a pilha definida em `--font-ui`, com Plus Jakarta Sans quando disponível e Segoe UI como opção local.

Prefira tokens de função no código dos componentes. Por exemplo, use `var(--button-bg)` no CSS e `text-link` no JSX. Se uma mesma cor tiver papéis diferentes, cada papel pode evoluir no respectivo token.

## Variação Azul e Areia

O fork usa `data-theme="azul-areia"` no elemento `html` do arquivo
`index.html`. Os botões principais usam azul com texto branco. O creme
suaviza as superfícies, e o amarelo indica a seção ativa e os trechos
citados. Controles e painéis têm cantos mais arredondados.

Remova o atributo `data-theme` para usar o tema base, com botões laranja.
Os dois temas compartilham os componentes e os seis tokens da paleta.
