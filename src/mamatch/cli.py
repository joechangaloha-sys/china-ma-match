"""Command line: `uv run mamatch <command>`."""

import argparse
import logging
from datetime import date, timedelta

from . import db


def cmd_init(args) -> None:
    db.init_db()
    if args.seed:
        from .seed import seed

        with db.session_scope() as s:
            seed(s)
    print("Database ready" + (" with example data" if args.seed else ""))


def cmd_ingest(args) -> None:
    from .ingest import cninfo, profile

    db.init_db()
    end = date.today()
    start = end - timedelta(days=args.days)
    added = 0
    for keyword in args.keyword or cninfo.DEFAULT_KEYWORDS:
        anns = cninfo.search(keyword, start, end, page_size=30, max_pages=args.pages)
        with db.session_scope() as s:
            for ann in anns:
                signal, by = profile.extract(ann)
                if profile.upsert(s, ann, signal, by):
                    added += 1
        print(f"{keyword}: {len(anns)} announcements")
    print(f"{added} new buyer signals indexed")


def cmd_serve(args) -> None:
    import uvicorn

    db.init_db()
    uvicorn.run("mamatch.web.app:app", host=args.host, port=args.port, reload=args.reload)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="mamatch")
    sub = p.add_subparsers(required=True)

    a = sub.add_parser("init-db", help="Create tables")
    a.add_argument("--seed", action="store_true", help="Add fictional example buyers and targets")
    a.set_defaults(func=cmd_init)

    a = sub.add_parser("ingest-cninfo", help="Index acquisition announcements from CNINFO")
    a.add_argument("--days", type=int, default=90)
    a.add_argument("--pages", type=int, default=2, help="Pages of 30 per keyword")
    a.add_argument("--keyword", action="append", help="Override the default keyword list")
    a.set_defaults(func=cmd_ingest)

    a = sub.add_parser("serve", help="Run the adviser workspace")
    a.add_argument("--host", default="127.0.0.1")
    a.add_argument("--port", type=int, default=8600)
    a.add_argument("--reload", action="store_true")
    a.set_defaults(func=cmd_serve)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
