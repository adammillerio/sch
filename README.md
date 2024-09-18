# Scholar (sch)

Scholar (`sch`) is a programmable bookmark and pseudo-search engine heavily inspired
by [YubNub](https://yubnub.org/). It is a  lightweight HTTP service for executing
scripts which generate URLs. These URLs are then issued to the user via an HTTP
redirect.

The main use case of sch is as a search engine in a browser toolbar, with
a predefined set of commands which "routes" you to the desired page or search
engine.

For a hands-on explanation and demonstration of Scholar as a tool, a public hosted
instance is available: https://sch.luphy.net/sch?s=sch_tree

As well as a general use doc: https://sch.luphy.net/sch?s=sch_help

A major difference is that Scholar is intended to be run locally or via a
self-hosted public instance. To get an instance of Scholar up and running on
a local machine, check the "Getting Started" guide below.

Scholar can also provide an interactive completion CLI using
[fzf](https://github.com/junegunn/fzf). See [tools/complete.sh](tools/complete.sh) for
an example.

To learn about writing commands, check the "Usage" section.

Guidance for how to run a self-hosted public instance can also be found in the
"Advanced Usage" section.

# Getting Started
## TL; DR

```bash
# Install scholar with pandoc
pip install scholar-search[pandoc]

# Clone and run sch against the example codex
git clone https://github.com/adammillerio/sch.git
sch run
```

And go to http://localhost:5000/sch?s=sch_help for usage info.

The public collection of codexes is available at
[adammillerio/sch_public](https://github.com/adammillerio/sch_public)

## Detailed

Scholar can be installed via pip:

```bash
# With pandoc
pip install scholar-search[pandoc]
# Without pandoc (install via other means)
pip install scholar-search
```

Rendering text pages depends on [`pandoc`](https://pandoc.org/). Scholar can be
installed with the `pandoc` extra to include the
[`pypandoc-binary`](https://pypi.org/project/pypandoc-binary/) package, which will
also download `pandoc` itself.

Refer to the [Pandoc Manual](https://pandoc.org/installing.html) for more info.

Commands are loaded into Scholar via a "Codex", which is just a Python file that
has a Flask app factory defined. This file can import other files or define
commands directly.

A basic hello world example (`hello_world.py`):

```python
#!/usr/bin/env python3
from sch import codex


@codex.command(name="hello")
def hello() -> str:
    return "https://github.com/adammillerio/sch"


# Flask Application Factory
# Run with sch --app hello_world run
def create_app():
    return codex.create_app()

```

An extension of the flask CLI, `sch` is provided, which can be used both to run
an HTTP server and to perform completions via the CLI:
```bash
sch --app hello_world search hello                    
https://github.com/adammillerio/sch
```

An example codex with some basic commands is provided at [app.py](app.py). Flask
will load `./app.py` by default if `--app` is not provided.

To start the sch webserver, run the example codex from the root of this repository:
```bash
sch run
 * Debug mode: off
INFO:werkzeug:WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
INFO:werkzeug:Press CTRL+C to quit
```

And go to http://localhost:5000/sch?s=sch_help for usage info.

This leverages Flask [Application Factories](https://flask.palletsprojects.com/en/2.3.x/patterns/appfactories/),
which are used to generate the final Flask implementation at the end of the root
codex. Above this, the Codex can be composed via importing commands or defining
them directly as neecessary.

# Usage
`sch` is best explained via hands on examples. This will demonstrate adding a 
single command to `sch`.

## The Goal
Write a scholar command, `gh`, which performs the following actions:

* `gh` - Go to GitHub homepage
    * `https://github.com`
* `gh {repo}` - View a GitHub repo
    * `https://github.com/{repo}`
* `gh search {repo} {query}` - Search a GitHub repo
    * `https://github.com/search?type=code&q=repo:{repo}+{query}`
* `gh search all {query}` - Search all of GitHub
    * `https://github.com/search?type=code&q={query}`

## Running Commands

Scholar commands can also be run interactively via the command line, which use a 
Flask test request context to execute the same HTTP request flow and display the 
generated redirect URL:

```bash
sch search gh
https://github.com
sch search gh search adammillerio/sch test search
https://github.com/search?type=code&q=repo:adammillerio%2Fsch+test+search
```

## Defining Commands
Commands are organized in Python source files which register commands to the root codex.

An example root codex definition file looks like this:

```python
#!/usr/bin/env python3
from sch import codex


@codex.command("gh")
def github(*args: str) -> str:
    """go to github"""

    return "https://github.com"

```

All commands have the same signature, any amount of strings as arguments, which 
generates another string. All actual HTTP redirection is handled by Flask. In this 
case, this is just a bookmark that makes `gh` go to the home page of GitHub:

```bash
sch search gh
https://github.com
```

This pattern is common enough that there is an `add_bookmark` command for quick 
registration:
```python
from sch import codex

codex.add_bookmark("gh", "https://github.com", "github git host")
```

## Accessing Arguments

All arguments to commands are strings, but they can be arbitrarily named as well
as dynamic:
```python
from sch import codex

@codex.command("gh")
def github(repo: str, *args: str) -> str:
    """go to github or view a repo"""

    if repo:
        return f"https://github.com/{repo}"
    else:
        return "https://github.com"
```

Now supplying a repo goes to the repo page as expected:

```bash
sch search gh adammillerio/sch
https://github.com/adammillerio/sch
```

## Sub-Commands
Commands can have other Commands registered under them in order to handle specific 
named parameters:

```python
from sch import query_args

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
```

This registers specific handlers for `gh search` and `gh search all`, which are reflected in the tree:
```bash
sch search gh sch_tree
gh - go to github or a view a repo
+-- search - search a github repo
   +-- all - search all of github
```

And also implements the last two search commands:
```bash
sch search gh search adammillerio/sch search query
https://github.com/search?type=code&q=repo:adammillerio%2Fsch+search+query
./sch.sh gh search all search query
sch search gh search all search query
https://github.com/search?type=code&q=search+query
```

These are search "proxies", which are basically just commands which take up all
the unused arguments as `*args` and sends them off as a search to a specific
place, such as GitHub. This is done via the `query_args` utility function.

For ease of use, there is also an `add_search` command for adding searches, similar
to `add_bookmark`.

# Advanced Usage
## Composing Commands
Commands can be composed without being registered to Scholar via the "generic" 
command decorator. For example, to make a factory for code bookmarks that generates 
GitHub and hosted doc links:

```python
from sch import codex, command, Command, format_doc

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
```

Which registers code bookmark sets for click and flask:
```bash
sch search click
https://github.com/pallets/click
sch search click docs
https://click.palletsprojects.com/en/8.1.x
sch search flask
https://github.com/pallets/flask
sch search flask docs
https://flask.palletsprojects.com/en/3.0.x/
```

Additionally, the `format_doc` utility decorator can be used to format the 
Command's docstring after definition to provide context specific `sch_help` 
and `sch_tree` information.

## Longform Command Help

To provide longform command help, a docstring can be provided:
```python
from sch import codex

@codex.command("gh")
def github(repo: str, *args: str) -> str:
    """go to github or a view a repo
    
    If a repo is provided, go to the repo on GitHub.

    If no repo is provided, go to the GitHub homepage.
    """

    if repo:
        return f"https://github.com/{repo}"
    else:
        return "https://github.com"
```

The first line of the docstring will become the command short help, which will 
display in the sch_tree:
```bash
sch search gh sch_tree
gh - go to github or a view a repo
+-- search - search a github repo
   +--all - search all of github
```

The entire docstring will be printed if `sch_help` is the first argument to any command:
```bash
sch search gh sch_help
def sch gh(repo: Optional[str] = None) -> str:

        go to github or a view a repo
        
        if repo:
            return https://github.com/{repo}
        else:
            return https://github.com
```

## Command Aliases

Commands can have aliases, which are alternative names that can be used during
command resolution:

```python
from sch import codex

@codex.command("help", aliases=["man"])
def help() -> str:
    return "/sch?s=sch_help"
```

```bash
sch search help sch_help      
def sch help{man}() -> str:
        return /sch?s=sch_help

sch search help         
/sch?s=sch_help

sch search man 
/sch?s=sch_help
```

Any command aliases will be displayed in curly braces next to the command name.

## Command Tags

As an alternative method of organization, commands can be tagged on creation or
during registration:

```python
from sch import codex

@codex.command("google", tags=["google"])
def google() -> str:
    """google search""""

    return "https://google.com"


@google.command("drive", tags=["drive"])
def google_drive() -> str:
    """google drive"""

    return "https://drive.google.com"


@codex.command("youtube", tags=["google", "youtube"])
def youtube() -> str:
    """youtube"""

    return "https://youtube.com"
```

Tags can be used to filter the tree of commands:

```bash
sch search --tag google sch_tree
sch - scholar search engine
|-- google - google search
|   +-- drive - google drive
+-- youtube - youtube

sch search --tag drive sch_tree
sch - scholar search engine
+-- google - google search
   +-- drive - google drive

sch search --tag youtube sch_tree
sch - scholar search engine
+-- youtube - youtube
```

Subcommands inherit the tags of their parent command. For example, the `google drive`
command has both the `drive` tag, and the `google` tag from the parent command.

In the web UI, all tags defined under the current view of commands will be shown
at the top. Clicking any tag will manually filter to only that tag.

## Default Command

If a command cannot be resolved during a query, a 404 is returned to the user. Scholar
can be configured to instead run a default command with all of the provided
arguments:

```python
from sch import codex, query_args


# Default all not found commands to Google search
@codex.default_command()
def default_cmd(*args: str) -> str:
    return f"https://google.com/search?q={query_args(*args)}"
```

The default command is like any other command except that it is always called
with ALL arguments to the query:

```
sch search this is not a real command
https://google.com/search?q=this+is+not+a+real+command
```

## Auto-Reloading

To enable auto-reloading of the codex during development, run `sch` with the
debug option, which enable's Flask's [Debug Mode](https://flask.palletsprojects.com/en/2.3.x/debugging/):

```bash
sch --debug run
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 275-051-761
127.0.0.1 - - [13/May/2024 23:02:25] "GET / HTTP/1.1" 302 -
127.0.0.1 - - [13/May/2024 23:02:25] "GET /sch?s=sch_tree HTTP/1.1" 200 -
 * Detected change in '/Users/aemiller/sch/example/base.py', reloading
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 275-051-761
```

## Exposing to the Internet
Sometimes it is useful to expose sch to the internet, ie to be used with mobile 
devices. To do this, first install a production WSGI server like Waitress:

```bash
pip install waitress
```

Then use the `waitress-serve` CLI to load and serve the Flask server:

```bash
waitress-serve --port 5000 --call app:create_app
```

More info on using Flask with Waitress is available in the [Flask Docs](https://flask.palletsprojects.com/en/2.3.x/deploying/waitress/)

The WSGI server itself can then be exposed to the internet via reverse proxy via
https. Be sure to change the URL scheme when doing this or generated URLs will
be incorrect:

```bash
waitress-serve --port 5000 --url-scheme https --call app:create_app
```

## Other Scholar Instances

Other Scholar instances can be added like any other search engine:

```python
codex.add_search(
    "foo",
    "http://foo.local:8432/sch?s=",
    "http://foo.local:8432/sch?s=sch_tree",
    "foo controller",
    disable_tree=True,
    disable_help=True,
)
```

The built-in tree and help commands are also disabled, so that they can be passed
through and handled by the remote instance. This is shown with an asterisk next
to the command options in the menu:
```
foo - foo controller ?* >*
```

Searches prefixed with `foo` will now be passed through:

```bash
smn sch foo
http://foo.local:8432/sch?s=sch_tree
smn sch foo test search
http://foo.local:8432/sch?s=test+search
```

This pattern is useful for exposing quick access to local information and tasks 
on remote hosts.

# Development

Install in development mode:
```bash
pip3 install -e '.[dev]'
```

## Type Checking

Ensure no type errors are present with [pyre](https://github.com/facebook/pyre-check):

```bash
pyre check              
ƛ No type errors found
```

**Note**: Pyre daemonizes itself on first run for faster subsequent executions. Be
sure to shut it down with `pyre kill` when finished.

## Formatting

Format code with the [ruff](https://github.com/astral-sh/ruff) formatter:

```bash
ruff
8 files left unchanged
```
