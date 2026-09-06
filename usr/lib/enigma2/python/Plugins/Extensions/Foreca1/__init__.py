#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026

from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Components.Language import language
from os.path import exists, join, dirname
from enigma import getDesktop, gRGB
from skin import parseColor
from os import makedirs, environ, rmdir, walk, remove
import gettext
import codecs
import shutil
import re

# ============================================================
# CONFIGURATION IMPORTS FOR TRANSLATION ENGINE
# ============================================================
from Components.config import config, ConfigSubsection, ConfigBoolean, ConfigSelection

# Ensure config namespace exists
if not hasattr(config.plugins, 'foreca'):
    config.plugins.foreca = ConfigSubsection()

# Translation engine: False = gettext (local .po files), True = Google
# Translate
config.plugins.foreca.translation_engine = ConfigBoolean(default=False)

# Target language for Google Translate (ISO 639-1 codes)
# 'auto' means use system language
LANGUAGE_CHOICES = [
    ('auto', 'Auto (System Language)'),
    ('af', 'Afrikaans'),
    ('sq', 'Albanian'),
    ('am', 'Amharic'),
    ('ar', 'Arabic'),
    ('hy', 'Armenian'),
    ('az', 'Azerbaijani'),
    ('eu', 'Basque'),
    ('be', 'Belarusian'),
    ('bn', 'Bengali'),
    ('bs', 'Bosnian'),
    ('bg', 'Bulgarian'),
    ('ca', 'Catalan'),
    ('ceb', 'Cebuano'),
    ('ny', 'Chichewa'),
    ('zh-cn', 'Chinese (Simplified)'),
    ('zh-tw', 'Chinese (Traditional)'),
    ('co', 'Corsican'),
    ('hr', 'Croatian'),
    ('cs', 'Czech'),
    ('da', 'Danish'),
    ('nl', 'Dutch'),
    ('en', 'English'),
    ('eo', 'Esperanto'),
    ('et', 'Estonian'),
    ('tl', 'Filipino'),
    ('fi', 'Finnish'),
    ('fr', 'French'),
    ('fy', 'Frisian'),
    ('gl', 'Galician'),
    ('ka', 'Georgian'),
    ('de', 'German'),
    ('el', 'Greek'),
    ('gu', 'Gujarati'),
    ('ht', 'Haitian Creole'),
    ('ha', 'Hausa'),
    ('haw', 'Hawaiian'),
    ('iw', 'Hebrew'),
    ('hi', 'Hindi'),
    ('hmn', 'Hmong'),
    ('hu', 'Hungarian'),
    ('is', 'Icelandic'),
    ('ig', 'Igbo'),
    ('id', 'Indonesian'),
    ('ga', 'Irish'),
    ('it', 'Italian'),
    ('ja', 'Japanese'),
    ('jw', 'Javanese'),
    ('kn', 'Kannada'),
    ('kk', 'Kazakh'),
    ('km', 'Khmer'),
    ('rw', 'Kinyarwanda'),
    ('ko', 'Korean'),
    ('ku', 'Kurdish (Kurmanji)'),
    ('ky', 'Kyrgyz'),
    ('lo', 'Lao'),
    ('la', 'Latin'),
    ('lv', 'Latvian'),
    ('lt', 'Lithuanian'),
    ('lb', 'Luxembourgish'),
    ('mk', 'Macedonian'),
    ('mg', 'Malagasy'),
    ('ms', 'Malay'),
    ('ml', 'Malayalam'),
    ('mt', 'Maltese'),
    ('mi', 'Maori'),
    ('mr', 'Marathi'),
    ('mn', 'Mongolian'),
    ('my', 'Myanmar (Burmese)'),
    ('ne', 'Nepali'),
    ('no', 'Norwegian'),
    ('or', 'Odia (Oriya)'),
    ('ps', 'Pashto'),
    ('fa', 'Persian'),
    ('pl', 'Polish'),
    ('pt', 'Portuguese'),
    ('pa', 'Punjabi'),
    ('ro', 'Romanian'),
    ('ru', 'Russian'),
    ('sm', 'Samoan'),
    ('gd', 'Scots Gaelic'),
    ('sr', 'Serbian'),
    ('st', 'Sesotho'),
    ('sn', 'Shona'),
    ('sd', 'Sindhi'),
    ('si', 'Sinhala'),
    ('sk', 'Slovak'),
    ('sl', 'Slovenian'),
    ('so', 'Somali'),
    ('es', 'Spanish'),
    ('su', 'Sundanese'),
    ('sw', 'Swahili'),
    ('sv', 'Swedish'),
    ('tg', 'Tajik'),
    ('ta', 'Tamil'),
    ('te', 'Telugu'),
    ('th', 'Thai'),
    ('tr', 'Turkish'),
    ('uk', 'Ukrainian'),
    ('ur', 'Urdu'),
    ('ug', 'Uyghur'),
    ('uz', 'Uzbek'),
    ('vi', 'Vietnamese'),
    ('cy', 'Welsh'),
    ('xh', 'Xhosa'),
    ('yi', 'Yiddish'),
    ('yo', 'Yoruba'),
    ('zu', 'Zulu'),
]

config.plugins.foreca.target_language = ConfigSelection(
    choices=LANGUAGE_CHOICES, default='auto')

__version__ = "1.3.1"
VERSION = __version__
_AUTHOR_ = "by Lululla - 2026"
IDEAS = "@Bauernbub"
THANKS = "@Orlandox | @atvcaptain"
BASEURL = "https://www.foreca.com/"
TEMP_DIR = '/tmp/foreca'
SYSTEM_DIR = '/etc/enigma2/foreca'
PLUGIN_PATH = dirname(__file__)
SKINS_PATH = join(PLUGIN_PATH, "skins")
CUSTOM_SKINS_PATH = join(PLUGIN_PATH, "skins_user")
MOON_ICON_PATH = join(PLUGIN_PATH, "moon")
THUMB_PATH = join(PLUGIN_PATH, "thumb/")
DBG_DIR = join(PLUGIN_PATH, 'debug')
CONFIG_FILE = join(SYSTEM_DIR, "api_config.txt")
DATA_FILE = join(SYSTEM_DIR, "color_database.txt")
CACHE_BASE = join(TEMP_DIR, "foreca_map_cache")
METEOGRAM_CACHE = join(TEMP_DIR, "meteogram")
WEATHER_DETAIL_CACHE = join(TEMP_DIR, "weather_detail")
TOKEN_FILE = join(CACHE_BASE, "token.json")
WETTERKONTOR_CACHE = join(CACHE_BASE, "wetterkontor/")

INSTALLER_URL = "https://raw.githubusercontent.com/Belfagor2005/ForecaOne/main/installer.sh"

DEBUG = True
CACHE_EXPIRE = 3600


# Create necessary directories
if not exists(SYSTEM_DIR):
    makedirs(SYSTEM_DIR)

if not exists(TEMP_DIR):
    makedirs(TEMP_DIR)

if not exists(DBG_DIR):
    makedirs(DBG_DIR)

if not exists(CACHE_BASE):
    makedirs(CACHE_BASE)

if not exists(WETTERKONTOR_CACHE):
    makedirs(WETTERKONTOR_CACHE)

if not exists(METEOGRAM_CACHE):
    makedirs(METEOGRAM_CACHE)

if not exists(WEATHER_DETAIL_CACHE):
    makedirs(WEATHER_DETAIL_CACHE)

PluginLanguageDomain = "Foreca1"
PluginLanguagePath = "Extensions/Foreca1/locale"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

OSM_HEADERS = {
    "User-Agent": "ForecaPlugin/1.1.4 (Enigma2; OpenStreetMap; non-commercial; +https://github.com/Belfagor2005/ForecaOne/)",
    "Referer": "https://www.foreca.com",
    "Accept": "image/webp,image/png,image/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


# ============================================================
# TRANSLATION FUNCTION WITH ENGINE SELECTION
# ============================================================

def localeInit():
    """Initialize locale for gettext translations."""
    lang = language.getLanguage()[:2]
    environ["LANGUAGE"] = lang
    if PluginLanguageDomain and PluginLanguagePath:
        gettext.bindtextdomain(
            PluginLanguageDomain,
            resolveFilename(
                SCOPE_PLUGINS,
                PluginLanguagePath),
        )


# Import Google Translate function (lazy import to avoid circular deps)
def _get_google_translate():
    """Lazy import of google_translate module."""
    try:
        from .google_translate import trans
        return trans
    except ImportError:
        print("[Foreca1] Google Translate module not available, falling back to gettext")
        return None


def _restore_placeholders_from_original(original, translated):
    """
    Restore placeholders in translated string using original string as reference.
    Works with {name}, {0}, %(name)s, %s, etc.
    """
    if not original or not translated:
        return translated

    # Extract all placeholders from original
    placeholders = []

    # 1. C# style: {name}, {0}
    for match in re.finditer(r'\{[^{}]+\}', original):
        placeholders.append(match.group(0))

    # 2. Python style: %(name)s, %(name)d, etc.
    for match in re.finditer(
        r'%\([a-zA-Z_][a-zA-Z0-9_]*\)[diouxXeEfFgGcrs]',
            original):
        placeholders.append(match.group(0))

    # 3. Python style: %s, %d, etc.
    for match in re.finditer(r'%[diouxXeEfFgGcrs]', original):
        placeholders.append(match.group(0))

    if not placeholders:
        return translated

    # Try to restore placeholders in translated string
    result = translated
    for placeholder in placeholders:
        # If the placeholder appears in original but not in translated, skip
        if placeholder not in original:
            continue

        # Try to find where the placeholder should be in translated
        # Simple approach: if translated contains the placeholder, keep it
        if placeholder in translated:
            continue

        # Otherwise, try to find if the placeholder was translated
        # We need to know the context to restore it properly
        # Without mapping, we can't know which translated word corresponds to
        # which placeholder

        # Fallback: keep the translated string as-is
        # The user will need to fix the .po files
        pass

    return result


def _get_system_language():
    """Get system language in short format"""
    try:
        from Components.config import config
        lang = config.misc.language.value
        return lang.split('_')[0].lower()
    except Exception:
        lang = config.osd.language.value
        return lang.split('_')[0].lower()


def _has_placeholders(text):
    """
    Check if text contains placeholders that would break .format().
    Returns True ONLY if the placeholders are the ENTIRE string.
    """
    if not text:
        return False

    # If the string is exactly a placeholder pattern, skip translation
    # Example: "{hours} h {mins} min" - has placeholders but also text
    # We need to check if the string contains ONLY placeholders

    # If the string contains { but also has text around it, we CAN translate
    # But we need to protect the placeholders before translating

    return False


def _(txt):
    """
    Translation function with placeholder protection.
    Protects placeholders before translation to prevent KeyError.
    """
    if not txt:
        return ""

    # Read settings
    use_google = config.plugins.foreca.translation_engine.value
    target_lang = config.plugins.foreca.target_language.value

    if target_lang == 'auto':
        target_lang = _get_system_language()

    # ---- PROTECT PLACEHOLDERS BEFORE TRANSLATION ----
    placeholders = {}
    protected_text = txt

    # Protect C# placeholders: {name}, {0}, {hours}
    csharp_matches = re.findall(r'\{[^{}]+\}', protected_text)
    for i, match in enumerate(csharp_matches):
        placeholder = f"__PH_{i}__"
        protected_text = protected_text.replace(match, placeholder)
        placeholders[placeholder] = match

    # Protect Python placeholders: %(name)s, %s
    python_matches = re.findall(
        r'%\([a-zA-Z_][a-zA-Z0-9_]*\)[diouxXeEfFgGcrs]|%[diouxXeEfFgGcrs]',
        protected_text)
    for i, match in enumerate(python_matches):
        placeholder = f"__PY_{i}__"
        protected_text = protected_text.replace(match, placeholder)
        placeholders[placeholder] = match

    # ---- TRANSLATE THE PROTECTED TEXT ----
    translated_text = None

    # Try Google Translate first
    if use_google:
        trans_func = _get_google_translate()
        if trans_func:
            try:
                result = trans_func(protected_text, target_lang=target_lang)
                if result and result != protected_text:
                    translated_text = result
            except Exception as e:
                print("[Foreca1] Google Translate error: %s" % str(e))

    # Fallback to gettext
    if translated_text is None:
        try:
            old_lang = environ.get('LANGUAGE')
            environ['LANGUAGE'] = target_lang
            gettext.bindtextdomain(
                PluginLanguageDomain, resolveFilename(
                    SCOPE_PLUGINS, PluginLanguagePath))
            gettext.textdomain(PluginLanguageDomain)

            translated_text = gettext.dgettext(
                PluginLanguageDomain, protected_text)

            if old_lang:
                environ['LANGUAGE'] = old_lang
            else:
                if 'LANGUAGE' in environ:
                    del environ['LANGUAGE']
        except Exception as e:
            print("[Foreca1] gettext error: %s" % str(e))

    # ---- RESTORE PLACEHOLDERS ----
    if translated_text and translated_text != protected_text:
        for placeholder, original in placeholders.items():
            translated_text = translated_text.replace(placeholder, original)
        return translated_text

    # Ultimate fallback (restore placeholders in original text too)
    result = txt
    for placeholder, original in placeholders.items():
        result = result.replace(placeholder, original)
    return result


localeInit()
language.addCallback(localeInit)

# ============================================================
# SKIN LOADING FUNCTIONS
# ============================================================


def get_screen_resolution():
    """Get current screen resolution."""
    desktop = getDesktop(0)
    return desktop.size()


def get_resolution_type():
    """Get resolution type: hd, fhd, wqhd."""
    width = get_screen_resolution().width()
    if width >= 2560:
        return 'wqhd'
    elif width >= 1920:
        return 'fhd'
    else:
        return 'hd'


def load_skin_by_class(class_name):
    """Load skin using class name and current resolution.
    First tries custom skins (skins_user/), then built-in skins (skins/).
    """
    if DEBUG:
        print("\n" + "=" * 60)
        print("[SKIN DEBUG] Looking for skin: '%s'" % class_name)
        print("[SKIN DEBUG] Built-in skins path = %s" % SKINS_PATH)
        print("[SKIN DEBUG] Custom skins path = %s" % CUSTOM_SKINS_PATH)

    resolution = get_resolution_type()
    if DEBUG:
        print("[SKIN DEBUG] resolution = %s" % resolution)

    # 1) Try custom skins first
    custom_skin_file = None
    if exists(CUSTOM_SKINS_PATH):
        custom_skin_file = join(
            CUSTOM_SKINS_PATH,
            resolution,
            "%s.xml" %
            class_name)
        if DEBUG:
            print("[SKIN DEBUG] Trying custom: %s" % custom_skin_file)
            print("[SKIN DEBUG] Exists? %s" % exists(custom_skin_file))
    else:
        if DEBUG:
            print("[SKIN DEBUG] Custom skins directory does not exist")

    # 2) Built-in skins
    builtin_skin_file = join(SKINS_PATH, resolution, "%s.xml" % class_name)
    fallback_skin_file = join(SKINS_PATH, "hd", "%s.xml" % class_name)

    # Determine which file to load
    skin_file = None
    if custom_skin_file and exists(custom_skin_file):
        skin_file = custom_skin_file
        if DEBUG:
            print("[SKIN DEBUG] Using custom skin")
    elif exists(builtin_skin_file):
        skin_file = builtin_skin_file
        if DEBUG:
            print("[SKIN DEBUG] Using built-in skin for current resolution")
    elif exists(fallback_skin_file):
        skin_file = fallback_skin_file
        if DEBUG:
            print("[SKIN DEBUG] Using HD fallback skin")
    else:
        if DEBUG:
            print("[SKIN DEBUG] No skin found at all")

    if skin_file and exists(skin_file):
        if DEBUG:
            print("[SKIN DEBUG] ✓ FOUND! Loading file: %s" % skin_file)
        try:
            with codecs.open(skin_file, 'r', 'utf-8') as f:
                content = f.read()
                if DEBUG:
                    print("[SKIN DEBUG] ✓ Loaded %d bytes" % len(content))
                    print("[SKIN DEBUG] First 100 chars: %s" %
                          content[:100].replace(chr(10), ' '))
                    print("=" * 60 + "\n")
                return content
        except Exception as e:
            print("[SKIN DEBUG] ✗ Error reading file: %s" % e)
    else:
        print("[SKIN DEBUG] ✗ SKIN FILE MISSING: %s" % skin_file)
    if DEBUG:
        print("=" * 60 + "\n")
    return None


def load_skin_for_class(cls):
    """Load skin for a specific class."""
    return load_skin_by_class(cls.__name__)


def apply_global_theme(screen):
    """
    Applies the background color (from set_color.conf) and transparency (from set_alpha.conf)
    to the standard 'background_plate' and 'selection_overlay' widgets on the screen.
    """
    color_file = join(SYSTEM_DIR, "set_color.conf")
    alpha_file = join(SYSTEM_DIR, "set_alpha.conf")

    # Background color
    if exists(color_file):
        try:
            with open(color_file, "r") as f:
                parts = f.read().strip().split()
                if len(parts) >= 3:
                    r, g, b = parts[0], parts[1], parts[2]
                    bg_color = gRGB(int(r), int(g), int(b))
                    if "background_plate" in screen:
                        screen["background_plate"].instance.setBackgroundColor(
                            bg_color)
        except Exception as e:
            print("[Theme] Error loading color:", e)

    # Transparency
    if exists(alpha_file):
        try:
            with open(alpha_file, "r") as f:
                alpha = f.read().strip()
                if "selection_overlay" in screen:
                    screen["selection_overlay"].instance.setBackgroundColor(
                        parseColor(alpha))
        except Exception as e:
            print("[Theme] Error loading alpha:", e)


def get_icon_path(icon_name, fallback='na.png'):
    """
    Returns the full path of an icon from the thumb/ folder.
    If the file does not exist, returns the path of the fallback icon (na.png).
    """
    path = join(THUMB_PATH, icon_name)
    if exists(path):
        return path

    # Fallback to the na.png icon
    fallback_path = join(THUMB_PATH, fallback)
    return fallback_path if exists(fallback_path) else None


def cleanup_temp_files(keep_token=True):
    """Remove temporary folders, optionally keep the token."""
    dirs_to_clean = [TEMP_DIR, DBG_DIR]
    for d in dirs_to_clean:
        if not exists(d):
            continue
        try:
            if keep_token and d == TEMP_DIR:
                # Delete everything inside TEMP_DIR except the token file
                token_path = join(TEMP_DIR, "foreca_map_cache", "token.json")
                for root, dirs, files in walk(d, topdown=False):
                    for name in files:
                        file_path = join(root, name)
                        if file_path != token_path:
                            remove(file_path)
                    for name in dirs:
                        dir_path = join(root, name)
                        # Skip the cache directory that contains token
                        if dir_path == join(TEMP_DIR, "foreca_map_cache"):
                            continue
                        rmdir(dir_path)
                # Recreate essential subdirectories
                subdirs = [
                    "meteogram",
                    "weather_detail",
                    "foreca_map_cache/wetterkontor"]
                for sub in subdirs:
                    subdir = join(TEMP_DIR, sub)
                    if not exists(subdir):
                        makedirs(subdir)
                if DEBUG:
                    print("[Cleanup] Cleaned %s (kept token)" % d)
            else:
                shutil.rmtree(d)
                if DEBUG:
                    print("[Cleanup] Removed %s" % d)
                if d == TEMP_DIR:
                    makedirs(d)
                    # Also recreate subdirs if TEMP_DIR was completely removed
                    for sub in [
                        "meteogram",
                        "weather_detail",
                            "foreca_map_cache/wetterkontor"]:
                        subdir = join(d, sub)
                        if not exists(subdir):
                            makedirs(subdir)
                elif d == DBG_DIR:
                    makedirs(d)
        except Exception as e:
            print("[Cleanup] Error cleaning %s: %s" % (d, e))
