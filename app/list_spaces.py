from .interactive import Token
import logging
import sys
import webexteamssdk
from datetime import timedelta
import asyncio

from typing import Optional, List, Callable, AsyncIterator, Tuple
from .webexteamsasyncapi import WebexTeamsAsyncAPI

log = logging.getLogger(__name__)

class MyException(Exception):
    pass

async def space_stats(api: WebexTeamsAsyncAPI,
                      space: webexteamssdk.Room,
                      running: Callable[[], bool]) -> Tuple[webexteamssdk.Room, dict]:
    # try to count all messages in the space
    message_count = 0
    earliest = '9'
    latest = '0'
    async for message in api.list_messages(p_roomId=space.id, p_max=500):
        message_count += 1
        if not running():
            return space, None
        earliest = min(earliest, str(message.created))
        latest = max(latest, str(message.created))
    result = dict(
        message_count=message_count,
        earliest=earliest,
        latest=latest
    )
    return space, result


async def as_list_spaces(access_token: str, running: Callable[[], bool]):
    api = WebexTeamsAsyncAPI(access_token)
    # async for space in api.list_spaces(max=100):
    tasks = []
    async for space in api.list_spaces(p_max=100):
        if not running():
            break
        print(f'{space.title}, {space.lastActivity}')
        # also schedule task to get space stats
        tasks.append(asyncio.create_task(space_stats(api, space, running)))

    try:
        if not running():
            raise MyException
        for task_done in asyncio.as_completed(tasks):
            if not running():
                raise MyException
            space, data = await task_done
            space: webexteamssdk.Room
            print(f'space stats for {space.title} done: {data}')

    except MyException:
        pass
    finally:
        for task in tasks:
            task.cancel()
    return


def list_spaces(user_id: str, sid: str, running: Callable[[], bool]):
    format = logging.Formatter(fmt='{levelname:8s} list_spaces: {message}', style='{')
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.ERROR)
    handler.setFormatter(format)
    log.addHandler(handler)

    try:
        log.debug(f'user_id={user_id}, sid={sid}')

        # First get an access token
        log.debug(f'trying to get access token')
        access_token = Token.get_token(user_id=user_id)
        if access_token is None:
            log.error(f'Failed to get access token for {user_id}')
            raise MyException

        lifetime_remaining = timedelta(seconds=access_token.lifetime_remaining_seconds)
        log.debug(f'access token still valid for {lifetime_remaining}')

        # need to make sure that the access token is good for another 10 minutes
        if lifetime_remaining.total_seconds() < 600:
            access_token.refresh()
            log.debug(
                f'had to refresh access token. New lifetime: '
                f'{timedelta(seconds=access_token.lifetime_remaining_seconds)}')

        asyncio.run(as_list_spaces(access_token.access_token, running))
        return

    except MyException:
        pass
    finally:
        # cleanup
        log.debug('cleaning up...')
        log.removeHandler(handler)
        print('-------------- Done ----------')
