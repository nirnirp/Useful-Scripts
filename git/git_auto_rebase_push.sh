#!/bin/bash

# The script detects uncommitted changes in the current Git repository,
# stages and commits them with a summary message (suitable for w.i.p work),
# rebases the current branch to clean up the commit history,
# and then safely force-pushes the changes to the remote repository.
# Wakachung / Nirp (c)

# Check for uncommitted changes
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Uncommitted changes detected."

    # Stage all changes
    git add .

    # Create a summary commit message
    commit_msg=$(git diff --cached --name-status | head -n 3 | sed "s/^\([A-Z]\)\(.*\)/\1: \2/" | tr '\n' '; ' | sed "s/; $/./")
    git commit -m "Summary of changes: $commit_msg"

    # Get the current branch
    current_branch=$(git branch --show-current)

    # Get the hash of the first commit in the current branch
    first_commit=$(git log --oneline --reverse | grep -m 1 -E "^[\da-f]{7} .*" | cut -d' ' -f1)

    # Rebase to clean up commit history
    git fetch origin
    git rebase -i "$first_commit^"

    # Push changes to the remote repository
    git push --force-with-lease --force-if-includes origin HEAD:"$current_branch"

    echo "Changes pushed successfully."

else
    echo "No changes detected."
fi
