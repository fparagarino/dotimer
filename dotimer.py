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
    if current < t.get("from", 0):
        return False
    if "until" in t and current > t["until"]:
        return False
    if "every" not in t and "at" in t and current == t["at"]:
        return True
    if "every" in t and current > 0 and (current - t.get("at", 0)) % t["every"] == 0:
        return True
    return False


def join_voices(voices):
    return voices[0] if len(voices) == 1 else f"{', '.join(voices[:-1])} and {voices[-1]}"


def speak(current, msg):
    print(f"  [{format_time(current)}] {msg}")
    speech_queue.put(msg)


def fire_events(current, timers):
    main = [t["voice"] for t in timers if should_fire(current, t)]
    if main:
        speak(current, join_voices(main))

    by_warn = {}
    for t in timers:
        n = t.get("warn")
        if n and should_fire(current + n, t):
            by_warn.setdefault(n, []).append(t["voice"])
    for n, voices in by_warn.items():
        unit = "second" if n == 1 else "seconds"
        speak(current, f"{join_voices(voices)} in {n} {unit}")


def upcoming_events(current, timers, n, horizon=3600):
    events = []
    for c in range(current + 1, current + horizon + 1):
        firing = [t for t in timers if should_fire(c, t)]
        if firing:
            events.append((c, firing))
            if len(events) >= n:
                break
    return events


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
    next_count = 3

    def load_config(name):
        nonlocal timers, rate, hotkey, hotkey_handle, next_count
        with open(os.path.join(script_dir, f"{name}.json")) as f:
            cfg = json.load(f)
        for t in cfg.get("timers", []):
            if "at" in t and isinstance(t["at"], str):
                t["at"] = parse_time(t["at"])
        timers = cfg.get("timers", [])
        rate = cfg.get("rate", 3)
        hotkey = cfg.get("hotkey", 'f9')
        next_count = cfg.get("next", 3)
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

    image_cache = {}
    def get_image(voice):
        if not voice or voice in image_cache:
            return image_cache.get(voice)
        try:
            image_cache[voice] = tk.PhotoImage(file=os.path.join(script_dir, "icons", f"{voice}.png"))
        except Exception:
            image_cache[voice] = None
        return image_cache[voice]

    selected = tk.StringVar(value=configs[0])
    def on_select(name):
        load_config(name)
        rebuild_checkboxes()
        update_next()
    tk.OptionMenu(root, selected, *configs, command=on_select).pack(pady=(20, 0))

    font = ("Consolas", 72)
    next_font = ("Consolas", 18)
    featured_font = ("Consolas", 28)
    clock = tk.Frame(root)
    clock.pack(padx=40, pady=20)
    mins = tk.Label(clock, text="00", font=font)
    mins.pack(side=tk.LEFT)
    tk.Label(clock, text=":", font=font).pack(side=tk.LEFT)
    secs = tk.Label(clock, text="00", font=font)
    secs.pack(side=tk.LEFT)

    next_frame = tk.Frame(root)
    next_frame.pack(padx=20, pady=(0, 20), anchor="w")
    tk.Label(next_frame, text="Next:").pack(anchor="w")
    next_list = tk.Frame(next_frame)
    next_list.pack(anchor="w")

    checkbox_frame = tk.Frame(root)
    checkbox_frame.pack(padx=20, pady=(0, 20), anchor="w")
    tk.Label(checkbox_frame, text="Timers:").pack(anchor="w")
    checkbox_list = tk.Frame(checkbox_frame)
    checkbox_list.pack(anchor="w")

    def update_label():
        m, _, s = format_time(current).rpartition(":")
        mins.config(text=m)
        secs.config(text=s)

    def update_next():
        for w in next_list.winfo_children():
            w.destroy()
        active = [t for t, v in zip(timers, enabled_vars) if v.get()]
        for i, (fire_time, firing) in enumerate(upcoming_events(current, active, next_count)):
            delta = fire_time - current
            text = f"  ({delta}s) {' & '.join(t['voice'] for t in firing)}"
            label = tk.Label(next_list, text=text, font=featured_font if i == 0 else next_font)
            icon = get_image(firing[0]["voice"])
            if icon:
                label.config(image=icon, compound="left")
            label.pack(anchor="w", pady=(0, 8 if i == 0 else 0))

    def rebuild_checkboxes():
        for w in checkbox_list.winfo_children():
            w.destroy()
        enabled_vars.clear()
        for t in timers:
            var = tk.BooleanVar(value=True)
            enabled_vars.append(var)
            cb = tk.Checkbutton(checkbox_list, text=t["voice"], variable=var, command=update_next)
            icon = get_image(t["voice"])
            if icon:
                cb.config(image=icon, compound="left")
            cb.pack(anchor="w")

    rebuild_checkboxes()
    update_next()

    def adjust(delta):
        nonlocal current
        current += delta
        update_label()
        update_next()

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
            update_next()
        else:
            next_tick = None
        root.after(50, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
