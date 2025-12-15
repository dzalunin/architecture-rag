import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from embeddings import E5Embeddings


# =================================================================
# Тестовые запросы с повышенным порогом релевантности
# =================================================================
TEST_QUERIES = [
    {
        "query": "хронология генетической войны",
        "topics": ["феррум", "войн", "генетическ", "кракен", "тираксу", "тедди", "ректор", "виндстар", "просперо", "дегрей"],
        "min_matches": 3
    },
    {
        "query": "кто такой дегрей",
        "topics": ["хранител", "рыцар", "совет", "ио", "просперо", "храм", "виндстар"],
        "min_matches": 2
    },
    {
        "query": "классификация синхродвигателей",
        "topics": ["классификац", "синхродвигатель", "скорост", "полет", "межзвёзд", "звездолёт"],
        "min_matches": 3
    },
    {
        "query": "устройство квантового клинка",
        "topics": ["клин", "кибер", "энергия", "эфир", "батарейк", "хранител"],
        "min_matches": 2
    },
    {
        "query": "роль кейла виндстара в битве при телуре",
        "topics": ["телур", "сфер", "виндстар", "аннигиляц", "x-staffel"],
        "min_matches": 2
    },
]


def is_relevant_strict(doc: Document, query_info: dict) -> tuple[bool, int, list]:
    text = doc.page_content.lower()
    topics = query_info["topics"]
    min_matches = query_info.get("min_matches", 2)

    found = []
    matches = 0
    for topic in topics:
        if re.search(r'\b' + topic + r'\w*', text):
            matches += 1
            found.append(topic)

    return matches >= min_matches, matches, found


def evaluate_index(index_path: Path, k: int = 5) -> Dict[str, Any]:
    info_path = index_path / "index_info.json"
    index_info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}

    embeddings = E5Embeddings(model_name=index_info.get("model", "intfloat/multilingual-e5-base"))
    vectorstore = FAISS.load_local(str(index_path), embeddings, allow_dangerous_deserialization=True)
    retriever = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": k, "score_threshold": 0.7}
    )

    print(f"ОЦЕНКА RAG-ИНДЕКСА")
    print(f"Папка: {index_path.name}")
    print(f"Модель: {index_info.get('model', '?')}")
    print(f"Чанков: {index_info.get('total_chunks', '?')}")
    print(f"Оцениваем по top-{k} документам\n{'='*80}")

    results = []
    for item in TEST_QUERIES:
        docs: List[Document] = retriever.invoke(item["query"])
        relevances = []
        analyses = []

        for i, doc in enumerate(docs):
            relevant, matches, found = is_relevant_strict(doc, item)
            relevances.append(1 if relevant else 0)
            analyses.append(
                {
                    "rank": i + 1,
                    "relevant": relevant,
                    "matches": matches,
                    "found": found,
                    "source": doc.metadata.get("source_path", "unknown"),
                    "page_content": doc.page_content.replace('\n', ' ')
                }
            )

        print(f"Запрос: {item['query']}")
        print(f"  Требуется совпадений: {item['min_matches']} из {len(item['topics'])}")

        for a in analyses:
            status = "RELEVANT" if a["relevant"] else "NOT RELEVANT"
            print(f"   {status} #{a['rank']} → {a['source']}")
            if a["found"]:
                print(f"       Совпадения: {', '.join(a['found'])}")
        print()

        results.append({
            "query": item["query"],
            "relevant_found": sum(relevances),
            "analysis": analyses
        })

    print("=" * 80)
    print("ИТОГОВАЯ ОЦЕНКА")
    print("=" * 80)

    return {
        "details": results,
        "config": {"k": k, "total_queries": len(TEST_QUERIES)}
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--json", type=Path, help="Сохранить отчёт")
    args = parser.parse_args()

    report = evaluate_index(args.index, args.k)

    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nОтчёт сохранён → {args.json}")