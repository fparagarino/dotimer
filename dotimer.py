import json, time, threading, queue, sys, subprocess, msvcrt

name = sys.argv[1] if len(sys.argv) > 1 else "config"
with open(f"{name}.json") as f:
    config = json.load(f)


def parse_time(s):
    parts = s.strip().split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid time format: '{s}' (expected MM:SS)")
    return int(parts[0]) * 60 + int(parts[1])

for t in config.get("timers", []):
    if "at" in t:
        t["at"] = parse_time(t["at"])

# Speech - uses Windows SAPI5 directly
speech_queue = queue.Queue()
rate = config.get("rate", 3)

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


def format_time(secs):
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"


def input_time(prompt):
    digits = ['', '', '', '']
    pos = 0

    def redraw():
        shown = [d if d else '_' for d in digits]
        sys.stdout.write("\r" + prompt + f"{shown[0]}{shown[1]}:{shown[2]}{shown[3]}")
        cursor_x = pos + (1 if pos >= 2 else 0)
        back = 5 - cursor_x
        if back > 0:
            sys.stdout.write("\b" * back)
        sys.stdout.flush()

    redraw()
    while True:
        ch = msvcrt.getwch()
        if ch == '\r':
            break
        if ch == '\x03':
            raise KeyboardInterrupt
        if ch in ('\b', '\x7f'):
            if pos > 0:
                pos -= 1
                digits[pos] = ''
                redraw()
        elif ch.isdigit() and pos < 4:
            digits[pos] = ch
            pos += 1
            redraw()

    print()
    mm = int((digits[0] or '0') + (digits[1] or '0'))
    ss = int((digits[2] or '0') + (digits[3] or '0'))
    return mm * 60 + ss


# Timer
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

def run_timer(start):
    timers = config.get("timers", [])
    current = start - 1
    ref = time.time()

    while True:
        time.sleep(0.05)
        new_current = start + int(time.time() - ref)
        while current < new_current:
            current += 1
            for t in timers:
                if should_fire(current, t):
                    print(f"\r  [{format_time(current)}] {t['voice']}                ")
                    speech_queue.put(t["voice"])
                notify = t.get("notify")
                if notify and should_fire(current + notify, t):
                    unit = "second" if notify == 1 else "seconds"
                    msg = f"{t['voice']} in {notify} {unit}"
                    print(f"\r  [{format_time(current)}] {msg}                ")
                    speech_queue.put(msg)
        print(f"\r  Running: {format_time(current)}  ", end="", flush=True)


def main():
    print("\n  DoTimer\n")

    try:
        start = input_time("  Start time: ")
        run_timer(start)
    except KeyboardInterrupt:
        print("\n  Bye.")

if __name__ == "__main__":
    main()
