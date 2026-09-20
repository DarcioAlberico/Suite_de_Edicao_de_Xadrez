# Propostas do passo 0b — leitura visual dos 18 diagramas casados sem FEN

Leitura visual independente (segundo leitor, não o modelo) dos 18 diagramas casados do conjunto de campo sem FEN anotada — passo 0b. É RASCUNHO: cada entrada só entra no conjunto quando um humano conferir o recorte contra a página e trocar 'confirmado' para true; tools/aplicar_0b.py grava só as confirmadas.

Se as propostas valerem: modelo certo em **10**, errado em **8** dos 18.

| n | livro | p. | portão | min_conf | proposta | difere do modelo | leitor | dúvida |
|---|---|---|---|---|---|---|---|---|
| 01 | Euwe, Kramer - Das Mittelspiel B | 25 | exportado | 0.979 | `4rr1k/1ppb3p/2q3p1/p7/3n4/1BP1B3/PP3PP1/2K2Q1R` | — | alta | c7/d7 conferidos na ampliação: peão e bispo (o bispo desta fonte tem a mitra curva) |
| 02 | Euwe, Kramer - Das Mittelspiel B | 25 | exportado | 0.850 | `r4rk1/p1nbb2p/3p2p1/2p1pPP1/1q1nP3/2N1B1N1/PP1Q4/2KR1B1R` | — | alta | — |
| 03 | Euwe, Kramer - Das Mittelspiel B | 25 | exportado | 0.972 | `r1bqrnk1/5pb1/p1pBp1p1/3pP1Np/5P1P/8/PPPQB1P1/2KR3R` | — | alta | — |
| 04 | Euwe, Kramer - Das Mittelspiel B | 40 | casa fraca | 0.573 | `r2qr1k1/pb1nbppp/1p3n2/3p1BB1/2pP3P/2N1PN2/PPQ2PP1/2KR3R` | — | alta | c6 vazia (o modelo hesitou nela a 0,57; a hachura é densa mas a casa está vazia) |
| 05 | GALLAGHER - Winning With the Kin | 124 | exportado | 1.000 | `r3k2r/pp1bqpn1/1n1P4/2p1P1p1/2B1NpP1/P7/1P1NQ3/R3K1R1` | — | alta | — |
| 06 | Koblenz - El dominio del arte de | 30 | ilegal | 0.341 | `r4rk1/pp3ppp/2pq1nb1/6N1/2BP4/7R/PPQ2PPP/4K1R1` | g8, a7, d6, g5, c4, c2, h2, e1 | alta | nesta fonte as pretas têm traço grosso e as brancas contorno fino (g8 rei preto, d6 dama preta, c2 dama branca, e1 rei branco — conferidos na ampliação) |
| 07 | Koblenz - El dominio del arte de | 30 | reparo | 0.029 | `3R4/p5r1/4q1k1/4p3/6n1/4NQ2/PPP5/6K1` | a7, g7, e6, g6, g4, f3, c2, h2, g1 | alta | mesma fonte do 06: e6 dama preta, f3 dama branca |
| 08 | Koblenz - El dominio del arte de | 50 | reparo | 0.002 | `3rr1k1/pp3pbp/6p1/2p5/3n1Pbq/3PN3/PPPQ1RBP/R1B3K1` | h7, c5, d4, f4, h4, d3, b2, d2, g2, g1 | confirmada pelo usuário | g4 bispo PRETO (corrigido pelo usuário 2026-09-20; a 1.ª leitura o tinha branco), h4 dama preta, g7 bispo preto, d2 dama branca |
| 09 | Koblenz - El dominio del arte de | 50 | reparo | 0.189 | `r4rk1/3qbppp/p1p5/1p2P3/6b1/1BP1B1Q1/PP3P1P/R4RK1` | a8, g8, d7, e7, g7, h7, g4, b2, f2, h2, g1 | confirmada pelo usuário | e7 bispo PRETO (corrigido pelo usuário 2026-09-20; a 1.ª leitura o tinha branco), g4 bispo preto; última fileira R4RK1 — rei g1, h1 vazia |
| 12 | Niemeijer - Zwarte Magie 100 zwa | 20 | casa fraca | 0.370 | `2B5/1KR3B1/4P3/pN1k2pN/1p4P1/P5B1/3PP1n1/n6q` | c8, g7, f5, g5, h5, g3, g2, a1 | alta | problema de mate: c8/g7/g3 bispos brancos, b5/h5 cavalos brancos, g2/a1 cavalos pretos |
| 13 | Niemeijer - Zwarte Magie 100 zwa | 20 | casa fraca | 0.347 | `5Rb1/4P3/KP6/1B1kq1P1/7p/p2N4/4P3/3Q1N2` | — | alta | — |
| 14 | Niemeijer - Zwarte Magie 100 zwa | 20 | reparo | 0.135 | `1K6/p7/p1PkppN1/R4Bp1/7P/5Qp1/1B3bp1/6qR` | g6 | alta | g6 é cavalo branco, não peão |
| 15 | Niemeijer - Zwarte Magie 100 zwa | 20 | casa fraca | 0.495 | `8/2p4K/1p2N2N/6pk/1p1bp1p1/3B2P1/1r1p4/q7` | h6 | alta | h6 é cavalo branco, não peão |
| 16 | Reinfeld_1001_Sacrificios_y_Comb | 40 | exportado | 0.957 | `r1bbr1k1/p2n1ppp/1p1Bp3/3q3Q/3PNP2/3B4/PP4PP/2R2R1K` | — | alta | — |
| 17 | Reinfeld_1001_Sacrificios_y_Comb | 150 | exportado | 0.981 | `r3k2r/ppp2ppp/1bn1b1q1/6NN/2pp4/8/PPP2PPP/R1BQR1K1` | — | alta | — |
| 18 | Stefaniu - Problematica Deschide | 100 | reparo | 0.002 | `r2qkbnr/pb3ppp/np1p4/1N1Np3/4PB2/8/PPP2PPP/R2QKB1R` | b5, e1, f1 | média | b5 é cavalo branco (não rei); f1: a tinta é pesada como a do bispo preto de b7, mas as pretas já têm bispos em f8 e b7 e as brancas só o de f4 — pela lógica da partida f1 é o bispo BRANCO; confirmar na página |
| 19 | 📚Yusupov Artur. Build Up Your Ch | 11 | exportado | 1.000 | `6k1/8/p7/r1r2Pp1/3R2Pp/1p6/1P4P1/3R2K1` | — | alta | a5/c5 torres pretas (cheias), d4/d1 brancas — conferido na ampliação |
| 20 | 📚Yusupov Artur. Build Up Your Ch | 11 | exportado | 1.000 | `r2r2k1/pb6/1p2pQ2/n1qP4/2P5/8/P4PPP/3RR1K1` | — | alta | — |
