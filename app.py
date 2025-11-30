import sys
import os
import math
import time
import random
import threading

import customtkinter as ctk
from tkinter import Canvas
from PIL import Image, ImageTk
import cv2

import main  # our music engine module


# ------------ Helper: resource path for PyInstaller ------------

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and PyInstaller one-file.
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ------------ App config ------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MusicApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("R/Q Music Engine")
        self.geometry("1600x900")
        self.resizable(False, False)

        # Engine thread & control
        self.engine_thread: threading.Thread | None = None
        self.engine_stop_event = threading.Event()
        self.press_count = 0  # for every 3rd press → change wallpaper

        # Selected key
        self.selected_key = ctk.StringVar(value="r")

        # ---------- Wallpaper / Background state ----------
        self.wallpaper_mode = "image"  # "image", "gif", "video"
        self.wallpaper_path: str | None = None

        # Static image
        self.wallpaper_image: Image.Image | None = None
        self.wallpaper_tk = None

        # GIF
        self.gif_frames: list[Image.Image] = []
        self.gif_index = 0
        self.gif_frame_duration = 0.1
        self.gif_last_time = 0.0

        # Video
        self.video_cap: cv2.VideoCapture | None = None
        self.video_frame: Image.Image | None = None
        self.video_fps = 30.0
        self.video_frame_interval = 1.0 / 30.0
        self.video_last_time = 0.0
        self.video_fade_progress = 0.0

        # Particles
        self.particles: list[dict] = []

        # Load initial wallpaper
        self._load_random_wallpaper()

        # Build GUI
        self._build_ui()

        # Animation parameters
        self.circle_phase = 0.0
        self.circle_running = False

        # Start animation loop
        self.after(20, self._animate_circle)

    # --------------------------------------------------------
    # WALLPAPER LOADING
    # --------------------------------------------------------

    def _load_random_wallpaper(self) -> None:
        """Pick a random file from wallpapers/ and configure mode."""
        wallpaper_dir = resource_path("wallpapers")

        if not os.path.isdir(wallpaper_dir):
            raise Exception(f"No 'wallpapers' folder found at: {wallpaper_dir}")

        exts = (".png", ".jpg", ".jpeg", ".gif",
                ".mp4", ".mov", ".avi", ".mkv", ".webm")

        all_wp = [
            os.path.join(wallpaper_dir, f)
            for f in os.listdir(wallpaper_dir)
            if f.lower().endswith(exts)
        ]

        if not all_wp:
            raise Exception("No wallpapers found in wallpapers/ folder!")

        # Close previous video if any
        if self.video_cap is not None:
            self.video_cap.release()
            self.video_cap = None

        self.wallpaper_path = random.choice(all_wp)
        lower = self.wallpaper_path.lower()

        if lower.endswith((".png", ".jpg", ".jpeg")):
            self.wallpaper_mode = "image"
            self.wallpaper_image = Image.open(self.wallpaper_path).convert("RGB")
            print(f"[Wallpaper] Static image: {os.path.basename(self.wallpaper_path)}")

        elif lower.endswith(".gif"):
            self.wallpaper_mode = "gif"
            self._load_gif(self.wallpaper_path)
            print(f"[Wallpaper] GIF: {os.path.basename(self.wallpaper_path)}")

        else:
            self.wallpaper_mode = "video"
            self._load_video(self.wallpaper_path)
            print(f"[Wallpaper] VIDEO: {os.path.basename(self.wallpaper_path)}")

    def _load_gif(self, path: str) -> None:
        self.gif_frames = []
        self.gif_index = 0
        self.gif_last_time = time.time()

        img = Image.open(path)
        duration_ms = img.info.get("duration", 100)
        self.gif_frame_duration = max(duration_ms / 1000.0, 0.03)

        try:
            while True:
                frame = img.convert("RGB")
                self.gif_frames.append(frame)
                img.seek(img.tell() + 1)
        except EOFError:
            pass

        if not self.gif_frames:
            self.wallpaper_mode = "image"
            self.wallpaper_image = Image.open(path).convert("RGB")

    def _load_video(self, path: str) -> None:
        self.video_cap = cv2.VideoCapture(path)
        if not self.video_cap.isOpened():
            print("Failed to open video. Falling back to black.")
            self.wallpaper_mode = "image"
            self.wallpaper_image = Image.new("RGB", (1920, 1080), "black")
            return

        fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
        self.video_fps = fps
        self.video_frame_interval = 1.0 / fps
        self.video_last_time = 0.0
        self.video_fade_progress = 0.0

        ret, frame = self.video_cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.video_frame = Image.fromarray(frame_rgb)
        else:
            self.wallpaper_mode = "image"
            self.wallpaper_image = Image.new("RGB", (1920, 1080), "black")

    # --------------------------------------------------------
    # UI LAYOUT
    # --------------------------------------------------------

    def _build_ui(self) -> None:
        main_frame = ctk.CTkFrame(self, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Left panel
        left_frame = ctk.CTkFrame(main_frame, corner_radius=15)
        left_frame.pack(side="left", fill="y", padx=20, pady=20)

        title_label = ctk.CTkLabel(
            left_frame,
            text="Music Engine",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title_label.pack(pady=(10, 20))

        desc_label = ctk.CTkLabel(
            left_frame,
            text="Choose which key\nyou want to use in-game.",
            justify="left",
        )
        desc_label.pack(pady=(0, 15))

        # Key selector
        key_label = ctk.CTkLabel(left_frame, text="Trigger key:")
        key_label.pack(anchor="w", padx=10)

        key_option = ctk.CTkComboBox(
            left_frame,
            values=["r", "q"],
            variable=self.selected_key,
            state="readonly",
            width=80,
        )
        key_option.pack(pady=(5, 15), padx=10, anchor="w")

        # Start button
        start_button = ctk.CTkButton(
            left_frame, text="Start Engine", command=self.start_engine
        )
        start_button.pack(pady=(10, 5), padx=10, fill="x")

        # Stop button
        stop_button = ctk.CTkButton(
            left_frame,
            text="Stop Engine",
            fg_color="#444444",
            command=self.stop_engine,
        )
        stop_button.pack(pady=(5, 10), padx=10, fill="x")

        # Status label
        self.status_label = ctk.CTkLabel(
            left_frame, text="Status: idle", text_color="#aaaaaa"
        )
        self.status_label.pack(pady=(10, 0), padx=10, anchor="w")

        # Right panel (visualizer)
        right_frame = ctk.CTkFrame(main_frame, corner_radius=15)
        right_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.canvas = Canvas(right_frame, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    # --------------------------------------------------------
    # ENGINE CONTROL
    # --------------------------------------------------------

    def start_engine(self) -> None:
        if self.engine_thread is not None and self.engine_thread.is_alive():
            return  # already running

        key = self.selected_key.get().lower()
        self.status_label.configure(text=f"Status: running (key = {key.upper()})")

        self.engine_stop_event.clear()
        self.press_count = 0

        # start engine in background thread
        self.engine_thread = threading.Thread(
            target=main.run_engine,
            args=(key, self._on_engine_step, self.engine_stop_event),
            daemon=True,
        )
        self.engine_thread.start()

        self.circle_running = True

    def stop_engine(self) -> None:
        if self.engine_thread is not None and self.engine_thread.is_alive():
            self.engine_stop_event.set()

        self.circle_running = False
        self.status_label.configure(text="Status: stopped")

    def _on_engine_step(self) -> None:
        """
        Called from engine thread every time the state advances (one key press).
        Every 3rd press we change wallpaper.
        """
        self.press_count += 1
        if self.press_count % 3 == 0:
            # schedule in main thread
            self.after(0, self._load_random_wallpaper)

    # --------------------------------------------------------
    # BACKGROUND FRAME FETCH
    # --------------------------------------------------------

    def _get_background_image(self, w: int, h: int) -> Image.Image:
        now = time.time()

        if self.wallpaper_mode == "image":
            frame = self.wallpaper_image or Image.new("RGB", (w, h), "black")

        elif self.wallpaper_mode == "gif":
            if self.gif_frames:
                if now - self.gif_last_time >= self.gif_frame_duration:
                    self.gif_last_time = now
                    self.gif_index = (self.gif_index + 1) % len(self.gif_frames)
                frame = self.gif_frames[self.gif_index]
            else:
                frame = Image.new("RGB", (w, h), "black")

        elif self.wallpaper_mode == "video":
            frame = self.video_frame or Image.new("RGB", (w, h), "black")
            if (
                self.video_cap is not None
                and now - self.video_last_time >= self.video_frame_interval
            ):
                self.video_last_time = now
                ret, frame_bgr = self.video_cap.read()
                if not ret:
                    # loop video and trigger fade
                    self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.video_fade_progress = 1.0
                    ret, frame_bgr = self.video_cap.read()
                if ret:
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    frame = self.video_frame = Image.fromarray(frame_rgb)

            # fade at loop
            if self.video_fade_progress > 0.0 and frame is not None:
                alpha = max(0.0, min(1.0, self.video_fade_progress))
                black = Image.new("RGB", frame.size, "black")
                frame = Image.blend(black, frame, 1.0 - alpha)
                self.video_fade_progress -= 0.03

        else:
            frame = Image.new("RGB", (w, h), "black")

        return frame.resize((w, h), Image.LANCZOS)

    # --------------------------------------------------------
    # PARTICLE SYSTEM
    # --------------------------------------------------------

    def _spawn_particle(self, w: int, h: int) -> None:
        x = random.uniform(w * 0.2, w * 0.8)
        y = random.uniform(h * 0.2, h * 0.8)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.1, 0.4)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        radius = random.uniform(2, 6)
        life = random.uniform(4.0, 8.0)

        self.particles.append(
            {
                "x": x,
                "y": y,
                "vx": vx,
                "vy": vy,
                "r": radius,
                "life": life,
                "max_life": life,
            }
        )

    def _update_and_draw_particles(self, w: int, h: int) -> None:
        if random.random() < 0.15:
            self._spawn_particle(w, h)

        alive: list[dict] = []
        for p in self.particles:
            p["life"] -= 0.05
            if p["life"] <= 0:
                continue

            p["x"] += p["vx"]
            p["y"] += p["vy"]

            if (
                p["x"] < -50
                or p["x"] > w + 50
                or p["y"] < -50
                or p["y"] > h + 50
            ):
                continue

            t = max(0.0, min(1.0, p["life"] / p["max_life"]))
            base_color = 80 + int(175 * t)
            color = f"#{base_color:02x}{base_color:02x}{base_color:02x}"

            r = p["r"] * (0.5 + 0.5 * t)
            x0 = p["x"] - r
            y0 = p["y"] - r
            x1 = p["x"] + r
            y1 = p["y"] + r

            self.canvas.create_oval(x0, y0, x1, y1, outline=color, fill="")
            alive.append(p)

        self.particles = alive

    # --------------------------------------------------------
    # VISUALIZER ANIMATION
    # --------------------------------------------------------

    def _animate_circle(self) -> None:
        self.canvas.delete("all")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        # Background
        bg_img = self._get_background_image(w, h)
        self.wallpaper_tk = ImageTk.PhotoImage(bg_img)
        self.canvas.create_image(0, 0, image=self.wallpaper_tk, anchor="nw")

        # Dark overlay
        self.canvas.create_rectangle(
            0, 0, w, h, fill="#000000", stipple="gray50", outline=""
        )

        # Particles
        self._update_and_draw_particles(w, h)

        # Circle
        cx = w / 2
        cy = h / 2
        base_r = min(w, h) * 0.30

        if self.circle_running:
            self.circle_phase += 0.15
            pulse = (math.sin(self.circle_phase) + 1) / 2
            r = base_r * (0.9 + 0.25 * pulse)
            color = "#32a852"
        else:
            self.circle_phase += 0.03
            pulse = (math.sin(self.circle_phase) + 1) / 2
            r = base_r * (0.8 + 0.1 * pulse)
            color = "#555555"

        x0 = cx - r
        y0 = cy - r
        x1 = cx + r
        y1 = cy + r

        self.canvas.create_oval(
            x0 - 10, y0 - 10, x1 + 10, y1 + 10, fill="", outline="#222222", width=4
        )
        self.canvas.create_oval(x0, y0, x1, y1, fill=color, outline="")

        self.canvas.create_text(
            cx,
            cy,
            text=self.selected_key.get().upper(),
            fill="white",
            font=("Segoe UI", int(r * 0.55), "bold"),
        )

        self.after(20, self._animate_circle)


# --------------------------------------------------
# RUN APP
# --------------------------------------------------

if __name__ == "__main__":
    app = MusicApp()
    app.mainloop()
