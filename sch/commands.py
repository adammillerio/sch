#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from enum import Enum
from functools import cache
from inspect import getdoc, signature
from re import compile as re_compile, Pattern
from typing import Any, Callable, Dict, Optional, Tuple, List, Set, Iterable

from sch.utils import CyclicalList, format_doc, query_args, escape_args

from anytree import (
    AbstractStyle,
    AsciiStyle,
    NodeMixin,
    RenderTree,
    Resolver,
    LevelOrderGroupIter,
)
from pypandoc import convert_text

# sch_help: An input box that is autofocused and filled with the current
# command scope, which will then submit the entry as another command to sch.
# sch_help: an interactive command help page. Displays an input box with the command
# that is autofocused and filled with the current command scope, which will then
# submit the entry as another command to sch.
# Any exceptions encountered during command execution will be redirected to this
# page for the invoked command. The string representation of the exception will
# be printed.
# Using the command "scope", inspect.signature, and inspect.getdoc, build a
# "simplified" python command definition. Most importantly, the signature shows
# the input and output type hints (all str), but other info like Optional can
# inform the user what may be missing.
# Size of input = 80 chars (terminal) + len(" (?) (>)") = 88 / 2 (readability) = 44
SCH_HELP = """\
<form action="/sch"><input type="text" name="s" value="{scope}" autofocus onfocus="this.setSelectionRange(this.value.length,this.value.length);" size="44" spellcheck="false" /></form>

{error_msg}

**def** [{colored_full_scope}{colored_alias_names}](/sch?s={scope_plus}){colored_command_signature}:
```cyan
    {docstring}
```
"""

# Input "REPL": An input box that is autofocused and filled with the current
# command scope, which will then submit the entry as another command to sch.
# Size of input = 80 chars (terminal) + len(" (?) (>)") = 88 / 2
SCH_INPUT = '<form action="/sch"><input type="text" name="s" value="{scope}" autofocus onfocus="this.setSelectionRange(this.value.length,this.value.length);" size="44" spellcheck="false" /></form>\n\n'

# Ideally the layout of scholar's page should be no wider than 680px. This helps
# with keeping the "depth" of the overall tree down.
SCH_FOOTER = """\
``` {{=html}}
<title>{sch_title}</title>
<style>
body {{ font-family: monospace; background-color: #002b36; max-width: 680px; margin: 0 auto; padding: 0 15; }}
input {{ background-color: #073642; color: #93a1a1; outline: none; width: 680px; margin-top: 15px; }}
p {{ color: #93a1a1; }}
a {{ color: #cb4b16; text-decoration: none; }}
.tag_list {{ text-align: justify; text-justify: inter-word; }}
.default_color {{ color: #cb4b16; }}
.yellow {{ color: #b58900; }}
.orange {{ color: #cb4b16; }}
.red {{ color: #dc322f; }}
.magenta {{ color: #d33682; }}
.violet {{ color: #6c71c4; }}
.blue {{ color: #268bd2; }}
.cyan {{ color: #2aa198; }}
.green {{ color: #859900; }}
.brcyan {{ color: #93a1a1; }}
</style>
```
"""


class Color(str, Enum):
    DEFAULT = "default_color"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"
    MAGENTA = "magenta"
    VIOLET = "violet"
    BLUE = "blue"
    CYAN = "cyan"
    GREEN = "green"
    BRCYAN = "brcyan"

    @classmethod
    def from_str(cls, color_str: Optional[str] = None) -> Color:
        return cls[color_str.upper()] if color_str else cls.DEFAULT


STEM_COLOR: Color = Color.GREEN
RETURN_COLOR: Color = Color.MAGENTA
DEPTH_COLORS: List[Color] = [
    Color.GREEN,
    Color.BLUE,
    Color.ORANGE,
    Color.YELLOW,
    Color.VIOLET,
]

# "inifinite" generator of colors, to be used for depth based resolution of command
# and argument color in command tree.
COLOR_WHEEL: CyclicalList[Color] = CyclicalList(DEPTH_COLORS)


class OutputFormat(str, Enum):
    """Supported output formats for SCH.

    These map to the format argument to pypandoc methods (-f and --format on CLI)
    and configure the final output of the text returned by any calls to SCH.
    """

    # Plain text mode, enabled when &sch_txt=true is passed to any command. Commands
    # return 200 with link as plain text. All utility commands (tree/help/etc)
    # return plain text via pandoc's markdown -> plain txt converter.
    TXT = "plain"
    # HTML mode. Default mode for SCH. Commands return 302 with redirect to link
    # as HTML. All utility commands (tree/help/etc) return HTML via pandoc's
    # markdown -> html converter.
    HTML = "html"


def command(
    name: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    aliases: Optional[Iterable[str]] = None,
    disable_tree: bool = False,
    disable_help: bool = False,
) -> Callable[..., Command]:
    """Create a "generic" command.

    This wraps any Scholar compatible function as a Command without attaching
    it to any Codex. This Command can have other Commands registered to it as
    usual in order to compose generic command sets, and can be registered like
    any other Command via add_command.

    Args:
        name: Optional[str]. Command Name. If this is not provided at definition,
            it must be provided as an argument to add_command.
        tags: Optional[Iterable[str]]. Tag(s) to apply to this Command.
        aliases: Optional[Iterable[str]]. Alias name(s) to apply to this Command.
        disable_tree: bool. If True, sch_tree will be disabled and forwarded through
            as a normal argument.
        disable_help: bool. If True, sch_help will be disabled and forwarded through
            as a normal argument.

    Returns:
        command_decorator: Callable[..., Command]. Decorator for creating a
            Command.
    """

    def decorator(func: Callable[..., str]) -> Command:
        return Command(
            command_func=func,
            name=name,
            tags=tags,
            aliases=aliases,
            disable_tree=disable_tree,
            disable_help=disable_help,
        )

    return decorator


def bookmark(
    url: str,
    short_help: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    aliases: Optional[Iterable[str]] = None,
    disable_tree: bool = False,
    disable_help: bool = False,
) -> Command:
    """Bookmark Command.

    A Bookmark Command is just a normal Command that returns a provided URL, with
    no other execution. It also has some custom help formatting.

    Bookmarks should be registered using add_bookmark but bookmark can also be
    used for generic composition like command.

    All bookmarks have the "bookmark" Command tag.

    Args:
        url: str. URL to redirect to for bookmark.
        short_help: Optional[str]. Any additional info to be provided in the
            Command help.
        tags: Optional[Iterable[str]]. Tag(s) to apply to this Command.
        aliases: Optional[Iterable[str]]. Alias name(s) to apply to this Command.
        disable_tree: bool. If True, sch_tree will be disabled and forwarded through
            as a normal argument.
        disable_help: bool. If True, sch_help will be disabled and forwarded through
            as a normal argument.

    Returns:
        bookmark_command: Command.
    """

    tag_set = {"bookmark"}
    if tags:
        tag_set.update(tags)

    help_str = short_help if short_help else ""

    @command(
        tags=tag_set,
        aliases=aliases,
        disable_tree=disable_tree,
        disable_help=disable_help,
    )
    @format_doc(url=url, help_str=help_str)
    def bookmark_command() -> str:
        """{help_str}

        return {url}
        """

        return url

    return bookmark_command


def search(
    url: str,
    fallback_url: str,
    short_help: Optional[str] = None,
    escaped: bool = False,
    tags: Optional[Iterable[str]] = None,
    aliases: Optional[Iterable[str]] = None,
    disable_tree: bool = False,
    disable_help: bool = False,
) -> Command:
    """Search Command.

    A Search Command is a Command which will issue a query with all provided
    arguments to a provided URL, which is typically a search engine. In addition,
    a fallback_url is provided, which will be returned if no search arguments
    are provided.

    By default, search queries are quoted (test+search) rather than escaped
    (test%20search). This can be changed by passing escaped=True.

    All searches have the "search" Command tag.

    Args:
        url: str. Search URL to redirect search query to.
        fallback_url: str. URL to redirect to when no query is provided.
        short_help: Optional[str]. Any additional info to be provided in the
            Command help.
        escaped: bool. Whether or not the search query should be escaped rather
            than quoted. Defaults to False.
        tags: Optional[Iterable[str]]. Tag(s) to apply to this Command.
        aliases: Optional[Iterable[str]]. Alias name(s) to apply to this Command.
        disable_tree: bool. If True, sch_tree will be disabled and forwarded through
            as a normal argument.
        disable_help: bool. If True, sch_help will be disabled and forwarded through
            as a normal argument.

    Returns:
        search_command: Command.
    """
    tag_set = {"search"}
    if tags:
        tag_set.update(tags)

    help_str = short_help if short_help else ""

    @command(
        tags=tag_set,
        aliases=aliases,
        disable_tree=disable_tree,
        disable_help=disable_help,
    )
    @format_doc(url=url, fallback_url=fallback_url, help_str=help_str)
    def search_command(*args: str) -> str:
        """{help_str}

        if args:
            return {url}{{*args}}
        else:
            return {fallback_url}
        """

        query = query_args(*args) if not escaped else escape_args(*args)

        if args:
            return f"{url}{query}"
        else:
            return fallback_url

    return search_command


class CommandNotFoundError(Exception):
    """No command found matching the name provided by the user."""

    pass


class Command(NodeMixin):
    """A Scholar Command.

    This is a general use wrapper to be applied to any Scholar-compatible functions,
    that is, functions which take one to many strings and return a URL as a string.

    Commands can have other Commands registered to them by name. These command
    names are then used to resolve a given Command to execute during a Scholar
    query.

    To register a Command to another Command, use either the Command.command decorator
    or the Command.add_command function.

    Commands can either be named at definition, or during registration later,
    however, they must have a name at runtime.

    Commands can also be tagged with any number of string based tags, which can
    be used for filtering.

    Args:
        command_func: Callable[..., str]. Scholar function to wrap.
        name: Optional[str]. Name of this Scholar Command.
        tags: Optional[Iterable[str]]. Tag(s) to apply to this Command.
        aliases: Optional[Iterable[str]]. Alias name(s) to apply to this Command.
        disable_tree: bool. If True, sch_tree will be disabled and forwarded through
            as a normal argument.
        disable_help: bool. If True, sch_help will be disabled and forwarded through
            as a normal argument.
        parent: Optional[Command]. Parent Command, if any.
        children: Optional[Tuple[Command, ...]]. Child (Sub) commands, if any.
    """

    # anytree: Switch to space separation instead of /, mostly for UX purposes.
    separator = " "

    # anytree: General use Node Resolver for command lookups.
    resolver: Resolver = Resolver("name", relax=True)

    # Command name regex, used for validation.
    NAME_REGEX: Pattern[str] = re_compile(r"^[\w-]+$")

    def __init__(
        self,
        command_func: Callable[..., str],
        name: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        aliases: Optional[Iterable[str]] = None,
        disable_tree: bool = False,
        disable_help: bool = False,
        parent: Optional[Command] = None,
        children: Optional[Tuple[Command, ...]] = None,
    ) -> None:
        super().__init__()

        self.name = name
        self.command_func = command_func
        self._tags: Set[str] = set(tags) if tags else set()
        self.aliases: Set[str] = set(aliases) if aliases else set()
        self.disable_tree = disable_tree
        self.disable_help = disable_help

        # Mapping of any registered command aliases to the actual child command
        # name.
        self.child_aliases: Dict[str, str] = {}

        self.parent = parent
        if children:
            self.children: Tuple[Command, ...] = children

    @property
    def tags(self) -> Set[str]:
        """Tags assigned to this Command.

        Tags can be set on the Command at definition time and are also inherited
        from any parent Command. All sub-Commands will also inherit this Command's
        tags.

        Returns:
            tags: Set[str]. Tags assigned to this Command.
        """

        return self._tags

    @tags.setter
    def tags(self, val: Set[str]) -> None:
        """Update tags assigned to this command.

        This updates the Command's tag set as well as the tag sets of any child
        Commands, which will propagate any top level tag definitions down the
        Command tree.

        Args:
            val: Set[str]. Tags to assign to this Command.
        """

        self._tags = val
        if self.children:
            # Add tags to any child commands.
            for node in self.children:
                node.tags = node.tags.union(val)

    @property
    def all_tags(self) -> List[str]:
        """Unique set of all tags used on Commands in this tree.

        Args:
            all_tags: List[str]. Sorted list of all tags found on Commands currently
                registered under this tree.
        """

        # TODO: There is probably a more optimal way to do this.
        all_tags = set()
        for node in self.descendants:
            all_tags.update(node.tags)

        return sorted(all_tags)

    @property
    def short_help(self) -> str:
        if func_doc := getdoc(self.command_func):
            return func_doc.split("\n")[0]
        else:
            return ""

    @property
    def alias_names(self) -> str:
        # {foobar}
        aliases = ",".join(self.aliases)

        return f"{{{aliases}}}" if aliases else ""

    @property
    def scope(self) -> str:
        # gh search
        # Don't include the root Codex in the scope. See full_scope for the
        # same value but inclusive of the Codex.
        return " ".join(node.name for node in self.path[1:])

    @property
    def scope_plus(self) -> str:
        # gh+search
        return self.scope.replace(" ", "+")

    @property
    def full_scope(self) -> str:
        # sch gh search.
        scope = self.scope

        # Only add space if there is a scope at all, to avoid issues with
        # splitting on spaces later
        return f"{self.path[0].name} " + scope if scope else f"{self.path[0].name}"

    @property
    def color(self) -> str:
        # Retrieve the depth based color ID for this command from the color
        # wheel. This is then used to assign a color class which sets the
        # desired pallette via css.
        return COLOR_WHEEL.get(self.depth).value

    @property
    def color_class(self) -> str:
        # {.green}
        return f"{{.{self.color}}}"

    @property
    def colored_name(self) -> str:
        # `sch`{.green}
        return f"`{self.name}`{self.color_class}"

    @property
    def colored_alias_names(self) -> str:
        # `{s}`{.green}
        return f"`{self.alias_names}`{self.color_class}" if self.alias_names else ""

    @property
    def colored_full_scope(self) -> str:
        """Generate a colored full scope for sch_help.

        This uses the color wheel to generate a colored scope of the path leading
        up to this command.

        Returns:
            colored_sig: str. Colored markdown signature.
        """

        colored_scope_parts = []
        for i, command in enumerate(self.full_scope.split(" ")):
            depth_color = COLOR_WHEEL.get(i).value
            node_color = f"{{.{depth_color}}}"
            colored_scope_parts.append(f"`{command}`{node_color}")

        return " ".join(colored_scope_parts)

    @property
    def colored_scope(self) -> str:
        """Generate a colored scope for sch_complete.

        This is the same as colored_full_scope, but omits the root command name.

        Feturns:
            colored_scope: str. Colored command scope.
        """

        colored_scope_parts = []

        # Iterate from first element onwards, starting in the color wheel at 1.
        for i, command in enumerate(self.full_scope.split(" ")[1:], 1):
            depth_color = COLOR_WHEEL.get(i).value
            node_color = f"{{.{depth_color}}}"
            colored_scope_parts.append(f"`{command}`{node_color}")

        return " ".join(colored_scope_parts)

    @property
    def colored_signature(self) -> str:
        """Generate a colored signature for sch_help.

        This uses the color wheel to generate a colored signature of all the arguments
        to a given command, if any. This is rendered via an offset that is derived
        in sch_help such that the first color in the signature is at the "depth" of
        the resolved command + 1.

        Returns:
            colored_sig: str. Colored markdown signature.
        """

        colored_sig_parts = []
        sig = signature(self.command_func)

        retval = sig.return_annotation
        if not isinstance(retval, str):
            retval = retval.__name__

        # Start at the depth of this command + 1, accounting for the root Codex,
        # so that args start at the correct color offset from the command.
        for i, param in enumerate(sig.parameters.values(), self.depth + 1):
            depth_color = COLOR_WHEEL.get(i).value
            node_color = f"{{.{depth_color}}}"
            colored_sig_parts.append(f"`{str(param)}`{node_color}")

        return (
            "("
            + ", ".join(colored_sig_parts)
            + f") -> `{retval}`{{.{RETURN_COLOR.value}}}"
        )

    @property
    def colored_tree_symbol(self) -> str:
        # > or >* if disabled.
        symbol = ">" if not self.disable_tree else ">*"

        return f"`{symbol}`{self.color_class}"

    @property
    def colored_help_symbol(self) -> str:
        # ? or ?* if disabled.
        symbol = "?" if not self.disable_help else "?*"

        return f"`{symbol}`{self.color_class}"

    @property
    def docstring(self) -> str:
        command_help = getdoc(self.command_func)
        if command_help:
            # "Re-pad" the newlines to be indented forward 4 spaces, after they
            # are stripped by clean-doc, to be used in the pseudo-docs for the
            # command.
            return command_help.replace("\n", "\n    ")
        else:
            return "(no command help defined)"

    def run(self, *args: str) -> str:
        """Run this Command's function.

        Args:
            *args: str. All remaining arguments from query.

        Returns:
            url: str. URL to redirect to.
        """

        return self.command_func(*args)

    def get_command(self, name: str) -> Command:
        if command_name := self.child_aliases.get(name, None):
            # Name provided is an alias to another command, retrieve it.
            command = self.resolver.get(self, command_name)
        else:
            # Attempt to resolve command with provided name.
            command = self.resolver.get(self, name)

        if not command:
            raise CommandNotFoundError(f"no command {name} found")

        return command

    @classmethod
    def validate_command_name(cls, name: str) -> None:
        """Validate a command name.

        This validates the supplied command name against a regex ensuring that
        command names only contain word characters (\w) or dashes.

        Args:
            name: str. Command name to validate.

        Raises:
            ValueError: If command name is invalid.
        """

        if not cls.NAME_REGEX.fullmatch(name):
            raise ValueError(
                f"invalid command name '{name}', names can only contain word "
                "characters ([a-zA-Z0-9_]) or dashes (-)"
            )

    def add_command(
        self,
        command: Command,
        name: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        aliases: Optional[Iterable[str]] = None,
    ) -> Command:
        """Register a Command as a sub-Command.

        If a name is provided, it will replace any name defined on the Command
        beforehand.

        Args:
            command: Command. Command to register as a sub-Command of this one.
            name: Optional[str]. Name override for Command.
            tags: Optional[Iterable[str]]. Additional tags to apply to Command, if
                any.
            aliases: Optional[Iterable[str]]. Alias name(s) to apply to this Command.

        Returns:
            command: Command.

        Raises:
            ValueError: If a command name was not provided, and the Command has
                no name.
        """

        if name:
            # Name override, set the name on the Command to the expected one. This
            # works alongside composing generic commands with @command()
            command.name = name
        else:
            if not command.name:
                raise ValueError("command name must be provided")

            name = command.name

        # Validate command name prior to insertion.
        self.validate_command_name(command.name)

        if self.resolver.get(self, command.name):
            raise ValueError(
                f"command '{self.full_scope}{command.name}' already exists"
            )

        if tags:
            command.tags = set(tags).union(command.tags)

        # Inherit all Command tags from the parent.
        command.tags = self.tags.union(command.tags)

        if aliases:
            command.aliases = set(aliases).union(command.aliases)

        for alias in command.aliases:
            if existing_alias := self.child_aliases.get(alias, None):
                raise ValueError(
                    f"command alias '{self.full_scope}{alias}' to '{existing_alias}' already exists"
                )

            self.child_aliases[alias] = name

        # Register the Command.
        command.parent = self

        return command

    def command(
        self,
        name: str,
        tags: Optional[Iterable[str]] = None,
        aliases: Optional[Iterable[str]] = None,
        disable_tree: bool = False,
        disable_help: bool = False,
    ) -> Callable[..., Command]:
        """Create and register a Command to this one.

        This wraps any Scholar compatible function as a Command and registers it
        as a sub-Command of this one.

        Args:
            name: str. Command name.
            tags: Optional[Iterable[str]]. Tag(s) to apply to this Command.
            aliases: Optional[Iterable[str]]. Alias name(s) to apply to this Command.
            disable_tree: bool. If True, sch_tree will be disabled and forwarded through
                as a normal argument.
            disable_help: bool. If True, sch_help will be disabled and forwarded through
                as a normal argument.

        Returns:
            command_decorator: Callable[..., Command]. Decorator for creating and
                registering the Command.
        """

        def decorator(func: Callable[..., str]) -> Command:
            command = Command(
                name=name,
                command_func=func,
                tags=tags,
                disable_tree=disable_tree,
                disable_help=disable_help,
            )

            return self.add_command(command, aliases=aliases)

        return decorator

    def add_bookmark(
        self,
        name: str,
        url: str,
        short_help: Optional[str] = None,
        **kwargs: Any,
    ) -> Command:
        """Register a Bookmark Command.

        A Bookmark Command is just a normal Command that returns a provided URL, with
        no other execution. It also has some custom help formatting.

        Args:
            name: str. Name to register Command under.
            url: str. URL to redirect to for bookmark.
            short_help: Optional[str]. Any additional info to be provided in the
                Command help.
            **kwargs: Passed on to @command decorator.

        Returns:
            command: Command.
        """

        cmd = bookmark(url, short_help, **kwargs)

        return self.add_command(cmd, name)

    def add_search(
        self,
        name: str,
        url: str,
        fallback_url: str,
        short_help: Optional[str] = None,
        escaped: bool = False,
        **kwargs: Any,
    ) -> Command:
        """Register a Search Command.

        A Search Command is a Command which will issue a query with all provided
        arguments to a provided URL, which is typically a search engine. In addition,
        a fallback_url is provided, which will be returned if no search arguments
        are provided.

        Args:
            name: str. Name to register Command under.
            url: str. Search URL to redirect search query to.
            fallback_url: str. URL to redirect to when no query is provided.
            short_help: Optional[str]. Any additional info to be provided in the
                Command help.
            escaped: bool. Whether or not the search query should be escaped rather
                than quoted. Defaults to False.
            **kwargs: Passed on to @command decorator.

        Returns:
            command: Command.
        """

        cmd = search(url, fallback_url, short_help, escaped, **kwargs)

        return self.add_command(cmd, name)

    @cache
    def render_help(
        self, output_format: OutputFormat = OutputFormat.TXT, error_msg: str = ""
    ) -> str:
        """Render the help page for this command.

        This will generate a simple help page that has a scoped REPL, the function
        docstring, if any, and a link back to the main tree.

        Args:
            output_format: OutputFormat. Pandoc output format.
            error_msg: str. Any error message from the previous command call, if
                this page is being rendered in response to a command error.

        Returns:
            help_str: str. Rendered help page for this command.
        """

        help_str = SCH_HELP.format(
            scope=self.scope,
            scope_plus=self.scope_plus,
            colored_full_scope=self.colored_full_scope,
            docstring=self.docstring,
            command_name=self.name,
            colored_command_signature=self.colored_signature,
            colored_alias_names=self.colored_alias_names,
            # Don't include code backticks if no error_msg... really just need
            # to switch to jinja...
            error_msg=f"```{{.brcyan}}\n{error_msg}\n```" if error_msg else "",
        ) + SCH_FOOTER.format(sch_title=f"sch ({self.name}?)")

        if output_format != OutputFormat.TXT:
            # Back button.
            help_str += "\n[<<](/sch?s=sch_tree)\n"

        return convert_text(
            help_str,
            output_format.value,
            format="md",
            extra_args=["--from=commonmark_x"],
        )

    @cache
    def render_complete(
        self,
        output_format: OutputFormat = OutputFormat.TXT,
        tags: Optional[Iterable[str]] = None,
    ) -> str:
        """Render a Command Completion from this Command onward.

        This print "completion" information about this command and all child
        commands in plain text. Right now this is just the full path to each
        command, along with any aliases separated by tab.

        The full list of completions will be returned to the user, typically to
        be used with completion tools like fzf.

        Args:
            output_format: OutputFormat. Pandoc output format.
            tags: Optional[Iterable[str]]. Tag(s) to filter tree on prior to
                rendering completions.

        Returns:
            rendered_completions: str. Fully rendered plain text list of all
                completions.
        """

        render_str = ""

        if tags:
            # Create a filtered copy of the tree with the provided tags.
            command = self.filter_tree(tags=tags)
        else:
            command = self

        # Sort tree alphabetically descending during render.
        def alphabetical(items: List[Command]) -> List[Command]:
            return sorted(items, key=lambda item: item.name)

        for row in RenderTree(command, AsciiStyle, childiter=alphabetical):
            node = row.node

            # Add a _tab separated_ collection of aliases if present
            # This is tab separated so that the aliases portion of the
            # completion line can be filtered out ie via cut -f 1
            # TODO: Tabs only show in code spans/blocks, so this has to be
            # manually composed here vs using node.colored_alias_names for now
            aliases = node.alias_names
            aliases = f"`\t{aliases}`{self.color_class}" if aliases else ""

            # Just print the full scope of each command
            # CommonMark: Two spaces before newline -> hard line break
            render_str += (
                f"[{node.colored_scope}{aliases}](/sch?s={node.scope_plus})  \n"
            )

        # Add (command...) as a small scope next to tab title.
        title = f"sch ({self.name}...)" if self.scope else "sch"

        if output_format != OutputFormat.TXT:
            # Back button.
            render_str += "\n[<<](/sch?s=sch_tree)\n"

        return convert_text(
            SCH_INPUT.format(scope=self.scope)
            + render_str
            + SCH_FOOTER.format(sch_title=title),
            output_format.value,
            format="md",
            # Add --preserve-tabs option to retain tab delimiter in completions
            extra_args=["--from=commonmark_x", "--preserve-tabs"],
        )

    @cache
    def render_tree(
        self,
        output_format: OutputFormat = OutputFormat.TXT,
        tags: Optional[Iterable[str]] = None,
    ) -> str:
        """Render a Command Tree from this Command onward.

        This will render and display an ASCII representation of this Command and
        all of it's subcommands for the user.

        Args:
            output_format: OutputFormat. Pandoc output format.
            tags: Optional[Iterable[str]]. Tag(s) to filter tree on prior to
                rendering tree.

        Returns:
            rendered_tree: str. Fully rendered ASCII tree of Command structure.
            tags: Optional[Iterable[str]]. Tag(s) to filter tree on prior to
                rendering.
        """

        return convert_text(
            self.render(output_format=output_format, tags=tags),
            output_format.value,
            format="md",
            # CommonMark markdown engine.
            extra_args=["--from=commonmark_x"],
        )

    def render(
        self,
        style: Optional[AbstractStyle] = None,
        output_format: OutputFormat = OutputFormat.HTML,
        tags: Optional[Iterable[str]] = None,
    ) -> str:
        """Render and return the CommandNode tree.

        Args:
            style: Optional[AbstractStyle]. Anytree "style" to use for rendering
                tree. Defaults to AsciiStyle().
            output_format: OutputFormat. Pandoc output format.
            tags: Optional[Iterable[str]]. Tag(s) to filter tree on prior to
                rendering.

        Returns:
            rendered_tree: str. Rendered CommandNode tree.
        """

        command = self
        scope = self.scope
        stem_color = STEM_COLOR.value

        if not style:
            style = AsciiStyle()

        if tags:
            # Create a filtered copy of the tree with the provided tags.
            command = command.filter_tree(tags=tags)

        render_str = ""

        first_row = True

        # Sort tree alphabetically descending during render.
        def alphabetical(items: List[Command]) -> List[Command]:
            return sorted(items, key=lambda item: item.name)

        for row in RenderTree(command, style, childiter=alphabetical):
            node = row.node
            # Generate a + separated query path from all nodes other than the
            # root.
            command_str = node.scope_plus

            # Add a link to invoking this command on the name itself, using the
            # full path.
            md_node_name = (
                f"[{node.colored_name}{node.colored_alias_names}](/sch?s={command_str})"
                if command_str
                # If it's the root command, just link back to tree.
                else f"[{node.colored_name}](/sch?s=sch_tree)"
            )

            if output_format is not OutputFormat.TXT:
                # Add a (?) that links to the sch_help for this command.
                md_help_link = (
                    f" [{node.colored_help_symbol}](/sch?s={command_str}+sch_help)"
                    if command_str
                    # Root tree, just link to main help.
                    else f" [{node.colored_help_symbol}](/sch?s=sch_help)"
                )
                # Add a (>) that links to the scoped sch_tree for this command.
                md_tree_link = (
                    f" [{node.colored_tree_symbol}](/sch?s={command_str}+sch_tree)"
                    if command_str
                    # Root tree, just link back to the root tree.
                    else f" [{node.colored_tree_symbol}](/sch?s=sch_tree)"
                )
            else:
                # These are meaningless in plain text, so don't render.
                md_help_link = ""
                md_tree_link = ""

            # Add a suffix which shows any defined short_help.
            if node.short_help:
                if len(node.short_help) > 57:
                    help_str = f" - {node.short_help[:54]}..."
                else:
                    help_str = f" - {node.short_help}"
            else:
                help_str = ""

            if first_row:
                # First row: Render the scoped "command prompt" as well as the
                # first node without the inline code prefix (since it is empty).
                first_row = False

                # Render the colored header of all tags available under this
                # Command tree.
                tag_str = (
                    self.colored_tag_links
                    if output_format is not OutputFormat.TXT
                    else ""
                )
                # If this is already a tag filtered tree, then add a back button
                # that returns to the non filtered one.
                tree_cmd_str = f"{self.scope_plus}+" if self.scope_plus else ""
                # TODO: Figure out some way to make the display of the tag line
                # justified.
                tag_back_str = (
                    f" [`back`{{.{RETURN_COLOR.value}}}](/sch?s={tree_cmd_str}sch_tree)"
                    if tags and output_format is not OutputFormat.TXT
                    else ""
                )

                render_str += (
                    SCH_INPUT.format(scope=scope)
                    # "Fenced div", which lets you wrap anything in a div which
                    # has a given class/ID in pandoc. This is used to justify the
                    # tag text.
                    + "::::: {.tag_list}\n"
                    + tag_str
                    + tag_back_str
                    # Close fenced div.
                    + "\n:::::"
                    + "\n\n"
                    + f"{row.pre}{md_node_name}{help_str}{md_help_link}{md_tree_link}  \n"
                )
            else:
                # All other rows, render the full line.
                # CommonMark: Two spaces before newline -> hard line break
                render_str += f"`{row.pre}`{{.{stem_color}}}{md_node_name}{help_str}{md_help_link}{md_tree_link}  \n"

        if scope and output_format is not OutputFormat.TXT:
            # Back button.
            render_str += "\n[<<](/sch?s=sch_tree)\n"

        # Add (command) as a small scope next to tab title.
        title_scope = f" ({self.name})" if scope else ""

        return render_str + SCH_FOOTER.format(sch_title=f"sch{title_scope}")

    def filter_tree(
        self,
        tags: Optional[Iterable[str]] = None,
        exclude_tags: Optional[Iterable[str]] = None,
    ) -> Command:
        """Create a filtered copy of the Command tree.

        This creates a filtered clone of the tree from this Command, iterating
        from the bottom of the Command tree up and removing any leaf commands
        which do not have the tag filters provided.

        The copy is then returned and can be used in place of the original Command
        tree.

        Args:
            tags: Optional[Iterable[str]]. Set of tags to filter Command tree on.
                Only Commands including at least one of the provided tags on itself
                or at least one of it's children will be included
            exclude_tags: Optional[Set[str]]. Set of tags to exclude from the
                filtered Command tree.

        Returns:
            filtered_tree: Command. Filtered clone of the Command tree.
        """

        # TODO: Mildly insane, there is probably a better way to do this.
        # Create a full copy of the tree.
        tree = deepcopy(self)

        if tags:
            tag_set = set(tags)
        else:
            tag_set = None

        if exclude_tags:
            exclude_tag_set = set(exclude_tags)
        else:
            exclude_tag_set = None

        # LevelOrderGroupIter goes by level from the top down, returning each
        # full "level" of the tree as a list of Command nodes. This generates
        # the full level iter and then reverses it, allowing us to filter from
        # the leaves up.
        iter_list = list(LevelOrderGroupIter(tree))
        iter_list.reverse()

        for level in iter_list:
            for node in level:
                # If this Command does not have any children anymore, meaning no
                # "lower" level nodes had any of the tags provided, and it also
                # does not match any tag filters provided, then detach it from the
                # tree. Because this is working from the bottom up, it will ensure
                # that a full branch to a given leaf is available so long as it
                # has any of the matching filter tags.
                if not node.children:
                    if exclude_tag_set and exclude_tag_set.intersection(node.tags):
                        node.parent = None

                    if tag_set and not tag_set.intersection(node.tags):
                        node.parent = None

        return tree

    @property
    def colored_tag_links(self) -> str:
        """Generate the colored header of tag links.

        This gets the sorted list of all tags avaialable under this scope and
        uses it to generate links to a filtered tree at the given scope by
        any one tag. Tags are colored by the color wheel starting from 0.

        Returns:
            colored_tag_links: str. Colored tag link header.
        """

        tags = []

        tree_cmd_str = f"{self.scope_plus}+" if self.scope_plus else ""

        for i, tag in enumerate(self.all_tags):
            color = COLOR_WHEEL.get(i).value

            tags.append(
                f"[`{tag}`{{.{color}}}](/sch?s={tree_cmd_str}sch_tree&sch_tags={tag})"
            )

        return " ".join(tags)
