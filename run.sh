#!/bin/sh
source_dir="$(dirname -- "$0")/src"
if [ "${1-}" = "--interpret" ]; then
    shift
    exec python3 "$source_dir/interpreter.py" "$@"
fi
exec python3 "$source_dir/assembler.py" "$@"
