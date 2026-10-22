# RE Hub

Todos os Resident Evil em um lugar, em ordem da história, no estilo da tela inicial do PS5:
jogos da Steam, decomps/recomps, emuladores, mods e troféus.
Abra com **`RE Hub.exe`** (não precisa de Python). Ou, para rodar o código direto, `Abrir RE Hub.bat`
(precisa de Python e de `pip install pillow`).

Abre em tela cheia (uma cópia só: clicar de novo no .exe só traz a janela para frente). Teclado: ← → capítulos
(no fim de uma aba, mais um toque na seta passa para a próxima) · ↑ ↓ versões · Enter jogar · G gerenciar · Tab troca de seção ·
F11 tela cheia · Esc sai da tela cheia · F5 atualizar · E extras · P perfil · H história · C personagens · L ofertas ·
F foto do card. O ✕ no canto de cima fecha o app; o logo no topo volta ao começo; a roda do mouse anda como as setas.

- **Seções:** "Linha do tempo" (história oficial), "Não canônicos" (spin-offs), "Perdidos" (versões canceladas, betas e
  demos), "Filmes" (CG, live-action e séries), "HQs e livros" (quadrinhos, mangás e os livros de S. D. Perry) e
  "Feito por fãs" e "Notícias" (as 20 últimas do REVIL, atualizadas a cada 30 minutos). A lista segue a de residentevil.com.br/jogos/ (`python tools/revil_update.py` reaplica).
- **Cards:** passe o mouse para destacar (com som); um clique abre o card em tamanho grande.
- **Barra de baixo:** ordem por história, lançamento ou **Recentes** (o que você jogou por último primeiro), filtro
  "Só instalados", trilha e efeitos ligados/desligados, **Extras**, **▶ Continuar** (volta ao último jogo que você abriu;
  o app também já abre nele) e menu de Opções.
- **Horas jogadas:** embaixo do título aparecem as horas, quando você jogou por último e quando a Steam atualizou o jogo
  ("atualizado desde a última vez ›" abre as notas da atualização). Tudo lido da própria Steam no PC.

## Extras (E, ou ☰ Extras na barra de baixo)

- **Perfil (P, ou clique no seu nome/troféus no topo):** platinas, troféus por tipo, horas na franquia, progresso de
  cada jogo e os seus troféus mais raros.
- **Linha da história (H):** todos os capítulos ano a ano, com os filmes que se passam dentro da história encaixados.
  Enter abre o capítulo no hub.
- **Fonte das informações: [Resident Evil Wiki em português](https://residentevil.fandom.com/pt-br/wiki/Resident_Evil_Wiki).**
  A lista de personagens, vilões e criaturas, os textos das fichas, das armas biológicas, dos vírus, dos lugares do mapa
  e a aba **Wiki** de cada jogo vêm de lá (guardados em `data/cache/wiki_pt`; o hub busca de novo a cada poucos dias).
  As fichas escritas à mão em `games/_personagens.json` completam a wiki (papel, bestiário, jogos onde aparece);
  `"pt": "<página>"` escolhe a página da wiki de uma ficha.
- **Personagens (C):** todos os personagens, vilões e armas biológicas da wiki em português (mais de 380; Tab troca
  o filtro), com o texto da wiki e em quais jogos aparece (clique para abrir o jogo). Cada ficha mostra **todas as
  versões** do personagem, uma imagem por jogo/filme, da mais antiga à mais nova (PageUp/PageDown ou LT/RT trocam).
- **Ofertas e lançamentos (L):** preço de cada jogo na Steam Brasil, os que estão na sua lista de desejos (★) e a
  contagem regressiva dos anunciados. Quando um jogo que você não tem entra em promoção, aparece um aviso (uma vez por
  dia) e o card ganha o selo "-50%". Para pôr a data de um anúncio à mão: `"data_lancamento": "2027-03-12"` (ou
  `"2027-03"`, `"2027"`) no capítulo em `games/_linha_do_tempo.json`.
- **Mapa (M):** onde cada capítulo acontece, num mapa-múndi e numa planta de Raccoon City (Tab troca). Clique num jogo
  para abri-lo. Os lugares ficam em `games/_mapa.json`.
- **Arquivos dos jogos (A):** os documentos e diários de cada jogo. A wiki em português não tem esses documentos,
  então eles vêm da wiki em inglês e são **traduzidos para o português** automaticamente (o botão "Português / Original" troca; fica guardado em `data/cache/arquivos`).
- **Relações (R):** famílias, parceiros e inimigos ligados por linhas (`games/_relacoes.json`).
- **Vírus e parasitas (V):** T, G, T-Veronica, Plaga, Uroboros, mofo... com quem criou, como age e quem foi infectado
  (`games/_virus.json`).
- **Conquistas do hub (K):** metas que o hub acompanha sozinho (linha do tempo completa, todas as versões de um jogo,
  horas, platinas, arquivos lidos...). Quando uma é liberada aparece um aviso com som de troféu.
- **Bestiário:** nas armas biológicas, a ficha mostra o ponto fraco, a melhor arma e onde ela é chefe.
- **Speedrun:** aba no painel com o recorde de cada categoria no speedrun.com (clique abre a run).
- **Foto do card (F):** salva uma imagem 1920x1080 do jogo selecionado (arte, capa, troféus e horas) em
  `Imagens/RE Hub`, pronta para postar.

## Prints e gravações

A aba **Prints** do painel mostra as prints da Steam (F12) e as capturas do Windows (Xbox Game Bar: Win+Alt+PrtScn e
Win+Alt+R; e pastas da Radeon/NVIDIA com o nome do jogo). Clique numa para ver em tela cheia (← → passam); dá para
**usar a print como fundo** do jogo (e voltar ao original). Se a janela do jogo tiver outro nome, ponha
`"nomes_janela": ["NOME DA JANELA"]` no .json do jogo.

## Controle e atalho

Funciona com controle de Xbox (e qualquer um que o Windows ou a Steam mostre como um): direcional/analógico andam,
A joga/abre, B volta, X gerenciar, Y foto do card, LB/RB trocam de seção, LT/RT trocam a aba do painel, analógico
direito rola o painel, Start abre Extras, View abre o Perfil, botão Xbox volta ao começo.
**Segurar o botão Xbox** ou apertar **Ctrl+Alt+H** de qualquer lugar traz o hub de volta para a frente.

## Sons de menu por jogo

Em Opções → "Sons de menu para <jogo>..." abre `data/sons/jogos/<id do capítulo>/`. Coloque ali os sons que quiser
(o app não traz os da Capcom) com o nome do efeito (`Navigation.mp3`, `Navigation_Enter.mp3`... a lista está no
LEIA-ME.txt da pasta); com o jogo selecionado, eles tocam no lugar dos sons do PS5.

## Trilha sonora

O app não traz as músicas (são da Capcom). Ele toca, em loop e com fade, a trilha que você tiver:

1. **Trilhas compradas na Steam:** vários RE vendem a trilha como DLC (veja a aba DLCs). Instale e o app acha sozinho.
2. **Sua própria música:** já existe uma pasta por jogo em `data/musica/<id do capítulo>/`; é só colocar os arquivos.
   Ou em Opções → "Escolher música para..." (mp3, wav, wma ou m4a), ou coloque arquivos em
   `data/musica/<id do capítulo>/` (ex.: `data/musica/re2/`).

Os sons da interface são os do PS5, em `data/sons/ps5` (Navigation ao passar e trocar, Navigation_Enter ao abrir,
Navigation_Back no Esc, Prompt ao abrir "Gerenciar", Prompt_Enter no Jogar, Control Center no menu de Opções e
Trophy_Notification quando chega troféu novo). Sem esses arquivos, o app usa tons próprios.
Ao abrir, uma tela de carregamento com o símbolo da Umbrella toca `inicio.mp3` (qualquer tecla pula).
Seções sem jogo (Perdidos, Filmes, HQs, Fãs) tocam o tema do menu, em `data/musica/_menu`. Com várias músicas na
pasta de um jogo, cada visita sorteia uma. Uma versão pode ter música própria: `data/musica/<id da versão>/`
(ex.: `re4_2005` toca The Drive original e `re4` o Remake). Cada música começa onde o som aparece, sem o silêncio
do início: depois de pôr músicas novas, rode `python tools/audio_inicio.py` (precisa de `pip install imageio-ffmpeg`).

## Instalar

Baixe **RE Hub - Instalar.exe** na página de releases do GitHub e abra: ele instala o app inteiro
em `%LOCALAPPDATA%\Programs\RE Hub` (ou na pasta que você escolher), cria os atalhos na área de
trabalho e no menu Iniciar e aparece em "Adicionar ou remover programas". Não pede administrador.
Para atualizar, rode a versão nova por cima: seus dados (`data/`) ficam.

Gerar o instalador: `python tools/build_installer.py --version 1.0.0` (sai em `build/installer`).

## Gerar o .exe de novo (depois de mudar o código)

```
python tools/make_icon.py
python -m PyInstaller --noconfirm --noconsole --onedir --contents-directory _internal --icon re_hub.ico --name "RE Hub" --distpath build/dist --workpath build --specpath build main.py
```

Depois copie `build/dist/RE Hub/RE Hub.exe` e a pasta `_internal` para cá. (O .exe agora vem com a pasta `_internal`
ao lado em vez de ser um arquivo único: abre em menos de meio segundo, porque não precisa descompactar nada.)

O catálogo (`games/`) e os dados (`data/`) ficam fora do .exe, então editar o catálogo não exige gerar de novo.
Cards já montados ficam em `data/cache/cards` (pode apagar à vontade; o app monta de novo).

## Outras franquias (Silent Hill e outras)

O programa é o mesmo para qualquer franquia. O que muda fica em **`franquia.json`** (nome, cor, logo, símbolo da
tela de carregamento, mensagens, feed de notícias, fontes dos títulos) e no catálogo `games/`.

Para criar o hub do Silent Hill numa pasta nova:

```
python tools/nova_franquia.py silent_hill "C:/Users/<você>/Documents/SH Hub"
```

Isso copia o programa, o `franquia.json` de `modelos/silent_hill/` (Halo do Sol na abertura, cor ferrugem, logo do
Silent Hill, notícias pelo Google Notícias), as fontes, os sons e o ffmpeg, e cria um catálogo vazio. Os dois hubs
abrem ao mesmo tempo sem conflito.

## Fontes dos títulos

Cada jogo mostra o título numa fonte parecida com a do logo da capa (as originais são da Capcom). São fontes livres do
Google Fonts, em `data/fontes`, carregadas só pelo app. A lista fica em `rehub/fonts.py`; para trocar a de um capítulo,
ponha `"fonte_titulo": "<chave>"` nele em `games/_linha_do_tempo.json`.

## Trailer

Aba **Trailer** no painel da direita: o trailer principal da página do jogo na Steam, tocando numa telinha
(com botões de pausar e de som; a trilha do capítulo pausa enquanto ele toca). Na primeira vez o app baixa e converte
o vídeo (uns 10 segundos) e guarda em `data/trailers`. A conversão usa o `data/ferramentas/ffmpeg.exe`.
Jogos fora da Steam ganham um botão para ver o trailer no YouTube.

## Mods (Fluffy Mod Manager)

Os mods são instalados pelo **Fluffy Mod Manager** (gratuito, de FluffyQuack): ele ativa, desativa, avisa conflitos
e faz backup sozinho. O app só baixa, abre e mostra a pasta de mods de cada jogo.

1. Em **Gerenciar**, seção "Mods — Fluffy Mod Manager", clique em **Baixar** (ou em Opções → Abrir Fluffy Mod Manager).
   Ele fica em `data/ferramentas/FluffyModManager`.
2. Baixe o mod (o botão **Nexus Mods** abre a página do jogo) e clique em **+ Adicionar mod** (.zip, .rar, .7z ou pasta):
   o arquivo vai para `Games\<jogo>\Mods` do Fluffy (RE2R, RE3R, RE4R, RE7, RE8 = Village, RE9 = Requiem).
   Nos outros jogos que o Fluffy aceita (RE HD, RE0, RE5, RE6, Revelations 2, clássicos), escolha o jogo no Fluffy uma
   vez e use **Indicar pasta**.
3. Abra o Fluffy (**Abrir Fluffy**) e ative o mod.
- **REFramework**: o botão **Pôr no Fluffy** baixa a versão nightly (a que acompanha as atualizações dos jogos; a
  estável, de 2025, trava nos jogos atualizados) e coloca na pasta de mods. Ative no Fluffy como qualquer mod.
- Mods que o app tinha ativado antes da troca continuam no jogo; em Gerenciar aparece **Desfazer e devolver
  originais** para tirá-los.

## Troféus

Vêm das conquistas da Steam do seu perfil (página pública, sem senha nem chave).
Ouro = menos de 10% dos jogadores têm, prata = menos de 35%, bronze = o resto; platina = 100%.
Precisa que "Detalhes dos jogos" esteja como Público na privacidade da Steam. Cache de 6 horas.

## Estrutura

```
main.py              abre o app
games/               catálogo: um .json por jogo
  _linha_do_tempo.json  capítulos em ordem da história
rehub/
  steam.py           acha a Steam, os jogos instalados e as artes
  trophies.py        troféus a partir das conquistas da Steam
  store.py           arte oficial e DLCs da loja da Steam
  launcher.py        onde cada jogo está e como abrir
  github.py          baixa releases do GitHub e extrai .zip com segurança
  fluffy.py          Fluffy Mod Manager (baixar, abrir, pasta de mods de cada jogo)
  mods.py            só para desfazer mods ativados pelo sistema antigo
  catalog.py         lê games/ e guarda suas escolhas (data/config.json)
  ui/                janelas (app.py = lista, manage.py = "Gerenciar", theme.py = visual)
data/                gerado pelo app: config, capas, recomps baixados e biblioteca de mods
```

## Adicionar um jogo

Crie `games/<id>.json`. Campos:

| campo | uso |
|---|---|
| `capitulo`, `versao`, `ordem` | em qual capítulo da linha do tempo entra, nome da versão e posição |
| `nome` | nome completo do jogo |
| `arte` | `{capa, fundo}`: links de imagens próprias (ex.: GOG) |
| `poster` | `{titulo, subtitulo}`: capa gerada quando não há arte em loja nenhuma |
| `tipo` | `steam` (precisa de `appid`) ou `local` |
| `github`, `asset`, `exe` | (local) baixa a última release que casa com `asset` e acha o `exe` |
| `args` | argumentos; `{iso}` vira a ISO escolhida pelo usuário |
| `dica`, `depois_de_baixar` | textos de ajuda |
| `sugestoes` | lista de `{nome, tipo: mod/ferramenta, github, asset, descricao}` |
| `projetos` | lista de `{nome, url, status}` mostrada como links |

