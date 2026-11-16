#!/bin/sh
set -eu

version=${1:-0.5.0}
case "$version" in *[!0-9.]*|'') echo 'Supply a stable x.y.z version.' >&2; exit 1;; esac
printf '%s\n' "$version" | awk -F. 'NF != 3 || $1 !~ /^[0-9]+$/ || $2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ {exit 1}'
platform=$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')
case "$platform" in linux/amd64|linux/arm64) arch=${platform#linux/};; *) echo "Unsupported Docker platform: $platform" >&2; exit 1;; esac
asset="tunet-agents-mcp_${version}_linux_${arch}.docker.tar.gz"
if test -n "${2:-}"; then
    download=$(cd "$2" && pwd -P)
else
    temp_root=$(cd "${TMPDIR:-/tmp}" && pwd -P)
    download=$(mktemp -d "$temp_root/tunet-container-XXXXXXXX")
    case "$download" in "$temp_root"/tunet-container-*) ;; *) exit 1;; esac
    trap 'rm -rf -- "$download"' EXIT HUP INT TERM
    GH_PROMPT_DISABLED=1 gh release download "v$version" --repo Tunet-xyz/terraform-agents --pattern "$asset" --pattern SHA256SUMS --dir "$download"
fi
expected=$(awk -v asset="$asset" '{sub(/\r$/, "")} $2 == asset {print $1}' "$download/SHA256SUMS")
test "${#expected}" = 64 || { echo 'The checksum manifest needs one valid entry for this image.' >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$download/$asset" | awk '{print $1}')
else
    actual=$(shasum -a 256 "$download/$asset" | awk '{print $1}')
fi
test "$actual" = "$expected" || { echo 'Image checksum verification failed.' >&2; exit 1; }
docker load --input "$download/$asset"
docker tag "tunet-agents-mcp:${version}-linux-${arch}" "tunet-agents-mcp:$version"
echo "MCP image ready: tunet-agents-mcp:$version"
