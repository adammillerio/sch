#!/usr/bin/env python3
from typing import cast, Optional, Tuple
from urllib.parse import quote_plus

import click
from flask import request
from flask.cli import FlaskGroup, ScriptInfo, pass_script_info

from sch.server import CodexServer

sch = FlaskGroup(
    name="sch",
    help="""\
scholar search engine

A codex to load must be given with the '--app' option,
'FLASK_APP' environment variable, or with a 'wsgi.py' or 'app.py' file
in the current directory.

To run an interactive completion using a codex, refer to the search subcommand.

To run the scholar server for browser search, refer to the run subcommand.
""",
)


@sch.command(
    "search",
    context_settings={"ignore_unknown_options": True},
)
@click.option(
    "--tag", type=str, multiple=True, help="filter tags to supply to sch_tags"
)
@click.argument("command", nargs=-1)
@pass_script_info
def sch_run(
    info: ScriptInfo, command: Tuple[str, ...], tag: Optional[Tuple[str, ...]]
) -> None:
    """run a scholar command via the cli

    Given a scholar command via CLI, this will return the generated redirect URL
    via stdout. This allows for interactive use of sch in the CLI for both testing
    and general use.

    Run sch_tree to get a tree of all defined commands. If the first argument of
    a command is sch_help (or ?), the function's full docstring will be printed.
    If the first argument of a command is sch_tree (or >), a tree of all defined
    commands from that command forward will be printed.

    Example:

    sch yt -> /sch?s=yt -> https://youtube.com

    sch yt test thing -> /sch?s=yt+test+search -> https://www.youtube.com/results?search_query=test+search
    """

    codex_server = cast(CodexServer, info.load_app())

    sch_tags = f'&sch_tags={",".join(tag)}' if tag else ""

    args_str = quote_plus(" ".join(command))

    with codex_server.test_request_context(
        f"/sch?sch_txt=true{sch_tags}&s={args_str}", method="GET"
    ):
        response = codex_server.sch()

        if response.status_code == 200:
            # Display command help.
            click.secho(response.data.decode().strip(), fg="green")
        else:
            click.secho(response.data.decode().strip(), fg="red")


def main() -> None:
    sch.main()


if __name__ == "__main__":
    main()
