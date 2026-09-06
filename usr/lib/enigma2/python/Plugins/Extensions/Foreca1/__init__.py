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

__version__ = "1.4.8"
VERSION = __version__
_AUTHOR_ = "by speedy - 2026"
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

INSTALLER_URL = "https://raw.githubusercontent.com/speedy005/Foreca/refs/heads/master/installer.sh"

DEBUG = True
CACHE_EXPIRE = 3600


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
    "User-Agent": "ForecaPlugin/1.1.4 (Enigma2; OpenStreetMap; non-commercial; +https://github.com/speedy005/Foreca/tree/master/)",
    "Referer": "https://www.foreca.com",
    "Accept": "image/webp,image/png,image/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


def localeInit():
    lang = language.getLanguage()[:2]
    environ["LANGUAGE"] = lang
    if PluginLanguageDomain and PluginLanguagePath:
        gettext.bindtextdomain(
            PluginLanguageDomain,
            resolveFilename(
                SCOPE_PLUGINS,
                PluginLanguagePath),
        )


def _(txt):
    if not txt:
        return ""

    translated = gettext.dgettext(PluginLanguageDomain, txt)
    if translated and translated != txt:
        return translated

    print(
        "[%s] fallback to default translation for %s" %
        (PluginLanguageDomain, txt)
    )
    return gettext.gettext(txt)


localeInit()
language.addCallback(localeInit)


# ============ DETECT SCREEN RESOLUTION ============
def get_screen_resolution():
    """Get current screen resolution"""
    desktop = getDesktop(0)
    return desktop.size()


def get_resolution_type():
    """Get resolution type: hd, fhd, wqhd"""
    width = get_screen_resolution().width()

    if width >= 2560:
        return 'wqhd'
    elif width >= 1920:
        return 'fhd'
    else:  # 1280x720 or smaller
        return 'hd'


def load_skin_by_class(class_name):
    """Load skin using class name and current resolution.
    First tries custom skins (skins_user/), then built-in skins (skins/).
    """
    if DEBUG:
        print("\n" + "=" * 60)
        print(f"[SKIN DEBUG] Looking for skin: '{class_name}'")
        print(f"[SKIN DEBUG] Built-in skins path = {SKINS_PATH}")
        print(f"[SKIN DEBUG] Custom skins path = {CUSTOM_SKINS_PATH}")

    resolution = get_resolution_type()
    if DEBUG:
        print(f"[SKIN DEBUG] resolution = {resolution}")

    # 1) Try custom skins first
    custom_skin_file = None
    if exists(CUSTOM_SKINS_PATH):
        custom_skin_file = join(
            CUSTOM_SKINS_PATH,
            resolution,
            f"{class_name}.xml")
        if DEBUG:
            print(f"[SKIN DEBUG] Trying custom: {custom_skin_file}")
            print(f"[SKIN DEBUG] Exists? {exists(custom_skin_file)}")
    else:
        if DEBUG:
            print("[SKIN DEBUG] Custom skins directory does not exist")

    # 2) Built-in skins
    builtin_skin_file = join(SKINS_PATH, resolution, f"{class_name}.xml")
    fallback_skin_file = join(SKINS_PATH, "hd", f"{class_name}.xml")

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
            print(f"[SKIN DEBUG] ✓ FOUND! Loading file: {skin_file}")
        try:
            with codecs.open(skin_file, 'r', 'utf-8') as f:
                content = f.read()
                if DEBUG:
                    print(f"[SKIN DEBUG] ✓ Loaded {len(content)} bytes")
                    print(
                        f"[SKIN DEBUG] First 100 chars: {content[:100].replace(chr(10), ' ')}")
                    print("=" * 60 + "\n")
                return content
        except Exception as e:
            print(f"[SKIN DEBUG] ✗ Error reading file: {e}")
    else:
        print(f"[SKIN DEBUG] ✗ SKIN FILE MISSING: {skin_file}")
    if DEBUG:
        print("=" * 60 + "\n")
    return None


def load_skin_for_class(cls):
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

    # transparency
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
                    print(f"[Cleanup] Cleaned {d} (kept token)")
            else:
                shutil.rmtree(d)
                if DEBUG:
                    print(f"[Cleanup] Removed {d}")
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
            print(f"[Cleanup] Error cleaning {d}: {e}")
