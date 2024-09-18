#!/usr/bin/env python3
from sch import codex

TAGS = ["base"]


codex.add_bookmark(
    "help", "/sch?s=sch_help", "what is this?", tags=TAGS, aliases=["man"]
)
codex.add_bookmark("back", "/sch?s=sch_tree", "back to main tree", tags=TAGS)
codex.add_bookmark("sch", "/sch?s=sch_tree", "sch main tree", tags=TAGS)


codex.add_bookmark(
    "xsearch",
    "https://apps.apple.com/us/app/xsearch-for-safari/id1579902068",
    "safari search replacement app",
    tags=TAGS,
)

codex.add_bookmark("aftermath", "https://aftermath.site", "gaming blog", tags=["games"])
