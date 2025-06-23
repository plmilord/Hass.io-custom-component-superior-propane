"""Superior Plus Propane API Client."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import async_timeout
from bs4 import BeautifulSoup, Tag
from slugify import slugify

from .const import (
    CUSTOMERS_URL,
    HOME_URL,
    LOGGER,
    LOGIN_PAGE_URL,
    LOGIN_URL,
    TANK_URL,
)

if TYPE_CHECKING:
    import aiohttp

# HTTP Status Codes
HTTP_OK = 200


class SuperiorPlusPropaneApiClientError(Exception):
    """Exception to indicate a general API error."""


class SuperiorPlusPropaneApiClientCommunicationError(
    SuperiorPlusPropaneApiClientError,
):
    """Exception to indicate a communication error."""


class SuperiorPlusPropaneApiClientAuthenticationError(
    SuperiorPlusPropaneApiClientError,
):
    """Exception to indicate an authentication error."""


class SuperiorPlusPropaneApiClient:
    """Superior Plus Propane API Client."""

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
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://mysuperioraccountlogin.com",
            "referer": "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F",
            "sec-ch-ua": (
                '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

    async def async_get_tanks_data(self) -> list[dict[str, Any]]:
        """Get tank data from Superior Plus Propane."""
        try:
            # Ensure we have a valid authenticated session
            await self._ensure_authenticated()

            # Get tank data using existing session
            return await self._get_tanks_from_page()

        except SuperiorPlusPropaneApiClientAuthenticationError:
            # If authentication fails, reset state and retry once
            LOGGER.debug("Authentication failed, attempting to re-authenticate")
            self._authenticated = False
            await self._ensure_authenticated()
            return await self._get_tanks_from_page()
        except Exception as exception:
            LOGGER.exception("Error getting tank data: %s", exception)
            msg = f"Failed to get tank data: {exception}"
            raise SuperiorPlusPropaneApiClientError(msg) from exception

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authenticated session."""
        if self._authenticated:
            # Try to validate current session by accessing a protected page
            try:
                async with async_timeout.timeout(10):
                    response = await self._session.get(HOME_URL, headers=self._headers)
                    if response.status == HTTP_OK and "Login" not in str(response.url):
                        LOGGER.debug("Session still valid, skipping authentication")
                        return
                    else:
                        LOGGER.debug("Session invalid, need to re-authenticate")
                        self._authenticated = False
            except Exception:
                LOGGER.debug("Session validation failed, need to re-authenticate")
                self._authenticated = False

        if not self._authenticated and not self._auth_in_progress:
            await self._authenticate()

    async def _authenticate(self) -> None:
        """Perform full authentication sequence."""
        if self._auth_in_progress:
            return

        self._auth_in_progress = True
        try:
            LOGGER.debug("Starting authentication sequence")

            # Step 1: Get CSRF token from login page
            csrf_token = await self._get_csrf_token()

            # Step 2: Login with credentials
            await self._login(csrf_token)

            # Mark as authenticated
            self._authenticated = True
            LOGGER.debug("Authentication completed successfully")

        except Exception:
            self._authenticated = False
            raise
        finally:
            self._auth_in_progress = False

    async def _get_csrf_token(self) -> str:
        """Get CSRF token from login page."""
        try:
            async with async_timeout.timeout(30):  # Increased from 10 to 30 seconds
                response = await self._session.get(
                    LOGIN_PAGE_URL, headers=self._headers
                )
                if response.status != HTTP_OK:
                    msg = f"Failed to get login page: {response.status}"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg)

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                csrf_element = soup.find(
                    "input", {"name": "__RequestVerificationToken"}
                )
                if not csrf_element or not isinstance(csrf_element, Tag):
                    msg = "CSRF token not found"
                    raise SuperiorPlusPropaneApiClientError(msg)

                csrf_value = csrf_element.get("value")
                if not csrf_value:
                    msg = "CSRF token value not found"
                    raise SuperiorPlusPropaneApiClientError(msg)

                if isinstance(csrf_value, list):
                    csrf_value = csrf_value[0] if csrf_value else None
                    if not csrf_value:
                        msg = "CSRF token value not found"
                        raise SuperiorPlusPropaneApiClientError(msg)

                return str(csrf_value)

        except TimeoutError as exception:
            msg = f"Timeout getting CSRF token: {exception}"
            raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exception

    async def _login(self, csrf_token: str) -> None:
        """Login to Superior Plus Propane."""
        payload = {
            "__RequestVerificationToken": csrf_token,
            "EmailAddress": self._username,
            "Password": self._password,
            "RememberMe": "true",
        }

        try:
            # Login POST request
            async with async_timeout.timeout(30):  # Increased timeout for login
                response = await self._session.post(
                    LOGIN_URL, headers=self._headers, data=payload
                )

                # Check if login was successful by looking at redirect URL
                # If still on login page, authentication failed
                if "Login" in str(response.url) or response.status != HTTP_OK:
                    msg = "Login failed - invalid credentials"
                    raise SuperiorPlusPropaneApiClientAuthenticationError(msg)

            # Navigate through required pages with longer timeouts
            LOGGER.debug("Login successful, navigating to required pages...")

            async with async_timeout.timeout(60):  # Increased timeout for navigation
                await self._session.get(HOME_URL, headers=self._headers)
                LOGGER.debug("Successfully navigated to HOME_URL")

                await self._session.get(CUSTOMERS_URL, headers=self._headers)
                LOGGER.debug("Successfully navigated to CUSTOMERS_URL")

        except TimeoutError as exception:
            msg = f"Timeout during login: {exception}"
            raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exception

    async def _get_tanks_from_page(self) -> list[dict[str, Any]]:
        """Get tank data from the tank page."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(TANK_URL, headers=self._headers)

                # Check if we were redirected to login page (session expired)
                if "Login" in str(response.url):
                    LOGGER.debug("Redirected to login page, session expired")
                    self._authenticated = False
                    raise SuperiorPlusPropaneApiClientAuthenticationError(
                        "Session expired"
                    )

                if response.status != HTTP_OK:
                    msg = f"Failed to get tank page: {response.status}"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg)

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # Check if page contains login form (another indicator of expired session)
                login_form = soup.find("form", {"action": "/Account/Login"})
                if login_form:
                    LOGGER.debug("Login form found on tank page, session expired")
                    self._authenticated = False
                    raise SuperiorPlusPropaneApiClientAuthenticationError(
                        "Session expired"
                    )

                # Find all tank rows
                tank_rows = soup.select("div.tank-row")
                tanks_data = []

                for idx, row in enumerate(tank_rows):
                    tank_data = await self._parse_tank_row(row, idx + 1)
                    if tank_data:
                        tanks_data.append(tank_data)

                if not tanks_data:
                    msg = "No tanks found"
                    raise SuperiorPlusPropaneApiClientError(msg)

                return tanks_data

        except TimeoutError as exception:
            msg = f"Timeout getting tank data: {exception}"
            raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exception

    def _extract_address(self, row: Tag) -> tuple[str, str] | None:
        """Extract and clean address from row."""
        address_element = row.select_one(".col-md-2")
        if not address_element:
            return None

        address_text = address_element.get_text(separator=" ", strip=True)
        address = address_text.split("\n")[0] if "\n" in address_text else address_text
        address = re.sub(r"\s+", " ", address).strip()
        tank_id = slugify(address.lower().replace(" ", "_"))
        return address, tank_id

    def _extract_tank_info(self, row: Tag) -> tuple[str, str]:
        """Extract tank size and type."""
        tank_info_element = row.select_one(".col-md-3")
        tank_size = "unknown"
        tank_type = "unknown"

        if tank_info_element:
            tank_info_text = tank_info_element.get_text()
            size_match = re.search(r"(\d+)\s*gal\.", tank_info_text)
            if size_match:
                tank_size = size_match.group(1)
            if "Propane" in tank_info_text:
                tank_type = "Propane"

        return tank_size, tank_type

    def _extract_level(self, row: Tag) -> str:
        """Extract level percentage from progress bar."""
        progress_bar = row.select_one("div.progress-bar")
        if progress_bar and progress_bar.get("aria-valuenow"):
            value = progress_bar.get("aria-valuenow")
            if isinstance(value, list):
                return value[0] if value else "unknown"
            return str(value) if value else "unknown"
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

    def _extract_price(self, row: Tag) -> str:
        """Extract price per gallon."""
        price_text = row.find(string=re.compile(r"\$\d+\.\d+"))
        if price_text:
            price_match = re.search(r"\$(\d+\.\d+)", str(price_text))
            if price_match:
                return price_match.group(1)
        return "unknown"

    async def _parse_tank_row(
        self, row: Tag, tank_number: int
    ) -> dict[str, Any] | None:
        """Parse a single tank row."""
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
            price_per_gallon = self._extract_price(row)

        except (AttributeError, ValueError, TypeError) as exception:
            LOGGER.warning("Error parsing tank row %d: %s", tank_number, exception)
            return None
        else:
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
                "price_per_gallon": price_per_gallon,
            }

    async def async_test_connection(self) -> bool:
        """Test if we can connect and authenticate."""
        try:
            tanks_data = await self.async_get_tanks_data()
            return len(tanks_data) > 0
        except SuperiorPlusPropaneApiClientAuthenticationError:
            return False
        except SuperiorPlusPropaneApiClientError:
            return False
