import os
import sys
import time
import random
import keyboard
import pygame


# -------------------------
# Helper: resource path for PyInstaller
# -------------------------

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller one-file.
    """
    if hasattr(sys, "_MEIPASS"):
        # When frozen by PyInstaller
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # When running from source
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# -------------------------
# Config
# -------------------------

SETS_PATH = resource_path("sets")
CROSSFADE_MS = 250  # crossfade length in milliseconds


# -------------------------
# Engine function
# -------------------------

def run_engine(trigger_key: str = "r", on_step=None, stop_event=None) -> None:
    """
    Main music engine loop.

    :param trigger_key: 'r' or 'q' (or anything keyboard module supports)
    :param on_step: optional callback called once every time the key
                    successfully advances the state (one press).
    :param stop_event: threading.Event instance used by the GUI to stop the loop.
    """

    # ------------- init pygame mixer -------------
    if not pygame.mixer.get_init():
        # use directsound on Windows to avoid issues
        os.environ.setdefault("SDL_AUDIODRIVER", "directsound")
        pygame.mixer.init()

    print("Music Engine started...")
    print(f"Trigger key: {trigger_key.upper()}")

    # ------------- load all sets -------------
    music_sets: dict[str, list[pygame.mixer.Sound]] = {}

    if not os.path.isdir(SETS_PATH):
        print(f"ERROR: sets folder not found: {SETS_PATH}")
        return

    for folder in os.listdir(SETS_PATH):
        folder_path = os.path.join(SETS_PATH, folder)
        if not os.path.isdir(folder_path):
            continue

        files = [
            f for f in os.listdir(folder_path)
            if f.lower().endswith(".wav") or f.lower().endswith(".ogg")
        ]
        if not files:
            continue

        files.sort()  # 1,2,3 order

        sounds: list[pygame.mixer.Sound] = []
        for f in files[:3]:
            full_path = os.path.join(folder_path, f)
            try:
                snd = pygame.mixer.Sound(full_path)
                sounds.append(snd)
            except Exception as e:
                print(f"Failed to load {full_path}: {e}")

        if len(sounds) == 3:
            music_sets[folder] = sounds
        else:
            print(
                f"Skipping set '{folder}' – needs exactly 3 valid audio files, has {len(sounds)}"
            )

    if not music_sets:
        print("No valid sets found in 'sets' folder. Exiting engine.")
        return

    print("Loaded sets:", list(music_sets.keys()))

    # ------------- state management -------------
    current_set_name: str | None = None  # e.g. "sandman"
    current_state: int = 1               # 1 = default, 2 = intense, 3 = vocals
    current_channel = pygame.mixer.Channel(0)

    def play_loop_sound(sound: pygame.mixer.Sound) -> None:
        """Play a sound in a loop with crossfade from previous one."""
        if current_channel.get_busy():
            current_channel.fadeout(CROSSFADE_MS)
        current_channel.play(sound, loops=-1, fade_ms=CROSSFADE_MS)

    def play_current_state() -> None:
        """Play sound corresponding to current_set_name + current_state."""
        if current_set_name is None:
            return

        sounds = music_sets[current_set_name]
        index = current_state - 1
        if 0 <= index < len(sounds):
            sound = sounds[index]
            print(f"Playing set '{current_set_name}' state {current_state}")
            play_loop_sound(sound)
        else:
            print(f"Invalid state {current_state} for set '{current_set_name}'")

    def choose_random_set(exclude: str | None = None) -> str:
        names = list(music_sets.keys())
        if exclude in names and len(names) > 1:
            names.remove(exclude)
        return random.choice(names)

    def start_set(set_name: str) -> None:
        nonlocal current_set_name, current_state
        current_set_name = set_name
        current_state = 1
        print(f"\n=== Switched to set: {current_set_name} (state 1) ===")
        play_current_state()

    def advance_state() -> None:
        """Handle key press: 1→2→3→random new set."""
        nonlocal current_state, current_set_name

        if current_set_name is None:
            return

        if current_state == 1:
            current_state = 2
            print(f"--> Set '{current_set_name}' → state 2 (INTENSE)")
            play_current_state()

        elif current_state == 2:
            current_state = 3
            print(f"--> Set '{current_set_name}' → state 3 (VOCALS)")
            play_current_state()

        elif current_state == 3:
            new_set = choose_random_set(exclude=current_set_name)
            print(f"--> Finished set '{current_set_name}', picking new set: '{new_set}'")
            start_set(new_set)

        else:
            current_state = 1
            play_current_state()

        # Notify GUI (for wallpaper change counter)
        if on_step is not None:
            try:
                on_step()
            except Exception as e:
                print("on_step callback error:", e)

    # ------------- start with random set -------------
    start_set(choose_random_set())

    print(
        f"Press '{trigger_key.upper()}' to advance state (1→2→3→new set). "
        f"Stop via GUI or Ctrl+C (when run standalone)."
    )

    # ------------- main loop -------------
    key_held = False

    try:
        while True:
            # If GUI gave a stop_event and it's set → stop
            if stop_event is not None and stop_event.is_set():
                break

            if keyboard.is_pressed(trigger_key):
                if not key_held:
                    advance_state()
                    key_held = True
            else:
                key_held = False

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt – stopping engine.")

    finally:
        # Fade out gracefully
        if current_channel.get_busy():
            current_channel.fadeout(500)
            time.sleep(0.5)
        print("Music engine stopped.")


# --------------------------------------------------
# Stand-alone mode (optional)
# --------------------------------------------------

if __name__ == "__main__":
    # Allow `python main.py r` for testing without GUI
    key = "r"
    if len(sys.argv) >= 2:
        key = sys.argv[1].lower()
    run_engine(trigger_key=key)
