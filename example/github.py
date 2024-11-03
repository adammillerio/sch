#!/usr/bin/env python3
from typing import Optional

from sch import Command, codex, command, format_doc, query_args


@codex.command("gh", tags=["github"])
def github(repo: Optional[str] = None) -> str:
    """go to github or a view a repo

    if repo:
        return https://github.com/{repo}
    else:
        return https://github.com
    """

    if repo:
        return f"https://github.com/{repo}"
    else:
        return "https://github.com"


@github.command("search")
def github_search(repo: str, *args: str) -> str:
    """search a github repo

    return https://github.com/search?type=code&q=repo:{repo}+{*args}
    """

    return f"https://github.com/search?type=code&q=repo:{query_args(repo, *args)}"


@github_search.command("all")
def github_search_all(*args: str) -> str:
    """search all of github

    return https://github.com/search?type=code&q={*args}
    """

    return f"https://github.com/search?type=code&q={query_args(*args)}"




def repo_command(repo: str, docs: str) -> Command:
    @command(tags=["code"])
    @format_doc(repo=repo)
    def code_repo() -> str:
        """go to {repo} on github"""

        return f"https://github.com/{repo}"

    @code_repo.command("docs")
    @format_doc(repo=repo)
    def code_repo_docs() -> str:
        """go to hosted docs for {repo}"""

        return docs

    return code_repo


codex.add_command(
    repo_command("pallets/click", "https://click.palletsprojects.com/en/8.1.x"),
    "click",
)
codex.add_command(
    repo_command("pallets/flask", "https://flask.palletsprojects.com/en/3.0.x/"),
    "flask",
)
