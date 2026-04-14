import json, time, threading, queue
import pyttsx3
from pynput import keyboard

with open("config.json") as f:
    config = json.load(f)

# Speech - single thread owns the engine
speech_queue = queue.Queue()

def speech_worker():
    engine = pyttsx3.init()
    while True:
        engine.say(speech_queue.get())
        engine.runAndWait()

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

def should_fire_interval(current, iv):
    first = iv.get("first", iv["every"])
    every = iv["every"]
    return current >= first and (current - first) % every == 0

def run_timer(start):
    global running
    cues = {parse_time(c["at"]): c["voice"] for c in config.get("cues", [])}
    intervals = config.get("intervals", [])
    fired_cues = {t for t in cues if t < start}

    current = start - 1
    ref = time.time()

    while running:
        time.sleep(0.05)
        new_current = start + int(time.time() - ref)
        while current < new_current:
            current += 1
            for iv in intervals:
                if current > 0 and should_fire_interval(current, iv):
                    speech_queue.put(iv["voice"])
            if current in cues and current not in fired_cues:
                fired_cues.add(current)
                speech_queue.put(cues[current])
        print(f"\r  Running: {format_time(current)}  ", end="", flush=True)


def main():
    global running
    hotkey_name = config.get("hotkey", "f9").upper()

    print(f"\n  DoTimer")
    print(f"  {len(config.get('intervals', []))} intervals, {len(config.get('cues', []))} cues")
    print(f"  Hotkey: {hotkey_name}\n")

    try:
        while True:
            raw = input("  Start time [00:00]: ").strip()
            try:
                start = parse_time(raw) if raw else 0
            except ValueError as e:
                print(f"  {e}")
                continue

            print(f"  Waiting for {hotkey_name}...")
            hotkey_event.clear()
            hotkey_event.wait()

            running = True
            t = threading.Thread(target=run_timer, args=(start,), daemon=True)
            t.start()

            hotkey_event.clear()
            hotkey_event.wait()

            running = False
            t.join()
            print(f"\n  Stopped.\n")
    except KeyboardInterrupt:
        running = False
        print("\n  Bye.")

if __name__ == "__main__":
    main()
