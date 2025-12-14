from pydantic import BaseModel


class RAGRequest(BaseModel):
    question: str
    k: int | None = None

class RAGResponse(BaseModel):
    answer: str
