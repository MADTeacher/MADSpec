#!/usr/bin/env bash
set -euo pipefail

# create-github-release.sh
# Creates a GitHub release with all template archives

VERSION="$1"

if [[ ! -f .genreleases/release-notes.txt ]]; then
  echo "Error: release-notes.txt not found" >&2
  exit 1
fi

# Release artifact paths for MADSpec's 5 agents × 2 scripts = 10 files
gh release create "$VERSION" \
  --title "$VERSION" \
  --notes-file .genreleases/release-notes.txt \
  .genreleases/madspec-template-cursor-agent-sh-"$VERSION".zip \
  .genreleases/madspec-template-cursor-agent-ps-"$VERSION".zip \
  .genreleases/madspec-template-opencode-sh-"$VERSION".zip \
  .genreleases/madspec-template-opencode-ps-"$VERSION".zip \
  .genreleases/madspec-template-kilocode-sh-"$VERSION".zip \
  .genreleases/madspec-template-kilocode-ps-"$VERSION".zip \
  .genreleases/madspec-template-roo-sh-"$VERSION".zip \
  .genreleases/madspec-template-roo-ps-"$VERSION".zip \
  .genreleases/madspec-template-sourcecraft-sh-"$VERSION".zip \
  .genreleases/madspec-template-sourcecraft-ps-"$VERSION".zip \
  .genreleases/madspec-template-copilot-sh-"$VERSION".zip \
  .genreleases/madspec-template-copilot-ps-"$VERSION".zip

echo "Created GitHub release $VERSION"

