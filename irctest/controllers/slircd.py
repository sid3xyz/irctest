"""
Controller for slircd-ng IRC server.
https://github.com/sid3xyz/slircd-ng
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Type

from irctest.basecontrollers import BaseServerController, DirectoryBasedController
from irctest.cases import BaseServerTestCase


# Base TOML configuration template
BASE_CONFIG = """\
# slircd-ng irctest configuration

[server]
name = "My.Little.Server"
network = "TestNet"
sid = "001"
description = "test server"
metrics_port = 0
{password_config}

[listen]
address = "{bind_address}"

{tls_config}

[database]
path = ":memory:"

[limits]
rate = 1000.0
burst = 1000.0

[security]
cloak_secret = "test-secret-do-not-use-in-production"
cloak_suffix = "test"
spam_detection_enabled = false

[security.rate_limits]
message_rate_per_second = 10000
connection_burst_per_ip = 10000
join_burst_per_client = 10000

[motd]
lines = [
    "Welcome to slircd-ng test server!",
]

[[oper]]
name = "operuser"
password = "operpassword"
hostmask = "*@*"
"""


class SlircdController(BaseServerController, DirectoryBasedController):
    software_name = "slircd-ng"
    _port_wait_interval = 0.01
    supported_sasl_mechanisms = {"PLAIN"}
    supports_sts = False
    extban_mute_char = None

    def create_config(self) -> None:
        super().create_config()
        with self.open_file("config.toml"):
            pass

    def run(
        self,
        hostname: str,
        port: int,
        *,
        password: Optional[str],
        ssl: bool,
        run_services: bool,
        faketime: Optional[str],
    ) -> None:
        self.create_config()
        assert self.directory

        self.hostname = hostname
        self.port = port

        bind_address = f"{hostname}:{port}"

        # TLS configuration
        tls_config = ""
        if ssl:
            self.gen_ssl()
            tls_config = f"""\
[tls]
address = "{hostname}:{port + 1}"
cert_path = "{self.pem_path}"
key_path = "{self.key_path}"
"""

        # Password configuration
        password_config = ""
        if password is not None:
            password_config = f'password = "{password}"'

        # Account registration settings based on test config
        account_reg_flags = ["custom-account-name"]
        if self.test_config.account_registration_before_connect:
            account_reg_flags.append("before-connect")
        if self.test_config.account_registration_requires_email:
            account_reg_flags.append("email-required")

        # Write configuration
        config_content = BASE_CONFIG.format(
            bind_address=bind_address,
            tls_config=tls_config,
            password_config=password_config,
        )

        # Add account registration config section with individual booleans
        before_connect = "true" if self.test_config.account_registration_before_connect else "false"
        email_required = "true" if self.test_config.account_registration_requires_email else "false"

        config_content += f"""
[account_registration]
enabled = true
before_connect = {before_connect}
email_required = {email_required}
custom_account_name = true
"""

        config_path = self.directory / "config.toml"
        with open(config_path, "w") as f:
            f.write(config_content)

        # Find slircd binary
        slircd_bin = os.environ.get("SLIRCD_BIN")
        if not slircd_bin:
            # Try common locations
            workspace_root = Path(__file__).parent.parent.parent.parent
            for path in [
                workspace_root / "target" / "debug" / "slircd-ng",
                workspace_root / "target" / "release" / "slircd-ng",
                workspace_root / "target" / "debug" / "slircd",
                workspace_root / "target" / "release" / "slircd",
                Path("/home/straylight/target/debug/slircd-ng"),
                Path("/home/straylight/target/release/slircd-ng"),
                Path("/home/straylight/target/debug/slircd"),
                Path("/home/straylight/target/release/slircd"),
            ]:
                if path.exists():
                    slircd_bin = str(path)
                    break

        if not slircd_bin or not Path(slircd_bin).exists():
            raise RuntimeError(
                f"slircd binary not found. Set SLIRCD_BIN environment variable. "
                f"Tried: {slircd_bin}"
            )

        if faketime and shutil.which("faketime"):
            faketime_cmd = ["faketime", "-f", faketime]
            self.faketime_enabled = True
        else:
            faketime_cmd = []

        self.proc = self.execute(
            [*faketime_cmd, slircd_bin, str(config_path)]
        )

    def wait_for_services(self) -> None:
        # slircd has built-in services, no need to wait
        pass

    def registerUser(
        self,
        case: BaseServerTestCase,
        username: str,
        password: Optional[str] = None,
    ) -> None:
        """Register a user account using NickServ."""
        client = case.addClient(show_io=False)
        case.sendLine(client, "CAP LS 302")
        case.sendLine(client, "NICK " + username)
        case.sendLine(client, "USER r e g :user")
        case.sendLine(client, "CAP END")
        while case.getRegistrationMessage(client).command != "001":
            pass
        case.getMessages(client)
        assert password
        case.sendLine(client, "NS REGISTER " + password)
        msgs = case.getMessages(client)
        # Look for success message
        case.sendLine(client, "QUIT")
        case.assertDisconnected(client)


def get_irctest_controller_class() -> Type[SlircdController]:
    return SlircdController
