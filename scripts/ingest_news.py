"""
News ingestion runner.

Pulls current-events news (GDELT) for the configured languages, enriches each
article with the chat model (level-graded summary, discussion prompts, vocab,
grammar tags, optional embedding) and writes the results to the RTI store
(local JSON file or a Fabric Eventhouse, per ``RTI_BACKEND``).

Usage:
    python scripts/ingest_news.py                      # all configured languages
    python scripts/ingest_news.py --languages es fr    # specific languages
    python scripts/ingest_news.py --level A2           # grade for a CEFR level
    python scripts/ingest_news.py --source sample      # offline fixture (no network)

Reads configuration from backend/.env (RTI_BACKEND, NEWS_LANGUAGES, GDELT_*,
AZURE_OPENAI_* / AZURE_OPENAI_EMBEDDING_DEPLOYMENT).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from app.repository import eventhouse  # noqa: E402
from app.services import news_ingestion  # noqa: E402


async def _run(args: argparse.Namespace) -> None:
    health = await eventhouse.ensure_ready()
    print(f"RTI store: {json.dumps(health, ensure_ascii=False)}")

    result = await news_ingestion.ingest_all(
        languages=args.languages,
        level=args.level,
        source=args.source,
        count=args.count,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.source == "gdelt" and result.get("fetched", 0) == 0:
        print(
            "\nNo articles fetched. GDELT's free API rate-limits by IP "
            "(1 request / 5s) and penalizes bursts with an extended cooldown.\n"
            "  • Wait ~15-30 minutes, then retry, or\n"
            "  • Generate fresh articles instantly (no network):\n"
            "        python scripts/ingest_news.py --source synthetic",
            file=sys.stderr,
        )
    elif args.source in ("sample",) and result.get("new", 0) == 0 and result.get("fetched", 0):
        print(
            "\nAll fetched articles were already stored (deduped by URL), so "
            "nothing new was ingested.\n"
            "  • To add fresh, unique articles every run, use:\n"
            "        python scripts/ingest_news.py --source synthetic",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest current-events news into the RTI store")
    parser.add_argument("--languages", nargs="*", default=None, help="Language codes (en/fr/es)")
    parser.add_argument("--level", default=None, help="CEFR level to grade for (A1..C2)")
    parser.add_argument(
        "--source",
        choices=["gdelt", "synthetic", "sample"],
        default="gdelt",
        help=(
            "News source: 'gdelt' (live, rate-limited), 'synthetic' (fresh "
            "generated articles every run — no network, always ingests), or "
            "'sample' (fixed offline fixture)"
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Articles per language for the synthetic source (default 8)",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
