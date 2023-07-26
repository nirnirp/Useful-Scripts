#!/bin/bash
find . -name 'go.mod' -print0 | while IFS= read -r -d '' line; do
    echo "Running go mod tidy in $(dirname "$line")"
    pushd "$(dirname "$line")" > /dev/null
    go mod tidy
    popd > /dev/null
done
