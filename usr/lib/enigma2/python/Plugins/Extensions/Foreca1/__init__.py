#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026

from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Components.Language import language
from Components.config import (
    config,
    ConfigSubsection,
    ConfigBoolean,
    ConfigSelection
)
from enigma import getDesktop, gRGB
from skin import parseColor

from os import (
    environ,
    walk,
    remove,
    rmdir,
    makedirs
)
from os.path import (
    exists,
    join,
    dirname
)

import gettext
import codecs
import shutil
import re


# ============================================================
# VERSION / PLUGIN INFORMATION
# ============================================================

__version__ = "1.4.2"
VERSION = __version__

_AUTHOR_ = "by speedy - 2026"
IDEAS = "@Bauernbub"
THANKS = "@Orlandox | @atvcaptain"

BASEURL = "https://www.foreca.com/"

INSTALLER_URL = (
    "https://raw.githubusercontent.com/"
    "speedy005/Foreca/main/installer.sh"
)


# ============================================================
# PATH CONFIGURATION
# ============================================================

TEMP_DIR = "/tmp/foreca"
SYSTEM_DIR = "/etc/enigma2/foreca"

PLUGIN_PATH = dirname(__file__)

SKINS_PATH = join(PLUGIN_PATH, "skins")
CUSTOM_SKINS_PATH = join(PLUGIN_PATH, "skins_user")
MOON_ICON_PATH = join(PLUGIN_PATH, "moon")
THUMB_PATH = join(PLUGIN_PATH, "thumb")

DBG_DIR = join(PLUGIN_PATH, "debug")

CONFIG_FILE = join(SYSTEM_DIR, "api_config.txt")
DATA_FILE = join(SYSTEM_DIR, "color_database.txt")

CACHE_BASE = join(TEMP_DIR, "foreca_map_cache")
METEOGRAM_CACHE = join(TEMP_DIR, "meteogram")
WEATHER_DETAIL_CACHE = join(TEMP_DIR, "weather_detail")
WETTERKONTOR_CACHE = join(CACHE_BASE, "wetterkontor")

TOKEN_FILE = join(CACHE_BASE, "token.json")


# ============================================================
# GENERAL CONFIGURATION
# ============================================================

DEBUG = True
CACHE_EXPIRE = 3600


# ============================================================
# TRANSLATION CONFIGURATION
# ============================================================

PluginLanguageDomain = "Foreca1"
PluginLanguagePath = "Extensions/Foreca1/locale"


# ------------------------------------------------------------
# Ensure plugin configuration namespace exists
# ------------------------------------------------------------

if not hasattr(config.plugins, "foreca"):
    config.plugins.foreca = ConfigSubsection()


# ------------------------------------------------------------
# Translation engine
#
# False = gettext / local PO files
# True  = Google Translate
# ------------------------------------------------------------

if not hasattr(config.plugins.foreca, "translation_engine"):
    config.plugins.foreca.translation_engine = ConfigBoolean(
        default=False
    )


# ------------------------------------------------------------
# Supported Google Translate languages
# ------------------------------------------------------------

LANGUAGE_CHOICES = [
    ("auto", "Auto (System Language)"),

    ("af", "Afrikaans"),
    ("sq", "Albanian"),
    ("am", "Amharic"),
    ("ar", "Arabic"),
    ("hy", "Armenian"),
    ("az", "Azerbaijani"),
    ("eu", "Basque"),
    ("be", "Belarusian"),
    ("bn", "Bengali"),
    ("bs", "Bosnian"),
    ("bg", "Bulgarian"),
    ("ca", "Catalan"),
    ("ceb", "Cebuano"),
    ("ny", "Chichewa"),

    ("zh-cn", "Chinese (Simplified)"),
    ("zh-tw", "Chinese (Traditional)"),

    ("co", "Corsican"),
    ("hr", "Croatian"),
    ("cs", "Czech"),
    ("da", "Danish"),
    ("nl", "Dutch"),
    ("en", "English"),
    ("eo", "Esperanto"),
    ("et", "Estonian"),
    ("tl", "Filipino"),
    ("fi", "Finnish"),
    ("fr", "French"),
    ("fy", "Frisian"),
    ("gl", "Galician"),
    ("ka", "Georgian"),
    ("de", "German"),
    ("el", "Greek"),
    ("gu", "Gujarati"),
    ("ht", "Haitian Creole"),
    ("ha", "Hausa"),
    ("haw", "Hawaiian"),

    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("hmn", "Hmong"),
    ("hu", "Hungarian"),
    ("is", "Icelandic"),
    ("ig", "Igbo"),
    ("id", "Indonesian"),
    ("ga", "Irish"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("jw", "Javanese"),
    ("kn", "Kannada"),
    ("kk", "Kazakh"),
    ("km", "Khmer"),
    ("rw", "Kinyarwanda"),
    ("ko", "Korean"),
    ("ku", "Kurdish (Kurmanji)"),
    ("ky", "Kyrgyz"),
    ("lo", "Lao"),
    ("la", "Latin"),
    ("lv", "Latvian"),
    ("lt", "Lithuanian"),
    ("lb", "Luxembourgish"),
    ("mk", "Macedonian"),
    ("mg", "Malagasy"),
    ("ms", "Malay"),
    ("ml", "Malayalam"),
    ("mt", "Maltese"),
    ("mi", "Maori"),
    ("mr", "Marathi"),
    ("mn", "Mongolian"),
    ("my", "Myanmar (Burmese)"),
    ("ne", "Nepali"),
    ("no", "Norwegian"),
    ("or", "Odia (Oriya)"),
    ("ps", "Pashto"),
    ("fa", "Persian"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("pa", "Punjabi"),
    ("ro", "Romanian"),
    ("ru", "Russian"),
    ("sm", "Samoan"),
    ("gd", "Scots Gaelic"),
    ("sr", "Serbian"),
    ("st", "Sesotho"),
    ("sn", "Shona"),
    ("sd", "Sindhi"),
    ("si", "Sinhala"),
    ("sk", "Slovak"),
    ("sl", "Slovenian"),
    ("so", "Somali"),
    ("es", "Spanish"),
    ("su", "Sundanese"),
    ("sw", "Swahili"),
    ("sv", "Swedish"),
    ("tg", "Tajik"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("th", "Thai"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
    ("ur", "Urdu"),
    ("ug", "Uyghur"),
    ("uz", "Uzbek"),
    ("vi", "Vietnamese"),
    ("cy", "Welsh"),
    ("xh", "Xhosa"),
    ("yi", "Yiddish"),
    ("yo", "Yoruba"),
    ("zu", "Zulu"),
]


if not hasattr(config.plugins.foreca, "target_language"):
    config.plugins.foreca.target_language = ConfigSelection(
        choices=LANGUAGE_CHOICES,
        default="auto"
    )


# ============================================================
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": (
        "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
}


OSM_HEADERS = {
    "User-Agent": (
        "ForecaPlugin/1.4.2 "
        "(Enigma2; OpenStreetMap; non-commercial; "
        "+https://github.com/speedy005/Foreca)"
    ),
    "Referer": "https://www.foreca.com",
    "Accept": (
        "image/webp,image/png,image/*;q=0.8"
    ),
    "Accept-Language": (
        "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive",
}


# ============================================================
# DIRECTORY HELPERS
# ============================================================

def ensure_dir(path):
    """
    Create a directory if it does not exist.

    Safe for Python 2 and Python 3.
    """
    if not path:
        return False

    if exists(path):
        return True

    try:
        makedirs(path)
        return True

    except OSError:
        # Another process may have created it meanwhile.
        if exists(path):
            return True

        print(
            "[Foreca1] ERROR: Cannot create directory: %s"
            % path
        )

        return False


def ensure_directories():
    """
    Create all directories required by Foreca.
    """

    directories = [
        SYSTEM_DIR,
        TEMP_DIR,
        DBG_DIR,
        CACHE_BASE,
        WETTERKONTOR_CACHE,
        METEOGRAM_CACHE,
        WEATHER_DETAIL_CACHE,
    ]

    for directory in directories:
        if not ensure_dir(directory):
            print(
                "[Foreca1] WARNING: Directory unavailable: %s"
                % directory
            )


ensure_directories()


# ============================================================
# LANGUAGE / LOCALE HELPERS
# ============================================================

def normalize_language(lang):
    """
    Normalize an Enigma2 language value.

    Examples:

        de_DE  -> de
        de-DE  -> de
        it_IT  -> it
        en_GB  -> en
        zh_CN  -> zh-cn
        zh_TW  -> zh-tw
        iw     -> he
        he_IL  -> he
    """

    if not lang:
        return "en"

    try:
        lang = str(lang).strip()
    except Exception:
        return "en"

    if not lang:
        return "en"

    lang = lang.replace("-", "_").lower()

    aliases = {
        "iw": "he",
        "iw_il": "he",
        "he_il": "he",
        "in": "id",
        "ji": "yi",
        "zh_cn": "zh-cn",
        "zh_tw": "zh-tw",
    }

    if lang in aliases:
        return aliases[lang]

    # Preserve Google-compatible regional Chinese.
    if lang.startswith("zh_cn"):
        return "zh-cn"

    if lang.startswith("zh_tw"):
        return "zh-tw"

    return lang.split("_")[0]


def get_system_language():
    """
    Return the current Enigma2 language in normalized form.
    """

    # Primary Enigma2 setting.
    try:
        lang = language.getLanguage()

        if lang:
            return normalize_language(lang)

    except Exception:
        pass


    # Fallback: config.misc.language
    try:
        lang = config.misc.language.value

        if lang:
            return normalize_language(lang)

    except Exception:
        pass


    # Fallback: config.osd.language
    try:
        lang = config.osd.language.value

        if lang:
            return normalize_language(lang)

    except Exception:
        pass


    # Final fallback.
    return "en"


# ============================================================
# GETTEXT INITIALIZATION
# ============================================================

def localeInit():
    """
    Initialize the Foreca gettext domain.

    The locale directory is relative to the plugin directory:

        Extensions/Foreca1/locale
    """

    try:
        lang = get_system_language()

        environ["LANGUAGE"] = lang

    except Exception as e:
        print(
            "[Foreca1] Language initialization error: %s"
            % str(e)
        )


    try:
        locale_path = resolveFilename(
            SCOPE_PLUGINS,
            PluginLanguagePath
        )

        gettext.bindtextdomain(
            PluginLanguageDomain,
            locale_path
        )

        # Explicitly select our domain.
        gettext.textdomain(
            PluginLanguageDomain
        )

    except Exception as e:
        print(
            "[Foreca1] gettext initialization error: %s"
            % str(e)
        )


# Initialize immediately.
localeInit()

# Reinitialize whenever the Enigma2 language changes.
try:
    language.addCallback(localeInit)
except Exception as e:
    print(
        "[Foreca1] Could not register language callback: %s"
        % str(e)
    )


# ============================================================
# GOOGLE TRANSLATE IMPORT
# ============================================================

def _get_google_translate():
    """
    Lazy-load Google Translate.

    This prevents an unnecessary import when gettext is used.
    """

    try:
        from .google_translate import trans
        return trans

    except ImportError as e:

        if DEBUG:
            print(
                "[Foreca1] Google Translate unavailable: %s"
                % str(e)
            )

        return None

    except Exception as e:

        print(
            "[Foreca1] Google Translate import error: %s"
            % str(e)
        )

        return None


# ============================================================
# PLACEHOLDER PROTECTION
# ============================================================

_PLACEHOLDER_PATTERN = re.compile(
    r"""
    %\([a-zA-Z_][a-zA-Z0-9_]*\)[diouxXeEfFgGcrs]
    |
    %[diouxXeEfFgGcrs]
    |
    \{[^{}]+\}
    """,
    re.VERBOSE
)


def _protect_placeholders(text):
    """
    Replace format placeholders with safe tokens.

    Supported examples:

        {name}
        {0}
        {hours}
        %(name)s
        %s
        %d
    """

    placeholders = {}

    if not text:
        return text, placeholders


    counter = [0]


    def replace_match(match):
        original = match.group(0)

        token = "ZXQPH%04dZXQ" % counter[0]

        counter[0] += 1

        placeholders[token] = original

        return token


    try:
        protected = _PLACEHOLDER_PATTERN.sub(
            replace_match,
            text
        )

    except Exception:
        return text, {}


    return protected, placeholders


def _restore_placeholders(text, placeholders):
    """
    Restore placeholders after translation.
    """

    if not text or not placeholders:
        return text


    result = text


    for token, original in placeholders.items():

        result = result.replace(
            token,
            original
        )


    return result


# ============================================================
# TRANSLATION FUNCTION
# ============================================================

def _(txt):
    """
    Foreca translation function.

    Translation order:

        1. Google Translate if enabled
        2. Local gettext
        3. Original text

    Placeholders are protected while translating.
    """

    if txt is None:
        return ""

    if txt == "":
        return ""


    # Make sure gettext is initialized.
    try:
        localeInit()
    except Exception:
        pass


    # Read configuration.
    try:
        use_google = (
            config.plugins.foreca
            .translation_engine.value
        )

    except Exception:
        use_google = False


    try:
        target_lang = (
            config.plugins.foreca
            .target_language.value
        )

    except Exception:
        target_lang = "auto"


    if not target_lang or target_lang == "auto":
        target_lang = get_system_language()


    target_lang = normalize_language(
        target_lang
    )


    # Protect placeholders.
    protected_text, placeholders = (
        _protect_placeholders(txt)
    )


    # --------------------------------------------------------
    # Google Translate
    # --------------------------------------------------------

    if use_google:

        trans_func = _get_google_translate()

        if trans_func:

            try:

                translated = trans_func(
                    protected_text,
                    target_lang=target_lang
                )

                if translated:

                    translated = _restore_placeholders(
                        translated,
                        placeholders
                    )

                    return translated

            except Exception as e:

                print(
                    "[Foreca1] Google Translate error: %s"
                    % str(e)
                )


    # --------------------------------------------------------
    # Local gettext
    # --------------------------------------------------------

    try:

        locale_path = resolveFilename(
            SCOPE_PLUGINS,
            PluginLanguagePath
        )

        gettext.bindtextdomain(
            PluginLanguageDomain,
            locale_path
        )

        translated = gettext.dgettext(
            PluginLanguageDomain,
            protected_text
        )


        # gettext returns the original text if no
        # translation is available.
        if translated:

            translated = _restore_placeholders(
                translated,
                placeholders
            )

            return translated


    except Exception as e:

        print(
            "[Foreca1] gettext error: %s"
            % str(e)
        )


    # --------------------------------------------------------
    # Final fallback
    # --------------------------------------------------------

    return txt


# ============================================================
# SCREEN / RESOLUTION HELPERS
# ============================================================

def get_screen_resolution():
    """
    Return current screen resolution.
    """

    try:
        desktop = getDesktop(0)
        return desktop.size()

    except Exception as e:

        print(
            "[Foreca1] Could not determine screen resolution: %s"
            % str(e)
        )

        return None


def get_resolution_type():
    """
    Return:

        hd
        fhd
        wqhd
    """

    size = get_screen_resolution()

    if size is None:
        return "hd"


    try:
        width = size.width()

    except Exception:
        return "hd"


    if width >= 2560:
        return "wqhd"

    if width >= 1920:
        return "fhd"

    return "hd"


# ============================================================
# SKIN LOADING
# ============================================================

def load_skin_by_class(class_name):
    """
    Load skin according to class name and resolution.

    Priority:

        1. skins_user/<resolution>/<class>.xml
        2. skins/<resolution>/<class>.xml
        3. skins/hd/<class>.xml
    """

    if not class_name:
        return None


    resolution = get_resolution_type()


    if DEBUG:

        print(
            "[SKIN DEBUG] Looking for skin: '%s'"
            % class_name
        )

        print(
            "[SKIN DEBUG] Resolution: %s"
            % resolution
        )

        print(
            "[SKIN DEBUG] Built-in path: %s"
            % SKINS_PATH
        )

        print(
            "[SKIN DEBUG] Custom path: %s"
            % CUSTOM_SKINS_PATH
        )


    # --------------------------------------------------------
    # Custom skin
    # --------------------------------------------------------

    custom_skin_file = join(
        CUSTOM_SKINS_PATH,
        resolution,
        "%s.xml" % class_name
    )


    # --------------------------------------------------------
    # Built-in skin
    # --------------------------------------------------------

    builtin_skin_file = join(
        SKINS_PATH,
        resolution,
        "%s.xml" % class_name
    )


    # --------------------------------------------------------
    # HD fallback
    # --------------------------------------------------------

    fallback_skin_file = join(
        SKINS_PATH,
        "hd",
        "%s.xml" % class_name
    )


    skin_file = None


    if exists(custom_skin_file):

        skin_file = custom_skin_file

        if DEBUG:
            print("[SKIN DEBUG] Using custom skin.")


    elif exists(builtin_skin_file):

        skin_file = builtin_skin_file

        if DEBUG:
            print(
                "[SKIN DEBUG] Using built-in %s skin."
                % resolution
            )


    elif exists(fallback_skin_file):

        skin_file = fallback_skin_file

        if DEBUG:
            print("[SKIN DEBUG] Using HD fallback skin.")


    if not skin_file:

        print(
            "[SKIN DEBUG] Skin not found: %s"
            % class_name
        )

        return None


    # --------------------------------------------------------
    # Read skin
    # --------------------------------------------------------

    try:

        with codecs.open(
            skin_file,
            "r",
            "utf-8"
        ) as skin:

            content = skin.read()


        if DEBUG:

            print(
                "[SKIN DEBUG] Loaded: %s"
                % skin_file
            )

            print(
                "[SKIN DEBUG] Size: %d bytes"
                % len(content)
            )


        return content


    except Exception as e:

        print(
            "[SKIN DEBUG] Error reading skin: %s"
            % str(e)
        )

        return None


def load_skin_for_class(cls):
    """
    Load skin for a class.
    """

    if cls is None:
        return None

    return load_skin_by_class(
        cls.__name__
    )


# ============================================================
# GLOBAL THEME
# ============================================================

def apply_global_theme(screen):
    """
    Apply Foreca global color and transparency settings.
    """

    if screen is None:
        return


    color_file = join(
        SYSTEM_DIR,
        "set_color.conf"
    )

    alpha_file = join(
        SYSTEM_DIR,
        "set_alpha.conf"
    )


    # --------------------------------------------------------
    # Background color
    # --------------------------------------------------------

    if exists(color_file):

        try:

            with open(
                color_file,
                "r"
            ) as color:

                parts = (
                    color.read()
                    .strip()
                    .split()
                )


            if len(parts) >= 3:

                r = int(parts[0])
                g = int(parts[1])
                b = int(parts[2])


                # Clamp values.
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))


                bg_color = gRGB(
                    r,
                    g,
                    b
                )


                if "background_plate" in screen:

                    screen[
                        "background_plate"
                    ].instance.setBackgroundColor(
                        bg_color
                    )


        except Exception as e:

            print(
                "[Theme] Error loading color: %s"
                % str(e)
            )


    # --------------------------------------------------------
    # Transparency / color
    # --------------------------------------------------------

    if exists(alpha_file):

        try:

            with open(
                alpha_file,
                "r"
            ) as alpha:

                value = (
                    alpha.read()
                    .strip()
                )


            if (
                value
                and "selection_overlay" in screen
            ):

                screen[
                    "selection_overlay"
                ].instance.setBackgroundColor(
                    parseColor(value)
                )


        except Exception as e:

            print(
                "[Theme] Error loading alpha: %s"
                % str(e)
            )


# ============================================================
# ICON HELPERS
# ============================================================

def get_icon_path(
    icon_name,
    fallback="na.png"
):
    """
    Return icon path.

    Uses thumb/<icon_name>.
    Falls back to thumb/na.png.
    """

    if not icon_name:
        icon_name = fallback


    path = join(
        THUMB_PATH,
        icon_name
    )


    if exists(path):
        return path


    fallback_path = join(
        THUMB_PATH,
        fallback
    )


    if exists(fallback_path):
        return fallback_path


    return None


# ============================================================
# TEMP / CACHE CLEANUP
# ============================================================

def cleanup_temp_files(
    keep_token=True
):
    """
    Clean Foreca temporary files.

    If keep_token=True, token.json is preserved.
    """

    token_path = join(
        CACHE_BASE,
        "token.json"
    )


    try:

        if not exists(TEMP_DIR):
            return


        for root, dirs, files in walk(
            TEMP_DIR,
            topdown=False
        ):

            # ------------------------------------------------
            # Files
            # ------------------------------------------------

            for name in files:

                file_path = join(
                    root,
                    name
                )


                if (
                    keep_token
                    and file_path == token_path
                ):
                    continue


                try:

                    remove(file_path)

                except Exception as e:

                    if DEBUG:
                        print(
                            "[Cleanup] "
                            "Could not remove %s: %s"
                            % (
                                file_path,
                                str(e)
                            )
                        )


            # ------------------------------------------------
            # Directories
            # ------------------------------------------------

            for name in dirs:

                dir_path = join(
                    root,
                    name
                )


                # Do not remove cache directory
                # if token should be preserved.
                if (
                    keep_token
                    and (
                        dir_path == CACHE_BASE
                        or dir_path.startswith(
                            CACHE_BASE + "/"
                        )
                    )
                ):
                    continue


                try:

                    rmdir(dir_path)

                except OSError:

                    # Directory is not empty or cannot
                    # currently be removed.
                    pass

                except Exception as e:

                    if DEBUG:
                        print(
                            "[Cleanup] "
                            "Could not remove directory "
                            "%s: %s"
                            % (
                                dir_path,
                                str(e)
                            )
                        )


        # ----------------------------------------------------
        # Recreate required directories
        # ----------------------------------------------------

        ensure_directories()


        if DEBUG:

            print(
                "[Cleanup] Temporary files cleaned."
            )


    except Exception as e:

        print(
            "[Cleanup] Cleanup error: %s"
            % str(e)
        )


# ============================================================
# MODULE INITIALIZATION
# ============================================================

# Make sure gettext is ready after all helper functions exist.
try:
    localeInit()
except Exception:
    pass

