"""
Server prefix validation tests.

All server-originated messages (numerics, PONG, NOTICE from server, etc.)
MUST include a server prefix (:<servername>).

This was identified as a common source of bugs in IRC server implementations.
Clients like irssi use the prefix to validate responses (e.g., for lag checks).
"""

import re

from irctest import cases
from irctest.patma import ANYSTR, StrRe


# Regex for server prefix: contains at least one dot, no ! (not a user prefix)
SERVER_PREFIX_RE = StrRe(r"[^!\s]+\.[^!\s]+")


class ServerPrefixTestCase(cases.BaseServerTestCase):
    """Tests that server-originated messages have proper prefixes."""

    @cases.mark_specifications("RFC2812")
    def testVersionPrefix(self):
        """VERSION response (351) must have server prefix."""
        self.connectClient("foo")
        self.sendLine(1, "VERSION")
        msg = self.getMessage(1)

        # 351 RPL_VERSION should have server prefix
        self.assertMessageMatch(
            msg,
            command="351",
            prefix=SERVER_PREFIX_RE,
        )

    @cases.mark_specifications("RFC2812")
    def testLusersPrefix(self):
        """LUSERS responses must have server prefix."""
        self.connectClient("foo")
        self.sendLine(1, "LUSERS")

        # Get at least one LUSERS response
        msg = self.getMessage(1)
        # Should be a 25x numeric
        self.assertTrue(
            msg.command.isdigit() and msg.command.startswith("2"),
            f"Expected LUSERS numeric, got {msg.command}",
        )
        self.assertTrue(
            msg.prefix is not None,
            f"LUSERS numeric {msg.command} must have a prefix: {msg}",
        )
        self.assertTrue(
            re.match(r"[^!]+\.[^!]+", msg.prefix),
            f"LUSERS numeric {msg.command} prefix must be server name: {msg}",
        )

    @cases.mark_specifications("RFC2812")
    def testMotdPrefix(self):
        """MOTD responses must have server prefix.

        Note: We check MOTD on explicit request since the welcome burst
        already sends MOTD and connectClient consumes those messages.
        """
        self.connectClient("foo")
        self.sendLine(1, "MOTD")

        # Wait for and verify 375 (start of MOTD)
        msg = self.getMessage(1)
        # Could be 375 (start) or 422 (no MOTD)
        if msg.command == "422":  # ERR_NOMOTD
            self.assertTrue(
                msg.prefix is not None,
                f"ERR_NOMOTD must have prefix: {msg}",
            )
            self.assertTrue(
                re.match(r"[^!]+\.[^!]+", msg.prefix),
                f"ERR_NOMOTD prefix must be server name: {msg}",
            )
        else:
            self.assertEqual(msg.command, "375", f"Expected 375 or 422, got {msg.command}")
            self.assertTrue(
                msg.prefix is not None,
                f"MOTD start (375) must have prefix: {msg}",
            )
            self.assertTrue(
                re.match(r"[^!]+\.[^!]+", msg.prefix),
                f"MOTD start (375) prefix must be server name: {msg}",
            )

    @cases.mark_specifications("RFC2812")
    def testPongPrefix(self):
        """PONG must have server prefix.

        This is critical for client lag detection. Without the prefix,
        clients like irssi cannot properly match PONG responses to their
        PING requests, leading to spurious disconnections.
        """
        self.connectClient("foo")
        self.sendLine(1, "PING test123")
        msg = self.getMessage(1)

        self.assertMessageMatch(
            msg,
            command="PONG",
            params=[ANYSTR, "test123"],
            prefix=SERVER_PREFIX_RE,
        )
        # First param should be the server name matching prefix
        self.assertEqual(
            msg.params[0],
            msg.prefix,
            f"PONG first param should match prefix: params={msg.params}, prefix={msg.prefix}",
        )

    @cases.mark_specifications("RFC2812")
    def testTimePrefix(self):
        """TIME response must have server prefix."""
        self.connectClient("foo")
        self.sendLine(1, "TIME")
        msg = self.getMessage(1)

        # 391 RPL_TIME
        self.assertMessageMatch(
            msg,
            command="391",
            prefix=SERVER_PREFIX_RE,
        )
