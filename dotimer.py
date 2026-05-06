import json, time, threading, queue, subprocess, os, tkinter as tk, keyboard

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
    hotkey = 'f9'
    enabled_vars = []
    hotkey_handle = None

    def load_config(name):
        nonlocal timers, rate, hotkey, hotkey_handle
        with open(os.path.join(script_dir, f"{name}.json")) as f:
            cfg = json.load(f)
        for t in cfg.get("timers", []):
            if "at" in t:
                t["at"] = parse_time(t["at"])
        timers = cfg.get("timers", [])
        rate = cfg.get("rate", 3)
        hotkey = cfg.get("hotkey", 'f9')
        if hotkey_handle is not None:
            keyboard.remove_hotkey(hotkey_handle)
            hotkey_handle = keyboard.add_hotkey(hotkey, toggle)

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

    root = tk.Tk()
    root.title("DoTimer")

    selected = tk.StringVar(value=configs[0])
    def on_select(name):
        load_config(name)
        rebuild_checkboxes()
    tk.OptionMenu(root, selected, *configs, command=on_select).pack(pady=(20, 0))

    font = ("Consolas", 72)
    clock = tk.Frame(root)
    clock.pack(padx=40, pady=20)
    mins = tk.Label(clock, text="00", font=font)
    mins.pack(side=tk.LEFT)
    tk.Label(clock, text=":", font=font).pack(side=tk.LEFT)
    secs = tk.Label(clock, text="00", font=font)
    secs.pack(side=tk.LEFT)

    checkbox_frame = tk.Frame(root)
    checkbox_frame.pack(padx=20, pady=(0, 20), anchor="w")

    def rebuild_checkboxes():
        for w in checkbox_frame.winfo_children():
            w.destroy()
        enabled_vars.clear()
        for t in timers:
            var = tk.BooleanVar(value=True)
            enabled_vars.append(var)
            tk.Checkbutton(checkbox_frame, text=t["voice"], variable=var).pack(anchor="w")

    rebuild_checkboxes()

    def update_label():
        m, _, s = format_time(current).rpartition(":")
        mins.config(text=m)
        secs.config(text=s)

    def adjust(delta):
        nonlocal current
        current += delta
        update_label()

    mins.bind("<Enter>", lambda e: mins.focus_set())
    mins.bind("<MouseWheel>", lambda e: adjust(60 if e.delta > 0 else -60))
    secs.bind("<Enter>", lambda e: secs.focus_set())
    secs.bind("<MouseWheel>", lambda e: adjust(1 if e.delta > 0 else -1))

    def toggle():
        nonlocal running
        running = not running
    hotkey_handle = keyboard.add_hotkey(hotkey, toggle)

    def tick():
        nonlocal current, next_tick
        if running:
            active = [t for t, v in zip(timers, enabled_vars) if v.get()]
            if next_tick is None:
                next_tick = time.time() + 1
            while time.time() >= next_tick:
                next_tick += 1
                current += 1
                fire_events(current, active)
            update_label()
        else:
            next_tick = None
        root.after(50, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
