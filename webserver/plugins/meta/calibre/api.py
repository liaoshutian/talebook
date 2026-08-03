#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import importlib
import logging
import traceback
from threading import Lock

import requests

from webserver.constants import CHROME_HEADERS, META_SOURCE_GOOGLE, META_SOURCE_AMAZON
from webserver.i18n import _

KEY = "Calibre"

# 用户选择的信息源 key → Calibre 插件名称
_SOURCE_TO_PLUGIN = {
    "google": "Google",
    "amazon": "Amazon.com",
}

_PLUGIN_CLASSES = {
    "Google": ("calibre.ebooks.metadata.sources.google", "GoogleBooks"),
    "Amazon.com": ("calibre.ebooks.metadata.sources.amazon", "Amazon"),
}


class CalibreMetadataPluginUnavailable(RuntimeError):
    """The configured metadata source is absent from Calibre's runtime registry."""


class CalibreMetadataApi:
    """使用 Calibre 内置的 Google Books 和 Amazon.com 插件查询书籍元数据"""

    ALLOWED_PLUGINS = frozenset({"Google", "Amazon.com"})
    _patched = False
    _plugins_registered = False
    _plugin_lock = Lock()

    @classmethod
    def _ensure_plugins_registered(cls):
        """Restore identify plugins omitted by the no-Qt slim built-in list."""
        if cls._plugins_registered:
            return

        from calibre.customize import ui

        with cls._plugin_lock:
            if cls._plugins_registered:
                return
            registered = {plugin.name for plugin in ui.metadata_plugins({"identify"})}
            for name in sorted(cls.ALLOWED_PLUGINS - registered):
                module_name, class_name = _PLUGIN_CLASSES[name]
                try:
                    plugin_class = getattr(importlib.import_module(module_name), class_name)
                    plugin = ui.initialize_plugin(plugin_class)
                    ui._initialized_plugins.append(plugin)
                    logging.info("已注册 slim runtime 缺失的 Calibre 元数据插件：%s", name)
                except Exception as err:
                    logging.exception("无法注册 Calibre 元数据插件 %s", name)
                    raise CalibreMetadataPluginUnavailable("Calibre metadata plugin unavailable: %s" % name) from err

            registered = {plugin.name for plugin in ui.metadata_plugins({"identify"})}
            missing = cls.ALLOWED_PLUGINS - registered
            if missing:
                raise CalibreMetadataPluginUnavailable("Calibre metadata plugins unavailable: %s" % ", ".join(sorted(missing)))
            cls._plugins_registered = True

    @classmethod
    def _ensure_patched(cls):
        if not cls._patched:
            try:
                from calibre.ebooks.metadata.sources.update import patch_plugins

                patch_plugins()
                cls._patched = True
            except Exception as e:
                logging.warning("calibre patch_plugins 失败：%s", e)

    @staticmethod
    def _make_log_abort():
        from io import BytesIO
        from threading import Event
        from calibre.ebooks.metadata.sources.base import create_log

        return create_log(BytesIO()), Event()

    @classmethod
    def _get_amazon_plugin(cls):
        from calibre.customize.ui import metadata_plugins

        cls._ensure_plugins_registered()
        amazon_plugin = None
        for plugin in metadata_plugins({"identify"}):
            if plugin.name == "Amazon.com":
                amazon_plugin = plugin
                break
        return amazon_plugin

    @classmethod
    def _identify(cls, timeout=30, source=None, **kwargs):
        from calibre.ebooks.metadata.sources.identify import identify

        cls._ensure_plugins_registered()
        cls._ensure_patched()
        log, abort = cls._make_log_abort()
        return identify(log, abort, allowed_plugins={source}, timeout=timeout, **kwargs)

    @classmethod
    def get_cover(cls, cover_url):
        if not cover_url:
            return None
        if not cover_url.lower().startswith("https://"):
            logging.error("Invalid cover url: %s", cover_url)
            return None
        headers = dict(CHROME_HEADERS)
        headers["Referer"] = cover_url
        response = requests.get(cover_url, headers=headers, verify=False, timeout=20)
        if response.status_code != 200:
            logging.error("Get cover fail, status_code[%s] != 200 OK", response.status_code)
            return None
        img = response.content
        return ("jpg", img)

    @classmethod
    def get_book_by_isbn(cls, isbn, sources=None, timeout=30):
        """按 ISBN 查询书籍信息，成功时返回含封面的 Metadata 对象，否则返回 None"""
        if not sources or META_SOURCE_GOOGLE not in sources:
            return None

        if not isbn:
            return None
        try:
            results = cls._identify(identifiers={"isbn": isbn}, timeout=timeout, source="Google")
            if not results:
                return None
            if results:
                for result in results[:1]:
                    result.provider_key = result.source = "google"
                    result.provider_value = isbn
                    result.author_sort = result.authors[0] if result.authors else ""
                    # Calibre Google 插件的评分是 0-5，乘以 2 转换为 0-10
                    result.rating = int(result.rating) * 2 if result.rating is not None else 0
            return results[:1]
        except CalibreMetadataPluginUnavailable:
            raise
        except Exception as e:
            logging.error(_("CalibreMetadataApi ISBN 查询失败 isbn=%s: %s"), isbn, e)
            logging.error(traceback.format_exc())
            return None

    @classmethod
    def get_book_by_title(cls, title, authors=None, sources=None, timeout=30):
        """按书名（及可选作者）查询书籍信息，成功时返回含封面的 Metadata 对象，否则返回 None"""
        if not sources or META_SOURCE_AMAZON not in sources:
            return None

        if not title:
            return None
        try:
            kwargs = {"title": title}
            if authors:
                kwargs["authors"] = authors if isinstance(authors, list) else [authors]
            results = cls._identify(timeout=timeout, source="Amazon.com", **kwargs)
            if not results:
                return None
            if results:
                amazon_plugin = cls._get_amazon_plugin()
                for result in results[:3]:
                    result.provider_key = result.source = "amazon"
                    result.provider_value = result.isbn if result.isbn else title
                    result.author_sort = result.authors[0] if result.authors else ""
                    # Calibre Google 插件的评分是 0-5，乘以 2 转换为 0-10
                    result.rating = int(result.rating) * 2 if result.rating is not None else 0
                    if amazon_plugin and amazon_plugin.cached_cover_url_is_reliable:
                        result.cover_url = amazon_plugin.get_cached_cover_url(result.identifiers)
            return results[:3]
        except CalibreMetadataPluginUnavailable:
            raise
        except Exception as e:
            logging.error(_("CalibreMetadataApi 书名查询失败 title=%s: %s"), title, e)
            return None
