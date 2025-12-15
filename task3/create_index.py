import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
import logging

from tqdm import tqdm
from embeddings import E5Embeddings

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Метаданные
# ---------------------------------------------------------

def load_metadata(meta_path: str) -> Dict[str, Dict[str, Any]]:
    """path → metadata (без самого path)"""
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metadata_map = {}
    for item in data:
        path = item["path"]
        metadata = {k: v for k, v in item.items() if k != "path"}
        metadata_map[path] = metadata

    return metadata_map


# ---------------------------------------------------------
# Загрузка markdown
# ---------------------------------------------------------

def load_markdown_documents(src_dir: str) -> List[Document]:
    docs = []
    src = Path(src_dir)

    md_files = list(src.rglob("*.md"))
    logger.info(f"Найдено {len(md_files)} markdown файлов")

    for file in md_files:
        try:
            text = file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Ошибка чтения {file}: {e}")
            continue

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": str(file),
                    "source_path": str(file.relative_to(src)).replace("\\", "/"),
                },
            )
        )

    logger.info(f"Загружено {len(docs)} markdown-файлов (custom loader)")
    return docs


# ---------------------------------------------------------
# Сплиттер
# ---------------------------------------------------------

def split_with_headers_and_chunks(
    documents: List[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> List[Document]:

    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
        ("#####", "Header 5"),
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )

    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True,
    )

    chunks = []
    for doc in tqdm(documents, desc="Разбиение документов"):
        header_splits = markdown_splitter.split_text(doc.page_content)

        for split in header_splits:
            split.page_content = " ".join(split.page_content.split())
            split.metadata = {**doc.metadata, **split.metadata}

        final_chunks = recursive_splitter.split_documents(header_splits)
        chunks.extend(final_chunks)

    logger.info(f"Создано {len(chunks)} финальных чанков")
    return chunks


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Создание FAISS индекса")
    parser.add_argument("--src", required=True, help="Папка с .md файлами")
    parser.add_argument("--out", required=True, help="Папка для индекса")
    parser.add_argument("--cache", type=str, help="Папка для локального кэша", default="./cache/models")
    parser.add_argument("--chunk_size", type=int, default=512)
    parser.add_argument("--chunk_overlap", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=16)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Документы
    logger.info("Загрузка Markdown...")
    docs = load_markdown_documents(args.src)
    
    # 2. Сплит
    logger.info("Разбиение...")
    chunks = split_with_headers_and_chunks(
        docs,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    # 3. Эмбеддинги
    embeddings = E5Embeddings(
        model_name="intfloat/multilingual-e5-base",
        batch_size=args.batch_size,
        cache_folder=args.cache,
    )

    # 4. Создание индекса
    logger.info("Создание FAISS индекса...")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # 5. Сохранение
    logger.info("Сохранение индекса...")
    vectorstore.save_local(str(out_path))

    info = {
        "model": "intfloat/multilingual-e5-base",
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "total_documents": len(docs),
        "total_chunks": len(chunks)
    }

    with open(out_path / "index_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    logger.info("Готово! Индекс успешно создан.")


if __name__ == "__main__":
    main()
