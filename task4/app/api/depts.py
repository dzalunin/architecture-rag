from typing import Dict
from fastapi import Request



def get_rag_container(request: Request) -> Dict:
    """
    Зависимость, возвращающая контейнер RAG.
    """
    return request.app.state.rag
