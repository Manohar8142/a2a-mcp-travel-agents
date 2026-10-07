"""CLI:  python -m travel_agents "Plan a trip from Hyderabad to Goa on 2026-11-20 for 3 nights, 2 travelers"

Flags: --provider mock|gemini|groq|openai   --stdio (call tools through a real MCP stdio subprocess)
"""
from __future__ import annotations

import argparse
import asyncio
import json

from dotenv import load_dotenv

from .llm import get_llm
from .system import build_system
from .tools_client import StdioMCPClient

DEFAULT = "Plan a trip from Hyderabad to Goa on 2026-11-20 for 3 nights, 2 travelers, hotel under 100. My name is Asha Rao. Book it."


async def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="A2A + MCP multi-agent travel assistant")
    p.add_argument("request", nargs="?", default=DEFAULT)
    p.add_argument("--provider", default=None, help="mock (default), gemini, groq or openai")
    p.add_argument("--stdio", action="store_true", help="use a real MCP stdio subprocess for tools")
    p.add_argument("--json", action="store_true", help="print the full plan as JSON")
    args = p.parse_args()

    async def go(tools=None):
        orch = build_system(get_llm(args.provider), tools)
        plan = await orch.plan(args.request)
        print("REQUEST:", args.request, "\n")
        print("A2A TRACE:")
        for line in plan.trace:
            print("  " + line)
        print("\nPLAN:\n" + (plan.summary or plan.needs_input or ""))
        if args.json:
            print(json.dumps(plan.__dict__, indent=2, default=str))

    if args.stdio:
        async with StdioMCPClient() as tools:
            print("MCP tools:", await tools.list_tools(), "\n")
            await go(tools)
    else:
        await go()


if __name__ == "__main__":
    asyncio.run(main())
