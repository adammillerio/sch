#!/usr/bin/env python3
from itertools import cycle, takewhile, dropwhile
from importlib.util import module_from_spec
from pkgutil import iter_modules
from types import ModuleType
from typing import (
    Any,
    cast,
    Callable,
    Iterable,
    Generic,
    TypeVar,
    List,
    Optional,
    Union,
)
from urllib.parse import quote_plus, quote

T = TypeVar("T")


def query_args(*args: str) -> str:
    """Transform *args from a command into a single quoted URL parameter value.

    This is commonly used when defining search proxies.

    Args:
        *args: str. All uncaptured arguments from a SCH command.

    Returns:
        query_args: str. Quoted URL parameter value.
    """

    return quote_plus(" ".join(args))


def escape_args(*args: str) -> str:
    """Transform *args from a command into a single escaped URL paramter value.

    Similar to query_args, but uses quote to replace characters with their escaped
    equivalents (ie " " -> "%20").

    Returns:
        escape_args: str. Escaped URL parameter value.
    """

    return quote(" ".join(args))


def format_doc(*args: Any, **kwargs: Any) -> Callable[..., Callable[..., str]]:
    """Format the docstring of a function after definition.

    Function docstrings themselves cannot be f-strings. This decorator when applied
    to a function will take the docstring and call format on it with any args or
    kwargs provided. This allows for dynamic composition of docstrings when
    making "generic" commands.

    Returns:
        format_decorator: Callable[..., Callable[..., str]]. Post-format decorator
            with the provided args/kwargs.
    """

    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        func.__doc__ = func.__doc__.format(*args, **kwargs)

        return func

    return decorator


def load_commands(commands_module: ModuleType) -> None:
    """Load all submodules of a module.

    Given a Python ModuleType containing Scholar "Codexes" (Modules), this will
    find and load each one, composing the Scholar Codex and Command tree.

    Args:
        commands_module: ModuleType. Loaded Python Module.
    """

    # Iterate through all submodules of the provided module.
    for importer, module_name, _is_package in iter_modules(commands_module.__path__):
        spec = importer.find_spec(module_name)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)


class CyclicalList(Generic[T]):
    """Cyclical List

    Initialized with any Iterable[T], this will generate an "infinite" list that
    repeats every len(Iterable[T]):

    c = CyclicalList(["green", "blue", "magenta"])
    c[0:3]
    ['green', 'blue', 'magenta']

    c[0:6]
    ['green', 'blue', 'magenta', 'green', 'blue', 'magenta']

    c[5]
    'magenta'

    Args:
        initial: Iterable[T]. Iterable to initialize cyclical list with.
    """

    def __init__(self, initial: Iterable[T]) -> None:
        self._initial_list: List[T] = list(initial)

    def __getitem__(self, item: Union[int, slice]) -> Optional[Union[T, List[T]]]:
        if isinstance(item, slice):
            if item.stop is None:
                raise ValueError("Cannot slice without stop")
            iterable = enumerate(cycle(self._initial_list))
            if item.start:
                iterable = dropwhile(lambda x: x[0] < item.start, iterable)
            return [
                element
                for _, element in takewhile(lambda x: x[0] < item.stop, iterable)
            ]

        # Negative index "handling".
        item = abs(item)

        for index, element in enumerate(cycle(self._initial_list)):
            if index == item:
                return element

    def __iter__(self) -> "cycle[T]":
        return cycle(self._initial_list)

    def get(self, idx: int) -> T:
        # It is physically impossible for this to be anything other than T at
        # this point, since the list is infinite.
        return cast(T, self[idx])
