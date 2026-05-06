import json, time, threading, queue, subprocess, os, tkinter as tk, keyboard

START_HOTKEY = 'f9'

script_dir = os.path.dirname(os.path.abspath(__file__))


def parse_time(s):
    parts = s.strip().split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid time format: '{s}' (expected MM:SS)")
    return int(parts[0]) * 60 + int(parts[1])


speech_queue = queue.Queue()


def format_time(secs):
    secs = int(secs)
    sign = '-' if secs < 0 else ''
    m, s = divmod(abs(secs), 60)
    return f"{sign}{m:02d}:{s:02d}"


def should_fire(current, t):
    if current < t.get("first", 0):
        return False
    if "last" in t and current > t["last"]:
        return False
    if "at" in t and current == t["at"]:
        return True
    if "every" in t and current > 0 and current % t["every"] == 0:
        return True
    return False


def fire_events(current, timers):
    for t in timers:
        if should_fire(current, t):
            print(f"  [{format_time(current)}] {t['voice']}")
            speech_queue.put(t["voice"])
        notify = t.get("notify")
        if notify and should_fire(current + notify, t):
            unit = "second" if notify == 1 else "seconds"
            msg = f"{t['voice']} in {notify} {unit}"
            print(f"  [{format_time(current)}] {msg}")
            speech_queue.put(msg)


def main():
    configs = sorted(f[:-5] for f in os.listdir(script_dir) if f.endswith(".json"))
    if not configs:
        print("  No .json configs found.")
        return

    timers = []
    rate = 3

    def load_config(name):
        nonlocal timers, rate
        with open(os.path.join(script_dir, f"{name}.json")) as f:
            cfg = json.load(f)
        for t in cfg.get("timers", []):
            if "at" in t:
                t["at"] = parse_time(t["at"])
        timers = cfg.get("timers", [])
        rate = cfg.get("rate", 3)

    load_config(configs[0])

    def speech_worker():
        while True:
            text = speech_queue.get()
            try:
                safe = text.replace("'", "''")
                subprocess.run(
                    ["powershell", "-Command",
                     f"$v=New-Object -ComObject SAPI.SpVoice;$v.Rate={rate};$v.Speak('{safe}')"],
                    creationflags=0x08000000
                )
            except Exception as e:
                print(f"  TTS error: {e}")

    threading.Thread(target=speech_worker, daemon=True).start()

    current = 0
    next_tick = None
    running = False
    fresh = True

    root = tk.Tk()
    root.title("DoTimer")

    selected = tk.StringVar(value=configs[0])
    tk.OptionMenu(root, selected, *configs, command=load_config).pack(pady=(20, 0))

    font = ("Consolas", 72)
    clock = tk.Frame(root)
    clock.pack(padx=40, pady=20)
    mins = tk.Label(clock, text="00", font=font)
    mins.pack(side=tk.LEFT)
    tk.Label(clock, text=":", font=font).pack(side=tk.LEFT)
    secs = tk.Label(clock, text="00", font=font)
    secs.pack(side=tk.LEFT)

    def update_label():
        sign = '-' if current < 0 else ''
        m, s = divmod(abs(current), 60)
        mins.config(text=f"{sign}{m:02d}")
        secs.config(text=f"{s:02d}")

    def adjust(delta):
        nonlocal current, fresh
        if running:
            return
        current += delta
        fresh = True
        update_label()

    mins.bind("<MouseWheel>", lambda e: adjust(60 if e.delta > 0 else -60))
    secs.bind("<MouseWheel>", lambda e: adjust(1 if e.delta > 0 else -1))

    def toggle():
        nonlocal running
        running = not running
    keyboard.add_hotkey(START_HOTKEY, toggle)

    def tick():
        nonlocal current, next_tick, fresh
        if running:
            if next_tick is None:
                if fresh:
                    fire_events(current, timers)
                    fresh = False
                next_tick = time.time() + 1
            while time.time() >= next_tick:
                next_tick += 1
                current += 1
                fire_events(current, timers)
            update_label()
        else:
            next_tick = None
        root.after(50, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
