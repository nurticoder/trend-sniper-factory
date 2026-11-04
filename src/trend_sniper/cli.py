import argparse
import json
from pathlib import Path

from .core import load_topic
from .queue import approve, enqueue


def main():
    parser = argparse.ArgumentParser(description="Trend Sniper Factory: local control room and rendering tools.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("connect-youtube", help="Connect the owner channel for reviewed releases")
    p.add_argument("--client",type=Path,required=True)
    p.add_argument("--auth-dir",type=Path,default=Path("local-data/youtube"))
    p = sub.add_parser("serve", help="Open the local control-room server")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--db", type=Path, default=None)
    p = sub.add_parser("render")
    p.add_argument("--topic", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("batch")
    p.add_argument("--topics", type=Path, nargs="+", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("approve", help="Attest you watched the video and checked rights/metadata/audience")
    p.add_argument("folder", type=Path)
    p.add_argument("--audience", choices=["made_for_kids", "not_made_for_kids"], required=True)
    p.add_argument("--reviewer", required=True)
    p = sub.add_parser("enqueue", help="Local schedule only; does not upload")
    p.add_argument("folder", type=Path)
    p.add_argument("--at", required=True)
    p.add_argument("--queue", type=Path, default=Path("queue.json"))
    args = parser.parse_args()
    try:
        if args.command == "connect-youtube":
            from .production.publisher import connect
            try:
                print(connect(args.client,args.auth_dir)["name"])
            except ImportError:
                parser.exit(1, 'Install the publisher with pip install -e ".[publish]"\n')
        elif args.command == "serve":
            try:
                import uvicorn
                from .web.app import create_app
            except ImportError:
                parser.exit(1, 'Install the dashboard dependencies: pip install -e ".[web]"\n')
            uvicorn.run(create_app(args.db), host="127.0.0.1", port=args.port)
        elif args.command in {"render", "batch"}:
            from .render import render
            if args.command == "render":
                print(render(load_topic(args.topic), args.out))
            else:
                topics = [load_topic(p) for p in args.topics]
                ids = [t["id"] for t in topics]
                if len(set(ids)) != len(ids):
                    raise ValueError("Batch topic IDs must be unique")
                for topic in topics:
                    print(render(topic, args.out / topic["id"]))
        elif args.command == "approve":
            approve(args.folder, args.audience, args.reviewer)
            print("Review saved for these exact files.")
        else:
            print(json.dumps(enqueue(args.folder, args.at, args.queue), indent=2))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
