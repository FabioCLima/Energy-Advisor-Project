"""Evaluation scenarios for the EcoHome Energy Advisor agent.

Each scenario defines a natural-language question, the tools the agent
MUST call to answer correctly (required_tools), and a rubric hint for
the LLM-as-judge.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scenario:
    id: str
    question: str
    required_tools: list[str]
    judge_rubric: str
    tags: list[str] = field(default_factory=list)


ALL_SCENARIOS: list[Scenario] = [
    Scenario(
        id="ev_charging_timing",
        question="Qual o melhor horário para carregar o Tesla Model 3 hoje à noite? Considere tarifa e previsão solar.",
        required_tools=["get_electricity_prices", "get_weather_forecast"],
        judge_rubric=(
            "A resposta deve indicar o horário de off-peak (0h–5h) com a tarifa correta em R$/kWh "
            "e mencionar se há geração solar relevante naquele período."
        ),
        tags=["ev", "pricing", "weather"],
    ),
    Scenario(
        id="home_office_cost_30d",
        question="Quanto gastei com home office nos últimos 30 dias? Quero o total em R$ por dispositivo.",
        required_tools=["query_energy_usage"],
        judge_rubric=(
            "A resposta deve listar custo por dispositivo de home office (PC, Monitor, AC escritório) "
            "com valores em R$ e mencionar projeção mensal ou anual."
        ),
        tags=["home_office", "cost"],
    ),
    Scenario(
        id="solar_generation_monthly",
        question="Quanto meu painel solar de 4kWp gerou no último mês em kWh e em R$ de economia?",
        required_tools=["query_solar_generation"],
        judge_rubric=(
            "A resposta deve incluir total de kWh gerado e economia estimada em R$ "
            "(kWh × tarifa). Deve mencionar o período consultado."
        ),
        tags=["solar", "savings"],
    ),
    Scenario(
        id="current_tariff_period",
        question="Qual a tarifa da Enel SP agora? Estou em horário de ponta?",
        required_tools=["get_electricity_prices"],
        judge_rubric=(
            "A resposta deve informar a tarifa atual em R$/kWh, o período tarifário (off-peak / "
            "mid-peak / peak) e o próximo horário mais barato."
        ),
        tags=["pricing"],
    ),
    Scenario(
        id="savings_ac_shift",
        question="Quanto economizaria por mês se desligasse o ar-condicionado do escritório entre 18h e 20h?",
        required_tools=["calculate_energy_savings", "get_electricity_prices"],
        judge_rubric=(
            "A resposta deve incluir estimativa de economia em kWh e R$ por mês, "
            "com a diferença de tarifa entre o horário de ponta e o alternativo explicitada."
        ),
        tags=["savings", "home_office", "pricing"],
    ),
    Scenario(
        id="energy_tips_ac",
        question="Quais as melhores práticas para reduzir o consumo do ar-condicionado?",
        required_tools=["search_energy_tips"],
        judge_rubric=(
            "A resposta deve citar dicas concretas da base de conhecimento "
            "com referência à fonte (source: <filename>)."
        ),
        tags=["rag", "tips"],
    ),
    Scenario(
        id="recent_summary_24h",
        question="Me dá um resumo do consumo de energia das últimas 24 horas.",
        required_tools=["get_recent_energy_summary"],
        judge_rubric=(
            "A resposta deve incluir total em kWh, custo estimado em R$ "
            "e os dispositivos com maior consumo no período."
        ),
        tags=["summary"],
    ),
    Scenario(
        id="device_consumption_pc",
        question="Quanto o PC do home office consumiu e custou nos últimos 30 dias?",
        required_tools=["query_energy_usage"],
        judge_rubric=(
            "A resposta deve mencionar especificamente o 'PC Home-Office (Ryzen 7)' "
            "com consumo em kWh e custo em R$ para o período."
        ),
        tags=["home_office", "device"],
    ),
    Scenario(
        id="solar_vs_grid_decision",
        question="Vale a pena ligar a lava-louça agora ou esperar a geração solar de hoje à tarde?",
        required_tools=["get_weather_forecast", "get_electricity_prices"],
        judge_rubric=(
            "A resposta deve comparar irradiância solar prevista com a tarifa atual "
            "e dar uma recomendação concreta de horário."
        ),
        tags=["solar", "weather", "scheduling"],
    ),
    Scenario(
        id="annual_solar_savings",
        question="Qual minha economia anual estimada com o painel solar considerando as tarifas da Enel SP?",
        required_tools=["query_solar_generation", "calculate_energy_savings"],
        judge_rubric=(
            "A resposta deve extrapolar a geração mensal para anual e calcular economia "
            "em R$ usando a tarifa média. Deve mencionar pressupostos do cálculo."
        ),
        tags=["solar", "savings", "annual"],
    ),
]

QUICK_SCENARIOS: list[Scenario] = [
    s for s in ALL_SCENARIOS
    if s.id in {"ev_charging_timing", "home_office_cost_30d", "current_tariff_period"}
]
