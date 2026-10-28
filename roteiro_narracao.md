# Roteiro de narração — Gasto × Desempenho na Atenção Primária

Conferido contra o **deck final de 7 slides** (`apresentacao-1.pptx`).
Tempo somado: **10 min 05 s**, sem contar as pausas entre slides.

Escrito para ser falado, não lido. Números por extenso onde a leitura em voz
alta é ambígua.

| Slide | Tema | Tempo |
|---|---|---|
| 1 | Capa | 25 s |
| 2 | Resumo | 80 s |
| 3 | Base de dados | 115 s |
| 4 | Modelo de dados | 105 s |
| 5 | O diferencial | 110 s |
| 6 | Operações | 110 s |
| 7 | Justificativa | 70 s |

---

## Slide 1 — Capa · 25 s

Boa tarde. Nosso trabalho integra duas informações públicas que hoje não
conversam entre si.

De um lado, quanto cada município gasta em Atenção Básica. Do outro, como esse
município é avaliado nos indicadores da Atenção Primária do Ministério da Saúde.

São os 497 municípios do Rio Grande do Sul, de 2018 a 2024.

---

## Slide 2 — Resumo · 80 s

A pergunta é simples de enunciar. Investir mais por habitante em atenção básica
se traduz em indicador melhor?

Ela não é simples de responder, e o motivo é que a base que responderia isso não
existe. O gasto está declarado no Tesouro Nacional. O desempenho está no
Ministério da Saúde. Os dois são públicos, cobrem os mesmos municípios e o mesmo
período. Mas ninguém publica os dois juntos.

Por isso os objetivos específicos seguem essa ordem.

Primeiro, modelar e implementar o esquema que integra as fontes, resolvendo
chaves e granularidades incompatíveis. Segundo, construir a dimensão versionada
a partir das Notas Técnicas do Ministério. Terceiro, quantificar a associação
entre gasto e desempenho por faixa de investimento.

O quarto é o que diferencia o trabalho: separar, na variação da série, o
desempenho real do efeito da mudança de regra. E o quinto é documentar a
completude e a qualidade dos dados, para entregar uma base confiável.

*(Apontar para a caixa de ressalva.)*

E adianto a ressalva que está aqui embaixo, porque ela muda como as conclusões
devem ser lidas. A subfunção que usamos reúne recurso próprio, federal e
estadual. O pagamento por desempenho é só uma parte do repasse federal. O que
medimos é associação, não causalidade.

---

## Slide 3 — Base de dados · 115 s

São duas bases de dados, mais um terceiro conjunto de documentos que não é base,
mas sem o qual as outras duas não se interpretam.

O FINBRA, do Tesouro Nacional, traz a despesa por função de cada município.
Olhamos a subfunção dez ponto trezentos e um, que é Atenção Básica. São
seiscentas e cinquenta e uma mil linhas.

O SISAB, do Ministério da Saúde, traz a série histórica dos indicadores, por
município e por quadrimestre, um relatório por indicador. Setenta e seis mil
linhas.

E as Notas Técnicas, que são as regras. A cinco de 2020, a onze de 2022 e o
Documento Orientador. São sete indicadores sob dois regimes de cálculo
diferentes. Nenhuma das duas bases publica o nome, a regra ou a meta de cada
indicador — isso só existe nos documentos.

As duas bases somam setecentas e vinte e sete mil linhas carregadas.

Vale dizer como escolhemos dentro de cada uma, porque não é automático. No
FINBRA, a mesma despesa aparece repetida em vários estágios de execução:
empenhada, liquidada, paga e inscrita em restos a pagar. Usamos a liquidada. No
SISAB, o relatório deixa escolher quais equipes entram no cálculo, e usamos a
visão que considera todas as equipes do município, porque é o mesmo escopo da
despesa.

*(Apontar para a linha da junção, embaixo.)*

A junção entre as duas tem uma pegadinha. O FINBRA identifica o município por
código IBGE de sete dígitos. O SISAB usa seis. O sétimo é dígito verificador.
Então a junção é uma divisão inteira por dez. Testamos nos 497 municípios e não
houve nenhuma colisão. Quem tentar juntar pelas colunas cruas recebe zero linhas
e acha que a base está errada.

E uma terceira informação, a coordenadoria regional de saúde, não existe em
nenhuma das duas. Veio da divisão oficial da Secretaria Estadual, porque parte
das análises agrega por região.

---

## Slide 4 — Modelo de dados · 105 s

O modelo é dimensional, com duas tabelas-fato: uma de despesa e uma de
desempenho.

A tabela de despesa é município, exercício, estágio e conta, dando o valor. A de
desempenho é município, quadrimestre e versão do indicador, dando o percentual.

*(Apontar para dim_indicador.)*

A decisão que vale explicar é essa dimensão aqui, a de indicadores.

A Nota Técnica cinco, de 2020, vigorou até o terceiro quadrimestre de 2021. A
partir do primeiro quadrimestre de 2022, entrou a Nota Técnica onze. E a mudança
não foi só de redação. Cinco dos sete indicadores mudaram de nome na troca.

Quer dizer que, se tratarmos a série como contínua, corremos o risco de comparar
medidas diferentes sob o mesmo rótulo.

Por isso cada versão de um indicador é uma linha própria, com a sua regra, o seu
intervalo de vigência e a nota técnica que a definiu. A chave da tabela é um
identificador nosso, e não o código do indicador, porque o código se repete
entre as versões. Cada fato aponta para a versão que valia no seu quadrimestre,
e isso impede a comparação indevida.

Duas tabelas menores resolvem problemas parecidos.

A população fica separada do município, por exercício, porque muda a cada ano.
Usar um valor fixo distorceria o gasto per capita de toda a série.

E a dimensão de contas guarda o nível e se a conta é residual. O FINBRA traz
linhas de demais subfunções, que são resíduo. Somar essas junto com as
subfunções nomeadas contaria o mesmo dinheiro duas vezes.

---

## Slide 5 — O diferencial · 110 s

Aqui está o ponto central do trabalho.

*(Apontar para a linha do tempo.)*

Essa linha mostra os documentos que regem o cálculo dos indicadores ao longo do
programa. À esquerda, o regime da Nota Técnica cinco, de 2020. À direita, o
regime da Nota Técnica onze. A divisão cai no primeiro quadrimestre de 2022. E
no fim, em abril de 2024, a Portaria três mil quatrocentos e noventa e três
encerra o Previne Brasil.

Repare que no mesmo ponto de 2022 entram dois documentos. A Nota Técnica onze,
de fevereiro, e a Portaria cento e dois, de janeiro.

*(Apontar para a caixa vermelha.)*

E é a Portaria cento e dois que traz o problema mais interessante.

O número divulgado e o número que remunerou o município podem ser diferentes.

Essa portaria determinou alcance de cem por cento em indicadores e quadrimestres
específicos, apenas para fins de financiamento, enquanto o alcance real era
outro. Foi o caso da cobertura vacinal de poliomielite e pentavalente. A
diferença está registrada em portaria — não é suposição nossa.

*(Pausa.)*

Então, para esses períodos, o percentual publicado não é medida de desempenho
assistencial. É um valor administrativo.

E a troca de Nota Técnica, por sua vez, atinge os vinte e dois quadrimestres da
série inteira.

Juntando as duas coisas: uma variação que aparece na série pode ser atendimento
que melhorou, pode ser regra que mudou, ou pode ser um valor fixado por decreto.
Sem separar isso, qualquer conclusão sobre desempenho fica frágil.

É por isso que a dimensão de indicadores é versionada, e é por isso que
analisamos cada regime separadamente antes de comparar um com o outro.

---

## Slide 6 — Operações e análises · 110 s

As consultas básicas servem para conhecer os dados e validar a integração. Gasto
per capita por município e por ano, ranking de desempenho por indicador,
evolução quadrimestral, composição do orçamento de saúde por subfunção, e
cobertura e completude dos dados.

Essa última importa mais do que parece, e por isso vem antes das outras. Um
município que falta em alguns quadrimestres gera uma média calculada sobre menos
períodos. Sem conferir isso antes, a lacuna aparece como diferença de
desempenho.

Nas avançadas, começamos dividindo os municípios em quintis de gasto com NTILE e
olhando a mediana de desempenho de cada faixa. A distribuição do gasto per
capita é muito assimétrica entre os municípios do estado, e numa distribuição
assim um coeficiente de correlação é dominado pelos extremos. Por faixa, dá para
ver se existe progressão. Se não existir, isso também é resposta.

Depois usamos funções de janela para a variação ano a ano. Essa é outra
pergunta: se um mesmo município melhorou os indicadores depois de aumentar o
gasto, usando ele próprio como referência, o que elimina as diferenças
estruturais entre municípios.

Comparamos também cada município com outros de porte semelhante, por junção
reflexiva. Comparar a capital com um município de cinco mil habitantes atribui à
gestão o que é efeito de escala. Interessam os casos em que a posição no ranking
de desempenho difere muito da posição no ranking de gasto.

E agregamos por coordenadoria regional, com expressões de tabela comuns
encadeadas, para ver se esses casos se concentram em alguma região.

*(Apontar para o último item.)*

O último item é metodológico. Os relatórios trazem só o percentual, sem o
numerador e o denominador que o originaram. Então a média simples daria o mesmo
peso a um município de mil habitantes e à capital. Toda agregação é ponderada
pela população, e apresentamos as duas médias lado a lado.

---

## Slide 7 — Justificativa · 70 s

Fechando, por que o tema cabe na disciplina.

A integração não é trivial. O código IBGE tem seis dígitos no SISAB e sete no
FINBRA. O gasto é anual e os indicadores são quadrimestrais. Os formatos de
arquivo diferem. Sem tratamento prévio, a junção não retorna nenhuma linha.

O indicador muda de definição no meio da série. Isso transforma a definição numa
dimensão versionada, com vigência e nota técnica próprias. É problema de
modelagem, não só de análise.

E são duas bases oficiais e abertas sobre o gasto e o desempenho dos 497
municípios do estado, seguindo as normas de extensão do PET-Saúde Digital, com
consultas que empregam funções de janela, CTEs, junção reflexiva e agregação por
faixa.

*(Pausa.)*

Uma limitação que assumimos desde já: fora de 2024, temos o percentual publicado
sem o numerador e o denominador que o originaram. Isso impede verificar qual
denominador foi aplicado a cada município, e essa escolha afeta o resultado.

Obrigado. Ficamos à disposição para perguntas.

---

## Notas de gravação

**Leia em voz alta antes.** Onde você tropeçar, a frase está comprida demais
para ser falada. Encurte. O texto é seu.

**Os tempos pressupõem fala pausada.** Se terminar um slide bem antes do tempo,
você está correndo.

**Três slides passam de um minuto e meio** — o 3, o 5 e o 6. Marquei no roteiro
momentos para apontar elementos da tela: a linha da junção no 3, a linha do
tempo e a caixa vermelha no 5, o último item da lista no 6. Se a gravação
mostrar o cursor, mover o ponteiro para o que você cita dá ao olho algo para
seguir.

**O slide 5 carrega o peso.** Fale mais devagar nele, e segure a pausa depois de
"é um valor administrativo".

**Microfone.** Fone com microfone embutido resolve. Grave sem eco, longe de
ventilador e geladeira. Ruído de fundo estraga mais que voz amadora.

**Divisão entre os três.** Slides 1 a 3 para o primeiro, 4 e 5 para o segundo,
6 e 7 para o terceiro. Dá cerca de três minutos e vinte para cada um, e quem
pegar o bloco do meio fica com o diferencial.

---

## Como gravar e exportar

**Opção A — PowerPoint.** *Apresentação de Slides → Gravar Apresentação de
Slides*. Narre um slide por vez; se errar, regrave só aquele. Depois, *Arquivo →
Exportar → Criar Vídeo*, que gera o MP4 com a narração embutida.

**Opção B — gravar fora e me mandar.** Um arquivo de áudio por slide
(`slide1.mp3` … `slide7.mp3`), em qualquer formato. Eu monto o MP4 com os slides
sincronizados. Se mandar um arquivo único, preciso junto dos tempos de troca de
slide.
