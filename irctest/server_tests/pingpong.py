"""
The PING and PONG commands
"""

from irctest import cases
from irctest.numerics import ERR_NEEDMOREPARAMS, ERR_NOORIGIN
from irctest.patma import ANYSTR, StrRe


class PingPongTestCase(cases.BaseServerTestCase):
    @cases.mark_specifications("Modern")
    def testPing(self):
        """https://github.com/ircdocs/modern-irc/pull/99

        PONG must include server prefix per RFC 2812:
        The response format is: :<server> PONG <server> <token>
        """
        self.connectClient("foo")
        self.sendLine(1, "PING abcdef")
        msg = self.getMessage(1)
        # PONG must have a server prefix (contains a dot, no !)
        self.assertMessageMatch(
            msg,
            command="PONG",
            params=[ANYSTR, "abcdef"],
            prefix=StrRe(r"[^!]+\.[^!]+"),  # Server prefix: contains dot, no !
        )
        # First param should match the prefix (server name)
        self.assertEqual(msg.params[0], msg.prefix,
            f"PONG first param should match prefix: params={msg.params}, prefix={msg.prefix}")

    @cases.mark_specifications("Modern")
    def testPingNoToken(self):
        """https://github.com/ircdocs/modern-irc/pull/99"""
        self.connectClient("foo")
        self.sendLine(1, "PING")
        m = self.getMessage(1)
        if m.command == ERR_NOORIGIN:
            self.assertMessageMatch(m, command=ERR_NOORIGIN, params=["foo", ANYSTR])
        else:
            self.assertMessageMatch(
                m, command=ERR_NEEDMOREPARAMS, params=["foo", "PING", ANYSTR]
            )

    @cases.mark_specifications("Modern")
    def testPingEmptyToken(self):
        """https://github.com/ircdocs/modern-irc/pull/99"""
        self.connectClient("foo")
        self.sendLine(1, "PING :")
        m = self.getMessage(1)
        if m.command == "PONG":
            # PONG must have server prefix
            self.assertMessageMatch(
                m,
                command="PONG",
                params=[ANYSTR, ""],
                prefix=StrRe(r"[^!]+\.[^!]+"),  # Server prefix
            )
        elif m.command == ERR_NOORIGIN:
            self.assertMessageMatch(m, command=ERR_NOORIGIN, params=["foo", ANYSTR])
        else:
            self.assertMessageMatch(
                m, command=ERR_NEEDMOREPARAMS, params=["foo", "PING", ANYSTR]
            )
