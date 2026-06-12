"""
storage/reminder_store.py — Persistent reminder storage with background scheduling.

Reminders are saved to reminders.json in the project root so they survive app restarts.
"""
import json
import threading
import time
import datetime
import logging
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Callable, Optional

from config import REMINDER_CHECK_INTERVAL

logger = logging.getLogger(__name__)
STORE_PATH = Path(__file__).parent.parent / "reminders.json"


@dataclass
class Reminder:
    id: str
    message: str
    time_str: Optional[str]    # "HH:MM" 24-hour, or None
    created_at: str            # ISO datetime string
    fired: bool = False

    @property
    def trigger_dt(self) -> Optional[datetime.datetime]:
        if not self.time_str:
            return None
        h, m = map(int, self.time_str.split(":"))
        dt = datetime.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        if dt <= datetime.datetime.now():
            dt += datetime.timedelta(days=1)
        return dt

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Reminder":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ReminderStore:
    def __init__(self, on_fire: Optional[Callable[[str], None]] = None):
        self.on_fire = on_fire
        self._reminders: list[Reminder] = []
        self._lock = threading.Lock()
        self._load()

        # Background thread checks for due reminders
        t = threading.Thread(target=self._scheduler_loop, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, message: str, time_str: Optional[str] = None) -> Reminder:
        r = Reminder(
            id=str(uuid.uuid4()),
            message=message,
            time_str=time_str,
            created_at=datetime.datetime.now().isoformat(),
        )
        with self._lock:
            self._reminders.append(r)
        self._save()
        logger.info("Reminder added: %s at %s", message, time_str)
        return r

    def delete(self, reminder_id: str) -> bool:
        with self._lock:
            before = len(self._reminders)
            self._reminders = [r for r in self._reminders if r.id != reminder_id]
            changed = len(self._reminders) < before
        if changed:
            self._save()
        return changed

    def all(self) -> list[Reminder]:
        with self._lock:
            return list(self._reminders)

    def clear_fired(self):
        with self._lock:
            self._reminders = [r for r in self._reminders if not r.fired]
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if STORE_PATH.exists():
            try:
                data = json.loads(STORE_PATH.read_text())
                self._reminders = [Reminder.from_dict(d) for d in data]
                logger.info("Loaded %d reminders from disk.", len(self._reminders))
            except Exception:
                logger.warning("Could not load reminders.json — starting fresh.")
                self._reminders = []

    def _save(self):
        try:
            STORE_PATH.write_text(
                json.dumps([r.to_dict() for r in self._reminders], indent=2)
            )
        except Exception as exc:
            logger.error("Could not save reminders: %s", exc)

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def _scheduler_loop(self):
        while True:
            time.sleep(REMINDER_CHECK_INTERVAL)
            now = datetime.datetime.now()
            fired_any = False
            with self._lock:
                for r in self._reminders:
                    if r.fired or not r.trigger_dt:
                        continue
                    if now >= r.trigger_dt:
                        r.fired = True
                        fired_any = True
                        if self.on_fire:
                            # Call the callback safely outside the lock
                            threading.Thread(
                                target=self.on_fire,
                                args=(r.message,),
                                daemon=True,
                            ).start()
            if fired_any:
                self._save()
