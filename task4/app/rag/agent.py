import time
from contextlib import asynccontextmanager
from typing import Any
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import dynamic_prompt, ModelRequest
from langchain_ollama import ChatOllama
from app.logging import logger
from app.rag.retrieval import RetrievalService
from app.rag.llm import OllamaClient
from app.settings import settings
from fastapi import FastAPI
from app.rag.safety import (
    strip_system_directives,
    SYSTEM_SAFETY
)


FEW_SHOT_EXAMPLES = """
Q: Приведи определение квантомета.
A:
1) Ответ: Это стреляющее энергетическими зарядами оружие.
2) Источники: [1] Квантомет.md

Q: Кто такой Чукчукка?
A:
1) Ответ: Это вуки, друг Декса Старрана 
2) Источники: [1] Чукчукка.md [2] Декс_Старран.md
"""

SYSTEM_PROMPT = (
    "Ты — ассистент по внутренней базе знаний компании. Отвечай строго на русском языке."
    f"{'\n\n' + SYSTEM_SAFETY + '\n\n' if settings.SAVE_MODE else ''}"
    "Отвечай только на основании предоставленного контекста и few-shot примеров."
    "Если контекст пуст - ответь «Я не знаю». Не выдумывай того, чего нет в контексте."
    "Всегда сначала выполняй скрытое размышление (Chain-of-Thought), но не раскрывай его."
    "Формат ответа:"
    "1) Краткие шаги (до 3 пунктов) со ссылками на фрагменты [номер]."
    "2) Итоговый ответ."
    "3) Источники: номера фрагментов, имена файлов из контекста"
)


@dynamic_prompt
def rag_prompt(request: ModelRequest) -> str:
    """
    Dynamic prompt RAG:
    - извлекает последние сообщения
    - делает поиск по FAISS
    """
    last_query  = request.state["messages"][-1].text      

    if settings.SAVE_MODE:
        try:
            last_query = strip_system_directives(last_query)
        except Exception as e:
            raise e

    retriever = request.state["retriever"]
    retrieved_docs = retriever.invoke(last_query)

    docs_content = "\n".join(
        f"[{i+1}] {doc.page_content}"
        f"Источник: {doc.metadata.get('source')}"
        f"Заголовок: {doc.metadata.get('canonical')}"
        for i, doc in enumerate(retrieved_docs)
    ) if retrieved_docs else 'Контекст пуст'
    print(f"Найдено документов {len(retrieved_docs)}")

    prompt = f"""
    {SYSTEM_PROMPT}
    Это контекст из базы знаний:
    {docs_content}
    Few-shot примеры:
    {FEW_SHOT_EXAMPLES}
    Теперь ответь на вопрос пользователя в соответствии с системными правилами.
    Вопрос: {last_query}
    """
    return prompt

class RAGState(AgentState):
    retriever: RetrievalService

@asynccontextmanager
async def agent_lifespan(app: FastAPI):
    """
    Инициализация RAG агента + загрузка моделей + логирование.
    """

    start = time.time()
    logger.info("rag_agent.init_start")

    # FAISS retriever
    retrieval = RetrievalService()

    # Ollama
    ollama_client = OllamaClient()
    await ollama_client.pull_model()

    model = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0.1
    )

    agent = create_agent(
        model=model,
        tools=[],
        debug=True,
        middleware=[rag_prompt],
        state_schema=RAGState
    )

    app.state.rag = {
        "agent": agent,
        "retriever": retrieval.as_retriever(),
    }

    logger.info("rag_agent.init_ok", elapsed=f"{time.time() - start:.3f}s")

    try:
        yield
    finally:
        logger.info("rag_agent.shutdown")
