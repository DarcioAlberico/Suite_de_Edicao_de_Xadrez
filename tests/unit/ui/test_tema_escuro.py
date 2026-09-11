"""O tema escuro é **projetado**, e não o claro invertido -- afirmado por medição.

"Tema escuro que é só o claro invertido" é um dos defeitos que a carta dos críticos (§3.3)
reprova sozinho, e é o único da lista que não dá para ver numa captura: um tema invertido parece
um tema escuro. O que o denuncia são três propriedades, e as três são números.

1. **A elevação inverte de sentido.** Em fundo claro tudo o que "sobe" fica mais claro: o botão e
   o poço do campo são mais claros que o painel. Em fundo escuro o costume é outro -- o botão
   sobe (clareia) e o **poço desce** (escurece), porque um poço mais claro que o painel é o tique
   inconfundível de paleta invertida. Uma inversão mecânica não consegue produzir isso: ela
   preserva a ordem relativa das luminâncias, e o poço continuaria acima do painel.

2. **A matiz sobrevive.** Uma inversão de canal (`255 - c`) roda a matiz em ~180°: o vermelho de
   "pare" vira ciano. Aqui `PROBLEMA_TEXTO` continua vermelho e `PRONTO_TEXTO` continua verde --
   o que muda é a luminosidade, o mínimo para cruzar o piso de contraste.

3. **O documento não segue a pele.** A folha do livro, o tabuleiro e a moldura ficam na paleta
   medida nas duas peles (S-224). Uma inversão global as levaria junto, e comparar um diagrama
   impresso em papel branco com um tabuleiro invertido é o produto deixando de funcionar.
"""

from __future__ import annotations

import pytest
from chess_diagram_ocr.ui import tokens

TOLERANCIA_DO_NEGATIVO = 0.02
"""Quão perto de `1 - c` um canal pode ficar e ainda contar como inversão.

Dois por cento é cinco níveis de 255: folga para o arredondamento de HSL para hexadecimal, e
longe demais para deixar passar uma inversão de verdade."""


def cor(papel: str, *, escuro: bool) -> str:
    return tokens.cor(papel, None, cromo_escuro=escuro)


def luminancia(hexadecimal: str) -> float:
    return tokens._luminancia(hexadecimal)


class TestElevacao:
    def test_o_poco_do_campo_troca_de_lado_entre_as_duas_paletas(self) -> None:
        """Claro: o poço sobe. Escuro: o poço desce. É a assinatura de uma paleta desenhada."""
        painel_claro = luminancia(cor(tokens.SUPERFICIE_PADRAO, escuro=False))
        poco_claro = luminancia(cor(tokens.SUPERFICIE_AFUNDADA, escuro=False))
        painel_escuro = luminancia(cor(tokens.SUPERFICIE_PADRAO, escuro=True))
        poco_escuro = luminancia(cor(tokens.SUPERFICIE_AFUNDADA, escuro=True))
        assert poco_claro > painel_claro, "na paleta clara o campo é mais claro que o painel"
        assert poco_escuro < painel_escuro, "na paleta escura o campo é mais **escuro** (F9)"

    def test_o_botao_sobe_nas_duas(self) -> None:
        """A face do controle é elevação nas duas paletas -- é o poço que muda de sentido."""
        for escuro in (False, True):
            painel = luminancia(cor(tokens.SUPERFICIE_PADRAO, escuro=escuro))
            botao = luminancia(cor(tokens.SUPERFICIE_ELEVADA, escuro=escuro))
            assert botao > painel, f"cromo_escuro={escuro}: o botão tem de subir"

    def test_pressionado_esta_sempre_mais_longe_do_painel_que_o_ponteiro(self) -> None:
        """A ordem repouso -> ponteiro -> pressionado é monotônica nas duas paletas."""
        for escuro in (False, True):
            face = luminancia(cor(tokens.SUPERFICIE_ELEVADA, escuro=escuro))
            sobre = luminancia(cor(tokens.SUPERFICIE_SOBRE, escuro=escuro))
            pressionada = luminancia(cor(tokens.SUPERFICIE_PRESSIONADA, escuro=escuro))
            direcao = 1.0 if escuro else -1.0
            assert direcao * (sobre - face) > 0, f"cromo_escuro={escuro}: o ponteiro não moveu"
            assert direcao * (pressionada - sobre) > 0, f"cromo_escuro={escuro}: sem pressionado"


class TestMatiz:
    @pytest.mark.parametrize(
        "papel",
        [
            tokens.BOTAO_PRIMARIO,
            tokens.BOTAO_DESTRUTIVO,
            tokens.PRONTO_TEXTO,
            tokens.PROBLEMA_TEXTO,
            tokens.DIVERGENTE_TEXTO,
            tokens.VIZINHA_TEXTO,
            tokens.ATENCAO,
            tokens.SELECAO,
            tokens.FOCO,
        ],
    )
    def test_a_matiz_do_papel_sobrevive_a_troca_de_pele(self, papel: str) -> None:
        """Um papel que trocasse de matiz seriam dois significados com um nome.

        O limite é 2°, e não é folga: a inversão de canal que este teste existe para excluir roda
        a matiz em ~180°. Dois graus é a tolerância do arredondamento de HSL para hexadecimal.
        """
        claro, escuro = cor(papel, escuro=False), cor(papel, escuro=True)
        if claro == escuro:
            pytest.skip(f"{papel} tem o mesmo valor nas duas paletas")
        assert tokens.distancia_de_matiz(claro, escuro) <= 2.0, (
            f"{papel}: {claro} -> {escuro} girou {tokens.distancia_de_matiz(claro, escuro):.1f}°"
        )

    def test_nenhum_papel_de_cromo_e_o_negativo_do_outro(self) -> None:
        """A prova direta: `#rrggbb` escuro nunca é `255 - c` do claro, canal a canal.

        É a definição literal de "invertido", e o teste a exclui papel por papel em vez de
        confiar na leitura de quem olha a captura.
        """
        invertidos = []
        for papel in tokens.CROMO:
            claro, escuro = cor(papel, escuro=False), cor(papel, escuro=True)
            canais_claros = tokens._canais(claro)
            canais_escuros = tokens._canais(escuro)
            pares = zip(canais_claros, canais_escuros, strict=True)
            if all(abs((1.0 - a) - b) < TOLERANCIA_DO_NEGATIVO for a, b in pares):
                invertidos.append(f"{papel}: {claro} -> {escuro}")
        assert invertidos == [], "\n".join(
            ["Papéis que são o negativo exato do claro:", *invertidos]
        )


class TestDocumento:
    @pytest.mark.parametrize("papel", list(tokens.SUPERFICIES_DE_DOCUMENTO))
    def test_a_superficie_do_documento_nao_segue_a_pele(self, papel: str) -> None:
        """A folha do livro e o tabuleiro ficam na paleta medida (S-224).

        O produto é comparar um diagrama impresso em papel branco com o que o modelo leu, e as
        doze marcações foram calibradas contra esse fundo. Uma aparência nova pode escurecer o
        cromo em volta; o que ela não pode é mudar o fundo da medição.
        """
        assert cor(papel, escuro=False) == cor(papel, escuro=True)

    def test_a_casa_do_tabuleiro_tambem_nao(self) -> None:
        """Xadrez impresso é claro-e-escuro em qualquer tema; um tabuleiro que troca de cor com a
        janela deixa de ser reconhecível como tabuleiro."""
        for papel in (tokens.CASA_CLARA, tokens.CASA_ESCURA, tokens.CASA_ULTIMO_LANCE):
            assert cor(papel, escuro=False) == cor(papel, escuro=True)


def test_todo_papel_de_cromo_tem_valor_nas_duas_paletas() -> None:
    """Um papel de cromo sem valor escuro resolve para a cor clara sob a pele escura.

    É exatamente como a moldura do grupo ficou invisível antes da F9 -- `MOLDURA` era papel de
    **documento** servindo de borda de controle, e dava 1,04:1 contra o painel escuro. A lista
    `tokens.CROMO` existe para esta asserção não depender de alguém lembrar.
    """
    faltando = [papel for papel in tokens.CROMO if papel not in tokens.NO_CROMO_ESCURO]
    assert faltando == [], f"papéis de cromo sem valor na paleta escura: {faltando}"
