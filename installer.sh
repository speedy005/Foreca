
#!/bin/bash

# =========================================================
# ForecaOne Installer
# =========================================================

VERSION="1.4.2"
CHANGELOG="Fix Malformated Locale Language.
Offer coffee if you like this plugin"

TMPPATH="/tmp/ForecaOne-install"
FILEPATH="/tmp/ForecaOne-main.tar.gz"
BACKUP_DIR="/tmp/foreca_backup"

CONFIG_DIR="/etc/enigma2/foreca"

DOWNLOAD_URL="https://github.com/speedy005/Foreca/archive/refs/heads/main.tar.gz"

# ---------------------------------------------------------
# Determine plugin path
# ---------------------------------------------------------

if [ -d "/usr/lib64" ]; then
    PLUGINPATH="/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1"
else
    PLUGINPATH="/usr/lib/enigma2/python/Plugins/Extensions/Foreca1"
fi

# ---------------------------------------------------------
# Global variables
# ---------------------------------------------------------

OSTYPE="Unknown"
STATUS=""
PYTHON="Unknown"
PYTHON_CMD="python"
PYTHON_VERSION="Unknown"

DISTRO="Unknown"
DISTRO_VERSION="Unknown"
BOX_TYPE="Unknown"

BACKUP_CREATED=0
INSTALL_STARTED=0


# =========================================================
# Functions
# =========================================================

log() {
    echo "[ForecaOne] $1"
}


error() {
    echo
    echo "========================================================="
    echo "ERROR: $1"
    echo "========================================================="
    echo
}


cleanup() {
    log "Cleaning up temporary files..."

    [ -d "$TMPPATH" ] && rm -rf "$TMPPATH"
    [ -f "$FILEPATH" ] && rm -f "$FILEPATH"
}


detect_os() {

    if [ -f "/var/lib/dpkg/status" ]; then

        OSTYPE="DreamOs"
        STATUS="/var/lib/dpkg/status"

    elif [ -f "/etc/opkg/opkg.conf" ] || [ -f "/var/lib/opkg/status" ]; then

        OSTYPE="OE"
        STATUS="/var/lib/opkg/status"

    elif [ -f "/etc/debian_version" ]; then

        OSTYPE="Debian"
        STATUS="/var/lib/dpkg/status"

    else

        OSTYPE="Unknown"
        STATUS=""

    fi

    log "Detected OS type: $OSTYPE"
}


detect_python() {

    if command -v python3 >/dev/null 2>&1; then

        PYTHON_CMD="python3"
        PYTHON="PY3"

    elif command -v python >/dev/null 2>&1; then

        if python --version 2>&1 | grep -q "^Python 3\."; then

            PYTHON_CMD="python"
            PYTHON="PY3"

        else

            PYTHON_CMD="python"
            PYTHON="PY2"

        fi

    else

        error "Python was not found."
        exit 1

    fi

    PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1)

    log "Python detected: $PYTHON_VERSION"

    if [ "$PYTHON" = "PY3" ]; then

        PACKAGESIX="python3-six"
        PACKAGEREQUESTS="python3-requests"
        PACKAGEPILLOW="python3-pillow"

    else

        PACKAGESIX="python-six"
        PACKAGEREQUESTS="python-requests"
        PACKAGEPILLOW="python-pillow"

    fi
}


detect_image() {

    BOX_TYPE=$(head -n 1 /etc/hostname 2>/dev/null || echo "Unknown")


    # OpenPLi / enigma.info
    if [ -f "/usr/lib/enigma.info" ]; then

        DISTRO=$(grep "^distro=" /usr/lib/enigma.info 2>/dev/null \
            | head -n 1 \
            | cut -d "=" -f 2-)

        DISTRO_VERSION=$(grep "^imageversion=" /usr/lib/enigma.info 2>/dev/null \
            | head -n 1 \
            | cut -d "=" -f 2-)


    # OpenATV / image-version
    elif [ -f "/etc/image-version" ]; then

        DISTRO=$(grep "^distro=" /etc/image-version 2>/dev/null \
            | head -n 1 \
            | cut -d "=" -f 2-)

        DISTRO_VERSION=$(grep "^version=" /etc/image-version 2>/dev/null \
            | head -n 1 \
            | cut -d "=" -f 2-)


    # Fallback
    else

        DISTRO="Unknown"
        DISTRO_VERSION="Unknown"

    fi


    [ -z "$DISTRO" ] && DISTRO="Unknown"
    [ -z "$DISTRO_VERSION" ] && DISTRO_VERSION="Unknown"
    [ -z "$BOX_TYPE" ] && BOX_TYPE="Unknown"


    log "Image: $DISTRO $DISTRO_VERSION"
}


install_wget() {

    if command -v wget >/dev/null 2>&1; then
        log "wget already installed."
        return 0
    fi


    log "wget not found. Installing wget..."


    case "$OSTYPE" in

        "DreamOs"|"Debian")

            apt-get update &&
            apt-get install -y wget

            ;;


        "OE")

            opkg update &&
            opkg install wget

            ;;


        *)

            error "Cannot install wget on unknown OS."
            exit 1

            ;;

    esac


    if ! command -v wget >/dev/null 2>&1; then

        error "wget installation failed."
        exit 1

    fi
}


package_installed() {

    local pkg="$1"


    case "$OSTYPE" in

        "DreamOs"|"Debian")

            if [ -f "$STATUS" ] &&
               grep -qs "^Package: $pkg$" "$STATUS"; then

                return 0

            fi

            ;;


        "OE")

            if command -v opkg >/dev/null 2>&1 &&
               opkg status "$pkg" 2>/dev/null |
               grep -q "^Status:.*ok installed"; then

                return 0

            fi

            ;;

    esac


    return 1
}


install_pkg() {

    local pkg="$1"


    [ -z "$pkg" ] && return 0


    if package_installed "$pkg"; then

        log "$pkg already installed."
        return 0

    fi


    log "Installing package: $pkg"


    case "$OSTYPE" in

        "DreamOs"|"Debian")

            apt-get update >/dev/null 2>&1 &&
            apt-get install -y "$pkg"

            ;;


        "OE")

            opkg update >/dev/null 2>&1 &&
            opkg install "$pkg"

            ;;


        *)

            log "Cannot install $pkg on unknown OS."
            return 1

            ;;

    esac


    if package_installed "$pkg"; then

        log "$pkg installed successfully."
        return 0

    fi


    log "Warning: Could not verify installation of $pkg."
    return 1
}


install_dependencies() {

    log "Checking dependencies..."


    if [ "$PYTHON" = "PY3" ]; then

        install_pkg "$PACKAGESIX" || true

    fi


    install_pkg "$PACKAGEREQUESTS" || true


    # Pillow is used by some versions of Foreca.
    # Install it if available.
    install_pkg "$PACKAGEPILLOW" || true


    # Additional OpenEmbedded dependencies
    if [ "$OSTYPE" = "OE" ]; then

        log "Installing additional OpenEmbedded dependencies..."

        for pkg in \
            ffmpeg \
            gstplayer \
            exteplayer3 \
            enigma2-plugin-systemplugins-serviceapp
        do

            install_pkg "$pkg" || true

        done

    fi
}


backup_config() {

    BACKUP_CREATED=0


    if [ ! -d "$CONFIG_DIR" ]; then

        log "No existing configuration directory found."
        log "Skipping configuration backup."

        return 0

    fi


    log "Creating configuration backup..."

    rm -rf "$BACKUP_DIR"


    if cp -a "$CONFIG_DIR" "$BACKUP_DIR"; then

        BACKUP_CREATED=1
        log "Configuration backup successful."

    else

        error "Configuration backup failed."
        exit 1

    fi
}


restore_config() {

    if [ "$BACKUP_CREATED" -ne 1 ]; then

        return 0

    fi


    if [ ! -d "$BACKUP_DIR" ]; then

        log "No backup found. Nothing to restore."
        return 0

    fi


    log "Restoring configuration..."


    mkdir -p "$CONFIG_DIR"


    if cp -a "$BACKUP_DIR"/. "$CONFIG_DIR"/ 2>/dev/null; then

        log "Configuration restored successfully."

    else

        log "Warning: Some configuration files could not be restored."

    fi


    rm -rf "$BACKUP_DIR"

    BACKUP_CREATED=0
}


download_package() {

    log "Downloading ForecaOne..."

    rm -f "$FILEPATH"


    if wget \
        --no-verbose \
        --timeout=30 \
        --tries=3 \
        "$DOWNLOAD_URL" \
        -O "$FILEPATH"
    then

        log "Download successful."

    else

        error "Failed to download ForecaOne package."

        cleanup
        exit 1

    fi


    if [ ! -s "$FILEPATH" ]; then

        error "Downloaded archive is empty."

        cleanup
        exit 1

    fi
}


extract_package() {

    log "Extracting package..."

    rm -rf "$TMPPATH"
    mkdir -p "$TMPPATH"


    if tar -xzf "$FILEPATH" -C "$TMPPATH"; then

        log "Extraction successful."

    else

        error "Failed to extract ForecaOne package."

        cleanup
        exit 1

    fi
}


find_plugin_source() {

    PLUGIN_SOURCE=""


    # Standard 32-bit / normal path
    if [ -d "$TMPPATH/Foreca-main/usr/lib/enigma2/python/Plugins/Extensions/Foreca1" ]; then

        PLUGIN_SOURCE="$TMPPATH/Foreca-main/usr/lib/enigma2/python/Plugins/Extensions/Foreca1"

        log "Found plugin in standard /usr/lib directory."


    # 64-bit path
    elif [ -d "$TMPPATH/Foreca-main/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1" ]; then

        PLUGIN_SOURCE="$TMPPATH/Foreca-main/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1"

        log "Found plugin in /usr/lib64 directory."


    # Search fallback
    else

        PLUGIN_SOURCE=$(find "$TMPPATH" \
            -type d \
            -path "*/Plugins/Extensions/Foreca1" \
            2>/dev/null \
            | head -n 1)


        if [ -n "$PLUGIN_SOURCE" ]; then

            log "Found plugin using fallback search:"
            log "$PLUGIN_SOURCE"

        fi

    fi


    if [ -z "$PLUGIN_SOURCE" ] || [ ! -d "$PLUGIN_SOURCE" ]; then

        error "Could not find Foreca1 plugin files in archive."

        echo
        echo "Available directories:"
        find "$TMPPATH" -maxdepth 6 -type d 2>/dev/null | head -50
        echo

        cleanup
        exit 1

    fi
}


backup_existing_plugin() {

    OLD_PLUGIN_BACKUP="/tmp/ForecaOne-old-plugin"


    rm -rf "$OLD_PLUGIN_BACKUP"


    if [ -d "$PLUGINPATH" ]; then

        log "Backing up currently installed plugin..."

        if cp -a "$PLUGINPATH" "$OLD_PLUGIN_BACKUP"; then

            log "Existing plugin backup created."

        else

            error "Could not backup existing plugin."
            exit 1

        fi

    fi
}


install_plugin() {

    log "Installing plugin files..."

    INSTALL_STARTED=1


    mkdir -p "$PLUGINPATH"


    if cp -a "$PLUGIN_SOURCE"/. "$PLUGINPATH"/; then

        log "Plugin files copied successfully."

    else

        error "Failed to copy plugin files."

        rollback_plugin
        cleanup

        exit 1

    fi


    # Verify that the plugin directory contains files
    if [ -z "$(find "$PLUGINPATH" -type f 2>/dev/null | head -n 1)" ]; then

        error "Plugin installation appears to be empty."

        rollback_plugin
        cleanup

        exit 1

    fi
}


rollback_plugin() {

    OLD_PLUGIN_BACKUP="/tmp/ForecaOne-old-plugin"


    if [ -d "$OLD_PLUGIN_BACKUP" ]; then

        log "Rolling back previous plugin installation..."

        rm -rf "$PLUGINPATH"
        mkdir -p "$(dirname "$PLUGINPATH")"


        if cp -a "$OLD_PLUGIN_BACKUP" "$PLUGINPATH"; then

            log "Plugin rollback successful."

        else

            log "WARNING: Plugin rollback failed!"

        fi


        rm -rf "$OLD_PLUGIN_BACKUP"

    else

        log "No previous plugin backup available."

    fi
}


remove_old_plugin_backup() {

    OLD_PLUGIN_BACKUP="/tmp/ForecaOne-old-plugin"

    [ -d "$OLD_PLUGIN_BACKUP" ] && rm -rf "$OLD_PLUGIN_BACKUP"
}


show_info() {

    echo
    echo "#########################################################"
    echo "#               INSTALLED SUCCESSFULLY                  #"
    echo "#                developed by LULULLA                   #"
    echo "#               https://corvoboys.org                   #"
    echo "#########################################################"
    echo "#           PLEASE RESTART YOUR DEVICE                  #"
    echo "#########################################################"
    echo
    echo "Debug information:"
    echo "---------------------------------------------------------"
    echo "BOX MODEL:      $BOX_TYPE"
    echo "OS SYSTEM:      $OSTYPE"
    echo "PYTHON:         $PYTHON_VERSION"
    echo "PYTHON TYPE:    $PYTHON"
    echo "IMAGE NAME:     $DISTRO"
    echo "IMAGE VERSION:  $DISTRO_VERSION"
    echo "PLUGIN VERSION: $VERSION"
    echo "PLUGIN PATH:    $PLUGINPATH"
    echo "---------------------------------------------------------"
    echo
    echo "Changelog:"
    echo "$CHANGELOG"
    echo
}


# =========================================================
# Main
# =========================================================

echo
echo "========================================================="
echo "             ForecaOne Installer v$VERSION"
echo "========================================================="
echo


# Must run as root
if [ "$(id -u)" -ne 0 ]; then

    error "This installer must be executed as root."

    exit 1

fi


# Detect environment
detect_os
detect_python
detect_image


# Check wget
install_wget


# Install dependencies
install_dependencies


# Prepare temporary directory
cleanup
mkdir -p "$TMPPATH"


# Backup configuration
backup_config


# Download
download_package


# Extract
extract_package


# Find plugin files
find_plugin_source


# Backup currently installed plugin
backup_existing_plugin


# Install plugin
install_plugin


# Restore configuration
restore_config


# Remove old plugin backup after successful installation
remove_old_plugin_backup


# Sync filesystem
sync


# Cleanup
cleanup


# Final information
show_info


exit 0

