"""Shared raid windows and durable, fail-closed spending reservations."""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def raid_window(cfg: dict, now: float | None = None) -> tuple[int, float, bool]:
    now = time.time() if now is None else now
    period = max(600, int(cfg.get("repeat_min", 30)) * 60)
    window = int(now // period)
    end = window * period + min(period - 60, int(cfg.get("assembly_sec", 600)))
    return window, end, now < end


def respawn_seconds(value: str) -> int | None:
    """Server countdown only. An unreadable timer never means 'already open'."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}:\d{2}(?::\d{2})?", value.strip()):
        return None
    parts = [int(p) for p in value.strip().split(":")]
    if any(p >= 60 for p in parts[1:]):
        return None
    return (parts[0] * 60 + parts[1]) if len(parts) == 2 else (parts[0] * 3600 + parts[1] * 60 + parts[2])


def party_ready(info: dict, cfg: dict) -> bool:
    """Match every configured hero individually; strangers cannot replace a medic."""
    from .pages import cyr_normalize

    party = cfg.get("party") or []
    if len(party) < 3 or sum(p.get("role") == "medic" for p in party) != 1:
        return False
    ready = info.get("ready") or []
    matched = set()
    for member in party:
        aliases = {cyr_normalize(n) for n in member.get("names", [])}
        matches = [str(p.get("id")) for p in ready if p.get("role") == member.get("role") and (
            str(p.get("id")) == str(member["id"]) if member.get("id")
            else cyr_normalize(p.get("name", "")) in aliases
        )]
        if len(matches) != 1 or matches[0] in matched:
            return False
        matched.add(matches[0])
    return len(matched) >= int(cfg.get("min_party", 3))


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class RepairBudget:
    """Reserve before clicking. Ambiguous outcomes consume the reservation.

    Actions reservations use GitHub contents CAS immediately, rather than relying
    on a commit five hours later. Only this small non-secret ledger is uploaded.
    """

    def __init__(self, path: Path, account: str):
        self.path = path
        self.account = account
        self.remote = os.environ.get("GITHUB_ACTIONS") == "true"
        self.sha = None
        self.url = ""
        if self.remote:
            repo = os.environ["GITHUB_REPOSITORY"]
            self.url = f"https://api.github.com/repos/{repo}/contents/state/{account}/repair-budget.json"

    def _request(self, method: str, body: dict | None = None) -> dict:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("durable repair budget requires GitHub token")
        req = urllib.request.Request(self.url, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)

    def _load(self) -> dict:
        if self.remote:
            try:
                result = self._request("GET")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                self.sha = None
                return {}
            self.sha = result["sha"]
            return json.loads(base64.b64decode(result["content"]))
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {}

    def _save(self, value: dict) -> None:
        if self.remote:
            body = {"message": f"state({self.account}): repair budget",
                    "content": base64.b64encode(json.dumps(value).encode()).decode()}
            if self.sha:
                body["sha"] = self.sha
            result = self._request("PUT", body)
            self.sha = result["content"]["sha"]
            return
        atomic_json(self.path, value)

    def reserve(self) -> dict | None:
        # One process per hero is enforced by workflow concurrency. Local use
        # additionally takes an exclusive file lock; a stale lock denies spending.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return None
        try:
            os.close(fd)
            data = self._load()
            day = datetime.now(timezone(timedelta(hours=3))).date().isoformat()
            # Never release a pending reservation across midnight: its server
            # operation might complete on the next day after an interrupted call.
            if data.get("status") == "pending" or (data.get("date") == day and data.get("reserved_gold", 0) >= 1):
                return None
            data = {"date": day, "reserved_gold": 1, "status": "pending"}
            self._save(data)
            return data
        finally:
            lock.unlink(missing_ok=True)

    def finish(self, reservation: dict, result: dict) -> None:
        # Unconfirmed operations remain pending and block further purchases.
        data = dict(reservation)
        data["result"] = {k: result.get(k) for k in ("ok", "gold", "silver", "qty", "message")}
        if result.get("ok"):
            data["status"] = "confirmed"
        elif result.get("not_submitted"):
            data["status"] = "not_submitted"
        self._save(data)


class SpawnWitness:
    """Share real server cooldown observations across independent runners.

    Each hero owns one small file. A missed short closed period can be
    recovered from a peer's observation; wall-clock passage alone never unlocks.
    """
    def __init__(self, root: Path, account: str, peers: list[str]):
        self.root, self.account, self.peers = root, account, peers
        self.remote = os.environ.get("GITHUB_ACTIONS") == "true"

    def _read(self, account: str, name: str) -> tuple[dict, str | None]:
        if not self.remote:
            path = self.root / "state" / account / name
            return (json.loads(path.read_text(encoding="utf8")) if path.exists() else {}, None)
        repo = os.environ["GITHUB_REPOSITORY"]
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("spawn witness requires GitHub token")
        url = f"https://api.github.com/repos/{repo}/contents/state/{account}/{name}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}, None
            raise
        return json.loads(base64.b64decode(data["content"])), data["sha"]

    def publish(self, observed_at: float, reopen_at: float) -> None:
        value = {"account": self.account, "closed_observed_at": observed_at, "reopen_at": reopen_at,
                 "source": "server closed cave and readable countdown"}
        if not self.remote:
            atomic_json(self.root / "state" / self.account / "dragon-spawn.json", value)
            return
        _, sha = self._read(self.account, "dragon-spawn.json")
        body = {"message": f"state({self.account}): observed dragon cooldown",
                "content": base64.b64encode(json.dumps(value).encode()).decode()}
        if sha:
            body["sha"] = sha
        repo = os.environ["GITHUB_REPOSITORY"]
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/contents/state/{self.account}/dragon-spawn.json",
            method="PUT", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            json.load(response)

    def reopened_since(self, attempt_start: float, now: float) -> dict | None:
        if not attempt_start:
            return None
        for peer in self.peers:
            try:
                data, _ = self._read(peer, "dragon-spawn.json")
                if data:
                    closed, reopen = data.get("closed_observed_at"), data.get("reopen_at")
                    if (type(closed) in (int, float) and type(reopen) in (int, float)
                            and attempt_start < closed <= reopen <= now):
                        return {"account": peer, "closed_observed_at": closed, "reopen_at": reopen}
                else:
                    # Migration: old agents already persisted the server-derived
                    # reopen time in runtime, but only committed at session end.
                    old, _ = self._read(peer, "runtime.json")
                    reopen = old.get("raid_reopen_at")
                    if type(reopen) in (int, float) and attempt_start + 60 < reopen <= now:
                        return {"account": peer, "reopen_at": reopen, "source": "persisted server cooldown"}
            except Exception:
                continue  # unknown peer state never grants a start
        return None
