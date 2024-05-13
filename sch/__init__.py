#!/usr/bin/env python3
from importlib import import_module
from typing import Any, Set, Optional

from sch.commands import bookmark, command, Command, CommandNotFoundError
from sch.errors import CodexNotFound
from sch.server import CodexServer
from sch.utils import format_doc, query_args, escape_args, load_commands


class Codex(Command):
    """Root Codex

    This is the root Node in the Scholar Command tree, and is instantiated to be
    used as a reference point for composing Commands.

    Currently all composition is done against a single Codex instance defined
    below.

    Args:
        name: str. Name of the Codex.
    """

    def __init__(self, name: str) -> None:
        def codex_func(*args: str) -> str:
            """scholar search engine"""

            return "/sch"

        super().__init__(command_func=codex_func, name=name)

    @staticmethod
    def load(path: str) -> None:
        """Load codexes from a given path.

        This will import the python module located at the path provided,
        which will compose the main Codex interface by executing all mapped files.

        This can be called as many times as desired prior to actually loading the
        Flask implementation via load_app.

        It then creates a CodexServer with the fully built Codex, which provides the
        web based implementation via Flask.

        Args:
            root_codex: str. Path to the root codex module to load.
        """

        try:
            # Import the codex and registry.
            module = import_module(path)
        except (FileNotFoundError, ModuleNotFoundError):
            raise CodexNotFound(name=path)

    def create_app(
        self,
        tags: Optional[Set[str]] = None,
        exclude_tags: Optional[Set[str]] = None,
        token: Optional[str] = None,
    ) -> CodexServer:
        """Create a CodexServer from the Codex.

        After loading all commands to the Codex via load, this will create a
        CodexServer, which provides a web implementation via Flask.

        Args:
            tags: Optional[Set[str]]. If provided, the Codex will be filtered such
                that only Commands including these tags will be available in the
                CodexServer.
            exclude_tags: Optional[Set[str]]. If provided, the Codex will be filtered
                such that Commands with these tags will be excluded in the
                CodexServer.
            token: Optional[str]. If provided, this will enable auth and a valid
                sch_token will need to be provided via the sch_login (!) command
                in order to use sch.

        Returns:
            codex_server: CodexServer. Flask WSGI app, with enumerated and filtered
                command Codex.
        """

        return CodexServer(
            codex_cmd=self,
            tags=tags,
            exclude_tags=exclude_tags,
            token=token,
            import_name="sch",
        )


# The root Codex node, which is imported by all other files to compose the Scholar
# Command tree.
codex = Codex(name="sch")
