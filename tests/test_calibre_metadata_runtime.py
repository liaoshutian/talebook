import sys
import types
from unittest import mock

import pytest

from webserver.plugins.meta.calibre.api import CalibreMetadataApi, CalibreMetadataPluginUnavailable


def _module(name, package=False):
    module = types.ModuleType(name)
    if package:
        module.__path__ = []
    return module


def _fake_calibre_modules(fail_amazon=False):
    initialized = []

    class GoogleBooks:
        name = "Google"

        def __init__(self, _path=None):
            pass

        def initialize(self):
            pass

    class Amazon:
        name = "Amazon.com"

        def __init__(self, _path=None):
            if fail_amazon:
                raise RuntimeError("amazon unavailable")

        def initialize(self):
            pass

    ui = _module("calibre.customize.ui")
    ui._initialized_plugins = initialized
    ui.metadata_plugins = lambda _capabilities: iter(initialized)

    def initialize_plugin(plugin_class):
        plugin = plugin_class(None)
        plugin.initialize()
        return plugin

    ui.initialize_plugin = initialize_plugin
    customize = _module("calibre.customize", package=True)
    customize.ui = ui
    google = _module("calibre.ebooks.metadata.sources.google")
    google.GoogleBooks = GoogleBooks
    amazon = _module("calibre.ebooks.metadata.sources.amazon")
    amazon.Amazon = Amazon
    return {
        "calibre": _module("calibre", package=True),
        "calibre.customize": customize,
        "calibre.customize.ui": ui,
        "calibre.ebooks": _module("calibre.ebooks", package=True),
        "calibre.ebooks.metadata": _module("calibre.ebooks.metadata", package=True),
        "calibre.ebooks.metadata.sources": _module("calibre.ebooks.metadata.sources", package=True),
        "calibre.ebooks.metadata.sources.google": google,
        "calibre.ebooks.metadata.sources.amazon": amazon,
    }, initialized


@pytest.fixture(autouse=True)
def reset_registration_state():
    CalibreMetadataApi._plugins_registered = False
    yield
    CalibreMetadataApi._plugins_registered = False


def test_registers_google_and_amazon_when_slim_registry_is_empty():
    modules, initialized = _fake_calibre_modules()
    with mock.patch.dict(sys.modules, modules):
        CalibreMetadataApi._ensure_plugins_registered()

    assert {plugin.name for plugin in initialized} == {"Google", "Amazon.com"}
    assert CalibreMetadataApi._plugins_registered is True


def test_registration_is_idempotent():
    modules, initialized = _fake_calibre_modules()
    with mock.patch.dict(sys.modules, modules):
        CalibreMetadataApi._ensure_plugins_registered()
        CalibreMetadataApi._ensure_plugins_registered()

    assert [plugin.name for plugin in initialized].count("Google") == 1
    assert [plugin.name for plugin in initialized].count("Amazon.com") == 1


def test_missing_plugin_raises_a_diagnostic_error():
    modules, _initialized = _fake_calibre_modules(fail_amazon=True)
    with mock.patch.dict(sys.modules, modules):
        with pytest.raises(CalibreMetadataPluginUnavailable, match="Amazon.com"):
            CalibreMetadataApi._ensure_plugins_registered()
