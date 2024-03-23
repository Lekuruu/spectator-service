
from osu.bancho.constants import ServerPackets, StatusAction
from osu.objects import Player, Channel
from typing import Union
from copy import copy

import session
import json

@session.game.events.register(ServerPackets.SPECTATE_FRAMES)
def frames(action, frames, score_frame, extra):
    session.manager.handle_frames(
        frames,
        action,
        extra,
        score_frame
    )

@session.game.events.register(ServerPackets.SEND_MESSAGE)
def on_message(sender: Player, message: str, target: Union[Player, Channel]):
    if target.name != '#spectator':
        return

    session.queue.submit(
        "spectator_message",
        sender=sender.name,
        message=message,
        target=session.manager.spectating.name
    )

@session.game.events.register(ServerPackets.USER_LOGOUT)
def user_logout(player: Player):
    session.redis.delete(f"stats:{player.id}")
    session.redis.lrem(f"spectating:{session.game.server}", 1, player.id)

@session.game.events.register(ServerPackets.USER_STATS)
def stats_update(player: Player):
    if not player:
        return

    user_dict = {
        "id": player.id,
        "name": player.name,
        "country": player.country,
        "server": session.game.server,
        "stats": {
            "rscore": player.rscore,
            "tscore": player.tscore,
            "acc": player.acc,
            "pp": player.pp,
            "playcount": player.playcount,
            "rank": player.rank,
        },
        "status": {
            "action": player.status.action.value,
            "text": player.status.text,
            "checksum": player.status.checksum,
            "mods": player.status.mods.value,
            "mode": player.status.mode.value,
            "beatmap_id": player.status.beatmap_id,
        }
    }

    session.redis.set(
        f"players:{session.game.server}:{player.id}",
        json.dumps(user_dict)
    )

    session.queue.submit(
        "stats_update",
        player.id,
        session.game.server
    )

    if not session.manager.spectating:
        return

    if player != session.manager.spectating:
        return

    if player.status.action == StatusAction.Afk:
        session.logger.info(f"{player} is {player.status}")
        session.game.bancho.stop_spectating()
        session.redis.lrem(f"spectating:{session.game.server}", 1, player.id)
        return

    if player.status.action in (StatusAction.Playing, StatusAction.Multiplaying):
        session.manager.current_status = copy(player.status)

@session.game.tasks.register()
def subscribe():
    """Start listening to the api pubsub channel"""
    session.api_queue.channel.subscribe("api")
    session.api_queue.logger.info('Listening to pubsub channel...')

@session.api_queue.register("stats_request")
def stats_request(server: str, player_id: int):
    """Got stats request from api queue"""
    if server != session.game.server:
        return

    session.game.bancho.request_stats([player_id])

@session.game.tasks.register(seconds=1, loop=True)
def event_listener():
    if not (message := session.api_queue.channel.get_message()):
        return

    if message["data"] == 1:
        return

    name, args, kwargs = eval(message["data"])

    if name not in session.api_queue.events:
        return

    session.api_queue.logger.debug(
        f'Got event for "{name}" with {args} and {kwargs}'
    )

    session.api_queue.events[name](*args, **kwargs)

@session.game.tasks.register(seconds=10, loop=True)
def spectator_controller():
    """Select a player to spectate, and update their stats"""
    if not session.manager.spectating:
        # Get spectating list
        spectating = {
            int(id) for id in session.redis.lrange(
                f"spectating:{session.game.server}", 0, -1
            )
        }

        # Get highest ranked player available
        players = [
            p for p in session.game.bancho.players
            if (p.rank != 0 and p.rank < 1000) and
               (p.id not in spectating) and
               (p.status.action != StatusAction.Afk)
        ]
        players.sort(key=lambda x: x.rank)
        player = players[0]

        # Add player to spectating list
        session.redis.lpush(f"spectating:{session.game.server}", player.id)
        session.logger.info(f"Spectating {player}")

        session.game.bancho.start_spectating(player)
        session.logger.info(f"{player} is {player.status}")

        if player.status.action == StatusAction.Afk:
            # Player is afk, choose another player
            session.redis.lrem(f"spectating:{session.game.server}", 1, player.id)
            session.game.bancho.stop_spectating()

    else:
        # We are already spectating someone
        if not session.game.bancho.connected:
            # The client disconnected from bancho
            session.redis.lrem(
                f"spectating:{session.game.server}", 1,
                session.manager.spectating.id
            )
            session.game.bancho.spectating = None
            return

        session.manager.spectating.request_stats()
