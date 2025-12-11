import importlib

import _pytest.unittest
import pytest

# Must be called before importing irctest.cases.
pytest.register_assert_rewrite("irctest.cases")

from irctest.basecontrollers import (  # noqa: E402
    BaseClientController,
    BaseServerController,
)
from irctest.cases import (  # noqa: E402
    BaseClientTestCase,
    BaseServerTestCase,
    _IrcTestCase,
)


def pytest_addoption(parser):
    """Called by pytest, registers CLI options passed to the pytest command."""
    parser.addoption(
        "--controller", help="Which module to use to run the tested software."
    )
    parser.addoption(
        "--services-controller", help="Which module to use to run a services package."
    )
    parser.addoption(
        "--openssl-bin", type=str, default="openssl", help="The openssl binary to use"
    )
    parser.addoption(
        "--skip-deprecated",
        action="store_true",
        default=False,
        help=(
            "Skip tests marked deprecated. When enabled, also skips Ergo-only tests "
            "(Ergo-proprietary, non-standard coverage)."
        ),
    )


def pytest_configure(config):
    """Called by pytest, after it parsed the command-line."""
    module_name = config.getoption("controller")
    services_module_name = config.getoption("services_controller")

    if module_name is None:
        print("Missing --controller option, errors may occur.")
        _IrcTestCase.controllerClass = None
        _IrcTestCase.show_io = True  # TODO
        return

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        pytest.exit("Cannot import module {}".format(module_name), 1)

    controller_class = module.get_irctest_controller_class()
    if issubclass(controller_class, BaseClientController):
        from irctest import client_tests as module

        if services_module_name is not None:
            pytest.exit("You may not use --services-controller for client tests.")
    elif issubclass(controller_class, BaseServerController):
        from irctest import server_tests as module
    else:
        pytest.exit(
            r"{}.Controller should be a subclass of "
            r"irctest.basecontroller.Base{{Client,Server}}Controller".format(
                module_name
            ),
            1,
        )

    if services_module_name is not None:
        try:
            services_module = importlib.import_module(services_module_name)
        except ImportError:
            pytest.exit("Cannot import module {}".format(services_module_name), 1)
        controller_class.services_controller_class = (
            services_module.get_irctest_controller_class()
        )

    _IrcTestCase.controllerClass = controller_class
    _IrcTestCase.controllerClass.openssl_bin = config.getoption("openssl_bin")
    _IrcTestCase.show_io = True  # TODO


def pytest_collection_modifyitems(session, config, items):
    """Called by pytest after finishing the test collection,
    and before actually running the tests.

    This function filters out client tests if running with a server controller,
    and vice versa. It also filters out deprecated tests when running with
    slircd controller (we focus on modern/future compliance only).
    """

    # First, check if we should run server tests or client tests
    server_tests = client_tests = False
    skip_deprecated = bool(config.getoption("skip_deprecated"))
    if _IrcTestCase.controllerClass is None:
        pass
    elif issubclass(_IrcTestCase.controllerClass, BaseServerController):
        server_tests = True
    elif issubclass(_IrcTestCase.controllerClass, BaseClientController):
        client_tests = True
    else:
        assert False, (
            f"{_IrcTestCase.controllerClass} inherits neither "
            f"BaseClientController or BaseServerController"
        )

    filtered_items = []

    # Iterate over each of the test functions (they are pytest "Nodes")
    for item in items:
        assert isinstance(item, _pytest.python.Function)

        # Skip deprecated tests when running slircd (modern/future focus only)
        if skip_deprecated and item.get_closest_marker("deprecated"):
            continue

        # Skip Ergo-specific tests when running slircd (we test standards, not Ergo emulation)
        if skip_deprecated and item.get_closest_marker("Ergo"):
            # Only skip if Ergo is the ONLY specification marker
            # (i.e., it's an Ergo-proprietary test, not a standard test that Ergo also supports)
            markers = [m.name for m in item.iter_markers()]
            standard_markers = {"RFC1459", "RFC2812", "IRCv3", "modern", "ircdocs"}
            if not any(m in standard_markers for m in markers):
                continue

        # unittest-style test functions have the node of UnitTest class as parent
        if tuple(map(int, _pytest.__version__.split("."))) >= (7,):
            assert isinstance(item.parent, _pytest.python.Class)
        else:
            assert isinstance(item.parent, _pytest.python.Instance)

        # and that node references the UnitTest class
        assert issubclass(item.parent.cls, _IrcTestCase)

        # and in this project, TestCase classes all inherit either from
        # BaseClientController or BaseServerController.
        if issubclass(item.parent.cls, BaseServerTestCase):
            if server_tests:
                filtered_items.append(item)
        elif issubclass(item.parent.cls, BaseClientTestCase):
            if client_tests:
                filtered_items.append(item)
        else:
            filtered_items.append(item)

    # Finally, rewrite in-place the list of tests pytest will run
    items[:] = filtered_items
