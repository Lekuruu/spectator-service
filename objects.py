
from osu.objects import ScoreFrame, Player, Status
from osu.bancho.constants import Mods, Mode

from datetime import datetime
from typing import List

import hashlib
import session
import json

class Score:
    def __init__(
        self,
        score_frames: List[ScoreFrame],
        player: Player,
        status: Status,
        passed: bool,
    ) -> None:
        self.player = player
        self.status = status
        self.passed = passed
        self.frames = score_frames
        self.data = self.frames[-1]

    @property
    def checksum(self) -> str:
        frame = self.frames[-1]
        return hashlib.md5(
            f"{frame.max_combo}osu{self.player.name}{self.status.checksum}{frame.total_score}{self.grade}".encode()
        ).hexdigest()

    @property
    def accuracy(self) -> float:
        if self.total_hits <= 0:
            return 0.0

        if self.mode == Mode.Osu:
            return (
                100.0 * ((self.data.c300 * 300) + (self.data.c100 * 100) + (self.data.c50 * 50))
                / (self.total_hits * 300)
            )

        elif self.mode == Mode.Taiko:
            return (
                100.0 * ((self.data.c100 * 0.5) + self.data.c300) / self.total_hits
            )

        elif self.mode == Mode.CatchTheBeat:
            return (
                100.0 * (self.data.c300 + self.data.c100 + self.data.c50) / self.total_hits
            )

        if Mods.ScoreV2 in self.mods:
            return (
                100.0 * (
                    (self.data.c50 * 50.0) +
                    (self.data.c100 * 100.0) +
                    (self.data.cKatu * 200.0) +
                    (self.data.c300 * 300.0) +
                    (self.data.cGeki * 305.0)
                )
                / (self.total_hits * 305.0)
            )

        return (
            100.0 * (
                (self.data.c50 * 50.0) +
                (self.data.c100 * 100.0) +
                (self.data.cKatu * 200.0) +
                ((self.data.c300 + self.data.cGeki) * 300.0)
            )
            / (self.total_hits * 300.0)
        )

    @property
    def total_hits(self) -> int:
        if self.mode == Mode.Osu:
            return self.data.c50 + self.data.c100 + self.data.c300 + self.data.cMiss

        elif self.mode == Mode.Taiko:
            return self.data.c100 + self.data.c300 + self.data.cMiss

        elif self.mode == Mode.CatchTheBeat:
            return self.data.c50 + self.data.c100 + self.data.c300 + self.data.cKatu + self.data.cMiss

        return self.data.c50 + self.data.c100 + self.data.c300 + self.data.cGeki + self.data.cKatu + self.data.cMiss

    @property
    def grade(self) -> str:
        num = self.data.c300 / self.data.total_hits
        num2 = self.data.c50 / self.data.total_hits

        if not self.passed:
            return "F"

        if num == 1.0:
            if Mods.Hidden in self.mods or Mods.Flashlight in self.mods:
                return "XH"
            return "X"

        if num > 0.9 and num2 <= 0.01 and self.data.cMiss == 0:
            if Mods.Hidden in self.mods or Mods.Flashlight in self.mods:
                return "SH"
            return "S"

        else:
            if num > 0.8 and self.data.cMiss == 0 or num > 0.9:
                return "A"

            if num > 0.7 and self.data.cMiss == 0 or num > 0.8:
                return "B"

            if num > 0.6:
                return "C"

        return "D"

    @property
    def mods(self) -> List[Mods]:
        return self.status.mods

    @property
    def mode(self) -> Mode:
        return self.status.mode

    @property
    def filename(self) -> str:
        name = f'{self.player.name} - {self.status.text} ({datetime.now().strftime("%Y-%m-%d %H-%M-%S")}) {self.status.mode.name}'

        # Remove invalid characters
        for invalid_char in [".", "..", "<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            name = name.replace(invalid_char, "")

        return name + ".osr"

    @property
    def filename_safe(self) -> str:
        return f"replay-{self.status.mode.name.lower()}_{self.checksum}.osr"

    @property
    def hp_graph(self) -> str:
        return ",".join(
            [
                f"{frame.time}|{min(1.0, frame.current_hp / 200)}"
                for frame in self.frames
            ]
        )

    def submit(self, replay_file: bytes) -> None:
        """Submit the score data to the queue, and store the replay file in cache"""
        session.queue.submit(
            "score",
            checksum=self.checksum,
            server=session.game.server,
            player=json.dumps({
                "id": self.player.id,
                "name": self.player.name,
                "country": self.player.country,
                "status": {
                    "action": self.status.action.value,
                    "text": self.status.text,
                    "checksum": self.status.checksum,
                    "mods": self.status.mods.value,
                    "mode": self.status.mode.value,
                    "beatmap_id": self.status.beatmap_id
                },
                "stats": {
                    "rscore": self.player.rscore,
                    "tscore": self.player.tscore,
                    "acc": self.player.acc,
                    "pp": self.player.pp,
                    "playcount": self.player.playcount,
                    "rank": self.player.rank
                }
            }),
            score=json.dumps({
                "c300": self.data.c300,
                "c100": self.data.c100,
                "c50": self.data.c50,
                "cGeki": self.data.cGeki,
                "cKatu": self.data.cKatu,
                "cMiss": self.data.cMiss,
                "total_score": self.data.total_score,
                "total_hits": self.data.total_hits,
                "max_combo": self.data.max_combo,
                "perfect": self.data.perfect,
                "mods": self.mods.value,
                "accuracy": self.accuracy,
                "grade": self.grade,
                "passed": self.passed,
                "length": round(len(self.frames) / 30),
                "filename": self.filename,
                "filename_safe": self.filename_safe
            })
        )

        session.redis.set(
            f'replays:{self.checksum}',
            replay_file,
            ex=60 * 60 * 96
        )
