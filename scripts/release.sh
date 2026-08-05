#!/bin/bash
# Cut a new release: bump version, prepend changelog, commit, tag, push.
# Run from the repo root:
#   ./scripts/release.sh [patch|minor|major] [--dry-run]
#
# Pushing the vX.Y.Z tag triggers .github/workflows/build.yml, which builds
# the .deb and attaches it to a new GitHub Release automatically.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTROL="$REPO_ROOT/packaging/control"
INIT_FILE="$REPO_ROOT/simple_yt_downloader/__init__.py"
CHANGELOG="$REPO_ROOT/packaging/changelog"
MAINTAINER="MD. Mahmudul Hasan <mdhasan0078@users.noreply.github.com>"

MODE="patch"
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    patch|minor|major) MODE="$arg" ;;
    --dry-run) DRY_RUN=1 ;;
    *) echo "usage: $0 [patch|minor|major] [--dry-run]" >&2; exit 1 ;;
  esac
done

OLD_VERSION=$(grep -oP '(?<=^Version: ).*' "$CONTROL")
IFS='.' read -r MAJOR MINOR PATCH <<< "$OLD_VERSION"
case "$MODE" in
  patch) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
  minor) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
  major) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
esac

if [ "$DRY_RUN" -ne 1 ] && [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
  echo "error: working tree not clean (commit or stash first)" >&2
  exit 1
fi

PREV_TAG=$(git -C "$REPO_ROOT" describe --tags --abbrev=0 2>/dev/null || true)
if [ -n "$PREV_TAG" ]; then
  LOG=$(git -C "$REPO_ROOT" log --oneline --no-decorate "$PREV_TAG..HEAD")
else
  LOG=$(git -C "$REPO_ROOT" log --oneline --no-decorate)
fi
BULLETS=$(printf '%s\n' "$LOG" | sed 's/^/  * /')

DATE=$(date -R -u)
ENTRY=$(cat <<EOF
simple-yt-downloader ($NEW_VERSION) unstable; urgency=medium

$BULLETS

 -- $MAINTAINER  $DATE

EOF
)

echo "Releasing v$NEW_VERSION (from v$OLD_VERSION, $MODE)"
echo "Changes since ${PREV_TAG:-the beginning}:"
printf '%s\n' "$LOG"

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "Would write the following changelog entry:"
  printf '%s\n' "$ENTRY"
  exit 0
fi

sed -i "s/^Version: .*/Version: $NEW_VERSION/" "$CONTROL"
sed -i "s/^__version__ = .*/__version__ = \"$NEW_VERSION\"/" "$INIT_FILE"
{ printf '%s' "$ENTRY"; cat "$CHANGELOG"; } > "$CHANGELOG.tmp"
mv "$CHANGELOG.tmp" "$CHANGELOG"

git -C "$REPO_ROOT" add packaging/control packaging/changelog simple_yt_downloader/__init__.py
git -C "$REPO_ROOT" commit -m "Bump version to $NEW_VERSION"
git -C "$REPO_ROOT" tag "v$NEW_VERSION"
git -C "$REPO_ROOT" push origin HEAD
git -C "$REPO_ROOT" push origin "v$NEW_VERSION"

echo "Pushed v$NEW_VERSION. GitHub Actions is building the .deb and will"
echo "attach it to the release. Verify at:"
echo "  https://github.com/MDHasan0078/smart-downloader/releases"
