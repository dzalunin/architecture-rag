from typing import Dict
from fastapi import APIRouter, Depends
from app.logging import logger
from app.api.models import RAGRequest, RAGResponse
from app.api.depts import get_rag_container
from app.rag.safety import PromptInjectionError

router = APIRouter()


@router.get("/healthcheck")
async def healthcheck():
    logger.debug('Call healthcheck')
    return {"status": "OK"}


@router.post("/ask")
async def ask(
    request: RAGRequest,
    rag: Dict = Depends(get_rag_container)
):

    try:
        agent = rag.get('agent')
        retriever = rag.get('retriever')

        query = {
                "messages": [
                    {"role": "user", "content": request.question}
                ],
                "retriever": retriever
                }

        # event = agent.invoke(query)
        answer = []
        for event in agent.stream(
            query,
            stream_mode="values",
        ):
            chunk = event["messages"][-1]
            # Вывод отладочной информации
            chunk.pretty_print()

            answer.append(chunk.text)

        return RAGResponse(answer="\n\n".join(answer))
    except PromptInjectionError as pe:
        return RAGResponse(answer=str(pe))
    except Exception as e:
        raise e
