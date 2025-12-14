from langchain.embeddings.base import Embeddings
from sentence_transformers import SentenceTransformer
from typing import List


# ---------------------------------------------------------
# E5 embeddings с нужными префиксами
# ---------------------------------------------------------
#  Можно заменить на:
# from langchain_huggingface import HuggingFaceEmbeddings
# embeddings = HuggingFaceEmbeddings(
#     model_name="intfloat/multilingual-e5-base",
#     encode_kwargs={
#         "prompt": "passage: ",
#         "batch_size": args.batch_size,
#         "normalize_embeddings": True,
#     },
#     query_encode_kwargs={
#         "prompt": "query: ",
#         "batch_size": args.batch_size,
#         "normalize_embeddings": True,
#     },
#     show_progress=True,
# )
class E5Embeddings(Embeddings):
    """
    SentenceTransformer + корректные префиксы + нормализация.
    """
    def __init__(self, model_name: str, batch_size: int = 16, cache_folder: str = None, show_progress: bool = True):
        self.model = SentenceTransformer(model_name, cache_folder=cache_folder)
        self.batch_size = batch_size
        self.show_progress = show_progress

    def _encode(self, texts: List[str]) -> List[List[float]]:
        emb = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=self.show_progress,
        )
        return [e.tolist() for e in emb]

    def embed_documents(self, texts: List[str]):
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, text: str):
        return self._encode([f"query: {text}"])[0]

    def __call__(self, text: str):
        return self.embed_query(text)
