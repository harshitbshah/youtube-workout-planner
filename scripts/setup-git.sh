#!/usr/bin/env bash
# Run once after cloning to configure the local git merge driver.
# This ensures workout_library.db always defers to the remote version
# (committed by GitHub Actions) instead of causing merge conflicts.

git config merge.keeptheirs.name "Always keep remote version"
git config merge.keeptheirs.driver 'cp -f "%B" "%A"'

echo "Git merge driver configured. No more DB conflicts on pull."
