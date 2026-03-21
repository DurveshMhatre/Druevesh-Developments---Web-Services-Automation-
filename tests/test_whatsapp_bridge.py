"""Unit tests for the whatsapp-web.js bridge retry logic."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestBridgeRetry:
    """Tests for bridge.py retry logic."""

    async def test_send_message_success(self):
        """Successful send should return response data."""
        from phase2_whatsapp.whatsapp_web_js import bridge

        mock_response = {"status": "sent", "id": "abc123"}

        with patch.object(bridge, "_request_with_retry", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            result = await bridge.send_message("919876543210", "Hello!")

        assert result["status"] == "sent"

    async def test_send_message_queues_on_failure(self):
        """Failed send should queue the message for later."""
        from phase2_whatsapp.whatsapp_web_js import bridge

        # Clear queue
        bridge._offline_queue.clear()

        with patch.object(bridge, "_request_with_retry", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Connection refused")
            result = await bridge.send_message("919876543210", "Hello!")

        assert result["status"] == "queued"
        assert len(bridge._offline_queue) == 1
        # Clean up
        bridge._offline_queue.clear()

    async def test_is_ready_returns_true(self):
        """is_ready should return True when server responds with ready status."""
        from phase2_whatsapp.whatsapp_web_js import bridge

        with patch.object(bridge, "_request_with_retry", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"status": "ready"}
            result = await bridge.is_ready()

        assert result is True

    async def test_is_ready_returns_false_on_error(self):
        """is_ready should return False when server is unreachable."""
        from phase2_whatsapp.whatsapp_web_js import bridge

        with patch.object(bridge, "_request_with_retry", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Connection refused")
            result = await bridge.is_ready()

        assert result is False

    async def test_get_queue_size(self):
        """get_queue_size should reflect queued messages."""
        from phase2_whatsapp.whatsapp_web_js import bridge

        bridge._offline_queue.clear()
        assert bridge.get_queue_size() == 0

        bridge._offline_queue.append({"phone": "91999", "message": "test"})
        assert bridge.get_queue_size() == 1

        bridge._offline_queue.clear()

    async def test_flush_offline_queue_sends_pending(self):
        """flush_offline_queue should send pending messages."""
        from phase2_whatsapp.whatsapp_web_js import bridge

        bridge._offline_queue.clear()
        bridge._offline_queue.append({"phone": "919876543210", "message": "Pending msg"})

        with patch.object(bridge, "_request_with_retry", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"status": "sent"}
            sent = await bridge.flush_offline_queue()

        assert sent == 1
        assert len(bridge._offline_queue) == 0
