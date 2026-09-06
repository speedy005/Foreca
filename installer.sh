#!/bin/bash

# =========================================================
# ForecaOne Installer
# =========================================================

version='1.4.5'

changelog='Fix Malformed Locale Language. Offer coffee if you like this plugin'


# =========================================================
# PATHS
# =========================================================

TMPPATH="/tmp/ForecaOne-install"
FILEPATH="/tmp/ForecaOne-master.tar.gz"

BACKUP_DIR="/tmp/foreca_backup"
OLD_PLUGIN_BACKUP="/tmp/ForecaOne-old-plugin"

CONFIG_DIR="/etc/enigma2/foreca"


# =========================================================
# DOWNLOAD
# =========================================================

# IMPORTANT:
# Keep this branch identical to INSTALLER_URL in __init__.py.

BRANCH="master"

DOWNLOAD_URL="https://github.com/speedy005/Foreca/archive/refs/heads/${BRANCH}.tar.gz"


# =========================================================
# DETERMINE PLUGIN PATH
# =========================================================

if [ -d "/usr/lib64" ]; then

    PLUGINPATH="/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1"

else

    PLUGINPATH="/usr/lib/enigma2/python/Plugins/Extensions/Foreca1"

fi


# =========================================================
# GLOBAL VARIABLES
# =========================================================

OSTYPE="Unknown"
STATUS=""

PYTHON="Unknown"
PYTHON_CMD=""
PYTHON_VERSION="Unknown"

DISTRO="Unknown"
DISTRO_VERSION="Unknown"
BOX_TYPE="Unknown"

PACKAGESIX=""
PACKAGEREQUESTS=""
PACKAGEPILLOW=""

PLUGIN_SOURCE=""

BACKUP_CREATED=0
INSTALL_STARTED=0


# =========================================================
# LOGGING
# =========================================================

log()
{
    echo "[ForecaOne] $1"
}


error()
{
    echo
    echo "========================================================="
    echo "ERROR: $1"
    echo "========================================================="
    echo
}


# =========================================================
# CLEANUP
# =========================================================

cleanup()
{
    log "Cleaning up temporary files..."

    if [ -d "$TMPPATH" ]; then
        rm -rf "$TMPPATH"
    fi

    if [ -f "$FILEPATH" ]; then
        rm -f "$FILEPATH"
    fi
}


# =========================================================
# OS DETECTION
# =========================================================

detect_os()
{
    if [ -f "/var/lib/dpkg/status" ]; then

        OSTYPE="DreamOs"
        STATUS="/var/lib/dpkg/status"

    elif [ -f "/var/lib/opkg/status" ] ||
         [ -f "/etc/opkg/opkg.conf" ]; then

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


# =========================================================
# PYTHON DETECTION
# =========================================================

detect_python()
{
    PYTHON_CMD=""
    PYTHON="Unknown"

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


    PYTHON_VERSION=$(
        "$PYTHON_CMD" --version 2>&1
    )

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


# =========================================================
# IMAGE DETECTION
# =========================================================

detect_image()
{
    BOX_TYPE=$(
        head -n 1 /etc/hostname 2>/dev/null
    )


    if [ -z "$BOX_TYPE" ]; then
        BOX_TYPE="Unknown"
    fi


    if [ -f "/usr/lib/enigma.info" ]; then

        DISTRO=$(
            grep "^distro=" /usr/lib/enigma.info 2>/dev/null |
            head -n 1 |
            cut -d "=" -f 2-
        )

        DISTRO_VERSION=$(
            grep "^imageversion=" /usr/lib/enigma.info 2>/dev/null |
            head -n 1 |
            cut -d "=" -f 2-
        )


    elif [ -f "/etc/image-version" ]; then

        DISTRO=$(
            grep "^distro=" /etc/image-version 2>/dev/null |
            head -n 1 |
            cut -d "=" -f 2-
        )

        DISTRO_VERSION=$(
            grep "^version=" /etc/image-version 2>/dev/null |
            head -n 1 |
            cut -d "=" -f 2-
        )

    else

        DISTRO="Unknown"
        DISTRO_VERSION="Unknown"

    fi


    [ -z "$DISTRO" ] &&
        DISTRO="Unknown"


    [ -z "$DISTRO_VERSION" ] &&
        DISTRO_VERSION="Unknown"


    log "Image: $DISTRO $DISTRO_VERSION"
    log "Box: $BOX_TYPE"
}


# =========================================================
# WGET
# =========================================================

install_wget()
{
    if command -v wget >/dev/null 2>&1; then

        log "wget already installed."
        return 0

    fi


    log "wget not found. Installing wget..."


    case "$OSTYPE" in

        DreamOs|Debian)

            if ! apt-get update; then
                error "apt-get update failed."
                exit 1
            fi

            if ! apt-get install -y wget; then
                error "wget installation failed."
                exit 1
            fi

            ;;


        OE)

            if ! opkg update; then
                error "opkg update failed."
                exit 1
            fi

            if ! opkg install wget; then
                error "wget installation failed."
                exit 1
            fi

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


    log "wget installed successfully."
}


# =========================================================
# PACKAGE CHECK
# =========================================================

package_installed()
{
    local pkg="$1"


    if [ -z "$pkg" ]; then
        return 1
    fi


    case "$OSTYPE" in

        DreamOs|Debian)

            if command -v dpkg-query >/dev/null 2>&1; then

                dpkg-query \
                    -W \
                    -f='${Status}' \
                    "$pkg" 2>/dev/null |
                    grep -q "install ok installed"

                return $?

            fi

            ;;


        OE)

            if command -v opkg >/dev/null 2>&1; then

                opkg status "$pkg" 2>/dev/null |
                    grep -q "^Status:.*ok installed"

                return $?

            fi

            ;;

    esac


    return 1
}


# =========================================================
# PACKAGE INSTALLATION
# =========================================================

install_pkg()
{
    local pkg="$1"


    if [ -z "$pkg" ]; then
        return 0
    fi


    if package_installed "$pkg"; then

        log "$pkg already installed."
        return 0

    fi


    log "Installing package: $pkg"


    case "$OSTYPE" in

        DreamOs|Debian)

            if ! apt-get update >/dev/null 2>&1; then
                log "Warning: apt-get update failed."
            fi


            if apt-get install -y "$pkg"; then

                log "$pkg installation finished."

            else

                log "Warning: Could not install $pkg."
                return 1

            fi

            ;;


        OE)

            if ! opkg update >/dev/null 2>&1; then
                log "Warning: opkg update failed."
            fi


            if opkg install "$pkg"; then

                log "$pkg installation finished."

            else

                log "Warning: Could not install $pkg."
                return 1

            fi

            ;;


        *)

            log "Cannot install $pkg on unknown OS."
            return 1

            ;;

    esac


    if package_installed "$pkg"; then

        log "$pkg verified successfully."
        return 0

    fi


    log "Warning: Could not verify $pkg."
    return 1
}


# =========================================================
# DEPENDENCIES
# =========================================================

install_dependencies()
{
    log "Checking dependencies..."


    if [ "$PYTHON" = "PY3" ]; then

        install_pkg "$PACKAGESIX" || true

    fi


    install_pkg "$PACKAGEREQUESTS" || true


    install_pkg "$PACKAGEPILLOW" || true


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


# =========================================================
# CONFIG BACKUP
# =========================================================

backup_config()
{
    BACKUP_CREATED=0


    if [ ! -d "$CONFIG_DIR" ]; then

        log "No existing configuration directory found."
        log "Skipping configuration backup."

        return 0

    fi


    log "Creating configuration backup..."


    if [ -d "$BACKUP_DIR" ]; then
        rm -rf "$BACKUP_DIR"
    fi


    if cp -a "$CONFIG_DIR" "$BACKUP_DIR"; then

        BACKUP_CREATED=1

        log "Configuration backup successful."

    else

        error "Configuration backup failed."
        exit 1

    fi
}


# =========================================================
# CONFIG RESTORE
# =========================================================

restore_config()
{
    if [ "$BACKUP_CREATED" -ne 1 ]; then
        return 0
    fi


    if [ ! -d "$BACKUP_DIR" ]; then

        log "No configuration backup found."
        return 0

    fi


    log "Restoring configuration..."


    mkdir -p "$CONFIG_DIR"


    if cp -a "$BACKUP_DIR"/. "$CONFIG_DIR"/; then

        log "Configuration restored successfully."

    else

        log "Warning: Configuration restore failed."

    fi


    rm -rf "$BACKUP_DIR"

    BACKUP_CREATED=0
}


# =========================================================
# DOWNLOAD
# =========================================================

download_package()
{
    log "Downloading ForecaOne v$version..."
    log "Branch: $BRANCH"


    rm -f "$FILEPATH"


    if wget \
        --no-verbose \
        --timeout=30 \
        --tries=3 \
        --https-only \
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


    if ! gzip -t "$FILEPATH" >/dev/null 2>&1; then

        error "Downloaded file is not a valid gzip archive."

        cleanup
        exit 1

    fi
}


# =========================================================
# EXTRACT
# =========================================================

extract_package()
{
    log "Extracting package..."


    rm -rf "$TMPPATH"


    if ! mkdir -p "$TMPPATH"; then

        error "Could not create temporary directory."

        cleanup
        exit 1

    fi


    if tar -xzf "$FILEPATH" -C "$TMPPATH"; then

        log "Extraction successful."

    else

        error "Failed to extract ForecaOne package."

        cleanup
        exit 1

    fi
}


# =========================================================
# FIND PLUGIN SOURCE
# =========================================================

find_plugin_source()
{
    PLUGIN_SOURCE=""


    # -----------------------------------------------------
    # Normal /usr/lib
    # -----------------------------------------------------

    if [ -d "$TMPPATH/Foreca-master/usr/lib/enigma2/python/Plugins/Extensions/Foreca1" ]; then

        PLUGIN_SOURCE="$TMPPATH/Foreca-master/usr/lib/enigma2/python/Plugins/Extensions/Foreca1"

        log "Found plugin in /usr/lib."


    # -----------------------------------------------------
    # 64-bit /usr/lib64
    # -----------------------------------------------------

    elif [ -d "$TMPPATH/Foreca-master/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1" ]; then

        PLUGIN_SOURCE="$TMPPATH/Foreca-master/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1"

        log "Found plugin in /usr/lib64."


    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    else

        PLUGIN_SOURCE=$(
            find "$TMPPATH" \
                -type d \
                -path "*/Plugins/Extensions/Foreca1" \
                2>/dev/null |
            head -n 1
        )


        if [ -n "$PLUGIN_SOURCE" ]; then

            log "Found plugin using fallback search:"
            log "$PLUGIN_SOURCE"

        fi

    fi


    if [ -z "$PLUGIN_SOURCE" ] ||
       [ ! -d "$PLUGIN_SOURCE" ]; then

        error "Could not find Foreca1 plugin files in archive."


        echo
        echo "Available directories:"
        echo "---------------------------------------------------------"

        find "$TMPPATH" \
            -maxdepth 8 \
            -type d \
            2>/dev/null |
            head -100

        echo


        cleanup
        exit 1

    fi


    if [ ! -f "$PLUGIN_SOURCE/__init__.py" ]; then

        error "Invalid plugin archive: __init__.py not found."

        cleanup
        exit 1

    fi


    if [ ! -f "$PLUGIN_SOURCE/plugin.py" ]; then

        error "Invalid plugin archive: plugin.py not found."

        cleanup
        exit 1

    fi


    log "Plugin source validation successful."
}


# =========================================================
# BACKUP EXISTING PLUGIN
# =========================================================

backup_existing_plugin()
{
    if [ -d "$OLD_PLUGIN_BACKUP" ]; then
        rm -rf "$OLD_PLUGIN_BACKUP"
    fi


    if [ ! -d "$PLUGINPATH" ]; then

        log "No existing ForecaOne installation found."
        return 0

    fi


    log "Backing up currently installed plugin..."


    if cp -a "$PLUGINPATH" "$OLD_PLUGIN_BACKUP"; then

        log "Existing plugin backup created."

    else

        error "Could not backup existing plugin."
        exit 1

    fi
}


# =========================================================
# INSTALL PLUGIN
# =========================================================

install_plugin()
{
    log "Installing ForecaOne v$version..."


    INSTALL_STARTED=1


    mkdir -p "$(dirname "$PLUGINPATH")"


    if ! mkdir -p "$PLUGINPATH"; then

        error "Could not create plugin directory."

        rollback_plugin
        cleanup

        exit 1

    fi


    if cp -a "$PLUGIN_SOURCE"/. "$PLUGINPATH"/; then

        log "Plugin files copied successfully."

    else

        error "Failed to copy plugin files."

        rollback_plugin
        cleanup

        exit 1

    fi


    if [ ! -f "$PLUGINPATH/__init__.py" ]; then

        error "Installation verification failed: __init__.py missing."

        rollback_plugin
        cleanup

        exit 1

    fi


    if [ ! -f "$PLUGINPATH/plugin.py" ]; then

        error "Installation verification failed: plugin.py missing."

        rollback_plugin
        cleanup

        exit 1

    fi


    if [ -z "$(find "$PLUGINPATH" -type f 2>/dev/null | head -n 1)" ]; then

        error "Plugin installation appears to be empty."

        rollback_plugin
        cleanup

        exit 1

    fi


    log "Plugin installation verified."
}


# =========================================================
# ROLLBACK
# =========================================================

rollback_plugin()
{
    if [ ! -d "$OLD_PLUGIN_BACKUP" ]; then

        log "No previous plugin backup available."

        return 0

    fi


    log "Rolling back previous plugin installation..."


    rm -rf "$PLUGINPATH"


    mkdir -p "$(dirname "$PLUGINPATH")"


    if cp -a "$OLD_PLUGIN_BACKUP" "$PLUGINPATH"; then

        log "Plugin rollback successful."

        rm -rf "$OLD_PLUGIN_BACKUP"

    else

        log "WARNING: Plugin rollback failed!"

    fi
}


# =========================================================
# REMOVE OLD BACKUP
# =========================================================

remove_old_plugin_backup()
{
    if [ -d "$OLD_PLUGIN_BACKUP" ]; then

        rm -rf "$OLD_PLUGIN_BACKUP"

        log "Old plugin backup removed."

    fi
}


# =========================================================
# SHOW INFORMATION
# =========================================================

show_info()
{
    echo
    echo "#########################################################"
    echo "#                                                     #"
    echo "#              FORECAONE INSTALLED                    #"
    echo "#                                                     #"
    echo "#########################################################"
    echo "#                                                     #"
    echo "#  Plugin Version: $version"
    echo "#                                                     #"
    echo "#  Developed by LULULLA                              #"
    echo "#  https://corvoboys.org                              #"
    echo "#                                                     #"
    echo "#  PLEASE RESTART YOUR DEVICE                         #"
    echo "#                                                     #"
    echo "#########################################################"
    echo


    echo "Debug information:"
    echo "---------------------------------------------------------"
    echo "BOX MODEL:       $BOX_TYPE"
    echo "OS SYSTEM:       $OSTYPE"
    echo "PYTHON:          $PYTHON_VERSION"
    echo "PYTHON TYPE:     $PYTHON"
    echo "IMAGE NAME:      $DISTRO"
    echo "IMAGE VERSION:   $DISTRO_VERSION"
    echo "PLUGIN VERSION:  $version"
    echo "PLUGIN PATH:     $PLUGINPATH"
    echo "BRANCH:          $BRANCH"
    echo "---------------------------------------------------------"
    echo


    echo "Changelog:"
    echo "---------------------------------------------------------"
    echo "$changelog"
    echo "---------------------------------------------------------"
    echo
}


# =========================================================
# MAIN
# =========================================================

echo
echo "========================================================="
echo "              ForecaOne Installer v$version"
echo "========================================================="
echo


# =========================================================
# ROOT CHECK
# =========================================================

if [ "$(id -u)" -ne 0 ]; then

    error "This installer must be executed as root."

    exit 1

fi


# =========================================================
# DETECT ENVIRONMENT
# =========================================================

detect_os
detect_python
detect_image


# =========================================================
# WGET
# =========================================================

install_wget


# =========================================================
# DEPENDENCIES
# =========================================================

install_dependencies


# =========================================================
# PREPARE TEMP
# =========================================================

cleanup


if ! mkdir -p "$TMPPATH"; then

    error "Could not create temporary directory."

    exit 1

fi


# =========================================================
# BACKUP CONFIGURATION
# =========================================================

backup_config


# =========================================================
# DOWNLOAD
# =========================================================

download_package


# =========================================================
# EXTRACT
# =========================================================

extract_package


# =========================================================
# FIND PLUGIN
# =========================================================

find_plugin_source


# =========================================================
# BACKUP CURRENT PLUGIN
# =========================================================

backup_existing_plugin


# =========================================================
# INSTALL
# =========================================================

install_plugin


# =========================================================
# RESTORE CONFIGURATION
# =========================================================

restore_config


# =========================================================
# REMOVE OLD BACKUP
# =========================================================

remove_old_plugin_backup


# =========================================================
# SYNC
# =========================================================

sync >/dev/null 2>&1 || true


# =========================================================
# CLEANUP
# =========================================================

cleanup


# =========================================================
# FINAL INFORMATION
# =========================================================

show_info


exit 0
