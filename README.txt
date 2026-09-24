RIFTWALKER 0.9.5 — Refinement & Diagnostics Patch

RIFTWALKER 0.9.2 — Monster Skin & Animation Patch

RIFTWALKER — 0.9 RELEASE CANDIDATE
==================================

STATUS
------
RIFTWALKER entrou em FEATURE FREEZE. A 0.9 RC foi preparada para a primeira
bateria de testes reais no notebook. Sistemas e conteúdo essenciais estão
ligados ao runtime; daqui até a 1.0 a prioridade passa a ser:

TESTAR -> QUEBRAR -> CORRIGIR -> BALANCEAR -> POLIR -> TESTAR DE NOVO.

Não considerar esta build como 1.0 final antes de rodá-la e jogá-la em Pygame.

COMO RODAR NO WINDOWS
---------------------
Opção rápida:
1. Extraia o ZIP inteiro.
2. Execute install_and_run.bat.
3. O script instala as dependências, roda auditorias/testes e abre main.py.

Manual:
    python -m pip install -r requirements.txt
    python release_audit.py
    python asset_integrity.py
    python self_test.py
    python stress_test.py
    python main.py

CONTROLES PRINCIPAIS
--------------------
WASD       mover
Mouse      mirar
Clique 1   ataque básico
Clique 2   especial/contextual
1..4       habilidades equipadas
Q          defesa/parry quando a classe permitir
SPACE      dash
ESC        pausa / voltar
C          Códice / Bestiário
J          Missões
H          Refúgio
O          Configurações
F3         debug / FPS

NÚCLEO DO JOGO
--------------
- Action RPG 2D + roguelite + exploração por Rupturas.
- 10 classes: Guerreiro, Mago, Arqueiro, Ceifador, Rasgado, Cronista,
  Artífice, Duelista, Oráculo e Guardião do Véu.
- 65 habilidades, raridades, exclusividades, Corrompidas, maestria,
  sinergias e evoluções.
- 28 equipamentos, sets, loot, crafting e economia.
- 6 regiões, 12 missões, campanha persistente e eventos.
- 6 bosses, 20 padrões, boss final, boss secreto, 5 finais e NG+.
- Memória do Véu: bosses/Superiores usam tendências de encontros anteriores
  sem ler input do jogador em tempo real.
- Inimigos em squads, Diretor de Encontros e adaptação limitada a +/-12%.
- Superiores, mutações, Bestiário e pesquisa no Arquivo do Véu.
- Status e reações elementais.
- Facções, reputação, conquistas, Provações e Legado de Ecos.
- Refúgio da Última Luz com 5 instalações evolutivas.
- Geração procedural por seed.
- Fixed timestep de 60 Hz independente do FPS de render.
- Autosave, backup, escrita atômica, 3 slots e checksum.

ÁUDIO DA RELEASE CANDIDATE
--------------------------
A 0.8 aguardava 52 arquivos de áudio. Na 0.9 RC esse buraco foi fechado e o
pipeline foi ampliado.

Conteúdo atual:
- 60 SFX / músicas / ambiences esperados pelo AudioRouter e MusicDirector;
- 91 falas únicas do personagem x voz masculina/feminina = 182 OGG;
- 31 falas provisórias de bosses/inimigos;
- TOTAL: 273 arquivos OGG.

Todos os 273 OGG passaram por:
- checagem de integridade do projeto;
- validação de cabeçalho/tamanho;
- FFprobe.

SFX e músicas da RC foram gerados proceduralmente pelo próprio projeto sem
samples externos. As vozes são síntese provisória em português e podem ser
substituídas posteriormente sem alterar a lógica de habilidade/legenda.

O runtime já usa áudio para, entre outros:
- UI;
- espada / impactos;
- arco / impactos;
- magia e elementos;
- parry;
- dash;
- dano / morte;
- cura;
- Rupturas;
- spawn de Superior;
- drops raros/lendários;
- mudança de fase e morte de boss;
- ambience por região;
- música dinâmica de menu, combate, Superior, boss, boss final e final;
- vozes do jogador e bosses;
- legendas configuráveis.

ARQUIVOS PRINCIPAIS
-------------------
main.py                       runtime Pygame / gameplay / menus
core_systems.py               classes, skills, maestria, save, memória
class_kit_systems.py          kits completos das 10 classes
content_systems.py            equipamento, sets, loot, unlocks
narrative_systems.py          regiões, capítulos, NPCs, missões
hub_systems.py                Refúgio, crafting, vendedores, expedições
creature_systems.py           Superiores, mutações, Bestiário, pesquisa
combat_status_systems.py      status, elementos e reações
build_synergy_systems.py      sinergias e evoluções
world_generation_systems.py   mapa procedural
boss_systems.py               bosses, fases, padrões e memória
endgame_systems.py            final, finais, NG+ e boss secreto
encounter_director_systems.py pacing e threat budget
faction_systems.py            facções e reputação
challenge_systems.py          conquistas e Provações
legacy_systems.py             meta progressão / Legado
player_experience_systems.py  dificuldade, tutorial, Códice, acessibilidade
profile_systems.py            3 slots / checksum / recovery
audio_systems.py              definição de cues, música e legendas
pygame_audio_runtime.py       mixer e ponte real com Pygame
production_systems.py         auditoria de release
release_audit.py              auditoria de conteúdo/assets
asset_integrity.py            validação dos assets
self_test.py                  teste automático principal
stress_test.py                stress sem Pygame
generate_audio_assets.py      gerador procedural do áudio base
generate_extra_audio.py       gerador dos cues adicionais
generate_voice_assets.py      gerador de voz provisória do jogador
generate_enemy_voice_assets.py gerador de voz provisória inimiga
generate_branding.py          ícone/branding funcional
riftwalker.spec               configuração PyInstaller

CONFIGURAÇÕES / ACESSIBILIDADE
------------------------------
A RC possui estrutura e runtime para:
- dificuldade;
- volume de música;
- volume SFX;
- legendas;
- redução de screen shake;
- redução de flashes;
- números de dano;
- escala de UI;
- resolução/fullscreen conforme configuração de inicialização.

SAVE
----
SAVE_VERSION = 8.
A build possui:
- 3 slots;
- metadata por slot;
- checksum SHA-256;
- backup;
- recuperação;
- save JSON versionado;
- autosave em pontos seguros.

BUILD .EXE
----------
A escola continuará recebendo a versão .py conforme exigido.
Para distribuição Windows existe pipeline preparado com PyInstaller:

    build_exe.bat

Esse script roda auditoria + testes antes de gerar o executável. O arquivo
riftwalker.spec inclui a pasta assets e o ícone. Os caminhos de asset funcionam
tanto em execução normal quanto dentro do _MEIPASS do PyInstaller.

TESTES OFFLINE JÁ PASSADOS
--------------------------
- compileall: OK
- release_audit: 0 blockers / 0 warnings
- asset_integrity: 273 OGG OK
- FFprobe: 273/273 OGG decodificáveis
- self_test: OK
- stress_test: OK
- 10 kits: OK
- 300 mapas procedurais: OK
- conectividade início -> boss: OK
- 300 planos de encontro: OK
- fairness clamp +/-12%: OK
- 6 bosses / fases / pattern decks: OK
- save v8 / 3 slots / checksum: OK

O QUE PRECISA ACONTECER QUANDO O NOTEBOOK VOLTAR
------------------------------------------------
1. Executar install_and_run.bat.
2. Confirmar inicialização do Pygame e mixer.
3. Seguir FIRST_REAL_TEST_CHECKLIST.txt.
4. Testar as 10 classes na mão.
5. Testar hitboxes, colisão, movimento, dash e parry.
6. Testar UI/menus em resoluções reais.
7. Escutar música, SFX e vozes em contexto e regular volumes.
8. Jogar a campanha e bosses, procurar softlocks/crashes.
9. Medir FPS/stutter e otimizar.
10. Balancear dificuldade, loot, skills e pacing.
11. Corrigir tudo que a bateria encontrar.
12. Só depois promover a candidata para 1.0.

ARTE E ÁUDIO DEFINITIVOS
------------------------
A RC agora tem áudio funcional completo para teste, mas "funcional" não
significa "arte final de lançamento comercial". Sprites, animações, vozes,
músicas/SFX e branding ainda podem ser refinados depois que o jogo for testado.
A arquitetura permite substituir assets mantendo os IDs/cues.

LICENÇAS / CRÉDITOS
-------------------
Leia CREDITS.txt. Os assets sonoros atuais foram produzidos dentro do projeto.
Nenhum sample externo de terceiros foi incorporado à RC. Se assets externos
forem adicionados futuramente, registrar autor, origem e licença antes do uso.

REGRA DE FEATURE FREEZE
-----------------------
A partir desta RC, nova mecânica só entra se corrigir uma lacuna essencial ou
um problema detectado por teste. O foco não é aumentar a lista de features.
O foco é transformar esta candidata em um jogo estável, legível e divertido.


0.9.3 WORLD & SCENARIO PATCH
- Cenários regionais substituem a arena em grade.
- 6 regiões com direção visual própria, props, partículas, Rupturas e boss arenas.


Veja PERFORMANCE_AND_DEBUG.txt para o modo F3 e relatórios de crash.
