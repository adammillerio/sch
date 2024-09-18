#!/usr/bin/env python3
from logging import Logger, getLogger
from uuid import uuid4
from typing import Any, cast, Dict, Set, List, Optional, Tuple

from flask import Flask, redirect, request
from flask.wrappers import Response

from sch.commands import Command, OutputFormat, CommandNotFoundError
from sch.readme import get_sch_help

logger: Logger = getLogger(__name__)


class CodexServer(Flask):
    """Scholar Codex Server

    This is the web server for the Codex. It provides a Flask based WSGI
    implementation for interacting with the Scholar Codex and Command tree. It
    has a single endpoint, /sch, which resolves, executes, and returns HTTP 302
    URL redirects of dynamically generated URLs to the user.

    Additionally, the following "built in" commands are avaialable:
    * sch_tree (>) - Display command tree, provide tag filters with &smn_tags
    * sch_help (?) - Display command help
    * sch_login (!) - Log in with &sch_token (if auth is enabled)
    * sch_logout (&) - Log out (if auth is enabled)

    By default the server provides HTTP redirects and HTML pages. If
    &sch_txt=true is provided as an argument, it will instead serve only plain
    text links and content.

    For more detail on the WSGI implementation and Command resolution, see the
    function docs for Codex.sch and Codex.get_command.

    Args:
        codex_cmd: Command. Root "Codex" command, which contains all mapped
            Commands.
        tags: Optional[Set[str]]. If provided, the codex_cmd will be filtered
            such that only Commands matching these tags are included.
        token: Optional[str]. If provided, this will enable auth and a valid
            sch_token will need to be provided via the sch_login (!) command
            in order to use sch.
        exclude_tags: Optional[Set[str]]. If provided, the Codex will be filtered
            such that Commands with these tags will be excluded in the
            CodexServer.

    Public Attributes:
        disable_sch_help: bool. If True, all sch_help commands will be silently
            ignored.
        disable_sch_tree: bool. If True, all sch_tree commands will be silently
            ignored.
        session_cookies: Dict[str, bool]. Valid sessions, if sch_token based
            auth is enabled.
    """

    def __init__(
        self,
        codex_cmd: Command,
        tags: Optional[Set[str]] = None,
        exclude_tags: Optional[Set[str]] = None,
        token: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.codex = codex_cmd

        if tags or exclude_tags:
            self.codex = self.codex.filter_tree(tags, exclude_tags)

        self.enable_sch_token: bool = token is not None
        self.sch_token = token

        self.add_url_rule("/sch", view_func=self.sch)
        self.add_url_rule("/", view_func=lambda: redirect("/sch?s=sch_tree", code=302))

        self.disable_sch_help = False
        self.disable_sch_tree = False
        self.disable_sch_complete = False

        self.session_cookies: Dict[str, bool] = {}

    def sch(self) -> Response:
        """scholar entrypoint

        This is the main and only HTTP endpoint on scholar currently. It should
        be set in browser configs to be invoked as:
        http://localhost:8432/sch?%s=%s

        Where %s is typically the entire (escaped) contents of a query in a search
        bar. This input will then be used to resolve a command in the codex and
        execute the command with any remaining arguments. The result of the command,
        which is always a string URL, will be issued back to the caller via a
        302 redirect.

        In the event of an error, the following HTTP codes will be provided:
        400 - No command is provided to the /sch call at all
        401 - User is not logged in (if auth is enabled)
        404 - No command could be resolved for the /sch call

        Currently, these errors just print a Codex name for fun.

        There are two additional built-in help commands which instead return an
        HTTP 200 with relevant information as plain text to the user:
        sch_tree - This will print the full command tree along with the first
            line of all command function docstrings. If it is the first argument
            to a command, the tree will be printed scoped to that command and
            it's subcommands.
        sch_help - If the first argument to any command is sch_help, then
            the full contents of the command function docstring will be returned.

        In the event of an exception during command execution, the user will be
        redirected to the sch_help page for the Command, displaying relevant
        information about the error.

        Otherwise, this is a normal flask request, so all request handling at the
        Codex or Command level can be through normal flask methods.

        Returns:
            response: Response. HTTP Response for request.
        """

        # /sch?s=gh - Go to GitHub homepage
        # /sch?s=gh+adammillerio/sch - View a GitHub repo
        # /sch?s=gh+search+adammillerio/sch+search+query - Search a GitHub repo
        # /sch?s=gh+search+all+search+query - Search all of GitHub
        logger.info(f"GET {request.url}")
        spell = request.args.get("s", None)
        if not spell:
            # No command provided at all.
            logger.error("ERR no command provided")
            return self.sch_fail("no command provided", 400)

        # ["gh"]
        # ["gh", "adammillerio/sch"]
        # ["gh", "adammillerio/sch", "search", "query"]
        # ["gh", "all", "search", "query"]
        args = spell.split(" ")

        if request.args.get("sch_txt", False):
            # Override to displaying plain text only. This is what the CLI
            # invocations of sch use and should always be fully compatible
            # with the HTML version. Fully compatible meaning it should be
            # formatted mostly the same (via pandoc) with all of the unneeded
            # pieces like input boxes and links removed. In general pandoc
            # does a good job of this, but in some cases inferring off the
            # output format is needed.
            output_format = OutputFormat.TXT
            mimetype = "text/plain"
        else:
            # By default, display as HTML (markdown rendered via pandoc).
            output_format = OutputFormat.HTML
            mimetype = "text/html"

        first_arg = args[0].lower()
        if first_arg == "sch_login" or first_arg == "!":
            # Login request.
            return self.sch_login(args)

        # Auth failed.
        if response := self.sch_auth():
            return response

        match args[0].lower():
            case "sch_tree" | ">":
                return self.sch_tree()
            case "sch_help" | "?":
                return self.sch_help()
            case "sch_complete" | "_":
                return self.sch_complete()
            case "sch_logout" | "&":
                # Logout request.
                return self.sch_logout()

        # Look up command function for command_name (yt).
        # Resolve Command and remaining command arguments
        # Which will be used to invoke the command.
        command, command_args = self.resolve_command(*args)

        if not command:
            if command := self.codex.get_default_command():
                # Default Command is set, use it instead with ALL arguments
                # provided.
                command_args = args

                logger.debug(
                    f"DBG command {spell} not found, using default command {command}"
                )
            else:
                # No command defined with this name and no default, give 404.
                logger.error(f"ERR command {spell} not found")
                return self.sch_fail(f"command {spell} not found", 404)

        # Only bother checking if there are arguments at all.
        if len(command_args):
            # Check if this is a scoped builtin command based on the last argument.
            match command_args[-1].lower():
                case "sch_tree" | ">":
                    return self.sch_tree(command)
                case "sch_help" | "?":
                    return self.sch_help(command)
                case "sch_complete" | "_":
                    return self.sch_complete(command)

        # Call Command function to get redirect URL
        # github()
        # github("adammillerio/sch")
        # github_search("adammillerio/sch", "test", "query")
        # github_search_all("test", "query")
        try:
            redirect_url = command.run(*command_args)
        except Exception as e:
            logger.exception(f"ERR encountered exception while running {spell}")
            return self.sch_error(command, e)

        # Issue a redirect to the URL provided by the command function
        # ie https://www.youtube.com/results?search_query=test+search
        # https://github.com
        # https://github.com/adammillerio/sch
        # https://github.com/search?type=code&q=repo%3Aadammillerio%2Fsch+test+query
        # https://github.com/search?type=code&q=test+query
        logger.info(f"302 {redirect_url}")
        return self.sch_redirect(redirect_url)

    @property
    def sch_txt(self) -> bool:
        """whether or not sch_txt (plain text mode) is enabled for this request.

        sch_txt is enabled by passing &sch_txt=true to any command.

        Override to displaying plain text only. This is what the CLI invocations
        of sch use and should always be fully compatible with the HTML version.
        Fully compatible meaning it should be formatted mostly the same (via pandoc)
        with all of the unneeded pieces like input boxes and links removed. In
        general pandoc does a good job of this, but in some cases inferring off the
        output format is needed.

        Returns:
            sch_txt: bool. whether or not sch_txt is enabled for this request.
        """

        return request.args.get("sch_txt", False)

    @property
    def mimetype(self) -> str:
        """mimetype to use for all Responses.

        This is tied to the state of sch_txt, and configures html by default,
        with fallback to text/plain during text mode.

        Returns:
            mimetype: str. HTML mimetype to use for Response.
        """

        return "text/html" if not self.sch_txt else "text/plain"

    @property
    def output_format(self) -> OutputFormat:
        """Pandoc output format for the request.

        This is the format passed to pandoc (via pypandoc) when rendering the
        markdown templates used for the SCH UI. It defaults to HTML, and uses
        plain text if sch_txt is enabled.

        Returns:
            output_format: OutputFormat. Output format for the request.
        """

        return OutputFormat.HTML if not self.sch_txt else OutputFormat.TXT

    def sch_redirect(self, url: str) -> Response:
        """Return the final "Redirect" response to the user.

        This is the output of /sch and is a 302 request to the generated URL by
        default. If sch_txt is enabled, it will instead just print the URL in
        plain text.

        Args:
            url: str. Generated URL from Command for redirect.

        Returns:
            redirect_response: Response. URL redirect response.
        """

        return (
            cast(Response, redirect(url, code=302))
            if not self.sch_txt
            else Response(url, 200, mimetype=self.mimetype)
        )

    def sch_print(self, text: str, code: int = 200) -> Response:
        """Print some non-redirect output as a Response.

        Args:
            text: str. Text to output to the user.
            code: int. HTML response code, defaults to 200.

        Returns:
            response: Response. Non-URL redirect text response.
        """

        return Response(text, code, mimetype=self.mimetype)

    def sch_fail(self, msg: str, code: int) -> Response:
        """General "HTTP-level" failure.

        This is any error that occurs prior to command execution, such as failure
        to resolve commands, lack of auth, etc.

        Args:
            msg: str. Error message.
            code: int. HTTP error code.

        Returns:
            response: Response. Fail response.
        """

        return self.sch_print(msg, code)

    def sch_auth(self) -> Optional[Response]:
        """Authorize a scholar request.

        If sch_token auth is enabled, this will check if the request has a
        sch_session cookie set that is a valid session. If there is no cookie set,
        or the cookie is invalid, a 401 error will be returned.

        Returns:
            maybe_deny_response: Optional[Response]. A HTTP 401 Response denying
                the user if their session cookie is invalid.
        """

        if not self.enable_sch_token:
            # Auth disabled.
            return

        if request_cookie := request.cookies.get("sch_session", None):
            if self.session_cookies.get(request_cookie, False):
                # Login valid.
                return

        # Auth invalid.
        logger.error("ERR invalid sch_session cookie")
        return self.sch_fail("unauthorized", 401)

    def sch_login(self, args: List[str]) -> Response:
        """Log in to Scholar.

        If sch_token auth is enabled, the sch_login (!) command will attempt to
        authorize the user using a token provided as the first argument. If the
        token matches the one set at CodexServer creation, then a sch_session
        cookie set to a new session will be set, and the user will be redirected
        to the root tree.

        Args:
            args: List[str]. All args provided to ?s= split by space.

        Returns:
            login_response: Response. Login response with new sch_session cookie,
                or a HTTP 400 if unsuccessful.
        """

        if not self.enable_sch_token:
            logger.error("ERR sch_login called but no token set")
            return self.sch_fail("no &sch_token provided", 400)

        if len(args) >= 2:
            if args[1] == self.sch_token:
                cookie = str(uuid4()).replace("-", "")
                self.session_cookies[cookie] = True

                # Login success, set sch_session cookie and render the main
                # command tree.
                success_response = self.sch_redirect("/sch?s=sch_tree")
                success_response.set_cookie("sch_session", cookie)
                return success_response
            else:
                logger.error("ERR sch_token invalid")
                return self.sch_fail("invalid sch_token", 401)
        else:
            logger.error("ERR no sch_token provided")
            return self.sch_fail("no sch_token provided", 401)

    def sch_logout(self) -> Response:
        """Logout of Scholar.

        This will delete the session cookie from the serverside collecton and
        null the user's session cookie. This is ran after auth so the cookie
        is guaranteed to be present.

        Returns:
            logout_response: Response. HTTP 200 text response indicating logout
                success.
        """

        del self.session_cookies[request.cookies.get("sch_session")]
        logout_response = self.sch_print("ok")

        # Logout success, delete cookie.
        logout_response.set_cookie("sch_session", "", expires=0)
        return logout_response

    def sch_tree(self, command: Optional[Command] = None) -> Response:
        """Render the scholar command tree from the root or a command "scope".

        This is initiated by "sch_tree" or ">" as the first argument, either to
        SCH itself for the full tree, or to any command for a tree scoped to
        that Command.

        ?s=sch_tree | ?s=> -> Root tree
        ?s=gh+sch_tree | ?s=gh+> -> Tree scoped at "gh" command.

        If the Scholar server is started with --no-sch-tree, this will instead
        just return a 404.

        Args:
            command: Optional[Command]. Optional Command to use for scoping the
                rendered tree.

        Returns:
            tree_response: Response. Rendered SCH command tree response.
        """

        scope = command if command else self.codex

        if sch_tags := request.args.get("sch_tags", None, type=str):
            # &sch_tags=public,code = filter scope to only Commands with either
            # public or code tags.
            tags = frozenset(sch_tags.split(","))
        else:
            # No tag filters provided.
            tags = None

        if not self.disable_sch_tree:
            # Debug: Render sch_tree for the given scope.
            return self.sch_print(scope.render_tree(self.output_format, tags))
        else:
            # Prod: Ignore sch_tree.
            logger.error("ERR sch_tree disabled, ignoring")
            return self.sch_fail("command not found", 404)

    def sch_complete(self, command: Optional[Command] = None) -> Response:
        """Render the scholar completion list from the root or a command "scope".

        This is initiated by "sch_complete" or "_" as the first argument, either
        to SCH itself for the full completion list, or to any command for
        completions under that Command.

        ?s=sch_complete | ?s=_ -> All completions
        ?s=gh+sch_complete | ?s=gh+_ -> Completions scoped at "gh" command.

        If the scholar server is started with --no-sch-tree, this will instead
        just return a 404.

        Args:
            command: Optional[Command]. Optional command to use for scoping the
                rendered completions.

        Returns:
            complete_response: Response. Rendered SCH completion response.
        """

        scope = command if command else self.codex

        if sch_tags := request.args.get("sch_tags", None, type=str):
            # &sch_tags=public,code = filter scope to only Commands with either
            # public or code tags.
            tags = frozenset(sch_tags.split(","))
        else:
            # No tag filters provided.
            tags = None

        if not self.disable_sch_complete:
            # Debug: Render sch_complete for the given scope.
            return self.sch_print(scope.render_complete(self.output_format, tags))
        else:
            # Ignore sch_complete.
            logger.error("ERR sch_tree disabled, ignoring")
            return self.sch_fail("command not found", 404)

    def sch_help(
        self, command: Optional[Command] = None, error_msg: str = ""
    ) -> Response:
        """Render the help page for a given command.

        This is initiated by "sch_help" or "?" as the first argument, either to
        SCH itself for the main README, or to any command for the help page
        for that command.

        ?s=sch_help | ?s=? -> main README
        ?s=gh+sch_help | ?s=gh+sch_help -> Help for the "gh" command.

        If the Scholar server is started with --no-sch-help, this will instead
        just return a 404.

        Args:
            command: Optional[Command]. Optional Command to use for generating
                help.
            error_msg: str. Optional error message, to be rendered above the
                command help if this is being invoked via sch_error.

        Returns:
            help_response: Response. Rendered SCH command help response.
        """

        if not command:
            # Print main sch readme.
            return self.sch_print(get_sch_help(self.output_format))

        if not self.disable_sch_help:
            # Debug: Go to sch_help.
            return self.sch_print(command.render_help(self.output_format, error_msg))
        else:
            # Prod: Ignore sch_help.
            logger.error(f"ERR sch_help disabled, ignoring")
            return self.sch_fail("command not found", 404)

    def sch_error(self, command: Command, exc: BaseException) -> Response:
        """Render a specialized sch_help page in response to a command error.

        This is invoked if an error is encountered during the actual execution
        of the resolved command.

        This is just a normal sch_help page, with some light mapping of exceptions
        to simplified error messages, which are displayed above the rendered
        help page.

        Args:
            command: Command. Command which generated the exception.
            exc: BaseException. Exception encountered during Command execution.

        Returns:
            error_response: Response. Rendered sch_help page with error response.
        """

        # Command error.
        error_msg = str(exc)
        if isinstance(exc, TypeError):
            # This will redirect to sch_help, which will show the
            # command signature, so this is the only relevant info
            # from this exception type.
            if "0 positional arguments" in error_msg:
                error_msg = "command takes no inputs"
            elif "required positional argument" in error_msg:
                error_msg = "required input missing"
            else:
                error_msg = str(exc)
        else:
            # Some other exception that should probably be wrapped
            # with more relevant info.
            error_msg = str(exc)

        return self.sch_help(command, error_msg)

    # TODO: While this does use anytree now, there's probably some way to do this
    # with just one Resolver call.
    def resolve_command(self, *args: str) -> Tuple[Optional[Command], Tuple[str, ...]]:
        """Resolve a Command and it's remaining args from the Codex.

        Given a full set of args from a call to /sch, this will traverse the tree
        of Commands in the Codex using each input argument, until one of two
        states is reached:
        * No Command exists with the given query argument, return the most recently
            resolved command with all remaining args, including this one.
        * A Command exists and has no Commands under it, so return it along with
            all remaining args.

        If no args are provided, or there is no matching root command, None and
        an empty Tuple will be returned instead.

        Args:
            *args: str. All arguments from a call to /sch

        Returns:
            command: Optional[Command]. Resolved command (if any).
            command_args: Tuple[str, ...]. Remaining args (if any).
        """

        if not args:
            # No command or args provided at all.
            return None, tuple()

        # Create mutable list of all args.
        arg_list = list(args)

        # Remove the first element in the arg_list.
        arg = arg_list.pop(0)

        # Resolve the first argument as a command on the root Codex.
        try:
            command = self.codex.get_command(arg)
        except CommandNotFoundError:
            # No root command exists with this name, so it is an error.
            return None, tuple(arg_list)

        if not arg_list:
            # Root command with no arguments.
            return command, tuple()

        while True:
            # Remove the first element in the arg_list.
            arg = arg_list.pop(0)
            # There is a command under the current Command's subcommands with
            # this name.
            try:
                command = command.get_command(arg)
            except CommandNotFoundError:
                # No command exists with this name, so it must just be an arg.
                return command, ((arg,) + tuple(arg_list))

            if command.children and arg_list:
                # This Command has it's own subcommands, and there are still
                # args to process, continue search.
                continue
            else:
                # This Command has no subcommands, it should run with any
                # remaining args.
                return command, tuple(arg_list)
