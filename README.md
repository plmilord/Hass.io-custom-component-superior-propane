# Superior Plus Propane Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/connorgallopo/Superior-Plus-Propane.svg)](https://github.com/connorgallopo/Superior-Plus-Propane/releases)

A custom Home Assistant integration for monitoring Superior Plus Propane tanks with automatic consumption tracking for the Energy Dashboard.

## Features

- **Multi-Tank Support**: Automatically discovers and monitors all tanks on your account
- **Comprehensive Monitoring**: Track tank level %, current gallons, capacity, reading dates, delivery history
- **Energy Dashboard Integration**: Built-in consumption tracking with proper `state_class: total_increasing`
- **Usage Analytics**: Monitor consumption rates and calculate days since last delivery
- **Native HA Integration**: No external scripts or automations required
- **HACS Compatible**: Easy installation and updates

## Tank Data Tracked

For each propane tank, the integration provides:

### Primary Metrics
- **Tank Level** (%) - Current fill percentage
- **Current Gallons** - Gallons currently in tank
- **Tank Capacity** - Total tank size in gallons

### Delivery & Timing
- **Reading Date** - When the level was last measured
- **Last Delivery** - Date of most recent propane delivery
- **Days Since Delivery** - Calculated days since last fill
- **Price per Gallon** - Current propane pricing

### Energy Dashboard Integration
- **Total Consumption** (ft³) - Cumulative gas usage with `total_increasing` state class
- **Consumption Rate** (ft³/h) - Current usage rate

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Install "Superior Plus Propane" from HACS
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "Superior Plus Propane"

### Manual Installation

1. Copy the `custom_components/superior_plus_propane` folder to your `custom_components` directory
2. Restart Home Assistant
3. Add the integration through the UI

## Configuration

1. **Add Integration**: Go to Settings → Devices & Services → Add Integration
2. **Search**: Look for "Superior Plus Propane"
3. **Credentials**: Enter your Superior Plus Propane account email and password
4. **Update Interval**: Choose update frequency (default: 1 hour, minimum: 5 minutes)
5. **Discovery**: The integration will automatically find all tanks on your account

### Configuration Options

- **Email Address**: Your Superior Plus Propane login email
- **Password**: Your account password
- **Update Interval**: How often to check for updates (300-86400 seconds)

## Entity Naming

Entities are automatically created using your tank's address for easy identification:

```
sensor.superior_plus_propane_123_main_street_level
sensor.superior_plus_propane_123_main_street_gallons
sensor.superior_plus_propane_123_main_street_capacity
sensor.superior_plus_propane_123_main_street_consumption_total
```

## Energy Dashboard

The integration automatically creates consumption sensors compatible with Home Assistant's Energy Dashboard:

1. Go to Settings → Dashboards → Energy
2. Add a Gas source
3. Select your tank's "Total Consumption" sensor
4. The integration tracks usage in cubic feet with proper state classes

## Device Organization

Each tank appears as a separate device in Home Assistant with:
- **Device Name**: "Propane Tank - [Address]"
- **Manufacturer**: Superior Plus Propane
- **All Sensors**: Grouped under the tank device

## Consumption Tracking

The integration intelligently tracks propane consumption:

- **Automatic Calculation**: Monitors gallon decreases between readings
- **Validation**: Only counts realistic consumption (0.1-15 gallons per update)
- **Unit Conversion**: Converts gallons to cubic feet for energy dashboard
- **Persistence**: Maintains consumption totals across Home Assistant restarts

## Troubleshooting

### Authentication Issues
- Verify your email and password are correct
- Check that you can log in to the Superior Plus website manually
- Some accounts may have two-factor authentication which isn't supported

### No Tank Data
- Ensure your account has active propane tanks
- Check that tanks appear when you log in to the website
- Verify the integration has completed its first data fetch

### Missing Sensors
- Check that the integration setup completed successfully
- Look for any error messages in Settings → System → Logs
- Try removing and re-adding the integration

## Technical Details

### Architecture
- **API Client**: Handles website authentication and data scraping
- **Data Coordinator**: Manages updates and consumption calculations
- **Sensors**: Individual entities for each tank metric
- **Async**: Fully async implementation following HA best practices

### Data Sources
All data is scraped from the Superior Plus Propane customer portal:
- Tank levels and readings from the main tanks page
- Delivery history and pricing information
- Account information for device naming

### Update Frequency
- **Default**: 1 hour (matches typical propane monitoring needs)
- **Configurable**: 5 minutes to 24 hours
- **Efficient**: Only processes changed data

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Superior Plus Propane. Use at your own risk.
