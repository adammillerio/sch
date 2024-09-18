# Tools

# complete.sh

`complete.sh` provides an interactive completion menu using the `sch_complete`
command and the fuzzy-find (fzf) tool: https://github.com/junegunn/fzf

## Annotated Script

```bash
# Get user supplied query, defaulting to empty string
QUERY=${@:-""}

sch search sch_complete | \
    fzf \
        # Set query to user supplied query, if any
        --query "${QUERY}" \
        # Set fzf prompt to "sch "
        --prompt 'sch ' \
        # Only allow one selection
        --no-multi \
        # Draw border around fzf window
        --border \
        # Bind Ctrl+/ to toggle visibility of the preview window
        --bind 'ctrl-/:toggle-preview' \
        # Tiebreak on "begin" search criteria
        # aka the result with the most matches in the query, starting from
        # the left (beginning), as well as the line with the shorter matched
        # "chunk" of consecutive characters
        --tiebreak 'begin,chunk' \
        # Rebind enter to return query even if there is no match, this is used
        # to submit the query to the default command in sch.
        # https://github.com/junegunn/fzf/issues/1693#issuecomment-699642792
        # cut -f 1 <<< {q} - Remove alias field if present
        # ie "homebrew cask\t{casks}" -> "homebrew cask"
        # See fzf "user actions" for more info
        --bind 'enter:replace-query+transform-query(cut -f 1 <<< {q})+print-query' \
        # Rebind tab to replace the query with the selected command, minus
        # any aliases, so that it can either be confirmed with another enter,
        # with any arguments. This puts the selection at position 1, so it
        # will move to position 2 to allow for multiple tab presses to cycle
        --bind 'tab:replace-query+transform-query(cut -f 1 <<< {q})+pos(2)' \
        # Use 1 space for displaying tab in alias separator
        --tabstop 1 \
        # Display the sch_help for the selection as in the preview window
        # {n] represents the current selected index. It is >= 0 when there
        # are selections available, and empty ("") otherwise.
        # {} is the current selection
        # {q} is the query
        # This will show help for the selected command if there are selections
        # and fallback to the query string otherwise. This keeps the help
        # for the command visible even after you start entering arguments
        --preview '[[ {n} ]] && sch search {} sch_help || sch search {q} sch_help' | \
    # Run sch search with fzf selection over stdin
    xargs sch search
```

