#!/usr/bin/env bash
set -euo pipefail

# create-github-release.sh
# Creates a GitHub release with all template archives

VERSION="$1"

if [[ ! -f .genreleases/release-notes.txt ]]; then
  echo "Error: release-notes.txt not found" >&2
  exit 1
fi

# Release artifact paths for MADSpec's 6 agents
gh release create "$VERSION" \
  --title "$VERSION" \
  --notes-file .genreleases/release-notes.txt \
  .genreleases/madspec-template-cursor-agent-"$VERSION".zip \
  .genreleases/madspec-template-opencode-"$VERSION".zip \
  .genreleases/madspec-template-kilocode-"$VERSION".zip \
  .genreleases/madspec-template-roo-"$VERSION".zip \
  .genreleases/madspec-template-sourcecraft-"$VERSION".zip \
  .genreleases/madspec-template-copilot-"$VERSION".zip

echo "Created GitHub release $VERSION"
