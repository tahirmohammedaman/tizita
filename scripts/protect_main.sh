#!/usr/bin/env bash
# Protect main (SPEC §15): require the `ci` check and a PR, 0 reviews, no force-push/deletion.
# GitHub Free only allows this on PUBLIC repos; run it right after making the repo public.
set -euo pipefail
repo="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
gh api -X PUT "repos/${repo}/branches/main/protection" --input - <<'JSON'
{"required_status_checks": {"strict": false, "contexts": ["ci"]},
 "enforce_admins": true,
 "required_pull_request_reviews": {"required_approving_review_count": 0},
 "restrictions": null, "allow_force_pushes": false, "allow_deletions": false}
JSON
echo "main protected on ${repo}"
