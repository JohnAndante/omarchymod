# OmarchyMod: scope handoff

Objetivo: fazer o [hyprmod do BlueManCZ](https://github.com/BlueManCZ/hyprmod)
(settings app GTK4/libadwaita pro Hyprland, com live preview, editor de
bind/bezier/monitor/window-rule e profiles) funcionar de verdade dentro do
[Omarchy](https://github.com/basecamp/omarchy): sem wiring manual, sem sumir no
próximo reload, e sem destoar do tema ativo.

Este arquivo e o handoff de contexto pra quem (agente ou humano) pegar o
trabalho a partir daqui. Sessao de origem: conversa em `pareazul-web-frotas` em
2026-09-03, nao relacionada ao projeto pareazul, so nasceu la. Revisado em
2026-09-03 depois de cruzar o plano com o codigo do hyprmod e com o Omarchy
4.0.2 instalado na maquina do usuario.

## Decisao principal: companion package, nao fork

O plano original era forkar o hyprmod. Depois de olhar o codigo, a decisao mudou
para **companion package**: um pacote `omarchymod` separado que instala o hyprmod
como dependencia e adiciona so a camada de integracao com o Omarchy por fora.

Motivos:

- O hyprmod **ja faz** a "abordagem recomendada" que o plano original descrevia.
  `hyprmod/core/setup.py` + `hyprmod/ui/onboarding_dialog.py` ja injetam a linha
  de include (`require("...")` / `dofile("...")` / `source = ...`) no entrypoint
  do usuario, ja suportam Lua mode, e ja andam a arvore de `source`/`require`
  inteira pra checar se ja esta configurado. Nao ha logica de config nova pra
  escrever.
- O valor da integracao (hook de gtk.css, ajuste do default path, deteccao de
  Omarchy, pacote AUR) e quase todo **externo** ao codigo do hyprmod.
- Um fork obriga rebase eterno contra um upstream ativo (4 PRs mergeados so nos
  commits recentes).

Ordem de preferencia:

1. Contribuir a deteccao de Omarchy + o hook de gtk.css **upstream** no hyprmod.
   Mesmo ecossistema (`hyprland-*`), o autor pode topar.
2. Companion package `omarchymod` que embrulha o hyprmod sem tocar no codigo
   dele: instala como dep, dropa o hook, aplica os overrides de config.
3. Fork so se o upstream recusar as mudancas de escopo.

Checar o [Omarchist](https://github.com/tahayvr/omarchist) antes de ir fundo:
GUI dedicada ao Omarchy com theme designer, ainda WIP. Pela doc publica nao cobre
keybindings, window rules nem monitor layout (o forte do hyprmod), mas pode haver
sobreposicao no theme designer que economiza trabalho, ou motivo pra conversar
com o autor.

## Realidade do Omarchy 4.x (corrige o modelo antigo)

O plano original assumia Omarchy classico: config `.conf`, arvore em
`~/.local/share/omarchy`, "5 arquivos fixos de usuario". **O Omarchy 4.x e
Lua-first** e tem arquitetura diferente. Confirmado na maquina do usuario
(pacote pacman `omarchy 4.0.2-1`, Hyprland em Lua mode):

- Entrypoint: `~/.config/hypr/hyprland.lua`, que faz
  `dofile(".../default/hypr/bootstrap.lua")` e `require("default.hypr.omarchy")`.
- `bootstrap.lua` poe `~/.config/?.lua` e `~/.local/state/?.lua` no
  `package.path`. Qualquer modulo Lua sob `~/.config` e `require`-avel. Nao
  existe mais a limitacao de "5 arquivos".
- O proprio `hyprland.lua` diz: *"Add any other personal Hyprland configuration
  below."* E territorio do usuario, explicitamente extensivel.
- Omarchy vive em `/usr/share/omarchy` (nao em `~/.local/share`).
- Overrides de usuario agora sao `.lua`: `hypr/monitors.lua`, `input.lua`,
  `bindings.lua`, `looknfeel.lua`, `autostart.lua`.
- Ordem de carga no `hyprland.lua`: bootstrap, `require("default.hypr.omarchy")`
  (que no fim carrega `omarchy.current.theme.hyprland`), depois os
  `require("hypr.*")` do usuario, depois `require("default.hypr.toggles")`,
  depois qualquer adicao do usuario.

## O que o companion package faz (superficie pequena)

1. **Detecta Omarchy** (`/usr/share/omarchy` existe, ou pacote instalado).
2. **Ajusta o default do managed path do hyprmod** para
   `~/.config/hypr/hyprmod/hyprland-gui.lua`. Ver "Reload prefix" abaixo, isso
   nao e cosmetico.
3. **Injeta o include** no `~/.config/hypr/hyprland.lua` (delegando pro
   `hyprmod.core.setup`, que ja faz isso). A linha entra no fim do arquivo, que
   e o lugar certo: ultima palavra ganha, escolha explicita do usuario vence os
   defaults e o tema.
4. **Sincroniza o gtk.css** do tema ativo para `~/.config/gtk-4.0/gtk.css` (e
   `gtk-3.0`), e dropa um hook `theme-set.d` pra refazer na troca de tema.
5. **Empacota no AUR** (`omarchymod` / `omarchymod-git`), seguindo o padrao do
   ecossistema (`hyprmod`, `omarchist-bin` ja estao la). Nao Flatpak/AppImage.

Fora de escopo, decisao consciente, **o companion nunca toca**: `looknfeel.lua`,
`monitors.lua`, `input.lua`, `bindings.lua`, defaults do Omarchy em
`/usr/share/omarchy`, `colors.toml`, arquivos de tema, toggles em
`~/.local/state/omarchy/toggles`.

## Backup e seguranca: nada e editado sem rede de protecao

Requisito explicito do usuario: tudo que os dois lados (companion + Omarchy)
podem tocar tem que ter backup pesado antes, pra nao quebrar o sistema.

**Principio**: nenhum arquivo compartilhado e mutado in-place sem (a) snapshot do
arquivo antes, (b) registro no manifesto, (c) caminho de reversao testado.

### Camadas

1. **Snapshot de sistema** (best-effort, opt-in). Se `snapper` estiver
   configurado, rodar `omarchy-snapshot create` antes da primeira instalacao.
   Barato e reverte tudo. Nao obrigatorio: nem todo mundo tem snapper (o proprio
   `omarchy-snapshot` sai com code 127 nesse caso), entao e um bonus, nao a
   defesa principal.
2. **Backup por arquivo**. Antes de tocar qualquer arquivo compartilhado, copiar
   para `~/.local/state/omarchymod/backups/<ISO8601>/<caminho-relativo>`. Cada
   operacao cria uma pasta nova com timestamp. Backup existente nunca e
   sobrescrito.
3. **Manifesto**: `~/.local/state/omarchymod/manifest.json`. Uma entrada por
   mutacao: arquivo, tipo (`append-line` / `create` / `symlink` / `hook-drop`),
   hash antes, hash depois, path do backup, timestamp. E o que o `--uninstall`
   le pra reverter com precisao.
4. **Escrita atomica**: toda escrita via tmpfile + rename. O `hyprland-config`
   ja expoe `atomic_write`, reusar.
5. **Reversao cirurgica**: o uninstall remove **so** a linha que a gente
   adicionou (match exato + comment marker tipo `-- omarchymod managed`),
   restaura o `gtk.css` do backup (ou remove, se a gente criou do zero), e
   remove o hook. Se algo divergiu do manifesto (usuario editou no meio), **nao
   forca**: avisa e aponta o backup pra reversao manual.

### Arquivos tocados pelos dois lados

| Arquivo | O que o companion faz | Quem mais escreve | Backup |
| --- | --- | --- | --- |
| `~/.config/hypr/hyprland.lua` | append de 1 linha `require(...)` | usuario; migrations do Omarchy (guarded) | obrigatorio antes do append |
| `~/.config/gtk-4.0/gtk.css` | cria ou symlinka pro gtk.css do tema | usuario (pode ter o proprio) | backup se existir; registrar se criamos |
| `~/.config/gtk-3.0/gtk.css` | idem | usuario | idem |
| `~/.config/omarchy/hooks/theme-set.d/omarchymod-gtk` | cria o hook | so a gente (nome namespaced) | registrar no manifesto |
| `~/.config/hypr/hyprmod/hyprland-gui.lua` | so o hyprmod escreve | so o hyprmod | sem conflito; hyprmod tem "automatic backups on save" no roadmap, ate la o manifesto aponta pra ele |

### Sobre as migrations do Omarchy

O Omarchy 4.x **modifica** `~/.config/hypr/hyprland.lua` e os arquivos de
override via migrations, mas so com guarda forte. Exemplos checados em
`/usr/share/omarchy/migrations/`:

- `1781063758.sh` reescreve `hyprland.lua` **so se nao contiver** a linha do
  bootstrap. Marker-gated, idempotente.
- `1781485962.sh` substitui `input.lua`/`bindings.lua` inteiros **so se o sha256
  bater com um hash stock conhecido**. Depois que o arquivo e editado, nunca mais
  toca.

Padrao do Omarchy: so sobrescreve arquivo que ele prova estar intocado. Uma
linha `require(...)` acrescentada no fim do `hyprland.lua` sobrevive a isso. O
risco residual e uma migration futura menos disciplinada; mitigacoes: o
`hyprmod.core.setup.needs_setup()` re-detecta e re-adiciona no proximo launch, e
o manifesto + backup permitem reverter se algo pior acontecer.

## Reload prefix: o managed path tem que ficar sob `hypr/`

O `bootstrap.lua` do Omarchy so limpa `package.loaded` para modulos com prefixo
`default.hypr`, `hypr` ou `omarchy.current.theme`. O default do hyprmod
(`~/.config/hypr/hyprland-gui.lua`, modulo `hyprland-gui`) **nao bate em
nenhum**. Consequencia: depois de `hyprctl reload` as configs do HyprMod ficam
stale ate um restart completo do Hyprland, porque o `require` fica cacheado e nao
re-executa.

Fix: o companion seta o managed path para `~/.config/hypr/hyprmod/hyprland-gui.lua`
(modulo `hypr.hyprmod.hyprland-gui`, bate no prefixo `hypr`, recarrega). O
hyprmod ja tem a constante `HYPRMOD_DIR = ~/.config/hypr/hyprmod`, so nao usa
como base do managed file por padrao.

## Sobreposicao de escopo com o theme layer

HyprMod e os temas do Omarchy escrevem **as mesmas chaves** do Hyprland. Visto em
`~/.local/state/omarchy/current/theme/hyprland.lua`: `general:col.active_border`,
`general:col.inactive_border`, `group:col.border_active/inactive`. O
`default/hypr/looknfeel.lua` tambem define `border_size`, `rounding`, animation
de borda, etc.

Com a linha do HyprMod no fim do `hyprland.lua`, **o HyprMod sempre vence o
tema** nessas chaves. Pode ser o comportamento desejado (escolha explicita do
usuario > tema), mas significa que trocar de tema nao aplica 100% enquanto o
HyprMod tiver aquela chave salva.

Decisao em aberto: o companion deveria configurar o hyprmod pra **nao gerenciar**
as chaves que o theme layer do Omarchy possui (cores/bordas/gradientes), ou
aceitar o conflito e documentar. Precisa ver se o hyprmod tem um mecanismo de
"ignore key" ou se isso e mudanca upstream.

## gtk.css / libadwaita

Problema real: nada no Omarchy escreve `~/.config/gtk-4.0/`, entao libadwaita
ignora o tema e renderiza Adwaita padrao (libadwaita so respeita `@define-color`
em `~/.config/gtk-4.0/gtk.css`). Confirmado em
[basecamp/omarchy#7557](https://github.com/basecamp/omarchy/issues/7557).

Mais facil do que o plano original achava: **cada tema ja traz um `gtk.css`
pronto** com os `@define-color` certos, em
`~/.local/state/omarchy/current/theme/gtk.css`. Nao precisa gerar do
`colors.toml`. O companion so:

1. Copia/symlinka esse arquivo pra `~/.config/gtk-4.0/gtk.css` e
   `~/.config/gtk-3.0/gtk.css` (com backup, ver acima).
2. Dropa `~/.config/omarchy/hooks/theme-set.d/omarchymod-gtk` que refaz o passo 1
   a cada troca de tema. O hook system e limpo: `omarchy-hook theme-set <nome>`
   roda tudo em `theme-set.d/`, com o nome do tema como arg. Precedente de
   terceiro: o `omazed` (live theme switching pro Zed) ja dropa um hook assim.

Candidato a PR upstream no Omarchy: resolve pra qualquer app GTK4 do sistema, nao
so pro nosso. A issue #7557 ja tem um script de referencia proposto (nao
mergeado).

## Lib de parsing

[hyprland-config](https://github.com/BlueManCZ/hyprland-config) (mesmo autor,
ja e dependencia do hyprmod) e parser round-trip Python: preserva
comentarios/formatacao, segue `source =` / `require` atraves de multiplos
arquivos, resolve globs, escreve so o que mudou, expõe `atomic_write`. E o que
sustenta tanto o append seguro do include quanto o managed file.

## Estado atual

- So existe como clone local em `~/Projects/omarchymod` com remote `upstream`
  apontando pro hyprmod original. Nenhum repo criado na conta/org do usuario.
- Com a decisao de companion package, o clone do hyprmod aqui vira material de
  estudo, nao base de fork. O companion `omarchymod` seria um repo novo e
  pequeno.

## Proximos passos

1. Prototipar o companion como script/pacote minimo: deteccao de Omarchy +
   backup/manifesto + ajuste do managed path + delegacao pro
   `hyprmod.core.setup` + hook de gtk.css.
2. Validar o ciclo de backup/uninstall num container ou VM Omarchy antes de
   rodar na maquina do usuario.
3. Decidir a sobreposicao de escopo com o theme layer (ignorar chaves de cor vs.
   documentar o conflito).
4. Sondar o autor do hyprmod sobre aceitar a deteccao de Omarchy + hook de
   gtk.css upstream (caminho 1 da decisao principal).
5. Look no Omarchist antes de duplicar o theme designer.
