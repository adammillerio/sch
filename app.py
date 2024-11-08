#!/usr/bin/env python3
import example
from sch import CodexServer, codex, load_commands, query_args

load_commands(example)


@codex.command(name="hello")
def hello() -> str:
    return "https://github.com/adammillerio/sch"


# Default all not found commands to Google search
@codex.default_command()
def default_cmd(*args: str) -> str:
    return f"https://google.com/search?q={query_args(*args)}"


# Flask Application Factory
# Run with sch run
def create_app() -> CodexServer:
    return codex.create_app()
