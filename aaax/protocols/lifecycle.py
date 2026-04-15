from __future__ import annotations

from typing import Literal

from aaax._vendor import ensure_vendor_paths

ensure_vendor_paths()

from sssn.core.channel import MessageContent


class LifecycleCommand(MessageContent):
    command: Literal["revoke", "pause", "resume", "drain"]
    system_id: str
    timeout: float = 30.0


class LifecycleResult(MessageContent):
    command: str
    system_id: str
    status: str
    reason: str = ""
