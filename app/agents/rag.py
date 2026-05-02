from __future__ import annotations
import json
import uuid
from typing import AsyncIterator, Callable, Awaitable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.prompts.prompt import RAG_CONTEXT_TEMPLATE, SYSTEM_PROMPT
from app.knowledge_base.retriever import HybridRetriever
from app.tools.tools import CalculatorTool, WebSearchTool

settings = get_settings()


class RAGAgent:
    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever
        self._tools     = [WebSearchTool(), CalculatorTool()]
        self._tool_map  = {t.name: t for t in self._tools}

        _base = dict(
            model=settings.openai_model,
            openai_api_key=settings.openai_api_key,
            temperature=0.4,
            streaming=True,
        )
        self._llm = ChatOpenAI(**_base).bind_tools(self._tools)

        self._sessions: dict[str, list] = {}

    async def generate_answer_stream(
        self,
        session_id: str,
        user_message: str,
        on_tool_use: Callable[[str, dict], Awaitable[None]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream response tokens.
        The LLM decides whether to call tools — no keyword matching.
        on_tool_use: async callback fired when tools or Knowledge Base are used.
        """
        if user_message.strip() == "__clear__":
            self._sessions.pop(session_id, None)
            return

        history  = self._sessions.setdefault(session_id, [])
        
        # ── Knowledge Base Retrieval ──────────────────────────────────────
        human_content = user_message
        if self._retriever.contains_records:
            hits = self._retriever.find_relevant_context(user_message)
            if hits:
                if on_tool_use:
                    await on_tool_use("use_knowledge_base", {"source": "Scanning Knowledge Base..."})
                context = "\n\n---\n\n".join(
                    f"[{h['metadata'].get('filename', 'doc')}, "
                    f"page {h['metadata'].get('page_number', '?')}]\n{h['content']}"
                    for h in hits
                )
                human_content = RAG_CONTEXT_TEMPLATE.format(context=context, question=user_message)

        messages = [SystemMessage(content=SYSTEM_PROMPT)] + history + [HumanMessage(content=human_content)]

        text_chunks: list[str] = []
        tool_acc: dict[int, dict] = {}

        async for chunk in self._llm.astream(messages):
            if chunk.content:
                text_chunks.append(chunk.content)
                yield chunk.content

            if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                for tc in chunk.tool_call_chunks:
                    idx = tc.get("index", 0)
                    if idx not in tool_acc:
                        tool_acc[idx] = {
                            "id":   tc.get("id", str(uuid.uuid4())),
                            "name": tc.get("name", ""),
                            "args": "",
                        }
                    if tc.get("name"): tool_acc[idx]["name"] = tc["name"]
                    if tc.get("args"): tool_acc[idx]["args"] += tc["args"]

        if not tool_acc:
            self._commit_to_memory(session_id, history, user_message, "".join(text_chunks))
            return

        resolved = []
        for tc in tool_acc.values():
            try:
                args = json.loads(tc["args"]) if tc["args"].strip() else {}
            except json.JSONDecodeError:
                args = {"query": tc["args"]}
            resolved.append({
                "id":   tc["id"],
                "name": tc["name"],
                "args": args,
                "type": "tool_call",
            })

        if on_tool_use:
            for r in resolved:
                if r["name"] == "web_search":
                    await on_tool_use("search_web", {"query": r["args"].get("query", "")})
                elif r["name"] == "calculator":
                    await on_tool_use("use_calculator", {"expression": r["args"].get("expression", "")})

        # ── Execute tools ─────────────────────────────────────────────────
        ai_msg    = AIMessage(content="", tool_calls=resolved)
        tool_msgs = await self._execute_plugins(resolved)
        messages2 = messages + [ai_msg] + tool_msgs

        final: list[str] = []
        async for chunk in self._llm.astream(messages2):
            if chunk.content:
                final.append(chunk.content)
                yield chunk.content

        self._commit_to_memory(session_id, history, user_message, "".join(final))

    def wipe_history(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _construct_user_prompt(self, query: str) -> HumanMessage:
        """Inject RAG context if documents exist and retrieval finds hits."""
        if not self._retriever.contains_records:
            return HumanMessage(content=query)
        hits = self._retriever.find_relevant_context(query)
        if not hits:
            return HumanMessage(content=query)
        context = "\n\n---\n\n".join(
            f"[{h['metadata'].get('filename', 'doc')}, "
            f"page {h['metadata'].get('page_number', '?')}]\n{h['content']}"
            for h in hits
        )
        return HumanMessage(
            content=RAG_CONTEXT_TEMPLATE.format(context=context, question=query)
        )

    async def _execute_plugins(self, calls: list[dict]) -> list[ToolMessage]:
        import asyncio

        async def _one(tc: dict) -> ToolMessage:
            tool = self._tool_map.get(tc["name"])
            try:
                result = await tool.arun(tc["args"]) if tool else f"Unknown tool: {tc['name']}"
            except Exception as e:
                result = f"Tool error: {e}"
            return ToolMessage(content=str(result), tool_call_id=tc["id"])

        return list(await asyncio.gather(*[_one(tc) for tc in calls]))

    def _commit_to_memory(self, session_id: str, history: list, user_msg: str, ai_content: str) -> None:
        self._sessions[session_id] = (
            history
            + [HumanMessage(content=user_msg)]
            + [AIMessage(content=ai_content)]
        )