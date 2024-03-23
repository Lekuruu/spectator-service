
# Spectator Service

This is part of a project called "watchtower", which provides an API for user statistics, and records replays of top players, by spectating them.

The goal of the spectator service is to find a player to spectate, update their stats in the cache, and submit replays of them to a queue.

## Setup

If you want to see this project in action, you need:

- A user account with an active osu! supporter tag
- A [redis](https://redis.com/) server

After that install the requirements:

```shell
python -m pip install -r requirements.txt
```

And finally, run the program:

```shell
python main.py <username> <password>
```

Here are some optional arguments:

```shell
python main.py [--server SERVER] [--redis-host REDIS_HOST] [--redis-port REDIS_PORT] [--redis-password REDIS_PASSWORD] [--redis-db REDIS_DB] <username> <password>
```