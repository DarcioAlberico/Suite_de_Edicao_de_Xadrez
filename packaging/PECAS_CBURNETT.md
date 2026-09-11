# Peças de xadrez do Caïssa Studio — atribuição

Os 12 arquivos de `assets/piece_images/` deste pacote (`bb.png` … `wr.png`, 70×70 RGBA) são
rasterizações do conjunto **cburnett**.

| | |
|---|---|
| **Autor** | Colin M. L. Burnett |
| **Conjunto** | `cburnett` |
| **Licença declarada** | GNU General Public License, versão 2 **ou posterior** |
| **Licença sob a qual este pacote os redistribui** | **GPL-3.0** (exercendo a opção "ou posterior") — texto integral em `GPL-3.0.txt`, nesta mesma pasta |
| **Origem upstream** | <https://github.com/lichess-org/lila> (`public/piece/cburnett`) |
| **Documento de atribuição consultado** | `Chess_diagram_to_FEN/resources/COPYING.md`, seção *Lichess (lila)* |

Os SVG originais e o SHA-256 de cada um estão em
`packaging/assets/piece_images_fonte/PROCEDENCIA.json`, no código-fonte deste projeto, junto
com o script que faz a conversão (`packaging/gerar_pecas_livres.py`). A rasterização é feita
pelo PyMuPDF do ambiente de empacotamento; nenhuma alteração é feita no desenho além da
mudança de escala para 70×70.

**Por que este conjunto, e não o que estava aqui antes.** Ver `PECAS_PROCEDENCIA.md`, nesta
mesma pasta: os 12 PNG que o projeto usava até 2026-09-09 foram medidos como sendo a mesma
arte de um conjunto que o único documento de atribuição disponível descreve como *"All
rights reserved. No open-source license provided."* Eles não são distribuídos por este
pacote.
