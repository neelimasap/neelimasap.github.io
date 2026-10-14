#!/bin/sh
# Full refresh: LinkedIn -> H-1B -> ATS sources + render index.html
cd "$(dirname "$0")" && mkdir -p prev && cp leads.json jobs.json index.html prev/ && (timeout 240 python3 refresh.py || echo "LinkedIn step timed out; reusing last jobs.json") && python3 h1b.py && (python3 community.py || true) && python3 sources.py && cp leads.json leads_raw.json && python3 verify.py && python3 dashboard.py
