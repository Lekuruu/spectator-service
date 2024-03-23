
from osu.bancho.constants import ServerPackets, StatusAction
from osu.objects import Player
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

@session.game.events.register(ServerPackets.USER_LOGOUT)
def user_logout(player: Player):
    session.redis.delete(f"stats:{player.id}")
    session.redis.lrem("spectating", 1, str(player.id))

@session.game.events.register(ServerPackets.USER_STATS)
def stats_update(player: Player):
    if not player:
        return

    session.redis.set(
        f"player:{player.id}",
        json.dumps({
            "id": player.id,
            "name": player.name,
            "country": player.country_code,
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
        })
    )

    if not session.manager.spectating:
        return

    if player != session.manager.spectating:
        return

    if player.status.action == StatusAction.Afk:
        session.logger.info(f"{player} is {player.status}")
        session.game.bancho.stop_spectating()
        session.redis.lrem("spectating", 1, str(player.id))
        return

    if player.status.action in (StatusAction.Playing, StatusAction.Multiplaying):
        session.manager.current_status = copy(player.status)

@session.game.tasks.register(seconds=10, loop=True)
def spectator_controller():
    if session.manager.spectating:
        # We are already spectating someone
        if not session.game.bancho.connected:
            # The client disconnected from bancho
            session.redis.lrem(
                "spectating", 1,
                str(session.manager.spectating.id)
            )
            session.game.bancho.spectating = None
            return

        session.manager.spectating.request_stats()
        return

    # Get spectating list
    spectating = {
        int(id)
        for id in session.redis.lrange("spectating", 0, -1)
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
    session.redis.lpush("spectating", str(player.id))
    session.logger.info(f"Spectating {player}")

    session.game.bancho.start_spectating(player)
    session.logger.info(f"{player} is {player.status}")

    if player.status.action == StatusAction.Afk:
        # Player is afk, choose another player
        session.redis.lrem("spectating", 1, str(player.id))
        session.game.bancho.stop_spectating()
