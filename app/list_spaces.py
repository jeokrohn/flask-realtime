from .interactive import Token
import logging
import sys
import webexteamssdk
from datetime import timedelta
import asyncio
import aiohttp

from typing import Optional, List, Callable, AsyncIterator, Tuple

log = logging.getLogger(__name__)


class WebexAsync:
    BASE = 'https://api.ciscospark.com/v1'

    def __init__(self, access_token: str):
        self.access_token = access_token

    @property
    def bearer(self):
        return f'Bearer {self.access_token}'

    async def request(self, method: str, url, **kwargs):
        headers = kwargs.pop('headers', dict())
        headers['Authorization'] = self.bearer
        client_connector_errors = 0
        while True:
            async with aiohttp.ClientSession() as session:
                try:
                    r = await session.request(method, url, ssl=False, headers=headers, **kwargs)
                except aiohttp.ClientConnectorError:
                    client_connector_errors += 1
                    if client_connector_errors < 5:
                        log.warning(f'{method} {url} got ClientConnectorError ({client_connector_errors}). Retry..')
                        continue
                    raise
                if r.status == 429:
                    retry_after = max(1, int(r.headers.get('Retry-After', 5)))
                    log.warning(f'{method} {url} got 429: waiting for {retry_after} seconds')
                    await asyncio.sleep(retry_after)
                    continue
                r.raise_for_status()
                data = await r.json()
            break
        return r, data

    async def get(self, url, **kwargs):
        _, data = await self.request('GET', url, kwargs=kwargs)
        return data

    @staticmethod
    def endpoint(base: str):
        return f'{WebexAsync.BASE}/{base}'

    async def pagination(self, url, factory, params):
        while url:
            log.debug(f'{self}.pagination: getting {url}')
            r, data = await self.request('GET', url, params=params)
            # parameters are only needed for the 1st call. The next url has parameters encoded
            params = dict()
            # try to get the next page (if present)
            try:
                url = str(r.links['next']['url'])
            except KeyError:
                url = None
            # return all items
            for i in data['items']:
                r = factory(i)
                yield r
            # for
        # while
        return

    def list_spaces(self, p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Room]:
        url = WebexAsync.endpoint('rooms')
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        r = self.pagination(url=url, factory=webexteamssdk.Room, params=params)
        return r

    def list_messages(self, p_roomId: Optional[str] = None,
                      p_mentionedPeople:Optional[List[str]]=None,
                      p_before:Optional[str]=None,
                      p_beforeMessage:Optional[str]=None,
                      p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Message]:
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        url = WebexAsync.endpoint('messages')
        return self.pagination(url, webexteamssdk.Message, params)

    def __repr__(self):
        return f'WebexAsync'


class MyException(Exception):
    pass


async def space_stats(api: WebexAsync,
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
    api = WebexAsync(access_token)
    # async for space in api.list_spaces(max=100):
    tasks = []
    c = 0
    async for space in api.list_spaces(p_max=100):
        if not running():
            break
        c += 1
        if c == 165000:
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
