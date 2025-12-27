"""Superior Propane API Client."""

from __future__ import annotations

import json
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

import aiohttp
import async_timeout
from bs4 import BeautifulSoup

from .const import (
    DASHBOARD_URL,
    LOGGER,
    LOGIN_PAGE_URL,
    LOGIN_URL,
    MAX_API_RETRIES,
    ORDERS_URL,
    RETRY_DELAY_SECONDS,
    TANK_DATA_URL,
)

# HTTP Status Codes
HTTP_OK = 200


class SuperiorPropaneApiClientAuthenticationError(Exception):
    """Exception to indicate an authentication error."""


class SuperiorPropaneApiClientCommunicationError(Exception):
    """Exception to indicate a communication error."""


class SuperiorPropaneApiClientError(Exception):
    """Exception to indicate a general API error."""


class SuperiorPropaneApiClient:
    """Superior Propane API Client."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._authenticated = False
        self._auth_in_progress = False
        self._session_corrupted = False

        self._session = session or aiohttp.ClientSession()

        self._headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9,fr-CA;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "origin": "https://mysuperior.superiorpropane.com",
            "sec-ch-ua": '"Chromium";v="129", "Not=A?Brand";v="8", "Google Chrome";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/129.0.0.0 Safari/537.36"
            ),
        }

    async def async_get_all_data(self) -> tuple[list[dict[str, Any]], dict[str, float]]:
        """Get all data from the Superior Propane."""
        await self._ensure_valid_session()
        self._session.cookie_jar.clear()
        self._authenticated = False
        await self._ensure_authenticated()

        tanks_data = await self._get_tanks_from_api()
        orders_totals = await self._get_orders_totals()
        return tanks_data, orders_totals

    async def async_test_connection(self) -> bool:
        """Test if we can connect and authenticate."""
        try:
            tanks_data = await self.async_get_all_data()
            return len(tanks_data) > 0

        except SuperiorPropaneApiClientAuthenticationError:
            return False

        except SuperiorPropaneApiClientError:
            return False

    async def _authenticate(self) -> None:
        if self._auth_in_progress:
            return

        self._auth_in_progress = True

        try:
            LOGGER.debug("Starting authentication sequence")

            # Load the login page to initialize cookies if needed
            async with async_timeout.timeout(60):
                response = await self._session.get(LOGIN_PAGE_URL, headers=self._headers, allow_redirects=True)

                if "maintenance" in str(response.url):
                    raise SuperiorPropaneApiClientCommunicationError("Site under scheduled maintenance")

                if response.status != HTTP_OK:
                    raise SuperiorPropaneApiClientCommunicationError(f"Login page returned {response.status}")

                await response.text()

            csrf_token = await self._get_csrf_token()

            if not csrf_token:
                raise SuperiorPropaneApiClientAuthenticationError("CSRF token not found in login page")

            await self._login(csrf_token)

            self._authenticated = True
            LOGGER.debug("Authentication successful")

        except SuperiorPropaneApiClientAuthenticationError as e:
            self._authenticated = False
            raise

        except (asyncio.TimeoutError, SuperiorPropaneApiClientCommunicationError):
            self._authenticated = False
            raise

        except Exception as e:
            self._authenticated = False
            raise SuperiorPropaneApiClientAuthenticationError(f"Authentication failed: {str(e)}") from e

        finally:
            self._auth_in_progress = False

    async def _ensure_authenticated(self) -> None:
        if self._authenticated:
            try:
                async with async_timeout.timeout(60):
                    response = await self._session.get(DASHBOARD_URL, headers=self._headers, allow_redirects=True)

                    if "individualLogin" in str(response.url):
                        LOGGER.debug("Redirected to login, forcing re-authentication")
                        self._authenticated = False

                    if response.status != HTTP_OK:
                        LOGGER.debug("HTTP request failed, forcing re-authentication")
                        self._authenticated = False

            except Exception as e:
                LOGGER.warning("Error validating session: %s", e)
                self._authenticated = False

        if not self._authenticated:
            await self._authenticate()
            await asyncio.sleep(8)

    async def _ensure_valid_session(self) -> None:
        """Recreate the session if it is suspected of being corrupted."""
        if self._session_corrupted:
            LOGGER.debug("Destroying corrupted aiohttp session and creating a new one")
            await self._session.close()
            self._session = aiohttp.ClientSession()
            self._session_corrupted = False
            self._authenticated = False

    async def _get_csrf_token(self) -> str:
        """Get CSRF token from cookies ('csrf_cookie_name')."""
        csrf_token = None
        for cookie in self._session.cookie_jar:
            if cookie.key == "csrf_cookie_name":
                csrf_token = cookie.value
                break

        if csrf_token:
            LOGGER.debug("Found CSRF token in cookie: %s", csrf_token)
            return csrf_token

        # If not found, fetch login page to set the cookie
        LOGGER.debug("CSRF cookie not found - fetching login page to initialize")
        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                async with async_timeout.timeout(60):
                    response = await self._session.get(LOGIN_PAGE_URL, headers=self._headers)
                    if response.status != HTTP_OK:
                        raise SuperiorPropaneApiClientCommunicationError(f"Failed to get login page: {response.status}")

                for cookie in self._session.cookie_jar:
                    if cookie.key == "csrf_cookie_name":
                        LOGGER.debug("CSRF token obtained after page load: %s", cookie.value)
                        return cookie.value

                LOGGER.warning("CSRF token still not found after fetching page (attempt %d)", attempt)
                if attempt == MAX_API_RETRIES:
                    raise SuperiorPropaneApiClientAuthenticationError("CSRF cookie 'csrf_cookie_name' not found")

                await asyncio.sleep(3 + (attempt * 2))

            except (asyncio.TimeoutError, SuperiorPropaneApiClientCommunicationError) as e:
                LOGGER.warning("Timeout getting CSRF token (attempt %d): %s", attempt, e)
                if attempt == MAX_API_RETRIES:
                    raise SuperiorPropaneApiClientCommunicationError("Timeout getting CSRF token after retries")

        raise SuperiorPropaneApiClientAuthenticationError("Unable to obtain CSRF token")

    async def _get_orders_totals(self) -> dict[str, float]:
        """Get orders history and compute totals."""
        orders_totals = {"total_litres": 0, "total_cost": 0.0}

        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                csrf_token = await self._get_csrf_token()
                payload = {
                    "csrf_superior_token": csrf_token,
                    "firstRun": "true",
                }

                api_headers = self._headers.copy()
                api_headers.update({
                    "content-type": "application/x-www-form-urlencoded",
                    "referer": DASHBOARD_URL,
                    "x-requested-with": "XMLHttpRequest",
                })

                async with async_timeout.timeout(60):
                    response = await self._session.post(ORDERS_URL, headers=api_headers, data=payload)

                    if response.status != HTTP_OK:
                        raise SuperiorPropaneApiClientCommunicationError(f"Failed to get orders: {response.status}")

                    data_html = await response.text()
                    #LOGGER.debug("Orders response (first 2000 chars): %s", data_html[:2000])

                    soup = BeautifulSoup(data_html, 'html.parser')
                    rows = soup.find_all('div', class_='orders__row cf')

                    for row in rows:
                        cols = row.find_all('div')
                        if len(cols) == 5:
                            product = cols[2].text.strip().upper()
                            if "PROPANE" in product:
                                try:
                                    amount_str = cols[3].text.strip().split()[0].replace(',', '')
                                    price_str = cols[4].text.strip().lstrip('$').replace(',', '')
                                    litres = int(float(amount_str))
                                    cost = round(float(price_str), 2)
                                    orders_totals['total_litres'] += litres
                                    orders_totals['total_cost'] = round(orders_totals['total_cost'] + cost, 2)
                                    #LOGGER.debug("Processed order: %d litres, %.2f $", litres, cost)
                                except ValueError as e:
                                    LOGGER.warning("Invalid order data: %s | Error: %s", row.text.strip(), e)

                    LOGGER.debug("Final totals: %d litres, %.2f $", orders_totals['total_litres'], orders_totals['total_cost'])
                    return orders_totals  # Success

            except (asyncio.TimeoutError, SuperiorPropaneApiClientCommunicationError) as e:
                LOGGER.debug("Error getting orders (attempt %d): %s", attempt, e)
                if attempt == MAX_API_RETRIES:
                    self._session_corrupted = True
                    LOGGER.debug("Marking session as corrupted after %d failed tank attempts – will recreate on next update",   )
                    raise SuperiorPropaneApiClientCommunicationError("Failed to get orders after retries")
                await asyncio.sleep(RETRY_DELAY_SECONDS + (attempt * 10))

            except SuperiorPropaneApiClientAuthenticationError:
                raise  # Propagate for re-authentication

        raise SuperiorPropaneApiClientError("Failed to get orders totals")

    async def _get_tanks_from_api(self) -> list[dict[str, Any]]:
        """Get tank data from the tank API endpoint."""
        tanks_data = []
        offset = 0
        limit = 10
        finished = False

        while not finished:
            for attempt in range(1, MAX_API_RETRIES + 1):
                try:
                    csrf_token = await self._get_csrf_token()
                    payload = {
                        "csrf_superior_token": csrf_token,
                        "limit": str(limit),
                        "offset": str(offset),
                        "firstRun": "true" if offset == 0 else "false",
                        "listIndex": str(offset + 1),
                    }

                    api_headers = self._headers.copy()
                    api_headers.update({
                        "content-type": "application/x-www-form-urlencoded",
                        "referer": DASHBOARD_URL,
                        "x-requested-with": "XMLHttpRequest",
                    })

                    async with async_timeout.timeout(60):
                        response = await self._session.post(TANK_DATA_URL, headers=api_headers, data=payload)

                        if response.status != HTTP_OK:
                            raise SuperiorPropaneApiClientCommunicationError(f"Failed to get tank data: {response.status}")

                        data_html = await response.text()
                        #LOGGER.debug("Tank API raw response (first 500 chars): %s", data_html[:500])

                        response_json = json.loads(data_html)
                        tank_list = json.loads(response_json.get("data", "[]"))
                        #LOGGER.debug("Tank API data: %s", json.dumps(tank_list, indent=2)[:5000])

                        if not response_json.get("status"):
                            if tanks_data and not tank_list:
                                LOGGER.debug("API returned status=false with empty tank list - assuming all tanks retrieved")
                                finished = True
                                break
                            raise SuperiorPropaneApiClientError(f"Tank API error: {response_json.get('message', 'Unknown')}")

                        if not tank_list:
                            LOGGER.debug("Empty tank list received - all tanks retrieved")
                            finished = True
                            break

                        tanks_in_batch = 0
                        for idx, tank in enumerate(tank_list, offset + 1):
                            tank_data = self._parse_tank_json(tank, idx)
                            if tank_data:
                                tanks_data.append(tank_data)
                                tanks_in_batch += 1

                        #LOGGER.debug("Retrieved %d tanks in this batch (total: %d)", tanks_in_batch, len(tanks_data))

                        finished = response_json.get("finished", True)
                        
                        if tanks_in_batch < limit:
                            #LOGGER.debug("Received fewer tanks than limit (%d < %d) - assuming all tanks retrieved", tanks_in_batch, limit)
                            finished = True
                        
                        offset += limit
                        break

                except json.JSONDecodeError as json_error:
                    LOGGER.debug("JSON parse error (attempt %d): %s. Raw: %s", attempt, json_error, data_html[:200].replace("\n", " ").strip())
                    if attempt == MAX_API_RETRIES:
                        if tanks_data:
                            LOGGER.warning("JSON error but returning %d tanks already collected", len(tanks_data))
                            return tanks_data
                        raise SuperiorPropaneApiClientError("Failed to get valid JSON after retries") from json_error
                    await asyncio.sleep(RETRY_DELAY_SECONDS + (attempt * 10))

                except (asyncio.TimeoutError, SuperiorPropaneApiClientCommunicationError) as e:
                    LOGGER.debug("Error getting tanks (attempt %d): %s", attempt, e)
                    if attempt == MAX_API_RETRIES:
                        if tanks_data:
                            LOGGER.warning("API error but returning %d tanks already collected", len(tanks_data))
                            return tanks_data
                        self._session_corrupted = True
                        LOGGER.debug("Marking session as corrupted after %d failed tank attempts", MAX_API_RETRIES)
                        raise SuperiorPropaneApiClientCommunicationError("Tank API timeout after retries")
                    await asyncio.sleep(RETRY_DELAY_SECONDS + (attempt * 10))

                except SuperiorPropaneApiClientAuthenticationError:
                    raise  # Propagate for re-authentication

        LOGGER.debug("Parsed %d tanks total", len(tanks_data))
        return tanks_data

    async def _login(self, csrf_token: str) -> None:
        """Perform login with CSRF token."""
        payload = {
            "csrf_superior_token": csrf_token,
            "login_email": self._username,
            "login_password": self._password,
        }

        login_headers = self._headers.copy()
        login_headers.update({
            "content-type": "application/x-www-form-urlencoded",
            "referer": LOGIN_PAGE_URL,
            "x-requested-with": "XMLHttpRequest",
        })

        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                async with async_timeout.timeout(60):
                    response = await self._session.post(LOGIN_URL, headers=login_headers, data=payload, allow_redirects=True)

                if "dashboard" in str(response.url):
                    LOGGER.debug("Login successful - redirected to dashboard")
                    return

                if "individualLogin" in str(response.url):
                    raise SuperiorPropaneApiClientAuthenticationError("Login failed - redirected to login")

                data_html = await response.text()

                raise SuperiorPropaneApiClientError(f"Unexpected login response: {data_html[:200]}")

            except asyncio.TimeoutError as e:
                LOGGER.warning("Timeout during login (attempt %d): %s", attempt, e)
                if attempt == MAX_API_RETRIES:
                    raise SuperiorPropaneApiClientCommunicationError("Login timeout after retries")
                await asyncio.sleep(3 + (attempt * 2))

            except SuperiorPropaneApiClientAuthenticationError as e:
                LOGGER.warning("Authentication error (attempt %d): %s", attempt, e)
                if attempt == MAX_API_RETRIES:
                    raise
                await asyncio.sleep(3 + (attempt * 2))

    def _parse_tank_json(self, tank: dict, tank_number: int) -> dict[str, Any] | None:
        """Parse a single tank from JSON data."""
        try:
            address = tank.get("adds_location", "Unknown")
            current_volume = tank.get("adds_fill", "Unknown")
            customer_number = tank.get("adds_customer_number", "Unknown")
            last_delivery = tank.get("adds_last_fill", "Unknown").split(" ")[0]
            last_reading = tank.get("adds_last_reading", "Unknown")
            level = tank.get("adds_fill_percentage", "Unknown")
            tank_id = tank.get("adds_tank_id", "Unknown")
            tank_name = tank.get("tank_name", "Unknown")
            tank_serial_number = tank.get("adds_serial_number", "Unknown").strip()
            tank_size = tank.get("adds_tank_size", "Unknown")
        except (AttributeError, ValueError, TypeError) as e:
            LOGGER.warning("Error parsing tank JSON %d: %s", tank_number, e)
            return None
        return {
            "address": address,
            "current_volume": current_volume,
            "customer_number": customer_number,
            "last_delivery": last_delivery,
            "last_reading": last_reading,
            "level": level,
            "tank_id": tank_id,
            "tank_name": tank_name,
            "tank_number": tank_number,
            "tank_serial_number": tank_serial_number,
            "tank_size": tank_size,
        }