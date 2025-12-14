from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from app.settings import settings


class RetrievalService:
    """
    Сервис для поиска ближайших документов в FAISS индексе.
    """

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            cache_folder=settings.EMBEDDING_MODELS_CACHE_DIR,
            encode_kwargs={
                "prompt": "passage: ",
                "batch_size": settings.EMBEDDING_BATCH_SIZE,
                "normalize_embeddings": True,
            },
            query_encode_kwargs={
                "prompt": "query: ",
                "batch_size": settings.EMBEDDING_BATCH_SIZE,
                "normalize_embeddings": True,
            },
            show_progress=False,
        )

        self.vectorstore = FAISS.load_local(
            folder_path=settings.VECTORSTORE_DIR,
            embeddings=self.embeddings,
            allow_dangerous_deserialization=True
        )

    def similarity_search(self, query: str, k: int | None = None):
        """
        Возвращает top-k наиболее релевантных документов.
        """
        k = k or settings.SEARCH_TOP_K
        return self.vectorstore.similarity_search(query, k=k)

    def as_retriever(self):
        """Возвращает retriever с top-k поиском."""
        return self.vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": settings.SEARCH_TOP_K, "score_threshold": 0.7}
        )