
from replays import ReplayManager
from events import EventQueue
from typing import Optional
from redis import Redis
from osu import Game

import argparse
import logging
import session

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] - <%(name)s> %(levelname)s: %(message)s"
)

def load_config() -> Optional[dict]:
    parser = argparse.ArgumentParser(
        prog="osu!recorder", description="Spectate and record replay files."
    )

    parser.add_argument(
        "<username>",
        help="Your bancho username"
    )
    parser.add_argument(
        "<password>",
        help="Your bancho password"
    )
    parser.add_argument(
        '--server',
        default='ppy.sh',
        help='Specify a private server to use'
    )
    parser.add_argument(
        '--redis-host',
        default='localhost',
        help='Specify the Redis host'
    )
    parser.add_argument(
        '--redis-port',
        default=6379,
        help='Specify the Redis port'
    )
    parser.add_argument(
        '--redis-password',
        default=None,
        help='Specify the Redis password'
    )
    parser.add_argument(
        '--redis-db',
        default=0,
        help='Specify the Redis database'
    )

    args = parser.parse_args()
    dict = args.__dict__

    return {
        "username": dict["<username>"],
        "password": dict["<password>"],
        "server": dict["server"],
        "redis": {
            "host": dict["redis_host"],
            "port": dict["redis_port"],
            "password": dict["redis_password"],
            "db": dict["redis_db"]
        }
    }

def main():
    session.config = load_config()

    session.game = Game(
        session.config["username"],
        session.config["password"],
        server=session.config["server"],
        tournament=True,
        disable_chat_logging=True
    )

    session.redis = Redis(
        host=session.config["redis"]["host"],
        port=session.config["redis"]["port"],
        password=session.config["redis"]["password"],
        db=session.config["redis"]["db"]
    )

    session.queue = EventQueue(
        "spectator",
        session.redis
    )

    session.manager = ReplayManager(session.game)
    session.logger.info("Loading tasks...")

    import tasks

    session.game.run()

    if session.manager.spectating:
        session.redis.lrem(
            "spectating", 1,
            str(session.manager.spectating.id)
        )

if __name__ == "__main__":
    main()
