# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os, glob

try:
    from Renderer import Renderer
except Exception:
    class Renderer(object):
        def __init__(self): self.source = None
        def applySkin(self, desktop, parent): return True

try:
    from enigma import ePixmap, eLabel, eTimer
except Exception:
    class ePixmap(object):
        def setPixmapFromFile(self, p): pass
        def show(self): pass
        def hide(self): pass
    class eLabel(object):
        def setText(self, p): pass
    class eTimer(object):
        def __init__(self): self.callback=[]
        def start(self,*a,**k): pass
        def stop(self): pass

from .ForecaWeatherConverter import ForecaWeatherConverter, PLUGIN_PATH, WEATHER_ANIM_PATH, WIND_DIRECTION_ANIM_PATH, WIND_SPEED_ANIM_PATH


def _truth(v): return str(v).lower() in ("1", "true", "yes", "on")


class _Base(Renderer):
    def __init__(self):
        Renderer.__init__(self)
        self.field = "temperature"
        self._parent = None
        self.mode = "static"
        self.fps = 8
        self.timer = None
        self.frames = []
        self.index = 0
        self.loop = True
        self.step = 1
        self.skin_path = None

    def applySkin(self, desktop, parent):
        self._parent = parent
        if getattr(self, "source", None) is None:
            self.source = parent
        for key, value in getattr(self, "skinAttributes", []):
            if key == "field": self.field = value
            elif key == "mode": self.mode = value.lower()
            elif key in ("path", "icon_path"): self.skin_path = value
            elif key in ("fps", "animation_fps"):
                try: self.fps = max(1, int(value))
                except Exception: pass
            elif key == "loop": self.loop = _truth(value)
            elif key == "step":
                try: self.step = max(1, int(value))
                except Exception: pass
        return Renderer.applySkin(self, desktop, parent)

    def _converter(self):
        c = ForecaWeatherConverter(self.field); c.source = getattr(self, "source", None); return c

    def _stop(self):
        if self.timer:
            try: self.timer.stop()
            except Exception: pass

    def preWidgetRemove(self, instance): self._stop()


class ForecaWeatherTextRenderer(_Base):
    """Text renderer in the same file; use render=ForecaWeatherTextRenderer."""
    GUI_WIDGET = eLabel
    def postWidgetCreate(self, instance):
        self.instance = instance; self._update()
    def changed(self, what): self._update()
    def _update(self):
        try: self.instance.setText(self._converter().text)
        except Exception: pass


class ForecaWeatherRenderer(_Base):
    """Pixmap renderer for weather, wind and moon icons.

    Modes:
      weather     -> animated_icons/<symbol> if present, otherwise static icon
      wind_dir    -> animated_icons/windspeed/<frames> for the direction
      wind_speed  -> animated_icons/wind_speed2/<frames> (speed value selects folder when applicable)
      moon        -> moon icon sequence using icon_number 0..100
      static      -> direct icon file from the resolved field
    """
    GUI_WIDGET = ePixmap

    def postWidgetCreate(self, instance):
        self.instance = instance
        self.timer = eTimer()
        try: self.timer.callback.append(self._tick)
        except Exception: pass
        self._update()

    def changed(self, what): self._update()

    def _resolved(self): return self._converter().resolve(self._converter()._source())

    def _start(self):
        self._stop()
        if not self.frames: return
        try: self.timer.start(max(20, int(1000.0 / self.fps)), True)
        except Exception: pass

    def _show(self, path):
        if not path: return
        try: self.instance.setPixmapFromFile(path); self.instance.show()
        except Exception: pass

    def _set_frames(self, frames):
        self.frames = sorted(frames); self.index = 0
        if self.frames: self._show(self.frames[0]); self._start()

    def _weather(self, symbol):
        symbol = str(symbol or "d000")
        directory = os.path.join(WEATHER_ANIM_PATH, symbol)
        frames = glob.glob(os.path.join(directory, "*.png")) if os.path.isdir(directory) else []
        if frames: self._set_frames(frames); return
        # Static icons are resolved through the plugin's normal icon directory.
        candidates = [os.path.join(PLUGIN_PATH, "images", symbol + ".png"), os.path.join(PLUGIN_PATH, "thumb", symbol + ".png")]
        for path in candidates:
            if os.path.exists(path): self._show(path); return
        try: self.instance.hide()
        except Exception: pass

    def _wind_dir(self, direction):
        d = str(direction or "wN")
        # Confirmed Foreca1 animation directory: animated_icons/windspeed.
        frames = glob.glob(os.path.join(WIND_DIRECTION_ANIM_PATH, "*.png"))
        if frames:
            # If files carry direction names, prefer them; otherwise use the complete sequence.
            named = [p for p in frames if d.lower() in os.path.basename(p).lower()]
            self._set_frames(named or frames); return
        for path in (os.path.join(PLUGIN_PATH, "thumb", d + ".png"), os.path.join(PLUGIN_PATH, "images", d + ".png")):
            if os.path.exists(path): self._show(path); return

    def _wind_speed(self, value):
        try: speed = float(value)
        except Exception: speed = 0.0
        # wind_speed2 is used by Foreca1 as the speed animation asset directory.
        directory = WIND_SPEED_ANIM_PATH
        frames = glob.glob(os.path.join(directory, "*.png"))
        if frames: self._set_frames(frames); return
        try: self.instance.hide()
        except Exception: pass

    def _moon(self):
        try: number = int(self._converter().value)
        except Exception: number = 0
        number = max(0, min(100, number))
        base = self.skin_path or os.path.join(PLUGIN_PATH, "moon")
        candidates = [
            os.path.join(base, "moon%04d.png" % number),
            os.path.join(base, "moon%03d.png" % number),
            os.path.join(base, "moon%d.png" % number),
        ]
        for path in candidates:
            if os.path.exists(path): self._show(path); return
        # Search common package moon folders only if explicit path was not supplied.
        if not self.skin_path:
            for folder in (os.path.join(PLUGIN_PATH, "moon"), os.path.join(PLUGIN_PATH, "images", "moon"), os.path.join(PLUGIN_PATH, "moon_icons")):
                for name in ("moon%04d.png" % number, "moon%03d.png" % number, "moon%d.png" % number):
                    path = os.path.join(folder, name)
                    if os.path.exists(path): self._show(path); return

    def _update(self):
        self._stop(); self.frames = []
        try:
            mode = self.mode
            if mode in ("moon", "moon_animation") or self.field.startswith("moon.icon_number"):
                self._moon(); return
            value = self._resolved()
            if mode in ("wind_dir", "wind_direction"): self._wind_dir(value); return
            if mode in ("wind_speed", "windspeed"): self._wind_speed(value); return
            if mode in ("weather", "weather_animation", "animation"):
                self._weather(value); return
            # Static: field is expected to resolve to a path or a filename.
            path = str(value or "")
            if not os.path.isabs(path): path = os.path.join(PLUGIN_PATH, path)
            if os.path.exists(path): self._show(path)
        except Exception:
            pass

    def _tick(self):
        if not self.frames: return
        self.index += self.step
        if self.index >= len(self.frames):
            if self.loop: self.index = 0
            else: self.index = len(self.frames) - 1
        self._show(self.frames[self.index])
        if self.loop or self.index < len(self.frames) - 1: self._start()

WeatherRenderer = ForecaWeatherRenderer
