import uuid
import time
import random
import webexteamssdk
import logging
import asyncio
import aiohttp
import sys
from datetime import timedelta
from typing import Callable, Optional, List

from .webexteamsasyncapi import WebexTeamsAsyncAPI
from .interactive import Token

log = logging.getLogger(__name__)


class MyException(Exception):
    pass


PEOPLE_IN_EACH_SPACE = 100
ONLY_GET_1ST_FEW = 2000
SPACE_PREFIX = 'zz auto generated'

async def add_membership(api: WebexTeamsAsyncAPI, space_id: str, member: webexteamssdk.Person) -> None:
    await api.create_membership(p_roomId=space_id, p_personId=member.id)
    log.debug('Added {} to space'.format(member.displayName))
    await api.create_message(p_roomId=space_id, p_text=f' New message after added {member.displayName} to space')
    log.debug(f'Added {member.displayName} to space and posted message')
    return


async def create_memberships(api: WebexTeamsAsyncAPI, space_id: str, members: List[webexteamssdk.Person]) -> None:
    log.info('Adding members to space...')
    tasks = [add_membership(api, space_id=space_id, member=m) for m in members]
    try:
        await asyncio.gather(*tasks)
    except aiohttp.ClientResponseError as e:
        log.error('ClientResponseError headers {}'.format(e.headers))
        raise
    except:
        raise
    return


async def clean_up_spaces(api: WebexTeamsAsyncAPI) -> None:
    """
    Delete all auto generated spaces
    :param api:
    :return:
    """
    spaces = []
    async for space in api.list_spaces():
        spaces.append(space)

    log.info(f'Found {len(spaces)} spaces')
    spaces = [s for s in spaces if s.title.startswith(SPACE_PREFIX)]
    log.info(f'Found {len(spaces)} auto generated spaces')
    log.info(f'Deleting {len(spaces)} spaces')

    async def delete_space(space: webexteamssdk.Room) -> None:
        await api.delete_space(p_roomId=space.id)
        log.info(f'deleted space \'{space.title}\'')

    await asyncio.gather(*[delete_space(s) for s in spaces])


async def as_create_spaces(access_token: str, running: Callable[[], bool], clean_up: bool):
    api = WebexTeamsAsyncAPI(access_token)

    if clean_up:
        await clean_up_spaces(api)
        return

    # who am I?
    me = await api.me()
    me_id = me.id

    # get all people
    log.info('Getting list of people...')
    people = []
    i = 0
    async for pp in api.list_people(p_max=100):
        people.append(pp)
        i += 1
        if i >= ONLY_GET_1ST_FEW - 1:
            break

    # we don't want to create spaces with myself
    people = [p for p in people if p.id != me_id]

    log.info('Found {} people: {}'.format(len(people), ', '.join((p.displayName for p in people))))
    while running():
        # create random rooms with some people
        random.shuffle(people)
        title = f'{SPACE_PREFIX} {str(uuid.uuid4())}'
        log.info('Creating space: {}'.format(title))
        r = await api.create_space(p_title=title)
        space_id = r.id

        await create_memberships(api, space_id=space_id, members=(p for p in people[:PEOPLE_IN_EACH_SPACE]))
        log.info('Created memberships and messages. Sleeping...')

        await asyncio.sleep(3)


def create_spaces(sid: str, running: Callable[[], bool], user_id: str, clean_up: Optional[bool] = False):
    # add a log.handler to stdout; log.output will be sent to the client via websocket
    format = logging.Formatter(fmt='{levelname:8s} create_spaces: {message}', style='{')
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.DEBUG)
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

        # run asynchronous task
        asyncio.run(as_create_spaces(access_token.access_token, running, clean_up))
        return

    except MyException:
        pass
    finally:
        # cleanup
        log.debug('cleaning up...')
        log.removeHandler(handler)
        print('-------------- Done ----------')
