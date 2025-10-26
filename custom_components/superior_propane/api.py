"""Superior Propane API Client."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
import asyncio
from datetime import datetime

import async_timeout
from bs4 import BeautifulSoup

from .const import (
    LOGGER,
    LOGIN_PAGE_URL,
    LOGIN_URL,
    MAX_API_RETRIES,
    ORDERS_URL,
    RETRY_DELAY_SECONDS,
    TANK_DATA_URL,
)

# Error messages
SESSION_EXPIRED_MSG = "Session expired"

if TYPE_CHECKING:
    import aiohttp

# HTTP Status Codes
HTTP_OK = 200
MAX_LOGIN_RETRIES = 3  # Number of retry attempts for login and CSRF token


class SuperiorPropaneApiClientError(Exception):
    """Exception to indicate a general API error."""


class SuperiorPropaneApiClientCommunicationError(SuperiorPropaneApiClientError):
    """Exception to indicate a communication error."""


class SuperiorPropaneApiClientAuthenticationError(SuperiorPropaneApiClientError):
    """Exception to indicate an authentication error."""


class SuperiorPropaneApiClient:
    """Superior Propane API Client."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = session
        self._authenticated = False
        self._auth_in_progress = False
        self._headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "accept-language": "en-US,en;q=0.9,fr-CA;q=0.8",
            "cache-control": "no-cache, no-store, must-revalidate",
            "pragma": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://mysuperior.superiorpropane.com",
            "referer": "https://mysuperior.superiorpropane.com/account/individualLogin",
            "sec-ch-ua": (
                '"Google Chrome";v="129", "Not=A?Brand";v="99", "Chromium";v="129"'
            ),
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
        """Get all data (tanks and orders totals) from the API."""
        await self._ensure_authenticated()
        tanks_data = await self._get_tanks_from_api()
        orders_totals = await self._get_orders_totals()
        return tanks_data, orders_totals

    async def _get_orders_totals(self) -> dict[str, float]:
        """Get orders history and compute totals."""
        await self._ensure_authenticated()
        
        orders_totals = {"total_litres": 0, "total_cost": 0.0}
        
        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                csrf_token = await self._get_csrf_token()
                payload = {
                    "csrf_superior_token": csrf_token,
                    "firstRun": "true",
                }
                async with async_timeout.timeout(10):
                    response = await self._session.post(ORDERS_URL, headers=self._headers, data=payload)
                    if "Login" in str(response.url):
                        LOGGER.debug("Redirected to login page, session expired")
                        self._authenticated = False
                        raise SuperiorPropaneApiClientAuthenticationError(SESSION_EXPIRED_MSG)
                    if response.status != HTTP_OK:
                        msg = f"Failed to get orders data: {response.status}"
                        raise SuperiorPropaneApiClientCommunicationError(msg)

                    data_html = await response.text()
                    LOGGER.debug("Orders response (first 2000 chars): %s", data_html[:2000])

                    # Parse HTML snippet
                    soup = BeautifulSoup(data_html, 'html.parser')
                    rows = soup.find_all('div', class_='orders__row cf')  # Fixed class name

                    for row in rows:
                        cols = row.find_all('div')
                        if len(cols) == 5:
                            product = cols[2].text.strip().upper()
                            if "PROPANE" in product:  # Filter on propane only
                                amount_str = cols[3].text.strip().split()[0]  # "283" from "283 litres"
                                price_str = cols[4].text.strip().lstrip('$')  # "264.81" from "$264.81"
                                try:
                                    litres = int(float(amount_str))
                                    cost = round(float(price_str), 2)
                                    orders_totals['total_litres'] += litres
                                    orders_totals['total_cost'] = round(orders_totals['total_cost'] + cost, 2)
                                    LOGGER.debug("Processed order: %d litres, %.2f $", litres, cost)
                                except ValueError as e:
                                    LOGGER.warning("Invalid amount or price in row: %s, error: %s", row.text.strip(), e)

                    LOGGER.debug("Final totals: %d litres, %.2f $", orders_totals['total_litres'], orders_totals['total_cost'])
                    return orders_totals  # Success, exit retry loop

            except (TimeoutError, SuperiorPropaneApiClientCommunicationError) as exception:
                LOGGER.warning("Error getting orders data on attempt %d: %s", attempt, exception)
                if attempt == MAX_API_RETRIES:
                    LOGGER.error("Exhausted all retry attempts for Orders API")
                    raise SuperiorPropaneApiClientError(f"Failed to get orders data: {exception}") from exception
                LOGGER.debug("Retrying Orders API call after %.1f seconds (attempt %d/%d)", RETRY_DELAY_SECONDS, attempt + 1, MAX_API_RETRIES)
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            except SuperiorPropaneApiClientAuthenticationError:
                self._authenticated = False
                raise  # Propagate the error so that async_get_all_data handles re-authentication

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authenticated session."""
        if self._authenticated:
            LOGGER.debug("Already authenticated, reusing existing session")
            return

        LOGGER.debug("Performing authentication")
        self._session.cookie_jar.clear()
        await self._authenticate()
        self._authenticated = True

    async def _authenticate(self) -> None:
        """Perform full authentication sequence."""
        if self._auth_in_progress:
            return
        self._auth_in_progress = True
        try:
            LOGGER.debug("Starting authentication sequence")
            self._session.cookie_jar.clear()
            csrf_token = await self._get_csrf_token()
            await self._login(csrf_token)
            self._authenticated = True
            LOGGER.debug("Authentication completed successfully")
        except Exception:
            self._authenticated = False
            raise
        finally:
            self._auth_in_progress = False

    async def _get_csrf_token(self) -> str:
        """Get CSRF token from cookies."""
        retries = MAX_LOGIN_RETRIES
        for attempt in range(1, retries + 1):
            try:
                async with async_timeout.timeout(60):
                    response = await self._session.get(LOGIN_PAGE_URL, headers=self._headers)
                    if response.status != HTTP_OK:
                        msg = f"Failed to get login page: {response.status}"
                        raise SuperiorPropaneApiClientCommunicationError(msg)

                    csrf_cookie = response.cookies.get("csrf_cookie_name")
                    if not csrf_cookie or not csrf_cookie.value:
                        msg = "CSRF token not found in cookies"
                        LOGGER.warning(msg)
                        return ""  # Fallback to empty token

                    LOGGER.debug("Found CSRF token in cookie: %s", csrf_cookie.value)
                    return csrf_cookie.value

            except TimeoutError as exception:
                LOGGER.warning("Timeout getting CSRF token attempt %d: %s", attempt, exception)
                if attempt == retries:
                    msg = f"Timeout getting CSRF token after {retries} attempts: {exception}"
                    raise SuperiorPropaneApiClientCommunicationError(msg) from exception
                await asyncio.sleep(2)  # Wait before retrying

    async def _login(self, csrf_token: str) -> None:
        """Login to Superior Propane."""
        payload = {
            "login_email": self._username,
            "login_password": self._password,
            "remember": "true",
        }
        if csrf_token:
            payload["csrf_superior_token"] = csrf_token

        retries = MAX_LOGIN_RETRIES
        for attempt in range(1, retries + 1):
            try:
                async with async_timeout.timeout(60):
                    response = await self._session.post(LOGIN_URL, headers=self._headers, data=payload)
                    html = await response.text()
                    LOGGER.debug("Login response status (attempt %d): %s, URL: %s", attempt, response.status, response.url)

                    # Check for JSON error response
                    try:
                        response_json = json.loads(html)
                        if response_json.get("status") == "error":
                            msg = f"Login failed: {response_json.get('message', 'Unknown error')}"
                            raise SuperiorPropaneApiClientAuthenticationError(msg)
                    except json.JSONDecodeError:
                        # Not JSON, check URL for login page redirect
                        if "Login" in str(response.url) or response.status != HTTP_OK:
                            msg = "Login failed - invalid credentials or server rejection (check logs for details)"
                            raise SuperiorPropaneApiClientAuthenticationError(msg)
                    return  # Success, exit retry loop

            except TimeoutError as exception:
                LOGGER.warning("Timeout during login attempt %d: %s", attempt, exception)
                if attempt == retries:
                    msg = f"Timeout during login after {retries} attempts: {exception}"
                    raise SuperiorPropaneApiClientCommunicationError(msg) from exception
                await asyncio.sleep(2)  # Wait before retrying
            except SuperiorPropaneApiClientAuthenticationError as e:
                LOGGER.debug("Authentication error on attempt %d: %s", attempt, e)
                if attempt == retries:
                    raise
                await asyncio.sleep(2)

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
                    async with async_timeout.timeout(10):
                        response = await self._session.post(TANK_DATA_URL, headers=self._headers, data=payload)
                        if "Login" in str(response.url):
                            LOGGER.debug("Redirected to login page, session expired")
                            self._authenticated = False
                            raise SuperiorPropaneApiClientAuthenticationError(SESSION_EXPIRED_MSG)
                        if response.status != HTTP_OK:
                            msg = f"Failed to get tank data: {response.status}"
                            raise SuperiorPropaneApiClientCommunicationError(msg)

                        response_text = await response.text()
                        try:
                            response_json = json.loads(response_text)
                            tank_list = json.loads(response_json.get("data", "[]"))
                            LOGGER.debug("Tank API data: %s", json.dumps(tank_list, indent=2)[:2000])
                            if not response_json.get("status"):
                                msg = f"Tank API returned error: {response_json.get('message', 'Unknown error')}"
                                raise SuperiorPropaneApiClientError(msg)
                        except json.JSONDecodeError as json_error:
                            LOGGER.warning("Failed to parse Tank API response as JSON on attempt %d: %s", attempt, json_error)
                            if attempt == MAX_API_RETRIES:
                                LOGGER.error("Exhausted all retry attempts for Tank API")
                                raise SuperiorPropaneApiClientError("Failed to parse tank API response as JSON") from json_error
                            LOGGER.debug("Retrying Tank API call after %.1f seconds (attempt %d/%d)", RETRY_DELAY_SECONDS, attempt + 1, MAX_API_RETRIES)
                            await asyncio.sleep(RETRY_DELAY_SECONDS)
                            continue

                        for idx, tank in enumerate(tank_list, offset + 1):
                            tank_data = self._parse_tank_json(tank, idx)
                            if tank_data:
                                tanks_data.append(tank_data)

                        finished = response_json.get("finished", True)
                        offset += limit
                        break  # Success: Exit the retry loop

                except TimeoutError as exception:
                    msg = f"Timeout getting tank data: {exception}"
                    raise SuperiorPropaneApiClientCommunicationError(msg) from exception
                except SuperiorPropaneApiClientAuthenticationError:
                    self._authenticated = False
                    raise  # Propagate the error so that async_get_all_data handles re-authentication

        LOGGER.debug("Parsed %d tanks: %s", len(tanks_data), json.dumps(tanks_data, indent=2)[:2000])
        return tanks_data

    def _parse_tank_json(self, tank: dict, tank_number: int) -> dict[str, Any] | None:
        """Parse a single tank from JSON data."""
        try:
            address = tank.get("adds_location", "Unknown")
            current_volume = tank.get("adds_fill", "Unknown")
            #current_volume = int(float(tank.get("adds_fill", "Unknown"))) if tank.get("adds_fill", "Unknown") != "Unknown" else "Unknown"
            customer_number = tank.get("adds_customer_number", "Unknown")
            last_delivery = tank.get("adds_last_fill", "Unknown").split(" ")[0]
            last_reading = tank.get("adds_last_reading", "Unknown")
            level = tank.get("adds_fill_percentage", "Unknown")
            #level = int(float(tank.get("adds_fill_percentage", "Unknown"))) if tank.get("adds_fill_percentage", "Unknown") != "Unknown" else "Unknown"
            tank_id = tank.get("adds_tank_id", "Unknown")
            tank_name = tank.get("tank_name", "Unknown")
            tank_serial_number = tank.get("adds_serial_number", "Unknown").strip()
            tank_size = tank.get("adds_tank_size", "Unknown")
        except (AttributeError, ValueError, TypeError) as exception:
            LOGGER.warning("Error parsing tank JSON %d: %s", tank_number, exception)
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

    async def async_test_connection(self) -> bool:
        """Test if we can connect and authenticate."""
        try:
            tanks_data = await self.async_get_all_data()
            return len(tanks_data) > 0
        except SuperiorPropaneApiClientAuthenticationError:
            return False
        except SuperiorPropaneApiClientError:
            return False