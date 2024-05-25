#!/usr/bin/env python3
from sch import codex, CodexServer, load_commands, query_args

import example

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
