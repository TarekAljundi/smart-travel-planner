# backend/app/services/agent.py
import json
import structlog
from typing import Type

from pydantic import BaseModel
from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.tools.rag_search import rag_search
from app.tools.classify_destination import classify_destination
from app.tools.live_conditions import live_conditions
from app.services.features import compute_features
from app.models.schemas import (
    RAGQuery,
    ClassifyInput,
    LiveConditionsInput,
    LiveConditionsOutput,
    ToolError,
    ClassifyByNameInput,
)
from prompts.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    SYNTHESIS_PROMPT_TEMPLATE,
    RAG_TOOL_DESCRIPTION,
    CLASSIFY_TOOL_DESCRIPTION,
    WEATHER_TOOL_DESCRIPTION,
)

settings = get_settings()
log = structlog.get_logger()


# ---------------------------------------------------------------------
#  Pydantic tools – each one calls the correct underlying function
# ---------------------------------------------------------------------
class RAGSearchTool(BaseTool):
    name: str = "search_destinations"
    description: str = RAG_TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = RAGQuery

    embedder: object
    session_factory: object

    class Config:
        arbitrary_types_allowed = True

    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, query: str, top_k: int = 3) -> str:
        rag_input = RAGQuery(query=query, top_k=top_k)
        async with self.session_factory() as session:
            results = await rag_search(rag_input, session, self.embedder, top_k=top_k)
        return json.dumps([r.model_dump() for r in results], default=str)


class ClassifyDestinationTool(BaseTool):
    name: str = "classify_destination"
    description: str = CLASSIFY_TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = ClassifyByNameInput

    classifier: object

    class Config:
        arbitrary_types_allowed = True

    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, destination: str) -> str:
        features = await compute_features(destination)
        inp = ClassifyInput(features=features)
        out = await classify_destination(inp, self.classifier)
        return out.model_dump_json()


class GetWeatherTool(BaseTool):
    name: str = "get_weather"
    description: str = WEATHER_TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = LiveConditionsInput

    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, city: str) -> str:
        inp = LiveConditionsInput(city=city)
        result = await live_conditions(inp)
        if isinstance(result, ToolError):
            return f"Error: {result.error} (retryable: {result.retryable})"
        return result.model_dump_json()


# ---------- The main agent function ----------
async def run_agent_and_stream_synthesis(
    query: str,
    classifier,
    embedder,
    session_factory,
):
    cheap_llm = ChatOpenAI(
        model=settings.cheap_model,
        openai_api_key=settings.groq_api_key,
        openai_api_base=settings.groq_api_base,
        temperature=0,
        streaming=False,
    )
    strong_llm = ChatOpenAI(
        model=settings.strong_model,
        openai_api_key=settings.groq_api_key,
        openai_api_base=settings.groq_api_base,
        temperature=0.4,
        streaming=True,
    )

    tools = [
        RAGSearchTool(embedder=embedder, session_factory=session_factory),
        ClassifyDestinationTool(classifier=classifier),
        GetWeatherTool(),
    ]

    agent = create_agent(
        model=cheap_llm,
        tools=tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
    )

    result = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
    messages = result["messages"]

    # Build a map of tool_call_id → result content
    tool_results = {}
    for msg in messages:
        if isinstance(msg, ToolMessage) and getattr(msg, "tool_call_id", None):
            tool_results[msg.tool_call_id] = msg.content

    # Emit events for each tool call, using the correct result
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_output = tool_results.get(tc["id"])
                yield f'data: {{"type": "tool_call", "tool": "{tc["name"]}", "input": {json.dumps(tc["args"])}}}\n\n'
                if tool_output:
                    yield f'data: {{"type": "tool_result", "tool": "{tc["name"]}", "output": {json.dumps(tool_output)}, "status": "success"}}\n\n'

    # Gather context for synthesis (using the same map)
    context = "\n".join(tool_results.values()) if tool_results else ""
    synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(query=query, context=context)

    async for chunk in strong_llm.astream(synthesis_prompt):
        if chunk.content:
            yield f'data: {{"type": "token", "content": "{chunk.content}"}}\n\n'
    yield 'data: [DONE]\n\n'