"""Constants for Superior Propane."""

from homeassistant.const import CURRENCY_DOLLAR
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "superior_propane"
ATTRIBUTION = "Data provided by Superior Propane"

# URLs
DASHBOARD_URL = "https://mysuperior.superiorpropane.com/dashboard"
LOGIN_PAGE_URL = "https://mysuperior.superiorpropane.com/account/individualLogin"
LOGIN_URL = "https://mysuperior.superiorpropane.com/account/loginFirst"
ORDERS_URL = "https://mysuperior.superiorpropane.com/myaccount/getAllOrders"
TANK_DATA_URL = "https://mysuperior.superiorpropane.com/myaccount/readTanks"

# Default update interval (seconds)
DEFAULT_UPDATE_INTERVAL = 7200

# Configuration options
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MIN_THRESHOLD = "min_consumption_threshold"
CONF_MAX_THRESHOLD = "max_consumption_threshold"
CONF_ADAPTIVE_THRESHOLDS = "adaptive_thresholds"

# Consumption threshold defaults
# These are percentages of tank capacity per hour
MIN_CONSUMPTION_PERCENTAGE = 0.0001  # 0.01% of tank per hour (pilot lights)
MAX_CONSUMPTION_PERCENTAGE = 0.05    # 5% of tank per hour (extreme usage)

# Absolute bounds for safety
ABSOLUTE_MIN_CONSUMPTION = 0.01  # Minimum 0.01 liters
ABSOLUTE_MAX_CONSUMPTION = 50.0  # Maximum 50 liters per reading

# Default static thresholds (for backwards compatibility)
DEFAULT_MIN_CONSUMPTION_LITERS = 0.01  # Lowered from 0.5
DEFAULT_MAX_CONSUMPTION_LITERS = 25.0  # Raised from 10.0

# Data validation
DATA_VALIDATION_TOLERANCE = 0.10  # 10% tolerance for liters vs percentage validation
TANK_SIZE_MIN = 20.0   # Minimum reasonable tank size
TANK_SIZE_MAX = 2000.0 # Maximum reasonable tank size

# Unit conversions
# 1 litre of liquid propane = ~0.2723 cubic meters of propane gas (at 60°F, 14.73 psi)
# This is the standard conversion factor used in the propane industry, derived from 1 US gallon = 36.39 cubic feet
LITERS_TO_CUBIC_METERS = 0.272297  # Propane litre to cubic meters conversion (at STP)
SECONDS_PER_HOUR = 3600  # Seconds in an hour
PERCENT_MULTIPLIER = 100.0  # For percentage calculations

# Unit for average price
CURRENCY_PER_LITER = f"{CURRENCY_DOLLAR}/L"

# Retry settings for API
MAX_API_RETRIES = 4  # Maximum number of API retries
RETRY_DELAY_SECONDS = 60  # Delay in seconds between each retry

# Retry interval in case of error
RETRY_INTERVAL = 300  # 5 minutes