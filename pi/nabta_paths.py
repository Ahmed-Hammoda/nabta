"""Where every Nabta file lives (one place for all scripts).

logs/
  2026-11/raw_log.csv        one row every 10 s
  2026-11/log_30min.csv      one averaged row every 30 min (+ "samples" = readings averaged)
  2026-11/decisions.csv      one decision per 30-min row
  2026-11/model_io.jsonl     one line per decision: model input (8 values), rules answer (8 keys), actions
  2026-12/...                a new folder only when a new month starts
  events.csv                 logger/controller started/stopped (shows when the Pi was off)
  controller_state.json      controller memory
  old_calibration/           logs from before the 17 Nov 2026 calibration

Turning the Pi off and on never makes new files: the scripts append to the current month's files.
Raw logs older than KEEP_RAW_MONTHS are compressed to raw_log.csv.gz (the other files stay as they are).
"""
import csv, glob, gzip, json, os, shutil
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "logs")
EVENTS = os.path.join(LOGS, "events.csv")
STATE = os.path.join(LOGS, "controller_state.json")
KEEP_RAW_MONTHS = 3


def now():
    return datetime.now().astimezone()


def month_of(t=None):
    t = t or now()
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    return t.strftime("%Y-%m")


def month_dir(t=None):
    d = os.path.join(LOGS, month_of(t))
    os.makedirs(d, exist_ok=True)
    return d


def raw_file(t=None):
    return os.path.join(month_dir(t), "raw_log.csv")


def avg_file(t=None):
    return os.path.join(month_dir(t), "log_30min.csv")


def decisions_file(t=None):
    return os.path.join(month_dir(t), "decisions.csv")


def model_io_file(t=None):
    """One JSON line per 30-min decision: the model's exact input, the rules' answer, what the Pi did."""
    return os.path.join(month_dir(t), "model_io.jsonl")


def append_jsonl(path, record):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + chr(10))
        f.flush()
        os.fsync(f.fileno())


def months():
    """Month folders, oldest first."""
    return sorted(os.path.basename(d) for d in glob.glob(os.path.join(LOGS, "[0-9][0-9][0-9][0-9]-[0-9][0-9]")))


def files(name, last=None):
    """Existing files called `name` in the month folders, oldest first (only the `last` months if given)."""
    ms = months()[-last:] if last else months()
    return [p for p in (os.path.join(LOGS, m, name) for m in ms) if os.path.exists(p)]


def read_csv(name, last=2):
    """All rows of `name` from the last `last` months, oldest first."""
    rows = []
    for p in files(name, last):
        with open(p, newline="") as f:
            rows += list(csv.DictReader(f))
    return rows


_checked = set()


def ensure_header(path, header):
    """If an existing CSV has an older header (fewer columns), rewrite it once with the new header.
    Old rows keep their values; new columns are left empty. Safe to call before every append."""
    if path in _checked or not os.path.exists(path) or os.path.getsize(path) == 0:
        _checked.add(path)
        return
    with open(path, newline="") as f:
        old = next(csv.reader(f), [])
    if old != list(header):
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        tmp = path + ".tmp"
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(header), extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") or "" for k in header})
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        log_event("files", "columns added", "%s: %s" % (os.path.basename(path), ", ".join(c for c in header if c not in old)))
    _checked.add(path)


def log_event(source, event, detail=""):
    os.makedirs(LOGS, exist_ok=True)
    new = not os.path.exists(EVENTS)
    with open(EVENTS, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "source", "event", "detail"])
        w.writerow([now().isoformat(timespec="seconds"), source, event, detail])
        f.flush()
        os.fsync(f.fileno())


def compress_old_raw():
    """gzip raw_log.csv in month folders older than KEEP_RAW_MONTHS. Returns the files compressed."""
    done = []
    t = now()
    y, mo = t.year, t.month - KEEP_RAW_MONTHS
    while mo < 1:
        y, mo = y - 1, mo + 12
    cutoff = "%04d-%02d" % (y, mo)          # e.g. in 2026-11 with 3 months kept: compress 2026-07 and older
    for m in [m for m in months() if m <= cutoff]:
        p = os.path.join(LOGS, m, "raw_log.csv")
        if os.path.exists(p):
            with open(p, "rb") as src, gzip.open(p + ".gz", "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.remove(p)
            done.append(p + ".gz")
    return done
