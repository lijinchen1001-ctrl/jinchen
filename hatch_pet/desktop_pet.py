import ctypes
import math
import random
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


DEFAULT_SCALE = 0.32
MIN_SCALE = 0.18
MAX_SCALE = 0.70
MOTION_TICK_MS = 24
ANIMATION_TICK_MS = 190
BOTTOM_MARGIN = 8
WAKE_SECONDS = 30.0


ASSETS = {
    "hatch": "hatch_pet_hatch.png",
    "idle": "hatch_pet_idle.png",
    "wave": "hatch_pet_wave.png",
    "sleep": "hatch_pet_sleep.png",
}


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0
DIB_RGB_COLORS = 0
SW_SHOW = 5

WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
WM_RBUTTONUP = 0x0205

VK_ESCAPE = 0x1B
WM_KEYDOWN = 0x0100

TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800

CMD_WAKE = 1001
CMD_SLEEP = 1002
CMD_BIGGER = 1003
CMD_SMALLER = 1004
CMD_EXIT = 1005


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_byte),
        ("rgbGreen", ctypes.c_byte),
        ("rgbRed", ctypes.c_byte),
        ("rgbReserved", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND,
    wintypes.HDC,
    ctypes.POINTER(POINT),
    ctypes.POINTER(SIZE),
    wintypes.HDC,
    ctypes.POINTER(POINT),
    wintypes.COLORREF,
    ctypes.POINTER(BLENDFUNCTION),
    wintypes.DWORD,
]
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


@dataclass
class Frame:
    width: int
    height: int
    premultiplied_bgra: bytes
    rgba: Image.Image


APP = None
WNDPROC_REF = None


def signed_word(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def premultiply_bgra(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA").tobytes()
    out = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        r, g, b, a = rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]
        out[i] = b * a // 255
        out[i + 1] = g * a // 255
        out[i + 2] = r * a // 255
        out[i + 3] = a
    return bytes(out)


class DesktopPet:
    def __init__(self, asset_dir: Path):
        self.asset_dir = asset_dir
        self.scale = DEFAULT_SCALE
        self.frames = {}
        self.state = "hatch"
        self.current_key = "hatch"
        self.frame_index = 0
        self.frame = None
        self.hwnd = None
        self.menu = None
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.target = None
        self.facing = 1
        self.dragging = False
        self.drag_started = False
        self.drag_start = (0, 0)
        self.drag_offset = (0, 0)
        self.walking_enabled = True
        self.active_until = 0.0
        self.pause_until = 0.0
        self.next_behavior_at = time.monotonic() + 1.0
        self.action_token = 0
        self.in_transition = False
        self.transition_target_key = None
        self.transition_target_state = None

        self.load_frames()
        self.frame = self.frames["hatch"][0]
        self.create_window()
        self.place_initially()
        self.render()
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.SetTimer(self.hwnd, 1, MOTION_TICK_MS, None)
        user32.SetTimer(self.hwnd, 2, ANIMATION_TICK_MS, None)
        user32.SetTimer(self.hwnd, 3, 2400, None)

    def screen_width(self):
        return user32.GetSystemMetrics(0)

    def screen_height(self):
        return user32.GetSystemMetrics(1)

    def max_x(self):
        return max(0, self.screen_width() - self.frame.width)

    def bottom_y(self):
        return max(0, self.screen_height() - self.frame.height - BOTTOM_MARGIN)

    def load_frames(self):
        def clean_rgba(path: Path):
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            rgb = image.convert("RGB")

            # The source cutouts have some contaminated RGB in transparent edge
            # pixels. Push nearby real colors outward so transforms keep a clean
            # edge when alpha is preserved by UpdateLayeredWindow.
            grown = alpha
            for _ in range(16):
                grown = grown.filter(ImageFilter.MaxFilter(3))
                rgb.paste(rgb.filter(ImageFilter.GaussianBlur(1.0)), mask=grown)

            # Nudge very faint alpha to zero; keep genuine soft antialiasing.
            alpha = alpha.point(lambda value: 0 if value < 5 else value)
            return Image.merge("RGBA", (*rgb.split(), alpha))

        def make_frame(source, *, sx=1.0, sy=1.0, rotate=0.0, y_offset=0, mirror=False):
            if mirror:
                source = ImageOps.mirror(source)
            w, h = source.size
            scaled = source.resize(
                (max(1, int(w * self.scale * sx)), max(1, int(h * self.scale * sy))),
                Image.Resampling.LANCZOS,
            )
            rotated = scaled.rotate(rotate, resample=Image.Resampling.BICUBIC, expand=True)
            pad = max(24, int(max(w, h) * self.scale * 0.11))
            base_w = int(w * self.scale) + pad * 2
            base_h = int(h * self.scale) + pad * 2
            canvas = Image.new("RGBA", (base_w, base_h), (0, 0, 0, 0))
            x = (base_w - rotated.width) // 2
            y = (base_h - rotated.height) // 2 + y_offset
            canvas.alpha_composite(rotated, (x, y))
            return Frame(canvas.width, canvas.height, premultiply_bgra(canvas), canvas)

        def make_sprite_frame(source, *, mirror=False):
            if mirror:
                source = ImageOps.mirror(source)
            w, h = source.size
            scaled = source.resize(
                (max(1, int(w * self.scale)), max(1, int(h * self.scale))),
                Image.Resampling.LANCZOS,
            )
            pad = max(24, int(max(w, h) * self.scale * 0.11))
            canvas = Image.new("RGBA", (scaled.width + pad * 2, scaled.height + pad * 2), (0, 0, 0, 0))
            canvas.alpha_composite(scaled, (pad, pad))
            return Frame(canvas.width, canvas.height, premultiply_bgra(canvas), canvas)

        sources = {
            state: clean_rgba(self.asset_dir / filename)
            for state, filename in ASSETS.items()
        }
        self.frames = {
            "hatch": [make_frame(sources["hatch"], y_offset=0), make_frame(sources["hatch"], y_offset=-3)],
            "sleep": [
                make_frame(sources["sleep"], sx=1.00, sy=1.00, y_offset=0),
                make_frame(sources["sleep"], sx=1.010, sy=0.990, y_offset=1),
                make_frame(sources["sleep"], sx=1.00, sy=1.00, y_offset=0),
                make_frame(sources["sleep"], sx=0.995, sy=1.005, y_offset=-1),
            ],
            "wave": [
                make_frame(sources["wave"], rotate=-1.2, y_offset=0),
                make_frame(sources["wave"], rotate=1.4, y_offset=-3),
                make_frame(sources["wave"], rotate=-0.8, y_offset=-1),
                make_frame(sources["wave"], rotate=1.0, y_offset=-2),
            ],
            "idle": [
                make_frame(sources["idle"], sx=1.00, sy=1.00, y_offset=0),
                make_frame(sources["idle"], sx=0.997, sy=1.003, y_offset=-1),
                make_frame(sources["idle"], sx=1.00, sy=1.00, y_offset=0),
                make_frame(sources["idle"], sx=1.003, sy=0.997, y_offset=1),
            ],
        }

        walk_paths = [self.asset_dir / f"walk_side_{index:02}.png" for index in range(1, 5)]
        if all(path.exists() for path in walk_paths):
            walk_sources = [clean_rgba(path) for path in walk_paths]
            self.frames["walk_left"] = [make_sprite_frame(source) for source in walk_sources]
            self.frames["walk_right"] = [make_sprite_frame(source, mirror=True) for source in walk_sources]
        else:
            walk_transforms = [
                (-1.4, -3, 1.006, 0.994),
                (-0.6, -1, 1.000, 1.000),
                (1.0, 0, 0.996, 1.005),
                (1.6, -2, 1.004, 0.996),
                (0.8, -3, 1.007, 0.993),
                (0.0, -1, 1.000, 1.000),
                (-0.8, 0, 0.997, 1.004),
                (-1.5, -2, 1.003, 0.997),
            ]
            self.frames["walk_right"] = [
                make_frame(sources["idle"], rotate=rot, y_offset=off, sx=sx, sy=sy)
                for rot, off, sx, sy in walk_transforms
            ]
            self.frames["walk_left"] = [
                make_frame(sources["idle"], rotate=-rot, y_offset=off, sx=sx, sy=sy, mirror=True)
                for rot, off, sx, sy in walk_transforms
            ]

    def frame_from_rgba(self, image: Image.Image):
        image = image.convert("RGBA")
        return Frame(image.width, image.height, premultiply_bgra(image), image)

    def aligned_canvas(self, image: Image.Image, width: int, height: int, *, y_offset=0):
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        x = (width - image.width) // 2
        y = height - image.height + y_offset
        canvas.alpha_composite(image, (x, y))
        return canvas

    def transform_rgba(self, image: Image.Image, scale=1.0, y_offset=0):
        width = max(1, int(image.width * scale))
        height = max(1, int(image.height * scale))
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
        x = (image.width - resized.width) // 2
        y = image.height - resized.height + y_offset
        canvas.alpha_composite(resized, (x, y))
        return canvas

    def start_transition(self, target_state: str, target_key=None):
        target_key = target_key or target_state
        if target_key not in self.frames:
            self.state = target_state
            return

        source = self.frame.rgba if self.frame else self.frames[target_key][0].rgba
        target = self.frames[target_key][0].rgba
        width = max(source.width, target.width)
        height = max(source.height, target.height)
        source = self.aligned_canvas(source, width, height)
        target = self.aligned_canvas(target, width, height)

        frames = []
        for index in range(1, 6):
            t = index / 5
            eased = t * t * (3 - 2 * t)
            from_layer = source.copy()
            from_layer.putalpha(from_layer.getchannel("A").point(lambda value, alpha=1 - eased: int(value * alpha)))

            scale = 0.94 + 0.06 * eased
            y_offset = int((1 - eased) * 8)
            to_layer = self.transform_rgba(target, scale=scale, y_offset=y_offset)
            to_layer.putalpha(to_layer.getchannel("A").point(lambda value, alpha=eased: int(value * alpha)))

            canvas = Image.alpha_composite(from_layer, to_layer)
            frames.append(self.frame_from_rgba(canvas))

        self.frames["_transition"] = frames
        self.in_transition = True
        self.transition_target_key = target_key
        self.transition_target_state = target_state
        self.current_key = "_transition"
        self.frame_index = 0
        self.frame = frames[0]
        self.render()

    def create_window(self):
        global WNDPROC_REF
        instance = kernel32.GetModuleHandleW(None)
        class_name = "CodexDesktopPetLayeredWindow"
        WNDPROC_REF = WNDPROC(self.wnd_proc)
        wc = WNDCLASS()
        wc.lpfnWndProc = WNDPROC_REF
        wc.hInstance = instance
        wc.lpszClassName = class_name
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            class_name,
            "Desktop Pet",
            WS_POPUP,
            0,
            0,
            self.frame.width,
            self.frame.height,
            None,
            None,
            instance,
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self.create_menu()

    def create_menu(self):
        self.menu = user32.CreatePopupMenu()
        user32.AppendMenuW(self.menu, MF_STRING, CMD_WAKE, "Wake 30s")
        user32.AppendMenuW(self.menu, MF_STRING, CMD_SLEEP, "Sleep Now")
        user32.AppendMenuW(self.menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(self.menu, MF_STRING, CMD_BIGGER, "Bigger")
        user32.AppendMenuW(self.menu, MF_STRING, CMD_SMALLER, "Smaller")
        user32.AppendMenuW(self.menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(self.menu, MF_STRING, CMD_EXIT, "Quit")

    def place_initially(self):
        self.x = max(20, self.max_x() - 70)
        self.y = self.bottom_y()

    def render(self):
        self.x = min(max(self.x, 0), self.max_x())
        if not self.active_until or self.state == "sleep":
            self.y = self.bottom_y()
        else:
            self.y = min(max(self.y, 0), self.bottom_y())

        hdc_screen = user32.GetDC(None)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        bits = ctypes.c_void_p()
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.frame.width
        bmi.bmiHeader.biHeight = -self.frame.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bitmap = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        old_bitmap = gdi32.SelectObject(hdc_mem, bitmap)
        ctypes.memmove(bits, self.frame.premultiplied_bgra, len(self.frame.premultiplied_bgra))

        dst = POINT(round(self.x), round(self.y))
        size = SIZE(self.frame.width, self.frame.height)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        if not user32.UpdateLayeredWindow(
            self.hwnd,
            hdc_screen,
            ctypes.byref(dst),
            ctypes.byref(size),
            hdc_mem,
            ctypes.byref(src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        gdi32.SelectObject(hdc_mem, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)

    def animation_key(self):
        if self.in_transition:
            return "_transition"
        moving = math.hypot(self.vx, self.vy) > 0.18 and self.walking_enabled and not self.dragging
        if self.state == "idle" and moving:
            return "walk_right" if self.facing >= 0 else "walk_left"
        return self.state

    def animation_tick(self):
        key = self.animation_key()
        if self.in_transition:
            frames = self.frames[key]
            if self.frame_index >= len(frames):
                self.in_transition = False
                self.state = self.transition_target_state
                self.current_key = self.transition_target_key
                self.frame_index = 0
                self.frame = self.frames[self.current_key][0]
                self.render()
                return
            self.frame = frames[self.frame_index]
            self.frame_index += 1
            self.render()
            return

        if key != self.current_key:
            self.start_transition(self.state, key)
            return
        frames = self.frames[key]
        self.frame = frames[self.frame_index % len(frames)]
        self.frame_index += 1
        self.render()

    def behavior_tick(self):
        now = time.monotonic()
        if now < self.next_behavior_at:
            return
        self.next_behavior_at = now + random.uniform(1.6, 3.4)
        if not self.dragging and self.active_until and now >= self.active_until:
            self.sleep_at_bottom()
        elif not self.dragging and self.state == "idle" and self.active_until:
            speed = math.hypot(self.vx, self.vy)
            action = random.choices(["wander", "pause", "wave"], weights=[8, 3 if speed < 0.4 else 1, 2], k=1)[0]
            if action == "wander":
                self.pick_bottom_target()
            elif action == "pause":
                self.pause_until = now + random.uniform(0.35, 1.1)
                self.target = None
            elif action == "wave":
                self.play_state("wave", random.randint(1200, 1900))

    def sleep_at_bottom(self):
        self.action_token += 1
        self.active_until = 0.0
        self.target = None
        self.vx = 0.0
        self.vy = 0.0
        self.y = self.bottom_y()
        self.start_transition("sleep")

    def wake_for_walk(self):
        self.action_token += 1
        self.active_until = time.monotonic() + WAKE_SECONDS
        self.y = self.bottom_y()
        self.start_transition("wave")
        token = self.action_token
        user32.SetTimer(self.hwnd, 4, 1300, None)
        self.pending_wake_token = token

    def finish_wake_wave(self):
        if getattr(self, "pending_wake_token", None) == self.action_token:
            self.start_transition("idle")
            self.pick_bottom_target()
        user32.KillTimer(self.hwnd, 4)

    def play_state(self, state: str, duration_ms: int):
        self.action_token += 1
        token = self.action_token
        self.vx *= 0.2
        self.vy *= 0.2
        self.start_transition(state)
        self.pending_play_token = token
        user32.SetTimer(self.hwnd, 5, duration_ms, None)

    def finish_play_state(self):
        if getattr(self, "pending_play_token", None) == self.action_token:
            if self.active_until:
                self.start_transition("idle")
                self.pick_bottom_target()
            else:
                self.sleep_at_bottom()
        user32.KillTimer(self.hwnd, 5)

    def pick_bottom_target(self):
        if not self.walking_enabled:
            self.target = None
            return
        step = random.randint(160, 520)
        direction = random.choice([-1, 1])
        if self.x <= 24:
            direction = 1
        elif self.x >= self.max_x() - 24:
            direction = -1
        tx = min(max(self.x + direction * step, 0), self.max_x())
        self.target = (tx, self.bottom_y())
        self.pause_until = 0.0

    def motion_tick(self):
        now = time.monotonic()
        self.behavior_tick()
        if not self.dragging and self.active_until and now >= self.active_until:
            self.sleep_at_bottom()
        elif self.walking_enabled and self.target and not self.dragging and self.state == "idle" and self.active_until:
            if now < self.pause_until:
                self.vx *= 0.88
                self.vy *= 0.88
            else:
                tx, ty = self.target
                dx = tx - self.x
                dy = ty - self.y
                distance = math.hypot(dx, dy)
                if distance < 10:
                    self.target = None
                    self.pause_until = now + random.uniform(0.45, 1.8)
                    self.vx *= 0.72
                    self.vy *= 0.72
                else:
                    desired_speed = min(2.2, max(0.5, distance / 190))
                    wobble = math.sin(now * random.uniform(0.7, 1.1)) * 0.018
                    desired_vx = dx / distance * desired_speed + random.uniform(-0.012, 0.012)
                    desired_vy = dy / distance * desired_speed + wobble * 0.18 + random.uniform(-0.004, 0.004)
                    self.vx += (desired_vx - self.vx) * 0.04
                    self.vy += (desired_vy - self.vy) * 0.04
                    self.vx *= 0.992
                    self.vy *= 0.992
                    if abs(self.vx) > 0.12:
                        self.facing = 1 if self.vx >= 0 else -1
        else:
            self.vx *= 0.84
            self.vy *= 0.84

        if not self.dragging:
            self.x += self.vx
            self.y += self.vy
            if self.active_until:
                self.y += (self.bottom_y() - self.y) * 0.12
            self.render()

        if self.walking_enabled and not self.target and not self.dragging and self.state == "idle" and self.active_until:
            if now > self.pause_until and random.random() < 0.025:
                self.pick_bottom_target()

    def set_scale(self, value: float):
        self.scale = min(MAX_SCALE, max(MIN_SCALE, value))
        self.load_frames()
        self.frame = self.frames[self.current_key][0]
        self.render()

    def show_menu(self):
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        cmd = user32.TrackPopupMenu(self.menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, point.x, point.y, 0, self.hwnd, None)
        if cmd == CMD_WAKE:
            self.wake_for_walk()
        elif cmd == CMD_SLEEP:
            self.sleep_at_bottom()
        elif cmd == CMD_BIGGER:
            self.set_scale(self.scale + 0.06)
        elif cmd == CMD_SMALLER:
            self.set_scale(self.scale - 0.06)
        elif cmd == CMD_EXIT:
            user32.DestroyWindow(self.hwnd)

    def wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TIMER:
            if wparam == 1:
                self.motion_tick()
            elif wparam == 2:
                self.animation_tick()
            elif wparam == 3:
                user32.KillTimer(hwnd, 3)
                self.sleep_at_bottom()
            elif wparam == 4:
                self.finish_wake_wave()
            elif wparam == 5:
                self.finish_play_state()
            return 0
        if msg == WM_LBUTTONDOWN:
            px = signed_word(lparam)
            py = signed_word(lparam >> 16)
            self.dragging = True
            self.drag_started = False
            cursor = POINT()
            user32.GetCursorPos(ctypes.byref(cursor))
            self.drag_start = (cursor.x, cursor.y)
            self.drag_offset = (px, py)
            user32.SetCapture(hwnd)
            return 0
        if msg == WM_MOUSEMOVE and self.dragging:
            cursor = POINT()
            user32.GetCursorPos(ctypes.byref(cursor))
            if math.hypot(cursor.x - self.drag_start[0], cursor.y - self.drag_start[1]) > 5:
                self.drag_started = True
            self.x = cursor.x - self.drag_offset[0]
            self.y = cursor.y - self.drag_offset[1]
            self.vx = 0.0
            self.vy = 0.0
            self.render()
            return 0
        if msg == WM_LBUTTONUP:
            user32.ReleaseCapture()
            self.dragging = False
            if self.drag_started:
                if self.active_until:
                    self.pick_bottom_target()
                else:
                    self.sleep_at_bottom()
            else:
                self.wake_for_walk()
            return 0
        if msg == WM_RBUTTONUP:
            self.show_menu()
            return 0
        if msg == WM_KEYDOWN and wparam == VK_ESCAPE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def resolve_asset_dir() -> Path:
    script_dir = Path(__file__).resolve().parent
    if all((script_dir / name).exists() for name in ASSETS.values()):
        return script_dir

    fallback = Path(r"D:\GeneratedPet\hatch_pet")
    if all((fallback / name).exists() for name in ASSETS.values()):
        return fallback

    return script_dir


def main():
    global APP
    APP = DesktopPet(resolve_asset_dir())
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("This desktop pet uses Windows layered windows.")
    main()
