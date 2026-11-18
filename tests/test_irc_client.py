from unittest.mock import AsyncMock, patch

import pytest

from src.irc_client import IRCClient


@pytest.mark.asyncio
async def test_irc_ping_pong(sample_settings, memory_manager):
    client = IRCClient(settings=sample_settings, memory=memory_manager)
    client._send = AsyncMock()

    await client._handle_line("PING :server.libera.chat")
    client._send.assert_called_once_with("PONG :server.libera.chat")


@pytest.mark.asyncio
async def test_irc_privmsg_reset(sample_settings, memory_manager):
    client = IRCClient(settings=sample_settings, memory=memory_manager)
    client.send_privmsg = AsyncMock()

    # User sends '!reset' to the bot in PM
    sender = "testuser"
    line = f":{sender}!user@host PRIVMSG {sample_settings.irc_nickname} :!reset"
    await client._handle_line(line)

    client.send_privmsg.assert_called_once()
    args = client.send_privmsg.call_args[0]
    assert args[0] == sender
    assert "حافظه مکالمه پاک شد" in args[1]


@pytest.mark.asyncio
async def test_irc_privmsg_chat(sample_settings, memory_manager):
    client = IRCClient(settings=sample_settings, memory=memory_manager)
    client.send_privmsg = AsyncMock()

    sender = "alice"
    line = f":{sender}!user@host PRIVMSG #ai-chat :{sample_settings.irc_nickname}: سلام"

    with patch("src.irc_client.chat_generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = ("درود بر شما!", None, {})
        await client._handle_line(line)

        mock_gen.assert_called_once()
        client.send_privmsg.assert_called_once_with("#ai-chat", "alice: درود بر شما!")
