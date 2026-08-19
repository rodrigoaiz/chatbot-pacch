from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import uvicorn

from chatbot_pacch.config import get_settings
from chatbot_pacch.database import Database
from chatbot_pacch.ingest import run_ingestion
from chatbot_pacch.evaluation import evaluate_retrieval
from chatbot_pacch.ollama import OllamaClient, OllamaError
from chatbot_pacch.rag.answer import build_messages
from chatbot_pacch.rag.embeddings import embed_pending_chunks
from chatbot_pacch.rag.retrieval import HybridRetriever, has_sufficient_evidence
from chatbot_pacch.portal.crawler import PortalClient
from chatbot_pacch.portal.discovery import parse_catalog


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatbot-pacch")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest", help="Indexa recursos del portal")
    ingest.add_argument("--subject", help="Slug de la asignatura")
    ingest.add_argument("--all", action="store_true", help="Indexa todo el catalogo")
    ingest.add_argument("--limit", type=int, help="Limite de paginas")

    embed = subcommands.add_parser("embed", help="Genera embeddings pendientes")
    embed.add_argument("--limit", type=int, help="Limite de fragmentos")
    embed.add_argument("--batch-size", type=int, default=8)

    sync = subcommands.add_parser(
        "sync", help="Actualiza paginas y genera sus embeddings"
    )
    sync.add_argument("--subject", help="Slug de la asignatura")
    sync.add_argument("--all", action="store_true", help="Indexa todo el catalogo")
    sync.add_argument("--limit", type=int, help="Limite de paginas")
    sync.add_argument("--batch-size", type=int, default=8)

    search = subcommands.add_parser("search", help="Prueba la busqueda hibrida")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=4)

    ask = subcommands.add_parser("ask", help="Prueba una respuesta RAG")
    ask.add_argument("question")

    evaluate = subcommands.add_parser("evaluate", help="Evalua la recuperacion")
    evaluate.add_argument(
        "--dataset", default="evaluation/historia_universal_1.json"
    )

    subcommands.add_parser("status", help="Muestra el estado local")
    subcommands.add_parser("subjects", help="Lista las materias disponibles")
    subcommands.add_parser("serve", help="Inicia el servidor web local")
    return parser


async def _status() -> int:
    settings = get_settings()
    database = Database(settings.database_path)
    database.initialize()
    result: dict[str, object] = {"database": database.corpus_stats()}
    try:
        result["ollama"] = await OllamaClient(settings.ollama_base_url).health()
    except OllamaError as exc:
        result["ollama"] = {"error": str(exc)}
    result["required_models"] = {
        "chat": settings.ollama_chat_model,
        "embedding": settings.ollama_embedding_model,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


async def _subjects() -> int:
    settings = get_settings()
    async with PortalClient(
        settings.portal_base_url,
        settings.user_agent,
        settings.request_delay_seconds,
        settings.request_timeout_seconds,
    ) as client:
        html = await client.get_text(
            f"{settings.portal_base_url}/objetos-de-aprendizaje"
        )
    objects = parse_catalog(html, settings.portal_base_url)
    counts = Counter((item.subject_slug, item.subject) for item in objects)
    print(f"{len(objects)} objetos de aprendizaje en {len(counts)} asignaturas\n")
    for (slug, name), count in counts.items():
        print(f"{name} ({count})\n  {slug}")
    return 0


async def _ingest(args: argparse.Namespace) -> int:
    settings = get_settings()
    stats = await run_ingestion(
        settings,
        subject=args.subject,
        index_all_objects=True if args.all else None,
        max_pages=args.limit,
    )
    print(json.dumps(asdict(stats), indent=2, ensure_ascii=False))
    return 1 if stats.failed else 0


async def _embed(args: argparse.Namespace) -> int:
    stats = await embed_pending_chunks(
        get_settings(), limit=args.limit, batch_size=max(1, args.batch_size)
    )
    print(json.dumps(asdict(stats), indent=2, ensure_ascii=False))
    return 0


async def _sync(args: argparse.Namespace) -> int:
    settings = get_settings()
    ingestion = await run_ingestion(
        settings,
        subject=args.subject,
        index_all_objects=True if args.all else None,
        max_pages=args.limit,
    )
    embeddings = await embed_pending_chunks(
        settings, batch_size=max(1, args.batch_size)
    )
    print(
        json.dumps(
            {
                "ingestion": asdict(ingestion),
                "embeddings": asdict(embeddings),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 1 if ingestion.failed else 0


async def _search(query: str, limit: int) -> int:
    settings = get_settings()
    database = Database(settings.database_path)
    results = await HybridRetriever(settings, database).search(query, limit)
    print(
        json.dumps(
            [asdict(result) for result in results], indent=2, ensure_ascii=False
        )
    )
    return 0


async def _ask(question: str) -> int:
    settings = get_settings()
    database = Database(settings.database_path)
    results = await HybridRetriever(settings, database).search(question, 3)
    if not has_sufficient_evidence(results):
        print("No encontre informacion suficiente en los recursos indexados.")
        return 1
    ollama = OllamaClient(settings.ollama_base_url)
    async for token in ollama.chat_stream(
        settings.ollama_chat_model, build_messages(question, results)
    ):
        print(token, end="", flush=True)
    print()
    print("\nFuentes:")
    for url in dict.fromkeys(result.url for result in results):
        print(f"- {url}")
    return 0


async def _evaluate(dataset: str) -> int:
    summary = await evaluate_retrieval(get_settings(), Path(dataset))
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    return 0 if not summary.failures else 1


def main() -> int:
    args = _parser().parse_args()
    if args.command == "status":
        return asyncio.run(_status())
    if args.command == "subjects":
        return asyncio.run(_subjects())
    if args.command == "ingest":
        return asyncio.run(_ingest(args))
    if args.command == "embed":
        return asyncio.run(_embed(args))
    if args.command == "sync":
        return asyncio.run(_sync(args))
    if args.command == "search":
        return asyncio.run(_search(args.query, args.limit))
    if args.command == "ask":
        return asyncio.run(_ask(args.question))
    if args.command == "evaluate":
        return asyncio.run(_evaluate(args.dataset))
    if args.command == "serve":
        settings = get_settings()
        if settings.app_host != "127.0.0.1":
            raise SystemExit("APP_HOST debe permanecer en 127.0.0.1 para el MVP local")
        uvicorn.run(
            "chatbot_pacch.main:app",
            host=settings.app_host,
            port=settings.app_port,
            root_path=settings.root_path,
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
