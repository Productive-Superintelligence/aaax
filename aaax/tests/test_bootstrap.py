import pytest

from aaax.bootstrap import bootstrap_kernel
from aaax.config import AAAXConfig
from aaax.kernel import (
    ACTION_GATE_ID,
    CAPABILITY_REQUEST_ID,
    HEARTBEAT_ID,
    KERNEL_REPLIES_ID,
    LIFECYCLE_ID,
    MODULE_LOADER_ID,
)


@pytest.mark.asyncio
async def test_bootstrap_creates_governance_channels():
    kernel = await bootstrap_kernel(AAAXConfig())
    channel_ids = {channel.id for channel in kernel.all_channels}

    assert CAPABILITY_REQUEST_ID in channel_ids
    assert ACTION_GATE_ID in channel_ids
    assert KERNEL_REPLIES_ID in channel_ids
    assert MODULE_LOADER_ID in channel_ids
    assert LIFECYCLE_ID in channel_ids
    assert HEARTBEAT_ID in channel_ids
    assert kernel._setup_done is True
    assert kernel._libos is not None
