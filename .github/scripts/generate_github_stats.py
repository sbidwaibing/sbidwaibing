#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime, timedelta

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
OWNER = os.environ.get("GITHUB_OWNER", "sbidwaibing")
README_PATH = os.environ.get("README_PATH", "README.md")

HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"
HEADERS["Accept"] = "application/vnd.github+json"

API = "https://api.github.com"

def paged_get(url, params=None):
    """Yield items across paginated GETs (per_page=100)."""
    if params is None:
        params = {}
    params["per_page"] = 100
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            # not a list -> return once
            yield data
            return
        if not data:
            break
        for item in data:
            yield item
        if len(data) < params["per_page"]:
            break
        page += 1

def get_repos(owner):
    url = f"{API}/users/{owner}/repos"
    return list(paged_get(url))

def sum_stars(repos):
    return sum(r.get("stargazers_count", 0) for r in repos)

def count_commits_for_repo(owner, repo_name, since=None):
    # Count commits authored by OWNER (commits with author=owner login)
    # Note: This counts commits where the commit author is the same login.
    url = f"{API}/repos/{owner}/{repo_name}/commits"
    params = {"author": owner}
    if since:
        params["since"] = since
    count = 0
    for _ in paged_get(url, params=params):
        count += 1
    return count

def search_count(query):
    # Uses the search API which returns total_count
    url = f"{API}/search/issues"
    params = {"q": query, "per_page": 1}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("total_count", 0)

def main():
    print(f"Generating stats for GitHub user: {OWNER}")
    repos = get_repos(OWNER)
    total_stars = sum_stars(repos)
    print(f"Found {len(repos)} repos. Total stars: {total_stars}")

    # commits last year
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    since_iso = one_year_ago.isoformat() + "Z"

    total_commits_last_year = 0
    total_commits_all_time = 0

    for r in repos:
        name = r["name"]
        try:
            c_last = count_commits_for_repo(OWNER, name, since=since_iso)
            c_all = count_commits_for_repo(OWNER, name, since=None)
            total_commits_last_year += c_last
            total_commits_all_time += c_all
        except requests.HTTPError as e:
            print(f"Warning: failed to count commits for {name}: {e}")

    # PRs authored (and merged)
    # Use the Search API: type:pr author:OWNER
    prs_authored_q = f"type:pr author:{OWNER}"
    prs_merged_q = f"type:pr author:{OWNER} is:merged"

    try:
        total_prs = search_count(prs_authored_q)
        total_prs_merged = search_count(prs_merged_q)
    except requests.HTTPError as e:
        print("Warning: search API failed:", e)
        total_prs = 0
        total_prs_merged = 0

    # Prepare replacement block
    stats_block = (
        "<!-- GITHUB-STATS:START -->\n"
        "### Sukrut's · Github Stats\n"
        " | Metrics                     | Count |\n"
        " |-----------------------------|-------|\n"
        f"|> Total Stars earned         | `{total_stars}` |\n"
        f"|> Total Commits (All Time)   | `{total_commits_all_time}` |\n"
        f"|> Total Commits (Last Year)  | `{total_commits_last_year}` |\n"
        f"|> Total PRs authored         | `{total_prs}` |\n"
        f"|> Total PRs merged           | `{total_prs_merged}` |\n"
        "<!-- GITHUB-STATS:END -->\n"
    )

    # Read README and replace between markers
    if not os.path.exists(README_PATH):
        print(f"Error: README not found at {README_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    start_marker = "<!-- GITHUB-STATS:START -->"
    end_marker = "<!-- GITHUB-STATS:END -->"

    if start_marker in readme and end_marker in readme:
        pre, _, rest = readme.partition(start_marker)
        _, _, post = rest.partition(end_marker)
        new_readme = pre + stats_block + post
    else:
        # markers not found, add block at top
        new_readme = stats_block + "\n" + readme

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_readme)

    print("README updated with new GitHub stats.")

if __name__ == "__main__":
    main()
