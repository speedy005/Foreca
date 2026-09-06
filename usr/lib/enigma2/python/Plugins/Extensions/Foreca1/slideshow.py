#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) @Lululla 2026
# slideshow.py - Manage overlay map Foreca One


from os.path import exists, join
from os import listdir, remove
import requests
from threading import Thread

from enigma import eTimer, ePicLoad
from datetime import datetime, timedelta

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from Components.ActionMap import HelpableActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch

from . import (
    _,
    DEBUG,
    WETTERKONTOR_CACHE,
    load_skin_for_class,
    apply_global_theme,
)


REGION_MAPS_EUROPE = [
    (_("Austria"), "oesterreich"),
    (_("Belgium"), "belgien"),
    (_("Czech Republic"), "tschechien"),
    (_("Denmark"), "daenemark"),
    (_("Finland"), "finnland"),
    (_("France"), "frankreich"),
    (_("Germany"), "deutschland"),
    (_("Greece"), "griechenland"),
    (_("Great Britain"), "grossbritannien"),
    (_("Hungary"), "ungarn"),
    (_("Ireland"), "irland"),
    (_("Italy"), "italien"),
    (_("Latvia"), "lettland"),
    (_("Luxembourg"), "luxemburg"),
    (_("Netherlands"), "niederlande"),
    (_("Norway"), "norwegen"),
    (_("Poland"), "polen"),
    (_("Portugal"), "portugal"),
    (_("Russia"), "russland"),
    (_("Slovakia"), "slowakei"),
    (_("Spain"), "spanien"),
    (_("Sweden"), "schweden"),
    (_("Switzerland"), "schweiz"),
]


REGION_MAPS_GERMANY = [
    (_("Baden-Wuerttemberg"), "badenwuerttemberg"),
    (_("Bavaria"), "bayern"),
    (_("Berlin"), "berlin"),
    (_("Brandenburg"), "brandenburg"),
    (_("Bremen"), "bremen"),
    (_("Hamburg"), "hamburg"),
    (_("Hesse"), "hessen"),
    (_("Mecklenburg-Vorpommern"), "mecklenburgvorpommern"),
    (_("Lower Saxony"), "niedersachsen"),
    (_("North Rhine-Westphalia"), "nordrheinwestfalen"),
    (_("Rhineland-Palatine"), "rheinlandpfalz"),
    (_("Saarland"), "saarland"),
    (_("Saxony"), "sachsen"),
    (_("Saxony-Anhalt"), "sachsenanhalt"),
    (_("Schleswig-Holstein"), "schleswigholstein"),
    (_("Thuringia"), "thueringen"),
]


REGION_MAPS_CONTINENTS = [
    (_("Europe"), "europa"),
    (_("North Africa"), "afrika_nord"),
    (_("South Africa"), "afrika_sued"),
    (_("North America"), "nordamerika"),
    (_("Middle America"), "mittelamerika"),
    (_("South America"), "suedamerika"),
    (_("Middle East"), "naherosten"),
    (_("East Asia"), "ostasien"),
    (_("Southeast Asia"), "suedostasien"),
    (_("Middle Asia"), "zentralasien"),
    (_("Australia"), "australienundozeanien"),
]


class ForecaSlideshow(Screen, HelpableScreen):
    """Slideshow for Wetterkontor weather maps"""

    def __init__(self, session, region_code, region_name):
        if DEBUG:
            print("[Foreca1] ForecaSlideshow class loaded")
            print(f"[Foreca1] Region code: {region_code}, Name: {region_name}")

        self.skin = load_skin_for_class(ForecaSlideshow)
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)
        self.setTitle(_("Weather Maps Slideshow"))
        self["selection_overlay"] = Label("")
        self["background_plate"] = Label("")

        self["title"] = Label(region_name)
        self["info"] = Label(_("Loading..."))
        self["key_red"] = StaticText(_("Play/Pause"))
        self["key_green"] = StaticText(_("Next"))
        self["key_yellow"] = StaticText(_("Previous"))
        self["key_blue"] = StaticText(_("Exit"))
        self["image"] = Pixmap()
        self["playButton"] = Pixmap()
        self["pauseButton"] = Pixmap()

        self.region_code = region_code
        self.current_image = 0
        self.total_images = 6
        self.is_playing = True
        self.slide_timer = eTimer()
        self.slide_timer.timeout.get().append(self.next_image)
        self.slide_interval = 4000  # 5 seconds
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.exit, _("Exit")),
                "red": (self.play_pause, _("Play/Pause")),
                "green": (self.next_image, _("Next Image")),
                "yellow": (self.previous_image, _("Previous Image")),
                "blue": (self.exit, _("Exit")),
                "left": (self.previous_image, _("Previous Image")),
                "right": (self.next_image, _("Next Image")),
                "up": (self.increase_speed, _("Increase Speed")),
                "down": (self.decrease_speed, _("Decrease Speed")),
                "ok": (self.play_pause, _("Play/Pause")),
            },
            -1
        )
        self.picload = ePicLoad()
        self.picload.PictureData.get().append(self.pic_data)
        self.clear_cache()
        self.onLayoutFinish.append(self.start_download)
        self.onLayoutFinish.append(self._apply_theme)
        self.onClose.append(self.clear_cache)

    def _apply_theme(self):
        apply_global_theme(self)

    def clear_cache(self):
        if exists(WETTERKONTOR_CACHE):
            try:
                for f in listdir(WETTERKONTOR_CACHE):
                    remove(join(WETTERKONTOR_CACHE, f))
                if DEBUG:
                    print(
                        f"[WetterKontor] Cleaned temporary files from {WETTERKONTOR_CACHE}")
            except Exception as e:
                print(f"[WetterKontor] Error cleaning temp files: {e}")

    def start_download(self):
        """Start image download after screen is ready"""
        # Configure picload NOW that widgets exist
        sc = AVSwitch().getFramebufferScale()
        self.picload.setPara([
            self["image"].instance.size().width(),
            self["image"].instance.size().height(),
            sc[0],
            sc[1],
            0,              # cache
            0,              # resize (0=simple)
            "#00000000"     # background color
        ])

        # Start download in background
        self["info"].setText(_("Downloading images..."))
        Thread(target=self.download_all_images).start()

    def download_all_images(self):
        """Download all 6 images for the region"""

        for i in range(self.total_images):
            url = f"http://img.wetterkontor.de/karten/{self.region_code}{i}.jpg"
            cache_file = join(
                WETTERKONTOR_CACHE,
                f"{self.region_code}_{i}.jpg")
            if not exists(cache_file):
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        with open(cache_file, 'wb') as f:
                            f.write(response.content)
                        if DEBUG:
                            print(f"[Foreca1] Downloaded: {url}")
                    else:
                        print(f"[Foreca1] Failed to download: {url}")
                except Exception as e:
                    print(f"[Foreca1] Error downloading {url}: {e}")

        self.show_image(0)

    def show_image(self, index):
        """Show a specific image with the corresponding day label."""
        if 0 <= index < self.total_images:
            self.current_image = index
            cache_file = join(
                WETTERKONTOR_CACHE,
                f"{self.region_code}_{index}.jpg")
            if exists(cache_file):
                # Calculate the corresponding day (today + index days)
                target_date = datetime.now() + timedelta(days=index)

                # Determine the day text
                if index == 0:
                    day_str = _("Today") + " " + \
                        target_date.strftime("%a %d.%m.%Y")
                elif index == 1:
                    day_str = _("Tomorrow") + " " + \
                        target_date.strftime("%a %d.%m.%Y")
                else:
                    day_str = target_date.strftime("%a %d.%m.%Y")

                # Update the info label
                self["info"].setText(
                    _("Image %(current)d/%(total)d – %(day)s") % {
                        "current": index + 1,
                        "total": self.total_images,
                        "day": day_str
                    }
                )
                self.picload.startDecode(cache_file)
            else:
                self["info"].setText(_("Image not available"))

    def pic_data(self, picInfo=None):
        """Callback when image is loaded"""
        ptr = self.picload.getData()
        if ptr:
            self["image"].instance.setPixmap(ptr)
            self["image"].instance.show()

            # Start slideshow timer if not already running
            if self.is_playing and not self.slide_timer.isActive():
                self.slide_timer.start(self.slide_interval)

    def next_image(self):
        """Show next image"""
        next_idx = (self.current_image + 1) % self.total_images
        self.show_image(next_idx)

    def previous_image(self):
        """Show previous image"""
        prev_idx = (self.current_image - 1) % self.total_images
        self.show_image(prev_idx)

    def play_pause(self):
        if self.is_playing:
            self.slide_timer.stop()
            # Recalculate the date for the current image
            target_date = datetime.now() + timedelta(days=self.current_image)
            if self.current_image == 0:
                day_str = _("Today") + " " + \
                    target_date.strftime("%a %d.%m.%Y")
            elif self.current_image == 1:
                day_str = _("Tomorrow") + " " + \
                    target_date.strftime("%a %d.%m.%Y")
            else:
                day_str = target_date.strftime("%a %d.%m.%Y")

            self["info"].setText(
                _("Image %(current)d/%(total)d – %(day)s (Paused)") % {
                    "current": self.current_image + 1,
                    "total": self.total_images,
                    "day": day_str
                }
            )
            self["playButton"].show()
            self["pauseButton"].hide()
            self.is_playing = False
        else:
            self.slide_timer.start(self.slide_interval)
            # When playback resumes, restore the normal text
            target_date = datetime.now() + timedelta(days=self.current_image)
            if self.current_image == 0:
                day_str = _("Today") + " " + \
                    target_date.strftime("%a %d.%m.%Y")
            elif self.current_image == 1:
                day_str = _("Tomorrow") + " " + \
                    target_date.strftime("%a %d.%m.%Y")
            else:
                day_str = target_date.strftime("%a %d.%m.%Y")

            self["info"].setText(
                _("Image %(current)d/%(total)d – %(day)s") % {
                    "current": self.current_image + 1,
                    "total": self.total_images,
                    "day": day_str
                }
            )
            self["playButton"].hide()
            self["pauseButton"].show()
            self.is_playing = True

    def increase_speed(self):
        """Increase slideshow speed"""
        if self.slide_interval > 1000:
            self.slide_interval -= 1000
            if self.is_playing:
                self.slide_timer.start(self.slide_interval)
            self["info"].setText(
                _("Faster: {}s").format(
                    self.slide_interval // 1000))

    def decrease_speed(self):
        """Decrease slideshow speed"""
        if self.slide_interval < 10000:
            self.slide_interval += 1000
            if self.is_playing:
                self.slide_timer.start(self.slide_interval)
            self["info"].setText(
                _("Slower: {}s").format(
                    self.slide_interval // 1000))

    def exit(self):
        """Exit slideshow"""
        self.slide_timer.stop()
        del self.picload
        self.close()


class ForecaMapsMenu(Screen, HelpableScreen):

    def __init__(self, session, map_type):
        self.skin = load_skin_for_class(ForecaMapsMenu)

        self.session = session
        self.map_type = map_type  # 'europe', 'germany', 'continents'
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        if map_type == 'europe':
            self.setTitle(_("European Weather Maps"))
            self.regions = REGION_MAPS_EUROPE
        elif map_type == 'germany':
            self.setTitle(_("German States Weather Maps"))
            self.regions = REGION_MAPS_GERMANY
        else:  # continents
            self.setTitle(_("Continents Weather Maps"))
            self.regions = REGION_MAPS_CONTINENTS

        self["background_plate"] = Label("")
        self["selection_overlay"] = Label("")

        self["list"] = MenuList([])
        self["info"] = Label(_("Loading available maps..."))
        self["title"] = Label()
        self.populate_list()
        self["actions"] = HelpableActionMap(
            self, "ForecaActions",
            {
                "cancel": (self.exit, _("Exit")),
                "red": (self.exit, _("Exit")),
                "up": (self.up, _("Increase Speed")),
                "down": (self.down, _("Decrease Speed")),
                "ok": (self.select_region, _("Select Region")),
            },
            -1
        )
        self.onLayoutFinish.append(self._apply_theme)
        self.onLayoutFinish.append(self.updateTitle)

    def _apply_theme(self):
        apply_global_theme(self)

    def updateTitle(self):
        current = self["list"].getCurrent()
        if current:
            region_name = current
            title_text = _("Foreca One | Map {}").format(region_name)
            if DEBUG:
                print(
                    f"[DEBUG] title_text = '{title_text}' (len={len(title_text)})")
            self["title"].setText(title_text)
            self["info"].setText(_("Map {} selected").format(region_name))
            if self["title"].instance:
                self["title"].instance.invalidate()

            if self["info"].instance:
                self["info"].instance.invalidate()

    def up(self):
        self["list"].up()
        self.updateTitle()

    def down(self):
        self["list"].down()
        self.updateTitle()

    def populate_list(self):
        items = []
        for name, code in self.regions:
            items.append(name)
        self["list"].setList(items)
        self.updateTitle()

    def select_region(self):
        index = self["list"].getSelectionIndex()
        if 0 <= index < len(self.regions):
            region_name, region_code = self.regions[index]
            self.session.open(ForecaSlideshow, region_code, region_name)

    def exit(self):
        self.close()
