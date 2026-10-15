#!/bin/sh
# Optional command links for an unpacked, relocatable toolchain.
set -eu

case "${1:-}" in
    "") prefix=/usr/local ;;
    --prefix)
        [ "$#" -eq 2 ] || { echo "Usage: $0 [--prefix DIR]" >&2; exit 1; }
        prefix=$2
        ;;
    *) echo "Usage: $0 [--prefix DIR]" >&2; exit 1 ;;
esac

script=$(readlink -f -- "$0")
toolchain=$(dirname -- "$script")
[ -x "$toolchain/bin/clang" ] || { echo "Cannot find bin/clang beside this installer." >&2; exit 1; }
mkdir -p -- "$prefix/bin"
destination=$(CDPATH= cd -- "$prefix/bin" && pwd -P)

# Check all names before making changes; preserve existing installations.
for executable in "$toolchain"/bin/*; do
    [ -f "$executable" ] && [ -x "$executable" ] || continue
    name=${executable##*/}
    link=$destination/$name
    if [ -e "$link" ] || [ -L "$link" ]; then
        if [ ! -L "$link" ] || [ "$(readlink -- "$link")" != "$executable" ]; then
            echo "Already exists: $link. Remove that command link before installing." >&2
            exit 1
        fi
    fi
done

for executable in "$toolchain"/bin/*; do
    [ -f "$executable" ] && [ -x "$executable" ] || continue
    link=$destination/${executable##*/}
    [ -L "$link" ] || ln -s -- "$executable" "$link"
done

echo "Installed command links in $destination. Keep the toolchain at $toolchain."
echo "Run: clang --version"
