"""Superior Propane API Client."""

from __future__ import annotations

import re
import json
from typing import TYPE_CHECKING, Any
import asyncio
from datetime import datetime

import async_timeout
from bs4 import BeautifulSoup
from bs4.element import Tag
from slugify import slugify

from .const import (
    CUSTOMERS_URL,
    HOME_URL,
    LOGGER,
    LOGIN_PAGE_URL,
    LOGIN_URL,
    TANK_URL,
    TANK_DATA_URL,
)

# Error messages
SESSION_EXPIRED_MSG = "Session expired"

if TYPE_CHECKING:
    import aiohttp

# HTTP Status Codes
HTTP_OK = 200
MAX_LOGIN_RETRIES = 3  # Number of retry attempts for login


class SuperiorPropaneApiClientError(Exception):
    """Exception to indicate a general API error."""


class SuperiorPropaneApiClientCommunicationError(
    SuperiorPropaneApiClientError,
):
    """Exception to indicate a communication error."""


class SuperiorPropaneApiClientAuthenticationError(
    SuperiorPropaneApiClientError,
):
    """Exception to indicate an authentication error."""


class SuperiorPropaneApiClient:
    """Superior Propane API Client."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
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
            "cache-control": "no-cache",
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

    async def async_get_tanks_data(self) -> list[dict[str, Any]]:
        """Get tank data from Superior Propane."""
        try:
            await self._ensure_authenticated()
            return await self._get_tanks_from_api()
        except SuperiorPropaneApiClientAuthenticationError:
            LOGGER.debug("Authentication failed, attempting to re-authenticate")
            self._authenticated = False
            await self._ensure_authenticated()
            return await self._get_tanks_from_api()
        except Exception as exception:
            LOGGER.exception("Error getting tank data: %s", exception)
            msg = f"Failed to get tank data: {exception}"
            raise SuperiorPropaneApiClientError(msg) from exception

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authenticated session."""
        if self._authenticated:
            try:
                async with async_timeout.timeout(10):
                    response = await self._session.get(HOME_URL, headers=self._headers)
                    if response.status == HTTP_OK and "Login" not in str(response.url):
                        LOGGER.debug("Session still valid, skipping authentication")
                        return
                    LOGGER.debug("Session invalid, need to re-authenticate")
                    self._authenticated = False
            except (TimeoutError, Exception) as e:
                LOGGER.debug("Session validation failed: %s - will re-authenticate", e)
                self._authenticated = False
                self._session.cookie_jar.clear()

        if not self._authenticated and not self._auth_in_progress:
            await self._authenticate()

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
        try:
            async with async_timeout.timeout(30):
                response = await self._session.get(
                    LOGIN_PAGE_URL, headers=self._headers
                )
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
            msg = f"Timeout getting CSRF token: {exception}"
            raise SuperiorPropaneApiClientCommunicationError(msg) from exception

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
                async with async_timeout.timeout(60):  # Increased to 60 seconds
                    response = await self._session.post(
                        LOGIN_URL, headers=self._headers, data=payload
                    )
                    html = await response.text()
                    #LOGGER.debug("Login response HTML (attempt %d): %s", attempt, html[:2000])
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

                    # Verify session by checking HOME_URL
                    async with async_timeout.timeout(60):
                        response = await self._session.get(HOME_URL, headers=self._headers)
                        LOGGER.debug("HOME_URL response status (attempt %d): %s, URL: %s", attempt, response.status, response.url)
                        if "Login" in str(response.url):
                            msg = "Login failed - session not established (redirected to login)"
                            raise SuperiorPropaneApiClientAuthenticationError(msg)

                    # Navigate to CUSTOMERS_URL
                    async with async_timeout.timeout(60):
                        response = await self._session.get(CUSTOMERS_URL, headers=self._headers)
                        LOGGER.debug("CUSTOMERS_URL response status (attempt %d): %s, URL: %s", attempt, response.status, response.url)
                        if response.status != HTTP_OK:
                            msg = f"Failed to navigate to CUSTOMERS_URL: {response.status}"
                            raise SuperiorPropaneApiClientCommunicationError(msg)

                    LOGGER.debug("Successfully navigated to CUSTOMERS_URL")
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

    async def _login_fallback(self) -> None:
        """Fallback login attempt using alternative endpoint and fields."""
        payload = {
            "default_login[email]": self._username,
            "default_login[password]": self._password,
            "remember": "true",
        }
        fallback_url = "https://mysuperior.superiorpropane.com/account/login?bypass_csrf=login"

        retries = MAX_LOGIN_RETRIES
        for attempt in range(1, retries + 1):
            try:
                async with async_timeout.timeout(60):
                    response = await self._session.post(
                        fallback_url, headers=self._headers, data=payload
                    )
                    html = await response.text()
                    #LOGGER.debug("Fallback login response HTML (attempt %d): %s", attempt, html[:2000])
                    LOGGER.debug("Fallback login response status (attempt %d): %s, URL: %s", attempt, response.status, response.url)

                    # Check for JSON error response
                    try:
                        response_json = json.loads(html)
                        if response_json.get("status") == "error":
                            msg = f"Fallback login failed: {response_json.get('message', 'Unknown error')}"
                            raise SuperiorPropaneApiClientAuthenticationError(msg)
                    except json.JSONDecodeError:
                        # Not JSON, check URL for login page redirect
                        if "Login" in str(response.url) or response.status != HTTP_OK:
                            msg = "Fallback login failed - invalid credentials or server rejection"
                            raise SuperiorPropaneApiClientAuthenticationError(msg)

                    # Verify session by checking HOME_URL
                    async with async_timeout.timeout(60):
                        response = await self._session.get(HOME_URL, headers=self._headers)
                        LOGGER.debug("HOME_URL response status (attempt %d): %s, URL: %s", attempt, response.status, response.url)
                        if "Login" in str(response.url):
                            msg = "Fallback login failed - session not established (redirected to login)"
                            raise SuperiorPropaneApiClientAuthenticationError(msg)

                    # Navigate to CUSTOMERS_URL
                    async with async_timeout.timeout(60):
                        response = await self._session.get(CUSTOMERS_URL, headers=self._headers)
                        LOGGER.debug("Successfully navigated to CUSTOMERS_URL (fallback)")
                        return

            except TimeoutError as exception:
                LOGGER.warning("Timeout during fallback login attempt %d: %s", attempt, exception)
                if attempt == retries:
                    msg = f"Timeout during fallback login after {retries} attempts: {exception}"
                    raise SuperiorPropaneApiClientCommunicationError(msg) from exception
                await asyncio.sleep(2)
            except SuperiorPropaneApiClientAuthenticationError as e:
                LOGGER.debug("Fallback authentication error on attempt %d: %s", attempt, e)
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
                    response = await self._session.post(
                        TANK_DATA_URL, headers=self._headers, data=payload
                    )
                    if "Login" in str(response.url):
                        LOGGER.debug("Redirected to login page, session expired")
                        self._authenticated = False
                        raise SuperiorPropaneApiClientAuthenticationError(
                            SESSION_EXPIRED_MSG
                        )
                    if response.status != HTTP_OK:
                        msg = f"Failed to get tank data: {response.status}"
                        raise SuperiorPropaneApiClientCommunicationError(msg)

                    response_text = await response.text()
                    #LOGGER.debug("Tank API response: %s", response_text[:2000])
                    try:
                        response_json = json.loads(response_text)
                        tank_list = json.loads(response_json.get("data", "[]"))
                        LOGGER.debug("Tank API data: %s", json.dumps(tank_list, indent=2)[:2000])
                        if not response_json.get("status"):
                            msg = f"Tank API returned error: {response_json.get('message', 'Unknown error')}"
                            raise SuperiorPropaneApiClientError(msg)
                    except json.JSONDecodeError:
                        LOGGER.error("Failed to parse Tank API response or data as JSON")
                        raise SuperiorPropaneApiClientError("Failed to parse tank API response as JSON")

                    tank_list = json.loads(response_json.get("data", "[]"))
                    for idx, tank in enumerate(tank_list, offset + 1):
                        tank_data = self._parse_tank_json(tank, idx)
                        if tank_data:
                            tanks_data.append(tank_data)

                    finished = response_json.get("finished", True)
                    offset += limit

            except TimeoutError as exception:
                msg = f"Timeout getting tank data: {exception}"
                raise SuperiorPropaneApiClientCommunicationError(msg) from exception

        if not tanks_data:
            LOGGER.debug("No tanks found in API response, trying HTML fallback")
            return await self._get_tanks_from_page()

        #LOGGER.debug("Parsed %d tanks: %s", len(tanks_data), tanks_data)
        LOGGER.debug("Parsed %d tanks: %s", len(tanks_data), json.dumps(tanks_data, indent=2)[:2000])
        return tanks_data

    def _parse_tank_json(self, tank: dict, tank_number: int) -> dict[str, Any] | None:
        """Parse a single tank from JSON data."""
        try:
            address = tank.get("adds_location", "unknown")
            tank_id = slugify(address.lower().replace(" ", "_"))
            tank_size = tank.get("adds_tank_size", "unknown")
            tank_type = tank.get("adds_tank_description", "unknown")
            level = tank.get("adds_fill_percentage", "unknown")
            current_gallons = tank.get("adds_fill", "unknown")
            reading_date = tank.get("adds_last_reading", "unknown").split(" ")[0]
            last_delivery = tank.get("adds_last_fill", "unknown").split(" ")[0]
            total_consumption = tank.get("adds_tank_usage", "unknown")
            # Calculate days since delivery
            try:
                last_delivery_date = datetime.strptime(last_delivery, "%Y-%m-%d")
                reading_date_obj = datetime.strptime(reading_date, "%Y-%m-%d")
                days_since_delivery = (reading_date_obj - last_delivery_date).days
                days_since_delivery = str(days_since_delivery) if days_since_delivery >= 0 else "unknown"
            except (ValueError, TypeError):
                LOGGER.warning("Failed to calculate days since delivery for tank %s", tank_id)
                days_since_delivery = "unknown"
        except (AttributeError, ValueError, TypeError) as exception:
            LOGGER.warning("Error parsing tank JSON %d: %s", tank_number, exception)
            return None
        return {
            "tank_id": tank_id,
            "tank_number": tank_number,
            "address": address,
            "tank_size": tank_size,
            "tank_type": tank_type,
            "level": level,
            "current_gallons": current_gallons,
            "reading_date": reading_date,
            "last_delivery": last_delivery,
            "total_consumption": total_consumption,
            "days_since_delivery": days_since_delivery,
        }

    async def _get_tanks_from_page(self) -> list[dict[str, Any]]:
        """Fallback: Get tank data from the tank page HTML."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(TANK_URL, headers=self._headers)
                if "Login" in str(response.url):
                    LOGGER.debug("Redirected to login page, session expired")
                    self._authenticated = False
                    raise SuperiorPropaneApiClientAuthenticationError(
                        SESSION_EXPIRED_MSG
                    )
                if response.status != HTTP_OK:
                    msg = f"Failed to get tank page: {response.status}"
                    raise SuperiorPropaneApiClientCommunicationError(msg)

                html = await response.text()
                #LOGGER.debug("Tank page HTML: %s", html[:2000])
                soup = BeautifulSoup(html, "html.parser")
                login_form = soup.find("form", {"action": "/account/individualLogin"})
                if login_form:
                    LOGGER.debug("Login form found on tank page, session expired")
                    self._authenticated = False
                    raise SuperiorPropaneApiClientAuthenticationError(
                        SESSION_EXPIRED_MSG
                    )

                tank_rows = soup.select("div.row")
                LOGGER.debug("Found %d tank rows", len(tank_rows))
                tanks_data = []
                for idx, row in enumerate(tank_rows):
                    tank_data = await self._parse_tank_row(row, idx + 1)
                    if tank_data:
                        tanks_data.append(tank_data)

                if not tanks_data:
                    msg = "No tanks found in HTML"
                    raise SuperiorPropaneApiClientError(msg)

                return tanks_data

        except TimeoutError as exception:
            msg = f"Timeout getting tank data: {exception}"
            raise SuperiorPropaneApiClientCommunicationError(msg) from exception

    def _extract_address(self, row: Tag) -> tuple[str, str] | None:
        """Extract and clean address from row."""
        address_element = row.select_one(".small-12.medium-5.columns p")
        if not address_element:
            return None
        address_text = address_element.get_text(separator=" ", strip=True)
        address = address_text.split("\n")[0] if "\n" in address_text else address_text
        address = re.sub(r"\s+", " ", address).strip()
        tank_id = slugify(address.lower().replace(" ", "_"))
        return address, tank_id

    def _extract_tank_info(self, row: Tag) -> tuple[str, str]:
        """Extract tank size and type."""
        tank_info_element = row.select_one(".small-12.medium-5.columns h4")
        tank_size = "unknown"
        tank_type = "unknown"
        if tank_info_element:
            tank_info_text = tank_info_element.get_text()
            size_match = re.search(r"(\d+)\s*gal\.", tank_info_text)
            if size_match:
                tank_size = size_match.group(1)
            if "Propane" in tank_info_text or "BULK PROPANE" in tank_info_text:
                tank_type = "Propane"
        return tank_size, tank_type

    def _extract_level(self, row: Tag) -> str:
        """Extract level percentage from progress bar."""
        progress_bar = row.select_one(".range-slider-active-segment")
        if progress_bar and "height" in progress_bar.get("style", ""):
            style = progress_bar.get("style", "")
            level_match = re.search(r"height:\s*([\d.]+)%", style)
            if level_match:
                return level_match.group(1)
        value_span = row.select_one(".range-value #sliderOutput1")
        if value_span:
            return value_span.get_text(strip=True)
        return "unknown"

    def _extract_gallons(self, row: Tag) -> str:
        """Extract current gallons."""
        gallons_text = row.find(string=re.compile(r"Approximately \d+ gallons in tank"))
        if gallons_text:
            gallons_match = re.search(
                r"Approximately (\d+) gallons in tank", str(gallons_text)
            )
            if gallons_match:
                return gallons_match.group(1)
        return "unknown"

    def _extract_date(self, row: Tag, pattern: str) -> str:
        """Extract date by pattern."""
        date_text = row.find(string=re.compile(pattern))
        if date_text and date_text.parent:
            full_text = date_text.parent.get_text()
            date_match = re.search(
                rf"{pattern}\s*(\d{{1,2}}/\d{{1,2}}/\d{{4}})", full_text
            )
            if date_match:
                return date_match.group(1)
        return "unknown"

    async def _parse_tank_row(
        self, row: Tag, tank_number: int
    ) -> dict[str, Any] | None:
        """Parse a single tank row from HTML."""
        try:
            address_info = self._extract_address(row)
            if not address_info:
                return None
            address, tank_id = address_info
            tank_size, tank_type = self._extract_tank_info(row)
            level = self._extract_level(row)
            current_gallons = self._extract_gallons(row)
            reading_date = self._extract_date(row, "Reading Date:")
            last_delivery = self._extract_date(row, "Last Delivery:")
        except (AttributeError, ValueError, TypeError) as exception:
            LOGGER.warning("Error parsing tank row %d: %s", tank_number, exception)
            return None
        return {
            "tank_id": tank_id,
            "tank_number": tank_number,
            "address": address,
            "tank_size": tank_size,
            "tank_type": tank_type,
            "level": level,
            "current_gallons": current_gallons,
            "reading_date": reading_date,
            "last_delivery": last_delivery,
        }

    async def async_test_connection(self) -> bool:
        """Test if we can connect and authenticate."""
        try:
            tanks_data = await self.async_get_tanks_data()
            return len(tanks_data) > 0
        except SuperiorPropaneApiClientAuthenticationError:
            return False
        except SuperiorPropaneApiClientError:
            return False