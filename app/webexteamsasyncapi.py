from typing import Optional, List, AsyncIterator, Tuple

import webexteamssdk
from webexteamssdk.models.immutable import ImmutableData
from logging import getLogger
import asyncio
import aiohttp

log = getLogger(__name__)


class MeetingInfo:
    __slots__ = ['roomId', 'meetingLink', 'sipAddress', 'meetingNumber', 'callInTollFreeNumber', 'callInTollNumber']

    def __init__(self, roomId, meetingLink, sipAddress, meetingNumber, callInTollFreeNumber, callInTollNumber):
        self.roomId = roomId
        self.meetingLink = meetingLink
        self.sipAddress = sipAddress
        self.meetingNumber = meetingNumber
        self.callInTollFreeNumber = callInTollFreeNumber
        self.callInTollNumber = callInTollNumber


class WebexTeamsAsyncAPI:
    BASE = 'https://api.ciscospark.com/v1'
    RETRIES_ON_CLIENT_CONNECTOR_ERRORS = 3
    CONCURRENT_REQUESTS = 40
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    def __init__(self, access_token: str):
        self.access_token = access_token

    @property
    def bearer(self):
        return f'Bearer {self.access_token}'

    async def request(self, method: str, url: str, **kwargs) -> Tuple[aiohttp.ClientResponse, dict]:
        headers = kwargs.pop('headers', dict())
        headers['Authorization'] = self.bearer
        client_connector_errors = 0
        while True:
            # get semaphore to limit the number of concurrent requests
            async with WebexTeamsAsyncAPI.semaphore:
                async with aiohttp.ClientSession() as session:
                    try:
                        r = await session.request(method, url, ssl=False, headers=headers, **kwargs)
                    except aiohttp.ClientConnectorError:
                        # retry on spurious sometimes ClientConnectorErrors
                        client_connector_errors += 1
                        if client_connector_errors < WebexTeamsAsyncAPI.RETRIES_ON_CLIENT_CONNECTOR_ERRORS:
                            log.warning(f'got ClientConnectorError: retry ({client_connector_errors}/'
                                        f'{WebexTeamsAsyncAPI.RETRIES_ON_CLIENT_CONNECTOR_ERRORS}), '
                                        f'{method} {url} ')
                            continue
                        raise
                    if r.status != 429:
                        r.raise_for_status()
                        data = await r.json()
                        break
                # async with aiohttp....
            # async with WebexTeamsAsyncAPI.semaphore
            # on 429 we need to wait some time and then retry
            # waiting has to happen outside of the context protected by the semaphore: we don't want to block
            # other tasks while we are waiting
            retry_after = max(1, int(r.headers.get('Retry-After', 5)))
            log.warning(f'got 429: waiting for {retry_after} seconds, {method} {url} ')
            await asyncio.sleep(retry_after)
        # while True
        return r, data

    async def get(self, url: str, **kwargs) -> dict:
        _, data = await self.request('GET', url, kwargs=kwargs)
        return data

    async def put(self, url: str, data=None, json=None, **kwargs) -> dict:
        _, data = await self.request('PUT', url, data=data, json=json, kwargs=kwargs)
        return data

    async def post(self, url: str, data=None, json=None, **kwargs) -> dict:
        _, data = await self.request('POST', url, data=data, json=json, kwargs=kwargs)
        return data

    async def delete(self, url: str, **kwargs) -> dict:
        _, data = await self.request('DELETE', url, kwargs=kwargs)
        return data

    async def update(self, url: str, **kwargs) -> dict:
        _, data = await self.request('GET', url, kwargs=kwargs)
        return data

    @staticmethod
    def endpoint(base: str) -> str:
        return f'{WebexTeamsAsyncAPI.BASE}/{base}'

    async def pagination(self, url: str, factory, params: dict) -> AsyncIterator[ImmutableData]:
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

    ######################## Spaces

    def list_spaces(self, p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Room]:
        url = WebexTeamsAsyncAPI.endpoint('rooms')
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        r = self.pagination(url=url, factory=webexteamssdk.Room, params=params)
        return r

    async def create_space(self, p_title: str, p_teamid: Optional[str] = None) -> webexteamssdk.Room:
        url = WebexTeamsAsyncAPI.endpoint('rooms')
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        space = await self.post(url, json=params)
        return webexteamssdk.Room(space)

    async def space_details(self, p_roomId: str) -> webexteamssdk.Room:
        url = f'{WebexTeamsAsyncAPI.endpoint("rooms")}/{p_roomId}'
        space = await self.get(url)
        return webexteamssdk.Room(space)

    async def space_meeting_details(self, p_roomId: str) -> MeetingInfo:
        url = f'{WebexTeamsAsyncAPI.endpoint("rooms")}/{p_roomId}/meetinginfo'
        data = await self.get(url)
        return MeetingInfo(**data)

    async def update_space(self, p_roomId:str, p_title:str):
        url = f'{WebexTeamsAsyncAPI.endpoint("rooms")}/{p_roomId}'
        data = {'title':p_title}
        data = await self.put(url, data=data)
        return webexteamssdk.Room(data)

    async def delete_space(self, p_roomId: str) -> None:
        url = f'{WebexTeamsAsyncAPI.endpoint("rooms")}/{p_roomId}'
        await self.delete(url)
        return

    # memberships



    def list_messages(self, p_roomId: Optional[str] = None,
                      p_mentionedPeople: Optional[List[str]] = None,
                      p_before: Optional[str] = None,
                      p_beforeMessage: Optional[str] = None,
                      p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Message]:
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        url = WebexTeamsAsyncAPI.endpoint('messages')
        return self.pagination(url, webexteamssdk.Message, params)

    def __repr__(self):
        return f'WebexTeamsAsyncAPI'
