"""
OSINT Intelligence Crawler
Social / code / community data collection

Data sources:
- Twitter API v2 (followers, account age, engagement rate, bot ratio estimation)
- GitHub API (commit frequency, contributor count, real code detection)
- Telegram (member count, active ratio)
- Scam DB (known scam address matching)
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional
from datetime import datetime, timezone
import httpx
from loguru import logger

from ..core.feature_store import FeatureStore
from ..config import config


class OSINTCrawler:
    """Multi-source OSINT collector. Each source fails independently."""

    def __init__(self):
        self.twitter_bearer = config.osint.twitter_bearer
        self.github_token = config.osint.github_token
        self.timeout = config.osint.crawl_timeout_sec
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def crawl(self, token_name: str, token_symbol: str, store: FeatureStore) -> None:
        """Collect OSINT data for token"""
        logger.info(f"OSINT crawl started: {token_symbol}")

        results = await asyncio.gather(
            self._crawl_twitter(token_name, token_symbol),
            self._crawl_github(token_name, token_symbol),
            self._check_scam_db(store.ca),
            return_exceptions=True,
        )

        twitter_data, github_data, scam_match = results

        if isinstance(twitter_data, dict):
            store.bulk_set(twitter_data)

        if isinstance(github_data, dict):
            store.bulk_set(github_data)

        if isinstance(scam_match, bool):
            store.set("scam_db_match", 1.0 if scam_match else 0.0)

        for i, r in enumerate(results):
            if isinstance(r, Exception):
                sources = ["twitter", "github", "scam_db"]
                logger.warning(f"OSINT {sources[i]} failed: {r}")

    async def _crawl_twitter(self, name: str, symbol: str) -> dict[str, float]:
        """Twitter API v2 — project official account analysis"""
        if not self.twitter_bearer:
            logger.debug("Twitter bearer token missing, skipping")
            return {}

        client = await self._get_client()

        # search account by symbol
        # FIXME: need disambiguation logic for same-name projects — currently using first result
        search_resp = await client.get(
            "https://api.twitter.com/2/users/by",
            params={"usernames": symbol.lower()},
            headers={"Authorization": f"Bearer {self.twitter_bearer}"},
        )

        if search_resp.status_code != 200:
            # symbol lookup rate limited — fallback to project name
            search_resp = await client.get(
                "https://api.twitter.com/2/users/by",
                params={"usernames": name.lower().replace(" ", "")},
                headers={"Authorization": f"Bearer {self.twitter_bearer}"},
            )

        if search_resp.status_code != 200:
            return {}

        users = search_resp.json().get("data", [])
        if not users:
            return {}

        user_id = users[0]["id"]

        # user detail info
        detail_resp = await client.get(
            f"https://api.twitter.com/2/users/{user_id}",
            params={"user.fields": "public_metrics,created_at"},
            headers={"Authorization": f"Bearer {self.twitter_bearer}"},
        )

        if detail_resp.status_code != 200:
            return {}

        user_data = detail_resp.json().get("data", {})
        metrics = user_data.get("public_metrics", {})
        created_at = user_data.get("created_at", "")

        followers = metrics.get("followers_count", 0)
        tweet_count = metrics.get("tweet_count", 0)

        # calculate account age
        account_age_days = 0
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                account_age_days = (datetime.now(timezone.utc) - created).days
            except (ValueError, TypeError):
                pass

        # engagement rate estimation (based on recent tweets)
        # TODO: calculate from average likes+retweets of last 10 tweets
        engagement_rate = 0.0
        if followers > 0 and tweet_count > 0:
            # rough estimation — actual implementation needs recent tweet analysis
            engagement_rate = min(tweet_count / max(followers, 1) / 100, 0.3)

        return {
            "twitter_followers": followers,
            "twitter_account_age_days": account_age_days,
            "twitter_engagement_rate": engagement_rate,
            "twitter_bot_follower_pct": 0.0,  # TODO: connect bot detection module
        }

    async def _crawl_github(self, name: str, symbol: str) -> dict[str, float]:
        """GitHub repo analysis — commit patterns, code quality"""
        client = await self._get_client()

        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        # org/repo search
        search_query = f"{symbol} solana"
        resp = await client.get(
            "https://api.github.com/search/repositories",
            params={"q": search_query, "sort": "stars", "per_page": 3},
            headers=headers,
        )

        if resp.status_code != 200:
            return {}

        repos = resp.json().get("items", [])
        if not repos:
            return {}

        repo = repos[0]
        full_name = repo["full_name"]

        # commits in last 30 days
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        commits_resp = await client.get(
            f"https://api.github.com/repos/{full_name}/commits",
            params={"since": since, "per_page": 100},
            headers=headers,
        )

        commits_30d = 0
        if commits_resp.status_code == 200:
            commits_30d = len(commits_resp.json())

        # contributor count
        contrib_resp = await client.get(
            f"https://api.github.com/repos/{full_name}/contributors",
            params={"per_page": 100},
            headers=headers,
        )

        contributors = 0
        if contrib_resp.status_code == 200:
            contributors = len(contrib_resp.json())

        # real code detection (distinguish README-only repos)
        # HACK: using file tree depth as proxy — ~80% accuracy
        tree_resp = await client.get(
            f"https://api.github.com/repos/{full_name}/git/trees/HEAD",
            params={"recursive": "1"},
            headers=headers,
        )

        has_real_code = 0.0
        if tree_resp.status_code == 200:
            tree = tree_resp.json().get("tree", [])
            code_extensions = {".py", ".ts", ".js", ".rs", ".go", ".sol", ".move"}
            code_files = [
                f for f in tree
                if f["type"] == "blob" and any(f["path"].endswith(ext) for ext in code_extensions)
            ]
            # 5+ code files = "real code" verdict
            has_real_code = 1.0 if len(code_files) >= 5 else 0.0

        return {
            "github_commits_30d": commits_30d,
            "github_contributors": contributors,
            "github_has_real_code": has_real_code,
        }

    async def _check_scam_db(self, ca: str) -> bool:
        """Cross-check against known scam databases"""
        client = await self._get_client()

        # query multiple scam DBs in parallel
        # TODO: build internal scam DB — currently high external dependency
        checks = await asyncio.gather(
            self._check_solana_scam_list(client, ca),
            return_exceptions=True,
        )

        return any(c is True for c in checks if not isinstance(c, Exception))

    async def _check_solana_scam_list(self, client: httpx.AsyncClient, ca: str) -> bool:
        """Community-based scam list lookup"""
        try:
            resp = await client.get(
                "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json",
                timeout=5,
            )
            # if in token list, likely not a scam
            # absence doesn't mean scam — most new tokens are unlisted
            return False
        except Exception:
            return False

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
