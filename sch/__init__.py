#!/usr/bin/env python3
from importlib import import_module
from typing import Any, Callable, Set, Optional

from sch.commands import bookmark, command, Command, CommandNotFoundError, search
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
        default_command: Optional[Command]. If provided, this command will be
            run instead of displaying a 404 if no Command can be resolved for
            a given query.
    """

    def __init__(self, name: str, default_command: Optional[Command] = None) -> None:
        self._default_command = default_command

        def root_cmd(*args: str) -> str:
            """scholar search engine"""

            return "/sch"

        super().__init__(command_func=root_cmd, name=name)

    def get_default_command(self) -> Optional[Command]:
        """Retrieve the default Command.

        Returns:
            default_cmd: Optional[Command]. Default command if any.
        """

        return self._default_command

    def set_default_command(self, command: Command, *args: Any, **kwargs: Any) -> None:
        """Set the default Command.

        If a default Command is set, it will be run instead of displaying a 404
        if no Command can be resolved for a given sch query. The default Command
        is like any other Command, except that it is always called with ALL
        arguments provided, including the unresolved Command "name", which is
        instead interpreted as the first argument to the default Command.

        Args:
            command: Command. Default Command to set.
        """

        self._default_command = command

    def default_command(self, *args: Any, **kwargs: Any) -> Callable[..., Command]:
        """Default Command decorator.

        This decorator can be used on any function to turn it into the default
        Command for the codex, ie:

        # Default all not found commands to Google search
        @codex.default_command()
        def default_cmd(*args: str) -> str:
            return f"https://google.com/search?q={query_args(*args)}"

        Returns:
            command_decorator: Callable[..., Command]. Decorator for creating and
                setting the default Command.
        """

        def decorator(func: Callable[..., str]) -> Command:
            command = Command(command_func=func, name="sch", *args, **kwargs)
            self._default_command = command

            return command

        return decorator

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
