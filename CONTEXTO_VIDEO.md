# Contexto — montagem do vídeo da apresentação

## Objetivo

Montar um MP4 narrado da apresentação "Gasto × Desempenho na Atenção Primária"
(INF01006, UFRGS), a partir de gravações de tela com áudio. O deck final tem
**7 slides** e o vídeo deve ficar perto de **10 minutos**.

---

## Estado atual

Existem **10 gravações**, cobrindo apenas os **slides 6 e 7**. Os slides 1 a 5
ainda não foram gravados.

Todas são MP4, 1280×720, H.264 + AAC 48 kHz estéreo, com o slide estático na
tela e a narração por cima.

Em ordem cronológica:

| # | Arquivo | Duração | Slide na tela |
|---|---|---|---|
| 01 | `2026-10-23_17-50-42.mp4` | 62,7 s | 6 |
| 02 | `2026-10-23_17-51-57.mp4` | 48,9 s | 6 |
| 03 | `2026-10-23_17-53-23.mp4` | 28,8 s | 6 |
| 04 | `2026-10-23_17-54-13.mp4` | 23,2 s | 6 |
| 05 | `2026-10-23_17-55-24.mp4` | 33,0 s | 6 |
| 06 | `2026-10-23_17-56-05.mp4` | 27,7 s | 6 |
| 07 | `2026-10-23_17-56-55.mp4` | 47,1 s | 6 |
| 08 | `2026-10-23_18-02-34.mp4` | 72,9 s | 7 |
| 09 | `2026-10-23_18-03-54.mp4` | 53,2 s | 7 |
| 10 | `2026-10-23_18-05-24.mp4` | 54,4 s | 7 |

**Não se sabe se são tomadas alternativas ou trechos sequenciais.** Essa é a
primeira coisa a descobrir pela transcrição. Uma montagem feita com a premissa
errada já foi tentada (pegando só a última de cada slide) e o resultado ficou
sem sentido.

---

## Problemas já medidos

**Volume muito baixo.** Média entre −36 e −40 dB em todos os arquivos. Fala
costuma ficar perto de −20 dB. Os picos estão entre −9 e −16 dB, ou seja, há
margem de sobra: é captação fraca, não saturação. O filtro abaixo resolve e
leva a média para cerca de −21 dB:

```
loudnorm=I=-16:TP=-1.5:LRA=11
```

Cuidado: normalizar áudio baixo levanta o ruído de fundo junto. Se o chiado
ficar audível, acrescentar `afftdn=nf=-25` antes do loudnorm.

**Ritmo mais rápido que o roteiro.** O roteiro prevê 110 s para o slide 6 e
70 s para o slide 7. As gravações mais longas dão 62 s e 72 s. No passo atual,
os sete slides somariam perto de 5 minutos, metade do alvo.

**Silêncio no início.** Algumas gravações começam com cerca de 1 s de silêncio;
outras começam com a fala já em curso, o que pode indicar corte no início.
Conferir caso a caso com `silencedetect`.

---

## Problema de conteúdo — ler antes de montar qualquer coisa

**As gravações são de uma versão ANTIGA do deck.**

Nas gravações, o slide 6 lista "Recálculo do indicador sob cada um dos três
denominadores" e o slide 7 diz "Três bases oficiais e abertas" e "há
denominadores concorrentes por registro".

O deck final (`apresentacao-1.pptx`) tem **duas** bases — FINBRA e SISAB, mais
as Notas Técnicas como regras, não como base — e **não tem** análise de
denominadores, porque a API do Ministério da Saúde foi descartada do projeto
(ela só cobre 2024).

Ou seja: **essas gravações mostram slides que o projeto já abandonou.** Se o
deck válido é o `apresentacao-1.pptx`, os slides 6 e 7 precisam ser regravados,
e o resto da montagem não deve ser feito sobre elas.

Confirmar isso com o usuário antes de investir tempo em edição.

---

## Ambiente

- `ffmpeg`, `ffprobe` e `pdftoppm` são as ferramentas necessárias.
- Transcrição: `pip install openai-whisper`, depois
  `whisper <arquivo> --language pt --model small --output_format txt`.
  O modelo `small` dá boa precisão em português; `base` é mais rápido e erra
  mais em termos técnicos.
- Atenção aos termos que o Whisper costuma errar neste material: "subfunção
  10.301", "quadrimestre", "NTILE", "FINBRA", "SISAB", "cod_ibge", "Previne
  Brasil", "capitação ponderada".

---

## Receita de montagem que já funcionou

Normalizar e reencodar cada parte com os **mesmos** parâmetros, depois
concatenar sem reencodar:

```bash
# uma parte
ffmpeg -ss 0.85 -i entrada.mp4 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.25" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 parte01.mp4 -y

# juntar
printf "file 'parte01.mp4'\nfile 'parte02.mp4'\n" > lista.txt
ffmpeg -f concat -safe 0 -i lista.txt -c copy final.mp4 -y
```

O `-ss` antes do `-i` apara o silêncio inicial. O `-r 30` fixo em todas as
partes é o que permite o `-c copy` na concatenação.

Para conferir o resultado:

```bash
ffmpeg -i final.mp4 -af volumedetect -f null - 2>&1 | grep volume
ffprobe -v error -show_entries format=duration -of csv=p=0 final.mp4
```

---

## Arquivos de referência

- `apresentacao-1.pptx` — deck final, 7 slides
- `roteiro_narracao.md` — roteiro de narração por slide, com tempos previstos
- As 10 gravações
