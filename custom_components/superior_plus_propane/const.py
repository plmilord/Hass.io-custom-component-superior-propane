"""Constants for superior_plus_propane."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "superior_plus_propane"
ATTRIBUTION = "Data provided by Superior Plus Propane"

# URLs
LOGIN_PAGE_URL = "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F"
LOGIN_URL = "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F"
HOME_URL = "https://mysuperioraccountlogin.com/"
CUSTOMERS_URL = "https://mysuperioraccountlogin.com/Customers"
TANK_URL = "https://mysuperioraccountlogin.com/Tank"

# Default update interval (seconds)
DEFAULT_UPDATE_INTERVAL = 3600  # 1 hour

# Configuration options
CONF_UPDATE_INTERVAL = "update_interval"

# Unit conversions
GALLONS_TO_CUBIC_FEET = 36.39  # Propane gallon to cubic feet conversion (at STP)
