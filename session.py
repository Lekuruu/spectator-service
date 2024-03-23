
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from replays import ReplayManager
    from events import EventQueue
    from redis import Redis
    from osu import Game

import logging

config: Optional[dict] = None
game: Optional["Game"] = None
redis: Optional["Redis"] = None
queue: Optional["EventQueue"] = None
manager: Optional["ReplayManager"] = None

logger = logging.getLogger("spectator")
