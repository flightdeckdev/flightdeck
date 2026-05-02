#!/usr/bin/env bash
# Two-step human-in-the-loop promote when flightdeck.yaml sets promotion_requires_approval: true.
# Usage:
#   promote_with_approval.sh request <release_id> <env> <window> "<reason>"
#   promote_with_approval.sh confirm <request_id> "<approval_reason>"
#
# The "request" step prints request_id=… for capture in CI logs or a follow-up job.
set -euo pipefail

cmd="${1:?command: request | confirm}"
shift

case "$cmd" in
  request)
    rel="${1:?release_id}"
    env="${2:?environment}"
    win="${3:?window}"
    reason="${4:?reason}"
    flightdeck release promote-request "$rel" --env "$env" --window "$win" --reason "$reason"
    ;;
  confirm)
    rid="${1:?request_id}"
    areason="${2:?approval_reason}"
    flightdeck release promote-confirm "$rid" --approval-reason "$areason"
    ;;
  *)
    echo "usage: $0 request <release_id> <env> <window> \"<reason>\"" >&2
    echo "       $0 confirm <request_id> \"<approval_reason>\"" >&2
    exit 2
    ;;
esac
