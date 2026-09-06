#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
#
# Google Translate API helper for Foreca One Weather Plugin

from __future__ import print_function

import hashlib
import json
import socket
import time

try:
    import urllib2
    from urllib import urlencode
    HTTPError = urllib2.HTTPError
    URLError = urllib2.URLError
    Request = urllib2.Request
    urlopen = urllib2.urlopen
    PY2 = True
except ImportError:
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    PY2 = False

try:
    text_type = unicode
except NameError:
    text_type = str

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)

try:
    integer_types = (int, long)
except NameError:
    integer_types = (int,)

from os import makedirs, remove, rename
from os.path import dirname, exists, join

from Components.config import config

from . import DEBUG, HEADERS, SYSTEM_DIR


# ============================================================
# CONFIGURATION
# ============================================================

TRANSLATE_API_URL = (
    "https://translate.googleapis.com/translate_a/single"
)

REQUEST_TIMEOUT = 8

# Google requests should not become excessively large.
MAX_CHARS_PER_REQUEST = 2000

# Maximum number of entries kept in the local cache.
MAX_CACHE_ENTRIES = 5000

CACHE_FILE = join(SYSTEM_DIR, "translation_cache.json")
CACHE_TMP_FILE = CACHE_FILE + ".tmp"

ENABLE_LOGGING = True

# If True, Arabic source text is returned unchanged.
# This preserves the behaviour of your previous version.
SKIP_ARABIC = True


# ============================================================
# RUNTIME STATE
# ============================================================

_translation_cache = {}

_cache_hits = 0
_cache_misses = 0
_cache_dirty = False

_cache_loaded = False


# ============================================================
# LOGGING
# ============================================================

def _log(message):
    """Debug logging compatible with Python 2 and Python 3."""

    if not ENABLE_LOGGING or not DEBUG:
        return

    try:
        timestamp = time.time()

        print(
            "[Foreca-1-Translate][%.2f] %s"
            % (timestamp, _to_unicode(message))
        )

    except Exception:
        try:
            print("[Foreca-1-Translate] %s" % message)
        except Exception:
            pass


# ============================================================
# UNICODE HELPERS
# ============================================================

def _to_unicode(value):
    """
    Convert arbitrary input to Unicode.

    Works correctly on Python 2 and Python 3.
    """

    if value is None:
        return u""

    if isinstance(value, text_type):
        return value

    if PY2:
        try:
            if isinstance(value, str):
                return value.decode("utf-8", "ignore")
        except Exception:
            pass

    else:
        try:
            if isinstance(value, bytes):
                return value.decode("utf-8", "ignore")
        except Exception:
            pass

    try:
        return text_type(value)
    except Exception:
        try:
            return u"%s" % value
        except Exception:
            return u""


def _to_utf8(value):
    """
    Convert Unicode to UTF-8 bytes for Python 2/3 HTTP handling.
    """

    value = _to_unicode(value)

    try:
        return value.encode("utf-8")
    except Exception:
        return value


def _clean_whitespace(text):
    """Normalize excessive whitespace."""

    text = _to_unicode(text)

    while u"  " in text:
        text = text.replace(u"  ", u" ")

    return text.strip()


# ============================================================
# LANGUAGE HANDLING
# ============================================================

_LANGUAGE_ALIASES = {
    "iw": "he",
    "iw_il": "he",
    "he_il": "he",

    "in": "id",
    "in_id": "id",

    "ji": "yi",

    "zh_cn": "zh-cn",
    "zh_sg": "zh-cn",

    "zh_tw": "zh-tw",
    "zh_hk": "zh-tw",
}


def _normalize_language(language_code):
    """
    Normalize Enigma2 / ISO language identifiers.

    Examples:
        de_DE -> de
        en_US -> en
        zh_CN -> zh-cn
        zh-TW -> zh-tw
        iw    -> he
    """

    if language_code is None:
        return "en"

    lang = _to_unicode(language_code)
    lang = lang.strip().lower()

    if not lang:
        return "en"

    lang = lang.replace("-", "_")

    if lang in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[lang]

    # Preserve Chinese region.
    if lang.startswith("zh_cn"):
        return "zh-cn"

    if lang.startswith("zh_tw"):
        return "zh-tw"

    # Normal language code.
    return lang.split("_")[0]


def _get_system_language():
    """
    Get the current Enigma2 system language.

    Falls back safely to English.
    """

    # First try Components.Language.
    try:
        from Components.Language import language

        value = language.getLanguage()

        if value:
            return _normalize_language(value)

    except Exception:
        pass

    # Then config.misc.language.
    try:
        value = config.misc.language.value

        if value:
            return _normalize_language(value)

    except Exception:
        pass

    # Then config.osd.language.
    try:
        value = config.osd.language.value

        if value:
            return _normalize_language(value)

    except Exception:
        pass

    return "en"


# ============================================================
# DIRECTORY HANDLING
# ============================================================

def _ensure_directory(path):
    """Create directory if necessary."""

    if not path:
        return False

    if exists(path):
        return True

    try:
        makedirs(path)
        return True

    except OSError:
        # Another process may have created it.
        return exists(path)

    except Exception as e:
        _log(
            "Cannot create directory '%s': %s"
            % (path, e)
        )
        return False


def _ensure_cache_dir():
    """Ensure translation cache directory exists."""

    return _ensure_directory(dirname(CACHE_FILE))


# ============================================================
# CACHE
# ============================================================

def load_cache_from_disk():
    """
    Load translation cache.

    Invalid/corrupted cache is ignored instead of breaking
    the whole plugin.
    """

    global _translation_cache
    global _cache_loaded
    global _cache_dirty

    if _cache_loaded:
        return

    _cache_loaded = True
    _cache_dirty = False

    if not _ensure_cache_dir():
        _translation_cache = {}
        return

    if not exists(CACHE_FILE):
        _translation_cache = {}
        return

    try:
        with open(CACHE_FILE, "r") as cache_file:
            raw = cache_file.read()

        raw = _to_unicode(raw)

        if not raw.strip():
            _translation_cache = {}
            return

        data = json.loads(raw)

        if isinstance(data, dict):
            _translation_cache = data
        else:
            _translation_cache = {}

        _log(
            "Translation cache loaded: %d entries"
            % len(_translation_cache)
        )

    except Exception as e:
        _log(
            "Cannot load translation cache: %s"
            % e
        )

        _translation_cache = {}

        # Do not delete the original cache automatically.
        # It may be useful for debugging.


def _write_cache_file():
    """
    Write cache atomically.

    First writes to .tmp and then replaces the old file.
    """

    if not _ensure_cache_dir():
        return False

    try:
        data = json.dumps(
            _translation_cache,
            ensure_ascii=False,
            indent=2
        )

        if not isinstance(data, string_types):
            data = _to_unicode(data)

        with open(CACHE_TMP_FILE, "wb") as cache_file:
            cache_file.write(_to_utf8(data))

        # os.rename works atomically on the same filesystem.
        try:
            rename(CACHE_TMP_FILE, CACHE_FILE)
        except Exception:
            # Fallback for platforms where replacing an existing
            # file with rename() is problematic.
            if exists(CACHE_FILE):
                try:
                    remove(CACHE_FILE)
                except Exception:
                    pass

            rename(CACHE_TMP_FILE, CACHE_FILE)

        return True

    except Exception as e:
        _log(
            "Cannot save translation cache: %s"
            % e
        )

        try:
            if exists(CACHE_TMP_FILE):
                remove(CACHE_TMP_FILE)
        except Exception:
            pass

        return False


def save_cache_to_disk():
    """
    Save cache only when modified.
    """

    global _cache_dirty

    if not _cache_dirty:
        return True

    if _write_cache_file():
        _cache_dirty = False
        return True

    return False


def _get_cache_key(text, target_lang):
    """
    Stable cache key.

    Language is part of the key, so the same text can have
    different translations for different target languages.
    """

    text = _to_unicode(text)
    target_lang = _normalize_language(target_lang)

    key_string = (
        _to_utf8(target_lang + ":" + text)
    )

    return hashlib.md5(key_string).hexdigest()


def _get_cached_translation(text, target_lang):
    """Return cached translation or None."""

    global _cache_hits
    global _cache_misses

    load_cache_from_disk()

    key = _get_cache_key(text, target_lang)

    if key in _translation_cache:
        _cache_hits += 1
        return _translation_cache[key]

    _cache_misses += 1
    return None


def _cache_translation(text, target_lang, translated):
    """
    Store translation in cache.

    The cache is not flushed immediately. This avoids writing
    to flash storage on every translation.
    """

    global _cache_dirty

    load_cache_from_disk()

    key = _get_cache_key(text, target_lang)

    _translation_cache[key] = _to_unicode(translated)
    _cache_dirty = True

    _trim_cache()

    return translated


def _trim_cache():
    """
    Limit cache size.

    JSON dictionaries do not provide a true LRU cache, so
    oldest inserted entries are removed as a simple safeguard.
    """

    global _cache_dirty

    if len(_translation_cache) <= MAX_CACHE_ENTRIES:
        return

    try:
        remove_count = (
            len(_translation_cache) - MAX_CACHE_ENTRIES
        )

        keys = list(_translation_cache.keys())

        for key in keys[:remove_count]:
            try:
                del _translation_cache[key]
            except KeyError:
                pass

        _cache_dirty = True

    except Exception:
        pass


def get_cache_stats():
    """Return cache statistics."""

    total = _cache_hits + _cache_misses

    if total:
        hit_rate = float(_cache_hits) / float(total)
    else:
        hit_rate = 0.0

    return {
        "hits": _cache_hits,
        "misses": _cache_misses,
        "size": len(_translation_cache),
        "hit_rate": hit_rate,
    }


def clear_cache():
    """Clear memory and disk cache."""

    global _cache_hits
    global _cache_misses
    global _cache_dirty

    _translation_cache.clear()

    _cache_hits = 0
    _cache_misses = 0
    _cache_dirty = False

    if exists(CACHE_FILE):
        try:
            remove(CACHE_FILE)
        except Exception as e:
            _log(
                "Cannot delete cache file: %s"
                % e
            )

    if exists(CACHE_TMP_FILE):
        try:
            remove(CACHE_TMP_FILE)
        except Exception:
            pass

    _log("Translation cache cleared")


def flush_cache():
    """
    Public helper to force pending cache data to disk.
    """

    return save_cache_to_disk()


# ============================================================
# ARABIC DETECTION
# ============================================================

def _is_arabic_char(char):
    """Return True if character belongs to an Arabic Unicode range."""

    try:
        code = ord(char)

        return (
            0x0600 <= code <= 0x06FF or
            0x0750 <= code <= 0x077F or
            0x08A0 <= code <= 0x08FF or
            0xFB50 <= code <= 0xFDFF or
            0xFE70 <= code <= 0xFEFF
        )

    except Exception:
        return False


def _is_text_arabic(text):
    """
    Determine whether text is predominantly Arabic.

    A threshold of 60% Arabic alphabetic characters is used.
    """

    text = _to_unicode(text)

    if not text:
        return False

    total_letters = 0
    arabic_letters = 0

    for char in text:

        try:
            if not char.isalpha():
                continue
        except Exception:
            continue

        total_letters += 1

        if _is_arabic_char(char):
            arabic_letters += 1

    if total_letters == 0:
        return False

    return (
        float(arabic_letters) /
        float(total_letters)
    ) >= 0.60


# ============================================================
# HTTP
# ============================================================

def _build_translation_url(text, target_lang):
    """
    Build Google Translate request URL.
    """

    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": target_lang,
        "dt": "t",
        "q": text,
    }

    return (
        TRANSLATE_API_URL +
        "?" +
        urlencode(params)
    )


def _get_response_body(response):
    """
    Read and decode HTTP response safely.
    """

    raw_data = response.read()

    if raw_data is None:
        return u""

    if isinstance(raw_data, bytes):
        return raw_data.decode("utf-8", "replace")

    return _to_unicode(raw_data)


def _extract_translation(data):
    """
    Extract translated text from Google response.

    Expected format is approximately:

        [
            [
                ["translated", "original", ...],
                ...
            ],
            ...
        ]
    """

    if not isinstance(data, list):
        return u""

    if not data:
        return u""

    segments = data[0]

    if not isinstance(segments, list):
        return u""

    result = []

    for segment in segments:

        if not isinstance(segment, list):
            continue

        if not segment:
            continue

        translated = segment[0]

        if translated is None:
            continue

        translated = _to_unicode(translated)

        if translated:
            result.append(translated)

    return u"".join(result)


# ============================================================
# SINGLE TRANSLATION
# ============================================================

def translate_text(text, target_lang=None, use_cache=True):
    """
    Translate one string.

    On any failure, the original text is returned.
    """

    start_time = time.time()

    if text is None:
        return u""

    text_unicode = _to_unicode(text)

    if not text_unicode:
        return u""

    # Keep leading/trailing whitespace out of the API request.
    original_text = text_unicode
    request_text = text_unicode.strip()

    if not request_text:
        return original_text

    if target_lang is None:
        target_lang = _get_system_language()

    target_lang = _normalize_language(target_lang)

    _log(
        "Translation requested: '%s' -> '%s'"
        % (
            request_text[:50],
            target_lang
        )
    )

    # No need to translate into the same language.
    source_lang = None

    # If the configured target language is English and text
    # is obviously Arabic etc., Google still handles detection.
    # Arabic skipping remains optional below.

    if SKIP_ARABIC and _is_text_arabic(request_text):
        _log(
            "Arabic text detected, skipped: '%s'"
            % request_text[:50]
        )
        return original_text

    if use_cache:
        cached = _get_cached_translation(
            request_text,
            target_lang
        )

        if cached is not None:
            _log(
                "Cache HIT: '%s'"
                % request_text[:50]
            )
            return cached

    # Never silently destroy text by truncating it.
    # Instead, split long text into chunks.
    if len(request_text) > MAX_CHARS_PER_REQUEST:
        _log(
            "Text exceeds %d chars; using chunk translation"
            % MAX_CHARS_PER_REQUEST
        )

        return _translate_long_text(
            request_text,
            target_lang,
            use_cache
        )

    url = _build_translation_url(
        request_text,
        target_lang
    )

    try:
        request = Request(url)

        if HEADERS:
            for key, value in HEADERS.items():
                try:
                    request.add_header(
                        key,
                        value
                    )
                except Exception:
                    pass

        response = None

        try:
            response = urlopen(
                request,
                timeout=REQUEST_TIMEOUT
            )

            raw_data = _get_response_body(response)

        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                pass

        if not raw_data:
            _log("Google returned an empty response")
            return original_text

        try:
            data = json.loads(raw_data)
        except Exception as e:
            _log(
                "Invalid JSON response: %s"
                % e
            )
            return original_text

        translated_text = _extract_translation(data)

        translated_text = _clean_whitespace(
            translated_text
        )

        if not translated_text:
            _log(
                "No translation returned for '%s'"
                % request_text[:50]
            )
            return original_text

        # Google sometimes returns exactly the source text.
        # This is still a valid result, so cache it.
        if use_cache:
            _cache_translation(
                request_text,
                target_lang,
                translated_text
            )

        elapsed = time.time() - start_time

        _log(
            "Translation completed in %.2fs: '%s' -> '%s'"
            % (
                elapsed,
                request_text[:30],
                translated_text[:30]
            )
        )

        return translated_text

    except HTTPError as e:
        _log(
            "HTTP %s during translation: %s"
            % (
                getattr(e, "code", "N/A"),
                e
            )
        )

    except URLError as e:
        _log(
            "URL error during translation: %s"
            % e
        )

    except socket.timeout:
        _log(
            "Translation timeout: '%s'"
            % request_text[:50]
        )

    except Exception as e:
        _log(
            "Translation error %s: %s"
            % (
                type(e).__name__,
                e
            )
        )

    return original_text


# ============================================================
# LONG TEXT
# ============================================================

def _split_text(text, max_length):
    """
    Split long text into reasonably readable chunks.

    Prefer newline and sentence boundaries instead of simply
    cutting in the middle of a word.
    """

    text = _to_unicode(text)

    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_length:

        candidate = remaining[:max_length]

        split_at = candidate.rfind(u"\n")

        if split_at < max_length // 2:
            split_at = candidate.rfind(u". ")

        if split_at < max_length // 2:
            split_at = candidate.rfind(u" ")

        if split_at < max_length // 3:
            split_at = max_length

        chunk = remaining[:split_at].strip()

        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


def _translate_long_text(text, target_lang, use_cache=True):
    """
    Translate text larger than MAX_CHARS_PER_REQUEST.
    """

    chunks = _split_text(
        text,
        MAX_CHARS_PER_REQUEST
    )

    translated_chunks = []

    for chunk in chunks:
        translated = translate_text(
            chunk,
            target_lang,
            use_cache
        )

        translated_chunks.append(
            translated
        )

    return u" ".join(
        translated_chunks
    )


# ============================================================
# BATCH TRANSLATION
# ============================================================

def translate_batch(texts, target_lang=None, use_cache=True):
    """
    Translate a list of strings.

    Each string is handled independently.

    This is intentionally more reliable than joining multiple
    strings with a separator because Google may alter separators.
    """

    if not texts:
        return []

    if target_lang is None:
        target_lang = _get_system_language()

    target_lang = _normalize_language(
        target_lang
    )

    results = []

    for text in texts:

        text_unicode = _to_unicode(text)

        if not text_unicode:
            results.append(u"")
            continue

        if (
            SKIP_ARABIC and
            _is_text_arabic(text_unicode)
        ):
            results.append(text_unicode)
            continue

        if use_cache:
            cached = _get_cached_translation(
                text_unicode.strip(),
                target_lang
            )

            if cached is not None:
                results.append(cached)
                continue

        translated = translate_text(
            text_unicode,
            target_lang,
            use_cache=use_cache
        )

        results.append(
            translated
        )

    # Persist all cache changes only once.
    if use_cache:
        save_cache_to_disk()

    return results


def translate_batch_strings(texts, target_lang=None):
    """
    High-level helper for string lists.
    """

    if not texts:
        return []

    valid_texts = []

    for item in texts:
        value = _to_unicode(item).strip()

        if value:
            valid_texts.append(value)

    if not valid_texts:
        return []

    return translate_batch(
        valid_texts,
        target_lang,
        use_cache=True
    )


# ============================================================
# SAFE TRANSLATION
# ============================================================

def safe_translate(text, fallback=None, **kwargs):
    """
    Translation wrapper that always returns usable text.
    """

    original = _to_unicode(text)

    try:
        translated = translate_text(
            original,
            **kwargs
        )

        if translated and translated.strip():
            return translated

    except Exception as e:
        _log(
            "safe_translate error: %s"
            % e
        )

    if fallback is not None:
        return _to_unicode(fallback)

    return original


def trans(text, target_lang=None):
    """
    Simple public translation function.

    This is the function imported by the main Foreca module:

        from .google_translate import trans
    """

    if text is None:
        return u""

    text = _to_unicode(text)

    if not text:
        return u""

    # Do not remove whitespace from the actual returned value.
    # Only use stripped text for translation.
    stripped = text.strip()

    if not stripped:
        return text

    if target_lang is None:
        target_lang = _get_system_language()

    target_lang = _normalize_language(
        target_lang
    )

    if SKIP_ARABIC and _is_text_arabic(stripped):
        return text

    cached = _get_cached_translation(
        stripped,
        target_lang
    )

    if cached is not None:
        return cached

    translated = translate_text(
        stripped,
        target_lang,
        use_cache=True
    )

    if translated:
        return translated

    return text


# ============================================================
# CACHE MAINTENANCE
# ============================================================

def shutdown():
    """
    Call this when the plugin is being closed if desired.

    Flushes pending translations to disk.
    """

    try:
        save_cache_to_disk()
    except Exception:
        pass


# ============================================================
# TESTING
# ============================================================

def test_translation():
    """
    Basic connectivity test.

    Do NOT compare against an exact expected sentence because
    machine translation can legitimately vary.
    """

    test_cases = [
        (u"Hello world", "it"),
        (u"Weather forecast", "es"),
        (u"Temperature", "fr"),
    ]

    if DEBUG:
        print("=" * 60)
        print("Foreca One TRANSLATION TEST")
        print("=" * 60)

    all_passed = True

    for original, lang in test_cases:

        try:
            result = translate_text(
                original,
                lang,
                use_cache=False
            )

            if result and result.strip():
                status = "PASS"
            else:
                status = "FAIL"
                all_passed = False

            if DEBUG:
                print(
                    "%s: '%s' -> '%s'"
                    % (
                        status,
                        original,
                        result
                    )
                )

        except Exception as e:

            all_passed = False

            if DEBUG:
                print(
                    "FAIL: '%s' -> %s"
                    % (
                        original,
                        e
                    )
                )

    if DEBUG:
        print("=" * 60)

        stats = get_cache_stats()

        print(
            "Cache: %d hits, %d misses, %.1f%% hit rate"
            % (
                stats["hits"],
                stats["misses"],
                stats["hit_rate"] * 100.0
            )
        )

        print("=" * 60)

    return all_passed


# ============================================================
# INITIALIZATION
# ============================================================

load_cache_from_disk()

_log(
    "Foreca One translation module loaded"
)

_log(
    "Python version: %s"
    % (
        "2" if PY2 else "3"
    )
)

_log(
    "System language: %s"
    % _get_system_language()
)


# ============================================================
# DIRECT TEST MODE
# ============================================================

if __name__ == "__main__":

    print(
        "Google Translate API for Foreca One"
    )

    print(
        "Python %s compatibility mode"
        % (
            "2" if PY2 else "3"
        )
    )

    if test_translation():
        print("Translation tests completed successfully.")
    else:
        print("One or more translation tests failed.")

    # Make sure pending cache changes are written.
    shutdown()
