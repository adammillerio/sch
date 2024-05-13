#!/usr/bin/env python3
from sch import codex, load_commands

import example

load_commands(example)


@codex.command(name="hello")
def hello() -> str:
    return "https://github.com/adammillerio/sch"


# Flask Application Factory
# Run with flask --app example_codex run
def create_app():
    return codex.create_app()
