import json, time, threading, queue, sys
import pyttsx3
from pynput import keyboard

name = sys.argv[1] if len(sys.argv) > 1 else "config"
with open(f"{name}.json") as f:
    config = json.load(f)

# Speech - single thread owns the engine
speech_queue = queue.Queue()

def speech_worker():
    try:
        engine = pyttsx3.init()
    except Exception as e:
        print(f"  TTS error: {e}")
        return
    while True:
        text = speech_queue.get()
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"  TTS error: {e}")

threading.Thread(target=speech_worker, daemon=True).start()


def parse_time(s):
    parts = s.strip().split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid time format: '{s}' (expected MM:SS)")
    return int(parts[0]) * 60 + int(parts[1])

def format_time(secs):
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"


# Hotkey
def get_hotkey(name):
    if hasattr(keyboard.Key, name.lower()):
        return getattr(keyboard.Key, name.lower())
    return keyboard.KeyCode.from_char(name)

target_key = get_hotkey(config.get("hotkey", "f9"))
hotkey_event = threading.Event()

def on_press(key):
    if key == target_key:
        hotkey_event.set()

listener = keyboard.Listener(on_press=on_press)
listener.daemon = True
listener.start()


# Timer
running = False

def should_fire(current, t):
    if current < t.get("first", 0):
        return False
    if "last" in t and current > t["last"]:
        return False
    if "at" in t and current == parse_time(t["at"]):
        return True
    if "every" in t and current % t["every"] == 0:
        return True
    return False

def run_timer(start):
    global running
    timers = config.get("timers", [])
    current = start - 1
    ref = time.time()

    while running:
        time.sleep(0.05)
        new_current = start + int(time.time() - ref)
        while current < new_current:
            current += 1
            for t in timers:
                if current > 0 and should_fire(current, t):
                    print(f"\r  [{format_time(current)}] {t['voice']}                ")
                    speech_queue.put(t["voice"])
        print(f"\r  Running: {format_time(current)}  ", end="", flush=True)


def main():
    global running
    hotkey_name = config.get("hotkey", "f9").upper()

    print(f"\n  DoTimer")
    print(f"  Hotkey: {hotkey_name}\n")

    try:
        raw = input("  Start time [00:00]: ").strip()
        try:
            start = parse_time(raw) if raw else 0
        except ValueError as e:
            print(f"  {e}")
            return

        print(f"  Waiting for {hotkey_name}...")
        hotkey_event.clear()
        hotkey_event.wait()
        listener.stop()

        running = True
        run_timer(start)
    except KeyboardInterrupt:
        running = False
        print("\n  Bye.")

if __name__ == "__main__":
    main()
