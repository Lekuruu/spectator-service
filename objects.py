
from osu.objects import ScoreFrame, Player, Status
from osu.bancho.constants import Mods

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
        if self.data.total_hits <= 0:
            return 1.0

        return (
            (self.data.c50 * 50 + self.data.c100 * 100 + self.data.c300 * 300)
            / self.data.total_hits * 100
        )

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
                "country": self.player.country_code,
                "status": {
                    "action": self.player.status.action.value,
                    "text": self.player.status.text,
                    "checksum": self.player.status.checksum,
                    "mods": self.player.status.mods.value,
                    "mode": self.player.status.mode.value,
                    "beatmap_id": self.player.status.beatmap_id
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
                "max_combo": self.data.max_combo,
                "perfect": self.data.perfect,
                "mods": self.mods.value,
                "accuracy": self.accuracy,
                "grade": self.grade,
                "passed": self.passed,
                "filename": self.filename,
                "filename_safe": self.filename_safe
            })
        )

        session.redis.set(
            f'replays:{self.checksum}',
            replay_file,
            ex=60 * 60 * 24
        )
