#!/usr/bin/env python3
from functools import cache

from flask import url_for
from pypandoc import convert_text

from sch.commands import SCH_INPUT

SCH_HELP = """\
# scholar - a macro search bar [>]({full_url}?s=sch_tree)

## what is this?

Scholar (sch) is a lightweight, self-hosted, and programmable replacement for
in-browser search. It consists of a "command prompt" which takes input
via the browser search bar in order to generate a HTTP 302 redirect URL.

An interactive REPL is available at the top of all pages. To view a tree of all
commands, enter `>`:

[`sch >`]({full_url}?s=sch_tree) -> [{full_url}?s=sch_tree]({full_url}?s=sch_tree)

To return to this help page, enter `?`:

[`sch ?`]({full_url}?s=sch_help) -> [{full_url}?s=sch_help]({full_url}?s=sch_help)

## how to run

Scholar is open source and is intended to be run locally:

[`sch gh adammillerio/sch`]({full_url}?s=gh+adammillerio/sch) -> [https://github.com/adammillerio/sch](https://github.com/adammillerio/sch)

[`README.md`](https://github.com/adammillerio/sch/blob/main/README.md) provides a guide for getting started. This public instance can still
be used for demonstration purposes.

The public collection of codexes is also open source:

[`sch gh adammillerio/sch_public`]({full_url}?s=gh+adammillerio/sch_public) -> [https://github.com/adammillerio/sch_public](https://github.com/adammillerio/sch_public)

For instructions on how to set up Scholar in the browser, as well as more general
information on commands and usage, see below.

## how to use
### chrome(ium) browsers
Go to `chrome://settings/searchEngines` in the
address bar (must be typed manually).

Under `Site Search` select the `Add` button:

  * Name: `Scholar`
  * Shortcut: `sch`
  * URL: `{full_url}?s=%s`

Typing `sch` and pressing Tab will now use Scholar. To make it the default search
engine, select `Make default` in the `...` menu next to the search engine.

### firefox
Go to `about:config` in address bar.

Search for `browser.urlbar.update2.engineAliasRefresh`, then hit the `+` button
to set it to `true`.

Go to `about:preferences#search` in address bar

Under `Search Shortcuts` select the `Add` button:

  * Search engine name: `Scholar`
  * Engine URL: `{full_url}?s=%s`
  * Alias: `sch`

Typing `sch` and pressing Tab will now use Scholar. To make it the default search
engine, select `Scholar` as `Default Search Engine`.

### ios (safari)
Safari only lets you use Apple's defined search engines by default. To add
custom engines, install an extension app like xSearch:

[`sch xsearch`]({full_url}?s=xsearch) -> [https://apps.apple.com/us/app/xsearch-for-safari/id1579902068](https://apps.apple.com/us/app/xsearch-for-safari/id1579902068)

In the app, open the `Add Engine` dialog with the button in the top right:

  * Engine Name: `Scholar`
  * Shortcuts: `sch`
  * URL: `{full_url}?s=%s`

Prefixing searches with `sch` will now route them to Scholar.

To make all searches go to Scholar, open the app settings, then enable the
`Override Safari Engine` option:

  * Engine: `Scholar`
  * Override Mode: `Global`

## usage
### navigation
To view a full tree of available commands, use `>` (`sch_tree`):

[`sch >`]({full_url}?s=sch_tree) -> [{full_url}?s=sch_tree]({full_url}?s=sch_tree)

```
sch - scholar search engine
|-- hello - world
|-- gh - go to github or a repo
|   +-- search - search a github repo
|       +-- all - search all of github
```

To view the help for a given command, use `?` (`sch_help`) as the first argument:

[`sch gh ?`]({full_url}?s=gh+sch_help) -> [{full_url}?s=gh+sch_help]({full_url}?s=gh+sch_help)

**def** [gh]({full_url}?s=gh)`(repo: Optional[str] = None) -> str:`
```sch_docstring
    go to github or a view a repo
    
    if repo:
        return https://github.com/{{repo}}
    else:
        return https://github.com
```

To view a scoped tree, use `>` (`sch_tree`) as the first argument:

[`sch gh >`]({full_url}?s=gh+sch_tree) -> [{full_url}?s=gh+sch_tree]({full_url}?s=gh+sch_tree)

```
gh - go to github or a repo
+-- search - search a github repo
    +-- all - search all of github
```

### commands
Each entry represents a command that can be "executed" via the search bar. All 
commands serve URL redirects generated in response to input(s).

Go to the homepage of GitHub:

[`sch gh`]({full_url}?s=gh) -> [https://github.com](https://github.com)

Go to the pallets/click repo on GitHub:

[`sch gh pallets/click`]({full_url}?s=gh+pallets/click) -> [https://github.com/pallets/click](https://github.com/pallets/click)

Some commands take a dynamic amount of arguments and act as proxies to other
search tools:

[`sch g my google query`]({full_url}?s=g+my+google+query) -> [https://google.com/search?q=my+google+query](https://google.com/search?q=my+google+query)

Others combine named and dynamic arguments:

[`sch gh search all Command`]({full_url}?s=gh+search+all+Command) -> [https://github.com/search?type=code&q=Command](https://github.com/search?type=code&q=Command)

[`sch gh search pallets/click Command`]({full_url}?s=gh+search+pallets/click+Command) -> [https://github.com/search?type=code&q=repo:pallets/click+Command](https://github.com/search?type=code&q=repo%3Apallets%2Fclick+Command)

Others are just bookmarks to cool stuff:

[`sch aftermath`]({full_url}?s=aftermath) -> [https://aftermath.site](https://aftermath.site)

### txt mode

Scholar can be used in the terminal by passing `&sch_txt=true` to any command, which
will enable plain-text only output:

[`curl '{full_url}?s=gh+sch_help&sch_txt=true'`]({full_url}?s=gh+sch_help&sch_txt=true)
```sch_docstring
def gh(repo: Optional[str] = None) -> str:

        go to github or a view a repo
        
        if repo:
            return https://github.com/{{repo}}
        else:
            return https://github.com
```

[`curl '{full_url}?s=gh+sch_tree&sch_txt=true'`]({full_url}?s=gh+sch_tree&sch_txt=true)
```sch_docstring
gh - go to github or a view a repo
+-- search - search a github repo
   +--all - search all of github
```

It will also output the link instead of generating a 302 redirect:

[`curl '{full_url}?s=gh&sch_txt=true'`]({full_url}?s=gh&sch_txt=true)
```sch_docstring
https://github.com
```

## ready?

[`sch back`]({full_url}?s=back) -> [{full_url}?s=sch_tree]({full_url}?s=sch_tree)

``` {{=html}}
<title>sch?</title>
<style>
body {{ font-family: monospace; background-color: #002b36; max-width: 680px; margin: 0 auto; padding: 0 15; }}
input {{ background-color: #073642; color: #93a1a1; outline: none; width: 680px; margin-top: 15px; }}
p {{ color: #93a1a1; }}
code {{ color: #859900 }}
a {{ color: #cb4b16; text-decoration: none; }}
h1 {{ color: #859900; margin-top: 15px; }}
h2 {{ color: #dc322f; }}
h3 {{ color: #cb4b16; }}
li::marker {{ color: #586e75; }}
li {{ color: #93a1a1; }}
.sch_docstring code {{ color: #2aa198; }};
</style>
```
"""


@cache
def get_sch_help(output_format: str = "html") -> str:
    full_url = url_for("sch", _external=True)
    return convert_text(
        SCH_INPUT.format(scope="") + SCH_HELP.format(full_url=full_url),
        output_format,
        format="md",
        extra_args=["--wrap=auto"],
    )
