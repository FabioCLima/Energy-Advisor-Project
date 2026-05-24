# EcoHome Energy Advisor — Avaliacao Tecnica e Explicacao Para Leigos

## 1. Resumo em linguagem simples

O EcoHome Energy Advisor e um prototipo de produto de inteligencia artificial para ajudar uma casa a tomar decisoes melhores sobre energia.

Imagine uma casa com painel solar, carro eletrico, home office e equipamentos que consomem energia em horarios diferentes. A pergunta pratica e: **quando vale a pena ligar ou carregar cada coisa para gastar menos?**

O projeto junta dados de consumo, geracao solar, clima, precos de energia, previsao de uso e um agente de IA que responde perguntas em linguagem natural. Em vez de ser apenas um notebook educativo, ele foi evoluido para parecer um produto inicial: tem dashboard, chat, avaliacao do agente, testes, container Docker e caminho de deploy em cloud.

## 2. Avaliacao tecnica da proposta

A proposta de transformar o projeto de algo educativo para um prototipo de produto e profissionalmente valida.

O motivo principal e que ele demonstra uma trajetoria importante para vagas de Machine Learning Engineer, AI Engineer e MLOps Engineer: sair de um modelo isolado e chegar em um sistema que roda, responde, mede qualidade, faz fallback quando uma fonte externa falha e pode ser publicado.

### Pontos fortes

- O projeto tem uma persona clara: Joao, morador de Sao Paulo, com Enel SP, home office, painel solar e Tesla.
- O problema e concreto: reduzir custo de energia e decidir melhores horarios de uso.
- O sistema nao depende apenas de IA generativa; ele combina banco de dados, regras de negocio, modelo preditivo, ferramentas e agente.
- O dashboard permite demonstrar valor rapidamente.
- O agente e avaliado por trajetoria: ele precisa chamar as ferramentas certas, nao apenas escrever uma resposta bonita.
- Ha comparacao entre baseline e modelo de ML, o que mostra maturidade de ML Engineering.
- O deploy foi pensado como produto: Streamlit Cloud para demo publica e AWS App Runner para uma historia cloud mais proxima de producao.

### Pontos que ainda sao prototipo

- Os dados de consumo sao sinteticos, baseados em uma persona, nao em usuarios reais.
- SQLite e otimo para demo, mas nao seria o banco final para muitos usuarios.
- A integracao ANEEL tem fallback rastreavel, mas a fonte externa pode falhar por SSL ou disponibilidade.
- O agente depende de chave de API para foundation model.
- O projeto ainda nao tem monitoramento real de drift de modelo, custo por chamada ou qualidade em producao.

### Veredito

Como portfolio, o projeto e forte. Como produto comercial, ele ainda e um MVP tecnico. A forma correta de apresenta-lo e:

> Um prototipo de produto de IA aplicada, com foco em MLOps, avaliacao de agente, previsao de consumo e deploy cloud.

Nao e necessario vender como sistema pronto para producao. O valor profissional esta justamente em mostrar que voce sabe separar o que esta pronto, o que e trade-off e o que viria depois.

## 3. Qual e o valor do projeto

Para um usuario comum, o valor e simples: entender onde esta gastando energia e receber recomendacoes praticas para economizar.

Para uma empresa ou entrevistador tecnico, o valor e mais amplo:

- Mostra como transformar dados em decisao.
- Mostra como integrar ML tradicional com foundation models.
- Mostra como construir um agente que usa ferramentas, em vez de apenas responder por memoria.
- Mostra preocupacao com avaliacao, deploy, fallback e reproducibilidade.
- Mostra pensamento de produto: dashboard, narrativa, fluxo de uso e experiencia visual.

Esse e o ponto central: **o projeto nao e so sobre prever consumo. Ele e sobre operacionalizar uma decisao inteligente.**

## 4. O que foi feito

O projeto passou por uma evolucao em camadas.

### Camada 1: Dados

Foi criado um banco SQLite com dados de uma casa simulada:

- consumo por dispositivo;
- custo em reais;
- horarios de uso;
- geracao solar;
- temperatura e irradiancia;
- categorias como EV, home office, eletrodomesticos e carga fixa.

Esses dados permitem que o sistema responda perguntas reais, por exemplo:

- quanto custou meu home office nos ultimos 30 dias?
- quanto o carro eletrico consumiu?
- quanto o painel solar gerou?
- qual dispositivo pesa mais na conta?

### Camada 2: Regras e servicos

A logica principal foi organizada em servicos:

- consulta de dados historicos;
- calculo de precos de energia;
- fallback para dados da ANEEL;
- previsao meteorologica via Open-Meteo;
- forecast de consumo;
- recomendacoes de otimizacao.

Essa separacao e importante porque o agente nao deveria conter toda a regra dentro do prompt. O agente chama ferramentas. As ferramentas chamam servicos. Os servicos fazem o trabalho confiavel.

### Camada 3: Machine Learning

O sistema tem previsao de consumo usando duas abordagens:

- um baseline sazonal simples;
- um modelo `HistGradientBoostingRegressor`.

O baseline serve como referencia. Isso e uma boa pratica de ML: um modelo mais complexo so faz sentido se superar uma alternativa simples.

O projeto tambem salva metricas de hold-out, como RMSE e MAE. Isso permite responder uma pergunta essencial em entrevista:

> Como voce sabe que o modelo esta ajudando?

A resposta nao fica baseada em opiniao; fica baseada em metrica.

### Camada 4: Dashboard

O Streamlit funciona como a interface de produto.

Ele mostra:

- KPIs financeiros;
- consumo por dispositivo;
- economia solar;
- custo liquido da rede;
- previsao de consumo;
- recomendacoes de otimizacao;
- exportacao CSV;
- status das fontes de dados.

Isso importa porque um produto de IA precisa ser entendido por pessoas. O dashboard e a ponte entre modelo, dados e decisao.

### Camada 5: Agente de IA

O agente permite que o usuario faca perguntas em linguagem natural.

Exemplo:

> Quando devo carregar o Tesla para economizar mais?

O agente nao deve simplesmente inventar a resposta. Ele segue um fluxo:

1. Recebe a pergunta.
2. Lembra do perfil da casa de Joao pelo system prompt.
3. Decide quais ferramentas precisa chamar.
4. Chama ferramentas como preco de energia, clima, consumo historico ou forecast.
5. Recebe os resultados dessas ferramentas.
6. Monta uma resposta com recomendacao, motivo, impacto estimado e limitacoes.

Esse padrao e chamado de agente com uso de ferramentas. O foundation model nao e usado como banco de dados; ele e usado como motor de raciocinio e linguagem.

## 5. Como o sistema funciona por ordem de processo

Em vez de olhar para uma grande imagem de arquitetura, vale entender o sistema como uma sequencia de processos.

### Processo A: Abrir o dashboard

1. O usuario abre o Streamlit.
2. O sistema garante que os dados de demo existem.
3. Se o banco ainda nao existe, ele cria tabelas e dados sinteticos.
4. Se os modelos locais ainda nao existem, ele prepara artefatos de forecast.
5. O dashboard consulta o banco e mostra os indicadores.
6. O usuario visualiza consumo, custo, solar, previsao e recomendacoes.

Aqui quase nao ha foundation model. E mais engenharia de dados, produto e visualizacao.

### Processo B: Consultar dados historicos

1. O usuario ou dashboard pede informacao historica.
2. Uma ferramenta consulta o SQLite.
3. Os dados sao agregados por dispositivo, periodo ou categoria.
4. O resultado volta em formato pequeno e interpretavel.

Isso evita enviar milhares de linhas para o modelo de linguagem. E uma boa pratica: o LLM recebe informacao resumida e relevante.

### Processo C: Prever consumo

1. O sistema carrega serie historica de consumo.
2. O roteador de forecast decide entre modelo ML e baseline.
3. O modelo gera previsao para as proximas horas.
4. O dashboard ou agente mostra o metodo usado e as metricas disponiveis.

Aqui entra ML tradicional, nao foundation model. O modelo faz previsao numerica.

### Processo D: Gerar recomendacao de economia

1. O sistema combina forecast de consumo com horarios de energia mais barata.
2. Ele identifica cargas que podem ser deslocadas, como EV ou alguns eletrodomesticos.
3. Calcula economia estimada em reais.
4. Ordena as melhores oportunidades.

Aqui ha raciocinio de produto e regras de dominio. O foundation model pode explicar a recomendacao, mas o calculo deve vir das ferramentas.

### Processo E: Fazer uma pergunta ao agente

1. O usuario escreve uma pergunta no chat.
2. O foundation model le a pergunta e o system prompt.
3. O agente decide quais ferramentas chamar.
4. As ferramentas buscam dados reais ou calculam estimativas.
5. O foundation model recebe os resultados.
6. O agente responde de forma estruturada.

O foundation model aparece principalmente em dois lugares:

- para interpretar a pergunta do usuario;
- para organizar a resposta final em linguagem natural.

Ele nao deve inventar preco, consumo ou geracao solar. Esses dados devem vir das ferramentas.

### Processo F: Avaliar o agente

1. Existem cenarios de teste com perguntas conhecidas.
2. Cada cenario define quais ferramentas o agente deveria usar.
3. O sistema roda o agente e registra as ferramentas chamadas.
4. A avaliacao mede se a trajetoria foi correta.
5. Opcionalmente, outro modelo avalia a qualidade da resposta final.

Essa parte e muito importante para AI Engineering. Sem avaliacao, um agente pode parecer bom em uma demo e falhar silenciosamente em casos reais.

## 6. O que e design system neste projeto

Design system nao e apenas escolher cores bonitas. E criar consistencia visual e funcional.

Neste projeto, o design system aparece em decisoes como:

- grupos de KPIs por tema: financeiro, energia e eficiencia;
- uso consistente de moeda, kWh, porcentagem e periodos;
- cores com significado: solar, consumo, importacao da rede, economia;
- labels mais legiveis para dispositivos;
- separacao entre dashboard e chat;
- alertas e captions para explicar fonte dos dados;
- botao de exportacao CSV;
- layout pensado para demonstracao rapida.

Para um produto de IA, isso e crucial. Se a interface parece confusa, o usuario perde confianca no modelo, mesmo que o modelo esteja correto.

## 7. O que e arquitetura neste projeto

Arquitetura e a forma como as partes conversam entre si.

Aqui a arquitetura pode ser entendida assim:

1. **Interface**: Streamlit mostra dashboard e chat.
2. **Agente**: LangGraph organiza o ciclo de raciocinio e chamada de ferramentas.
3. **Ferramentas**: funcoes especificas que o agente pode chamar.
4. **Servicos**: codigo de negocio reutilizavel, como pricing, forecast e optimizer.
5. **Dados**: SQLite, documentos RAG, cache ANEEL e artefatos de modelo.
6. **Deploy**: Docker, Streamlit Cloud e AWS App Runner.

A decisao boa aqui e que cada camada tem um papel claro. Isso ajuda a testar, explicar e evoluir.

## 8. Como um agente funciona neste sistema

Um agente e diferente de um chatbot simples.

Um chatbot simples recebe uma pergunta e responde diretamente. Um agente recebe uma pergunta, decide se precisa agir, usa ferramentas e so depois responde.

Neste projeto, o agente segue o padrao ReAct:

- **Reason**: pensar no que precisa fazer;
- **Act**: chamar uma ferramenta;
- **Observe**: ler o resultado da ferramenta;
- repetir se precisar;
- responder ao usuario.

Exemplo pratico:

Pergunta:

> Qual melhor horario para carregar o Tesla hoje?

O agente deveria:

1. entender que e uma pergunta de agendamento;
2. chamar `get_electricity_prices` para saber horarios baratos;
3. chamar `get_weather_forecast` para entender solar;
4. opcionalmente consultar consumo/forecast;
5. responder com horario recomendado e justificativa.

O foundation model escolhe o caminho e escreve a resposta. As ferramentas fornecem os fatos.

## 9. Onde os foundation models sao usados

Foundation models sao modelos grandes treinados em muitos dados, como modelos de linguagem capazes de interpretar texto, raciocinar e gerar respostas.

Neste projeto, eles sao usados para:

- interpretar perguntas do usuario;
- decidir quais ferramentas chamar;
- transformar resultados tecnicos em uma resposta compreensivel;
- atuar como juiz opcional na avaliacao de respostas.

Eles nao sao usados para:

- calcular consumo historico;
- guardar os dados da casa;
- substituir o banco de dados;
- fazer forecast numerico principal;
- inventar preco de energia.

Essa separacao e uma boa pratica. O foundation model conversa e orquestra. As ferramentas calculam e buscam dados.

## 10. O que deve ser estudado em seguida

Para evoluir profissionalmente de Data Scientist para MLE ou AI Engineer, os proximos estudos mais importantes sao:

### MLOps

- versionamento de dados e modelos;
- pipelines de treino automatizados;
- registro de modelos;
- monitoramento de drift;
- deploy reproduzivel;
- rollback de modelo.

### AI Engineering

- desenho de agentes;
- avaliacao de agentes;
- tool calling;
- RAG;
- observabilidade de chamadas LLM;
- controle de custo e latencia;
- guardrails e seguranca.

### Engenharia de Software

- testes unitarios e de integracao;
- organizacao em camadas;
- configuracao por variaveis de ambiente;
- logs estruturados;
- containers;
- CI/CD.

### Cloud

- AWS App Runner ou ECS;
- ECR/GHCR;
- Secrets Manager ou Parameter Store;
- CloudWatch logs;
- healthchecks;
- separacao entre ambiente local, demo e producao.

### Produto e UX

- design system;
- hierarquia de informacao;
- metricas que ajudam decisao;
- onboarding do usuario;
- explicacao de limitacoes;
- clareza visual para confianca em IA.

## 11. Proximos passos recomendados para o projeto

A sequencia mais profissional daqui para frente seria:

1. Publicar demo no Streamlit Cloud.
2. Publicar container na AWS App Runner.
3. Atualizar README com links reais de deploy.
4. Rodar avaliacao do agente apos deploy.
5. Criar uma pequena pagina de "limitations and next steps".
6. Adicionar monitoramento basico de custo, latencia e erros.
7. Evoluir de SQLite para Postgres/TimescaleDB se a proposta for multiusuario.

## 12. Conclusao

O projeto tem valor porque mostra uma transicao importante: de aprendizado para produto.

Ele nao e apenas um exemplo de IA. Ele combina dados, ML, agente, interface, avaliacao e deploy. Isso e exatamente o tipo de maturidade que diferencia um projeto educativo de um prototipo profissional.

A melhor forma de apresenta-lo e dizer:

> Eu construi um prototipo de produto de IA para decisao energetica residencial, com forecast, agente com ferramentas, avaliacao de qualidade e deploy cloud-ready. O foco foi mostrar como transformar modelo e dados em um sistema operavel.
