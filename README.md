# Superior Plus Propane Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/connorgallopo/Superior-Plus-Propane.svg)](https://github.com/connorgallopo/Superior-Plus-Propane/releases)

A custom Home Assistant integration for monitoring **Superior Plus Propane** tanks with automatic consumption tracking for the Energy Dashboard. Seamlessly integrate your propane tank monitoring with your smart home automation.

> **Compatible with Superior Plus Propane's mySuperior customer portal** - Monitor your propane tanks directly in Home Assistant using the same data from your [mySuperior account](https://mysuperioraccountlogin.com/).

## About Superior Plus Propane

[Superior Plus Propane](https://www.superiorpluspropane.com/) has been serving customers since 1922 with over 200 service locations across 22 states. Their **mySuperior** customer portal provides 24/7 access to:
- View fuel levels and tank percentages
- Schedule deliveries
- Manage your account
- Make payments
- Track delivery history

This integration brings all that tank monitoring data directly into your Home Assistant dashboard.

## Features

- **Multi-Tank Support**: Automatically discovers and monitors all tanks on your Superior Plus Propane account
- **Real-Time Monitoring**: Track tank level %, current gallons, capacity, reading dates, and delivery history
- **Energy Dashboard Integration**: Built-in consumption tracking with proper `state_class: total_increasing` for Home Assistant's Energy Dashboard
- **Smart Analytics**: Monitor consumption rates, calculate days since last delivery, and track usage patterns
- **Native HA Integration**: No external scripts, automations, or additional hardware required
- **HACS Compatible**: Easy installation and automatic updates
- **Secure Authentication**: Uses your existing mySuperior portal credentials

## Tank Data Tracked

For each propane tank on your Superior Plus Propane account, the integration provides:

### Primary Metrics
- **Tank Level** (%) - Current fill percentage from tank monitoring system
- **Current Gallons** - Exact gallons currently in tank
- **Tank Capacity** - Total tank size in gallons

### Delivery & Service Information
- **Reading Date** - When the level was last measured by Superior Plus
- **Last Delivery** - Date of most recent propane delivery
- **Days Since Delivery** - Automatically calculated days since last fill
- **Price per Gallon** - Current propane pricing from your account

### Energy Dashboard Integration
- **Total Consumption** (ft³) - Cumulative gas usage with `total_increasing` state class
- **Consumption Rate** (ft³/h) - Current usage rate for trend analysis

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations" 
3. Click the three dots menu → "Custom repositories"
4. Add this repository URL: `https://github.com/connorgallopo/Superior-Plus-Propane`
5. Category: "Integration"
6. Install "Superior Plus Propane" from HACS
7. Restart Home Assistant
8. Go to Settings → Devices & Services → Add Integration
9. Search for "Superior Plus Propane"

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/connorgallopo/Superior-Plus-Propane/releases)
2. Copy the `custom_components/superior_plus_propane` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Add the integration through Settings → Devices & Services → Add Integration

## Configuration

### Prerequisites
- Active Superior Plus Propane account with propane service
- Registered [mySuperior portal account](https://mysuperioraccountlogin.com/)
- Email address and password for your mySuperior account

### Setup Steps

1. **Add Integration**: Go to Settings → Devices & Services → Add Integration
2. **Search**: Look for "Superior Plus Propane"
3. **Credentials**: Enter your mySuperior portal email and password
4. **Update Interval**: Choose update frequency (default: 1 hour, minimum: 5 minutes)
5. **Auto-Discovery**: The integration will automatically find all tanks on your account

### Configuration Options

- **Email Address**: Your mySuperior portal login email
- **Password**: Your mySuperior account password  
- **Update Interval**: How often to check for updates (300-86400 seconds)

> **Note**: This integration uses the same login credentials as the [mySuperior customer portal](https://mysuperioraccountlogin.com/). If you can log in there, you can use this integration.

## Entity Naming

Entities are automatically created using your tank's service address for easy identification:

```
sensor.superior_plus_propane_123_main_street_level
sensor.superior_plus_propane_123_main_street_gallons
sensor.superior_plus_propane_123_main_street_capacity
sensor.superior_plus_propane_123_main_street_consumption_total
sensor.superior_plus_propane_123_main_street_consumption_rate
sensor.superior_plus_propane_123_main_street_days_since_delivery
```

## Energy Dashboard Integration

The integration automatically creates consumption sensors compatible with Home Assistant's Energy Dashboard:

1. Go to Settings → Dashboards → Energy
2. Add a Gas source
3. Select your tank's "Total Consumption" sensor
4. View your propane usage alongside other energy sources

The integration intelligently tracks propane consumption by:
- Monitoring gallon decreases between readings
- Converting gallons to cubic feet (36.39 ft³ per gallon)
- Validating realistic consumption patterns
- Maintaining totals across Home Assistant restarts

## Device Organization

Each propane tank appears as a separate device in Home Assistant:
- **Device Name**: "Propane Tank - [Service Address]"
- **Manufacturer**: Superior Plus Propane
- **Model**: Tank capacity (e.g., "100 Gallon Tank")
- **All Sensors**: Grouped under the respective tank device

## Automation Examples

### Low Tank Alert
```yaml
automation:
  - alias: "Propane Tank Low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.superior_plus_propane_main_house_level
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Main house propane tank is at {{ states('sensor.superior_plus_propane_main_house_level') }}%"
```

### Delivery Reminder
```yaml
automation:
  - alias: "Propane Delivery Overdue"
    trigger:
      - platform: numeric_state
        entity_id: sensor.superior_plus_propane_main_house_days_since_delivery
        above: 365
    action:
      - service: persistent_notification.create
        data:
          message: "It's been over a year since your last propane delivery"
```

## Troubleshooting

### Authentication Issues
- Verify your email and password work on [mysuperioraccountlogin.com](https://mysuperioraccountlogin.com/)
- Ensure your account has active propane service
- Check for any account restrictions or two-factor authentication

### No Tank Data
- Confirm your tanks appear in the mySuperior portal
- Verify you have active propane service with Superior Plus
- Check that tank monitoring is enabled on your account

### Missing Sensors
- Review Home Assistant logs: Settings → System → Logs
- Ensure the integration setup completed without errors
- Try removing and re-adding the integration

### Update Issues
- Check your internet connection
- Verify the mySuperior portal is accessible
- Consider increasing the update interval if you're experiencing rate limiting

## Technical Details

### Data Sources
All data is retrieved from Superior Plus Propane's official customer systems:
- Tank levels and readings from the mySuperior portal
- Delivery history and service information
- Account details for device identification

### Architecture
- **Async Implementation**: Fully asynchronous following Home Assistant best practices
- **API Client**: Handles secure authentication and data retrieval
- **Data Coordinator**: Manages updates and consumption calculations  
- **Entity Platform**: Individual sensors for each tank metric
- **Storage**: Persistent consumption tracking across restarts

### Privacy & Security
- Credentials are stored securely using Home Assistant's credential storage
- No data is transmitted to third parties
- All communication is directly with Superior Plus Propane's servers

## Supported Regions

This integration works with Superior Plus Propane service areas across:
- 22 U.S. States where Superior Plus Propane operates
- 200+ service locations nationwide
- All customers with mySuperior portal access

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper testing
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### Development Setup
```bash
# Clone the repository
git clone https://github.com/connorgallopo/Superior-Plus-Propane.git
cd Superior-Plus-Propane

# Install development dependencies
pip install -r requirements.txt

# Run linting
ruff check .
```

## Support

- **Issues**: [GitHub Issues](https://github.com/connorgallopo/Superior-Plus-Propane/issues)
- **Discussions**: [GitHub Discussions](https://github.com/connorgallopo/Superior-Plus-Propane/discussions)
- **Superior Plus Support**: [Contact Superior Plus Propane](https://www.superiorpluspropane.com/) for account-related issues

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with, endorsed by, or officially supported by Superior Plus Propane. It is an independent project that interfaces with publicly available customer portal data. Use at your own risk.

**Superior Plus Propane** and **mySuperior** are trademarks of Superior Plus LP.

---

### Keywords for Discovery
*propane, propane tank, propane monitoring, Superior Plus, Superior Plus Propane, mySuperior, tank level, propane delivery, energy dashboard, home assistant, smart home, propane automation, tank monitoring, fuel monitoring, propane sensor*
