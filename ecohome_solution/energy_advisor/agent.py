from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from loguru import logger

from .config import Settings
from .logging import configure_logging
from .prompts import SYSTEM_INSTRUCTIONS
from .tools import TOOL_KIT


class EnergyAdvisorAgent:
    """
    LangGraph ReAct agent wrapped in a clean, portfolio-ready interface.

    Usage:
        agent = EnergyAdvisorAgent()
        result = agent.invoke("When should I charge my EV?")
        print(result["messages"][-1].content)
    """

    def __init__(
        self,
        instructions: str = SYSTEM_INSTRUCTIONS,
        settings: Settings | None = None,
        model: str | None = None,
    ) -> None:
        # Load .env from repo root or ecohome_solution/
        try:
            from dotenv import load_dotenv  # type: ignore
            for candidate in (".env", os.path.join("..", ".env")):
                if os.path.exists(candidate):
                    load_dotenv(candidate)
                    break
        except ImportError:
            pass

        self.settings = settings or Settings()
        configure_logging(self.settings.log_level)
        self._configure_langsmith()

        selected_model = model or self.settings.selected_model()
        api_key = self.settings.selected_api_key()
        if not api_key:
            raise ValueError(
                "No API key found. Set OPENAI_API_KEY, VOCAREUM_API_KEY, "
                "or ENERGY_ADVISOR_API_KEY in your .env file."
            )

        logger.info(
            "Initialising EnergyAdvisorAgent | model={} preset={}",
            selected_model,
            self.settings.model_preset,
        )

        llm = ChatOpenAI(
            model=selected_model,
            temperature=self.settings.temperature,
            base_url=self.settings.base_url,
            api_key=api_key,
        )

        self.graph = create_react_agent(
            model=llm,
            tools=TOOL_KIT,
            prompt=SystemMessage(content=instructions),
        )

    def invoke(self, question: str, context: str | None = None) -> dict[str, Any]:
        """Run the agent on a natural-language question.

        Args:
            question: The user's question.
            context: Optional extra context injected as a system message.

        Returns:
            The LangGraph state dict. Final answer is in result["messages"][-1].content.
        """
        messages = []
        if context:
            messages.append(("system", context))
        messages.append(("user", question))
        return self.graph.invoke({"messages": messages})

    def get_agent_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return [t.name for t in TOOL_KIT]

    def _configure_langsmith(self) -> None:
        """Set LangSmith environment variables from settings if present."""
        if self.settings.langchain_api_key:
            os.environ.setdefault("LANGCHAIN_API_KEY", self.settings.langchain_api_key)
        if self.settings.langchain_tracing_v2:
            os.environ.setdefault("LANGCHAIN_TRACING_V2", self.settings.langchain_tracing_v2)
        if self.settings.langchain_project:
            os.environ.setdefault("LANGCHAIN_PROJECT", self.settings.langchain_project)
        if self.settings.langchain_endpoint:
            os.environ.setdefault("LANGCHAIN_ENDPOINT", self.settings.langchain_endpoint)
