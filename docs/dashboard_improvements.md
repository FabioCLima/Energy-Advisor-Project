# Dashboard Improvements — Energy Advisor

> Levantado em 23/05/2026 a partir de revisão visual do dashboard de João (Enel SP, últimos 30 dias).

---

## Bugs / Inconsistências de Dados

### B1 — Home Office Cost com valor duplicado e divergente
- **Onde:** KPI card "Home Office Cost" vs caixa "Home Office Cost Report"
- **Problema:** KPI mostra R$ 57.34; o report box mostra R$ 52.57 (80.1 kWh) — mesmo período, valores diferentes
- **Correção:** Unificar a fonte de dados para ambos os componentes; verificar se há diferença entre `cost_period` e `cost_projected`

### B2 — Formatação quebrada nas projeções do Home Office Report
- **Onde:** Caixa "Home Office Cost Report"
- **Problema:** "Monthly projection: R$ 32.37++" e "Annual projection: ++R$ 630.79" — o `++` aparece em posições inconsistentes
- **Correção:** Remover o `++`; usar formatação `≈ R$ X` ou `R$ X / mês` se for estimativa

### B3 — Labels de valor ausentes no gráfico Home Office Cost
- **Onde:** Topo das barras no gráfico "Home Office Cost — last 30 days"
- **Problema:** Aparece "R$-" ao invés do valor numérico — string de formatação não está recebendo o número
- **Correção:** Verificar o `text=` ou `hovertemplate` do Plotly; garantir que o valor não é `None` antes de formatar

---

## KPIs Ausentes

### K1 — Autossuficiência Solar
- **Cálculo:** `Solar Generation / Total Consumption = 481 / 1036 = 46%`
- **Por que adicionar:** É a métrica principal de qualquer instalação solar — recrutador e usuário esperam ver isso
- **Onde colocar:** 5º card na linha de KPIs, ou substituir "Home Office Cost" por um card mais relevante e mover home office para o relatório abaixo

### K2 — Economia Gerada pelo Solar em R$
- **Cálculo:** `kWh solar × tarifa média`
- **Por que adicionar:** Conecta a geração solar ao impacto financeiro real

### K3 — Custo Líquido da Rede
- **Cálculo:** `Total Cost − Economia Solar`
- **Por que adicionar:** O usuário quer saber o que realmente pagou à Enel, não o custo bruto

---

## Gráfico: Consumption by Device

### D1 — Tesla Model 3 distorce a escala
- **Problema:** ~600 kWh do Tesla (~58% do total) comprime todos os outros dispositivos a barras ilegíveis
- **Opções:**
  - Separar EV em card/seção própria "EV Charging" e excluir do bar chart
  - Adicionar anotação "Tesla = 58% do consumo total" e usar escala relativa para os demais
  - Escala logarítmica (menos intuitiva, mas resolve o espaço)

### D2 — Sem percentual nas barras
- **Problema:** Não é possível comparar proporções sem cálculo manual
- **Correção:** Adicionar `% do total` como label ou tooltip em cada barra

---

## Gráfico: Solar vs Consumption

### S1 — Unidade do eixo Y incorreta
- **Problema:** Label diz `kWh` mas o gráfico mostra média horária por 30 dias — unidade correta é `kW` (potência média)
- **Correção:** Alterar o label do eixo Y para `kW (média)`; ajustar o título se necessário

### S2 — Excedente solar não está destacado
- **Problema:** Quando solar > consumo há crédito injetado na rede — a área de excedente está invisível no gráfico atual
- **Correção:** Adicionar área destacada (ex: verde claro) para as horas onde `solar > consumption`; legendar como "Excedente → rede"

---

## Gráfico: Enel SP Tariffs

### T1 — Labels sobrepostos em todas as barras
- **Problema:** R$0.538, R$0.656, R$0.987 aparecem em cada barra individualmente gerando poluição visual
- **Correção:** Mostrar label apenas na primeira barra de cada faixa de preço; ou remover labels das barras e usar tooltips

### T2 — Hora atual não está marcada
- **Problema:** O usuário não sabe se está em horário de pico agora
- **Correção:** Adicionar linha vertical `shape` no Plotly indicando a hora atual com label "Agora"

---

## Gráfico: Home Office Cost

### H1 — Eixo Y mal calibrado
- **Problema:** Escala vai até 30 mas os dados parecem na faixa 0-25, comprimindo o gráfico desnecessariamente
- **Correção:** Usar `range=[0, max_value * 1.15]` para dar respiro sem desperdiçar espaço

---

## UX / Layout

### U1 — Sem seletor de período
- **Problema:** "Last 30 days" está fixo — usuário não consegue explorar 7d, mês atual, comparativo
- **Correção:** Adicionar `st.selectbox` ou `st.radio` com opções "7 dias / 30 dias / Mês atual"

### U2 — Layout desconexo entre tarifas e consumo
- **Problema:** "Solar vs Consumption" (top-right) e "Enel SP Tariffs" (bottom-left) são complementares mas estão em lados opostos
- **Sugestão:** Colocar os dois gráficos relacionados ao tempo (solar e tarifas) na mesma coluna ou em seção dedicada "Análise Temporal"

### U3 — Nenhum insight acionável visível
- **Problema:** O usuário vê os dados mas não tem uma recomendação clara ("melhor hora para carregar o EV hoje")
- **Sugestão:** Adicionar card de "Insight do dia" gerado pelo agente, conectando tarifa atual + previsão solar + dispositivos agendáveis

---

## Priorização

| # | ID | Item | Esforço | Impacto |
|---|---|---|---|---|
| 1 | B1 | Inconsistência R$ 57.34 vs R$ 52.57 | Baixo | Alto |
| 2 | K1 | KPI de Autossuficiência Solar (46%) | Baixo | Alto |
| 3 | B2 | Formatação "++" nas projeções | Baixo | Médio |
| 4 | B3 | Labels "R$-" no gráfico home office | Baixo | Médio |
| 5 | T2 | Linha "Agora" no gráfico de tarifas | Baixo | Médio |
| 6 | S1 | Corrigir unidade Y-axis: kWh → kW | Baixo | Baixo |
| 7 | D1 | Separar Tesla do bar chart de dispositivos | Médio | Alto |
| 8 | S2 | Destacar excedente solar no gráfico de área | Médio | Alto |
| 9 | K2, K3 | KPIs de economia solar e custo líquido | Médio | Alto |
| 10 | T1 | Limpar labels sobrepostos nas tarifas | Baixo | Médio |
| 11 | U1 | Seletor de período (7d / 30d) | Médio | Médio |
| 12 | U3 | Card de "Insight do dia" | Alto | Alto |
