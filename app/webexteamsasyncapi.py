"""
Basic asynchronous Webex Teams API helper.
"""
from logging import getLogger
import asyncio
from dataclasses import dataclass
from typing import Optional, List, AsyncIterator, Tuple, Dict, Callable

import webexteamssdk
from webexteamssdk.models.immutable import ImmutableData
import aiohttp

log = getLogger(__name__)


@dataclass
class MeetingInfo:
    """
    Return value of space_meeting_details() call
    """
    __slots__ = ['roomId', 'meetingLink', 'sipAddress', 'meetingNumber', 'callInTollFreeNumber', 'callInTollNumber']

    roomId: str
    meetingLink: str
    sipAddress: str
    meetingNumber: str
    callInTollFreeNumber: str
    callInTollNumber: str


class WebexTeamsAsyncAPI:
    """
    Basis asynchronous Webex Teams API handler
    """
    BASE = 'https://api.ciscospark.com/v1'
    RETRIES_ON_CLIENT_CONNECTOR_ERRORS = 3
    RETRIES_ON_502 = 3
    CONCURRENT_REQUESTS = 100
    MAX_WAIT_ON_429 = 20

    def __init__(self, access_token: str, base=BASE, concurrent_requests=CONCURRENT_REQUESTS):
        self.access_token = access_token
        # semaphore to limit number of concurrent requests against the Webex Teams API
        self.semaphore = asyncio.Semaphore(concurrent_requests)
        self.base = base

    @property
    def bearer(self):
        """
        Bearer token for Authorization header
        :return:
        """
        return f'Bearer {self.access_token}'

    @property
    def auth_header(self) -> Dict[str, str]:
        """
        Authorization header based on the access token of the API
        :return:
        """
        return {'Authorization': self.bearer}

    async def request(self, method: str, url: str, **kwargs) -> Tuple[aiohttp.ClientResponse, dict]:
        """
        Execute one API request. Return the response and the JSON body as dict. Handles 429 and
        spurious ClientConnectorErrors
        :param method: GET, POST, PUT, ...
        :param url: url to access
        :param kwargs: additional arguments for aiohttp.request
        :return: tuple of response object and JSON body as dict
        """
        headers = kwargs.pop('headers', dict())
        headers.update(self.auth_header)
        client_connector_errors = 0
        status_502 = 0
        while True:
            # get semaphore to limit the number of concurrent requests
            async with self.semaphore:
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
                    if r.status == 502:
                        # sometimes requests simply fail... Retry
                        status_502 += 1
                        if status_502 < WebexTeamsAsyncAPI.RETRIES_ON_502:
                            log.warning(f'got 502: retry ({status_502}/'
                                        f'{WebexTeamsAsyncAPI.RETRIES_ON_502}), '
                                        f'{method} {url} ')
                            continue
                    if r.status != 429:
                        r.raise_for_status()
                        if r.status == 204:
                            data = dict()
                        else:
                            data = await r.json()
                        break
                # async with aiohttp....
            # async with WebexTeamsAsyncAPI.semaphore
            # on 429 we need to wait some time and then retry
            # waiting has to happen outside of the context protected by the semaphore: we don't want to block
            # other tasks while we are waiting
            retry_after = int(r.headers.get('Retry-After', '5')) or 1
            # never wait more than the defined maximum
            retry_after = min(retry_after, WebexTeamsAsyncAPI.MAX_WAIT_ON_429)
            log.warning(f'got 429: waiting for {retry_after} seconds, {method} {url} ')
            await asyncio.sleep(retry_after)
        # while True
        return r, data

    async def get(self, url: str, **kwargs) -> dict:
        _, data = await self.request('GET', url, **kwargs)
        return data

    async def put(self, url: str, data=None, json=None, **kwargs) -> dict:
        _, data = await self.request('PUT', url, data=data, json=json, **kwargs)
        return data

    async def post(self, url: str, data=None, json=None, **kwargs) -> dict:
        _, data = await self.request('POST', url, data=data, json=json, **kwargs)
        return data

    async def delete(self, url: str, **kwargs) -> dict:
        _, data = await self.request('DELETE', url, **kwargs)
        return data

    async def update(self, url: str, **kwargs) -> dict:
        _, data = await self.request('GET', url, **kwargs)
        return data

    def endpoint(self, domain: str) -> str:
        """
        get a full endpoint for a given domain
        :param domain: rooms, devices, people, ...
        :return: endpoint URL
        """
        return f'{self.base}/{domain}'

    async def pagination(self, url: str, params: dict,
                         factory: Callable[[Dict], ImmutableData]) -> AsyncIterator[ImmutableData]:
        """
        Async iterator handling RFC5988 pagination of list requests
        :param url: start url for 1st GET
        :param params: params to be passed to initial GET; subsequent GETs are parameterized through next URL
        :param factory: factory method to create instances of returned objects
        :return: object instances created by factory
        """
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

    # Spaces
    @property
    def rooms_endpoint(self):
        return self.endpoint('rooms')

    def list_spaces(self, p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Room]:
        url = self.rooms_endpoint
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        return self.pagination(url=url, params=params, factory=webexteamssdk.Room)

    async def create_space(self, p_title: str, p_teamId: Optional[str] = None) -> webexteamssdk.Room:
        url = self.rooms_endpoint
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        space = await self.post(url, json=params)
        return webexteamssdk.Room(space)

    async def space_details(self, p_roomId: str) -> webexteamssdk.Room:
        url = f'{self.rooms_endpoint}/{p_roomId}'
        space = await self.get(url)
        return webexteamssdk.Room(space)

    async def space_meeting_details(self, p_roomId: str) -> MeetingInfo:
        url = f'{self.rooms_endpoint}/{p_roomId}/meetinginfo'
        data = await self.get(url)
        return MeetingInfo(**data)

    async def update_space(self, p_roomId: str, p_title: str):
        url = f'{self.rooms_endpoint}/{p_roomId}'
        data = {'title': p_title}
        data = await self.put(url, json=data)
        return webexteamssdk.Room(data)

    async def delete_space(self, p_roomId: str) -> None:
        url = f'{self.rooms_endpoint}/{p_roomId}'
        await self.delete(url)
        return

    # memberships
    @property
    def membership_endpoint(self):
        return self.endpoint('memberships')

    def list_memberships(self, p_roomId: Optional[str] = None, p_personId: Optional[str] = None,
                         p_personEmail: Optional[str] = None,
                         p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Membership]:
        url = self.membership_endpoint
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        return self.pagination(url=url, params=params, factory=webexteamssdk.Membership)

    async def create_membership(self, p_roomId: str, p_personId: Optional[str] = None,
                                p_personEmail: Optional[str] = None,
                                p_isModerator: Optional[bool] = None) -> webexteamssdk.Membership:
        url = self.membership_endpoint
        data = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        r = await self.post(url=url, json=data)
        return webexteamssdk.Membership(r)

    async def membership_details(self, p_membershipId) -> webexteamssdk.Membership:
        url = f'{self.membership_endpoint}/{p_membershipId}'
        r = await self.get(url)
        return webexteamssdk.Membership(r)

    async def update_membership(self, p_membershipId: str, p_isModerator: bool) -> webexteamssdk.Membership:
        url = f'{self.membership_endpoint}/{p_membershipId}'
        r = await self.put(url, json={'isModerator': p_isModerator})
        return webexteamssdk.Membership(r)

    async def delete_membership(self, p_membershipId) -> None:
        url = f'{self.membership_endpoint}/{p_membershipId}'
        await self.delete(url)

    # person
    @property
    def people_endpoint(self):
        return self.endpoint('people')

    def list_people(self, p_email: Optional[str] = None, p_displayName: Optional[str] = None,
                    p_id: Optional[str] = None,
                    p_orgId: Optional[str] = None, p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Person]:
        url = self.people_endpoint
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        return self.pagination(url=url, params=params, factory=webexteamssdk.Person)

    async def create_person(self, p_emails: List[str], p_displayName: Optional[str] = None,
                            p_firstName: Optional[str] = None,
                            p_lastName: Optional[str] = None, p_avatar: Optional[str] = None,
                            p_orgId: Optional[str] = None,
                            p_roles: Optional[List[str]] = None,
                            p_licenses: Optional[List[str]] = None) -> webexteamssdk.Person:
        url = self.people_endpoint
        data = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        r = await self.post(url=url, json=data)
        return webexteamssdk.Person(r)

    async def people_details(self, p_personId) -> webexteamssdk.Person:
        url = f'{self.people_endpoint}/{p_personId}'
        r = await self.get(url)
        return webexteamssdk.Person(r)

    async def update_person(self, p_personId, p_emails: Optional[List[str]], p_displayName: Optional[str] = None,
                            p_firstName: Optional[str] = None,
                            p_lastName: Optional[str] = None, p_avatar: Optional[str] = None,
                            p_orgId: Optional[str] = None,
                            p_roles: Optional[List[str]] = None,
                            p_licenses: Optional[List[str]] = None) -> webexteamssdk.Membership:
        url = f'{self.people_endpoint}/{p_personId}'
        data = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and k != 'p_personId' and v is not None}
        r = await self.put(url, json=data)
        return webexteamssdk.Membership(r)

    async def delete_person(self, p_personId) -> None:
        url = f'{self.people_endpoint}/{p_personId}'
        await self.delete(url)

    async def me(self):
        url = f'{self.people_endpoint}/me'
        r = await self.get(url)
        return webexteamssdk.Person(r)

    # messages
    @property
    def messages_endpoint(self):
        return self.endpoint('messages')

    def list_messages(self, p_roomId: Optional[str] = None,
                      p_mentionedPeople: Optional[List[str]] = None,
                      p_before: Optional[str] = None,
                      p_beforeMessage: Optional[str] = None,
                      p_max: Optional[int] = None) -> AsyncIterator[webexteamssdk.Message]:
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        return self.pagination(url=self.messages_endpoint, params=params, factory=webexteamssdk.Message)

    def list_direct_messages(self, p_personId: Optional[str] = None,
                             p_personEmail: Optional[str] = None) -> AsyncIterator[webexteamssdk.Message]:
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        url = f'{self.messages_endpoint}/direct'
        return self.pagination(url=url, params=params, factory=webexteamssdk.Message)

    async def create_message(self, p_roomId: Optional[str] = None, p_toPersonId: Optional[str] = None,
                             p_toPersonEmail: Optional[str] = None, p_text: Optional[str] = None,
                             p_markdown: Optional[str] = None) -> webexteamssdk.Message:
        params = {k[2:]: v for k, v in locals().items() if k.startswith('p_') and v is not None}
        url = f'{self.messages_endpoint}'
        r = await self.post(url=url, json=params)
        return webexteamssdk.Message(r)

    async def get_message_detail(self, p_messageId: str) -> webexteamssdk.Message:
        url = f'{self.messages_endpoint}/{p_messageId}'
        r = await self.get(url=url)
        return webexteamssdk.Message(r)

    async def delete_message(self, p_messageId: str) -> None:
        url = f'{self.messages_endpoint}/{p_messageId}'
        await self.delete(url=url)
        return

    def __repr__(self):
        return f'WebexTeamsAsyncAPI'
