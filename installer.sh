#!/bin/bash

version='1.4.2'
changelog = 'Fix Malformated Locale Language.\nOffer coffee if you like this plugin'
TMPPATH=/tmp/ForecaOne-install
FILEPATH=/tmp/ForecaOne-main.tar.gz

# Config directory where user settings are stored
CONFIG_DIR="/etc/enigma2/foreca"
BACKUP_DIR="/tmp/foreca_backup"

if [ ! -d /usr/lib64 ]; then
    PLUGINPATH=/usr/lib/enigma2/python/Plugins/Extensions/Foreca1
else
    PLUGINPATH=/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1
fi

echo "Starting ForecaOne installation..."


cleanup() {
    echo "Cleaning up temporary files..."
    [ -d "$TMPPATH" ] && rm -rf "$TMPPATH"
    [ -f "$FILEPATH" ] && rm -f "$FILEPATH"
}

# Backup configuration if it exists
backup_config() {
    if [ -d "$CONFIG_DIR" ]; then
        echo "Backing up configuration from $CONFIG_DIR to $BACKUP_DIR ..."
        rm -rf "$BACKUP_DIR" 2>/dev/null
        cp -r "$CONFIG_DIR" "$BACKUP_DIR"
        if [ $? -eq 0 ]; then
            echo "Backup successful."
        else
            echo "Backup failed! Aborting."
            exit 1
        fi
    else
        echo "No existing configuration directory found. Skipping backup."
    fi
}

# Restore configuration after installation
restore_config() {
    if [ -d "$BACKUP_DIR" ]; then
        echo "Restoring configuration from $BACKUP_DIR to $CONFIG_DIR ..."
        mkdir -p "$CONFIG_DIR"
        cp -r "$BACKUP_DIR"/* "$CONFIG_DIR"/ 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "Configuration restored successfully."
        else
            echo "Warning: Failed to restore some configuration files."
        fi
        rm -rf "$BACKUP_DIR"
    fi
}

detect_os() {
    if [ -f /var/lib/dpkg/status ]; then
        OSTYPE="DreamOs"
        STATUS="/var/lib/dpkg/status"
    elif [ -f /etc/opkg/opkg.conf ] || [ -f /var/lib/opkg/status ]; then
        OSTYPE="OE"
        STATUS="/var/lib/opkg/status"
    elif [ -f /etc/debian_version ]; then
        OSTYPE="Debian"
        STATUS="/var/lib/dpkg/status"
    else
        OSTYPE="Unknown"
        STATUS=""
    fi
    echo "Detected OS type: $OSTYPE"
}

detect_os

if ! command -v wget >/dev/null 2>&1; then
    echo "Installing wget..."
    case "$OSTYPE" in
        "DreamOs"|"Debian")
            apt-get update && apt-get install -y wget || { echo "Failed to install wget"; exit 1; }
            ;;
        "OE")
            opkg update && opkg install wget || { echo "Failed to install wget"; exit 1; }
            ;;
        *)
            echo "Unsupported OS type. Cannot install wget."
            exit 1
            ;;
    esac
fi

if python --version 2>&1 | grep -q '^Python 3\.'; then
    echo "Python3 image detected"
    PYTHON="PY3"
    Packagesix="python3-six"
    Packagerequests="python3-requests"
    Packagepillow="python3-pillow"
else
    echo "Python2 image detected"
    PYTHON="PY2"
    Packagerequests="python-requests"
    Packagepillow="python-pillow"
    if [ "$OSTYPE" = "DreamOs" ] || [ "$OSTYPE" = "Debian" ]; then
        Packagesix="python-six"
    else
        Packagesix="python-six"
    fi
fi

install_pkg() {
    local pkg=$1
    if [ -z "$STATUS" ] || ! grep -qs "Package: $pkg" "$STATUS" 2>/dev/null; then
        echo "Installing $pkg..."
        case "$OSTYPE" in
            "DreamOs"|"Debian")
                apt-get update && apt-get install -y "$pkg" || { echo "Could not install $pkg, continuing anyway..."; }
                ;;
            "OE")
                opkg update && opkg install "$pkg" || { echo "Could not install $pkg, continuing anyway..."; }
                ;;
            *)
                echo "Cannot install $pkg on unknown OS type, continuing..."
                ;;
        esac
    else
        echo "$pkg already installed"
    fi
}

[ "$PYTHON" = "PY3" ] && install_pkg "$Packagesix"
install_pkg "$Packagerequests"

if [ "$OSTYPE" = "OE" ]; then
    echo "Installing additional dependencies for OpenEmbedded..."
    for pkg in ffmpeg gstplayer exteplayer3 enigma2-plugin-systemplugins-serviceapp; do
        install_pkg "$pkg"
    done
fi

cleanup
mkdir -p "$TMPPATH"

# Backup configuration before installing new version
backup_config

echo "Downloading ForecaOne..."
wget --no-check-certificate 'https://github.com/speedy005/Foreca/archive/refs/heads/main.tar.gz' -O "$FILEPATH"
if [ $? -ne 0 ]; then
    echo "Failed to download ForecaOne package!"
    cleanup
    exit 1
fi

echo "Extracting package..."
tar -xzf "$FILEPATH" -C "$TMPPATH"
if [ $? -ne 0 ]; then
    echo "Failed to extract ForecaOne package!"
    cleanup
    exit 1
fi

echo "Installing plugin files..."
mkdir -p "$PLUGINPATH"

if [ -d "$TMPPATH/Foreca-main/usr/lib/enigma2/python/Plugins/Extensions/Foreca1" ]; then
    cp -r "$TMPPATH/Foreca-main/usr/lib/enigma2/python/Plugins/Extensions/Foreca1"/* "$PLUGINPATH/" 2>/dev/null
    echo "Copied from standard plugin directory"
lif [ -d "$TMPPATH/Foreca-main/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1" ]; then
    cp -r "$TMPPATH/Foreca-main/usr/lib64/enigma2/python/Plugins/Extensions/Foreca1"/* "$PLUGINPATH/" 2>/dev/null
    echo "Copied from lib64 plugin directory"
elif [ -d "$TMPPATH/ForecaOne-main/usr" ]; then
    cp -r "$TMPPATH/ForecaOne-main/usr"/* /usr/ 2>/dev/null
    echo "Copied entire usr structure"
else
    echo "Could not find plugin files in extracted archive"
    echo "Available directories:"
    find "$TMPPATH" -type d -name "*ForecaOne*" | head -10
    cleanup
    exit 1
fi

# Restore user configuration after installing new version
restore_config
sync

# --- Début des modifications pour OpenPLi/OpenATV ---
box_type=$(head -n 1 /etc/hostname 2>/dev/null || echo "Unknown")

# Détection de la version de l'image
if [ -f /usr/lib/enigma.info ]; then
    # OpenPLi : on utilise /usr/lib/enigma.info
    distro_value=$(grep '^distro=' /usr/lib/enigma.info 2>/dev/null | awk -F '=' '{print $2}')
    distro_version=$(grep '^imageversion=' /usr/lib/enigma.info 2>/dev/null | awk -F '=' '{print $2}')
elif [ -f /etc/image-version ]; then
    # OpenATV : on utilise /etc/image-version
    distro_value=$(grep '^distro=' /etc/image-version 2>/dev/null | awk -F '=' '{print $2}')
    distro_version=$(grep '^version=' /etc/image-version 2>/dev/null | awk -F '=' '{print $2}')
else
    distro_value="Unknown"
    distro_version="Unknown"
fi

python_vers=$(python --version 2>&1)
# --- Fin des modifications ---

cat <<EOF

#########################################################
#               INSTALLED SUCCESSFULLY                  #
#                developed by LULULLA                   #
#               https://corvoboys.org                   #
#########################################################
#           Please RESTART YOUR DEVICE FOR APPLY        #
#########################################################
^^^^^^^^^^Debug information:
BOX MODEL: $box_type
OS SYSTEM: $OSTYPE
PYTHON: $python_vers
IMAGE NAME: ${distro_value:-Unknown}
IMAGE VERSION: ${distro_version:-Unknown}
PLUGIN VERSION: $version
EOF