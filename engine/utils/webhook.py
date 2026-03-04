"""
Webhook alert dispatcher
Sends high-risk token alerts to Discord/Telegram channels

Status: WIP — Discord integration first, Telegram next
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class AlertPayload:
    ca: str
    score: float
    grade: str
    flags: list[str]
    chain: str = "solana"


class WebhookDispatcher:
    """Dispatches threat alerts to configured webhook endpoints."""

    def __init__(self, discord_url: Optional[str] = None, telegram_bot_token: Optional[str] = None):
        self.discord_url = discord_url
        self.telegram_bot_token = telegram_bot_token
        self._queue: asyncio.Queue[AlertPayload] = asyncio.Queue()

    async def send_alert(self, payload: AlertPayload) -> bool:
        """Send alert if score exceeds threshold."""
        if payload.score < 7.0:
            return False

        # TODO: implement Discord webhook POST
        # TODO: implement Telegram bot sendMessage
        logger.info(
            f"[ALERT] {payload.ca[:8]}... score={payload.score} "
            f"grade={payload.grade} flags={payload.flags}"
        )
        await self._queue.put(payload)
        return True

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()
