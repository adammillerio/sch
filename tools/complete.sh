#!/bin/bash
# complete.sh ${@}
# Perform an interactive scholar completion using the fuzzy-find (fzf) tool.
# Annotated version with argument explanations in tools/README.md
QUERY=${@:-""}

sch search sch_complete | \
    fzf \
        --query "${QUERY}" \
        --prompt 'sch ' \
        --no-multi \
        --border \
        --bind 'ctrl-/:toggle-preview' \
        --tiebreak 'begin,chunk' \
        --bind 'enter:replace-query+transform-query(cut -f 1 <<< {q})+print-query' \
        --bind 'tab:replace-query+transform-query(cut -f 1 <<< {q})+pos(2)' \
        --tabstop 1 \
        --preview '[[ {n} ]] && sch search {} sch_help || sch search {q} sch_help' | \
    xargs sch search

