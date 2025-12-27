<span align="center">

<a href="https://github.com/plmilord/Hass.io-custom-component-superior-propane"><img src="https://raw.githubusercontent.com/plmilord/Hass.io-custom-component-superior-propane/master/images/icon.png" width="150"></a>

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/plmilord/Hass.io-custom-component-superior-propane.svg)](https://GitHub.com/plmilord/Hass.io-custom-component-superior-propane/releases/)
[![HA integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.superior_propane.total)](https://analytics.home-assistant.io/custom_integrations.json)

# Home Assistant custom component - Superior Propane

</span>

A custom Home Assistant integration for monitoring **Superior Propane** tanks with automatic consumption tracking for the Energy Dashboard. Seamlessly integrate your propane tank monitoring with your smart home automation.

> **Compatible with Superior Propane's mySuperior customer portal** - Monitor your propane tanks directly in Home Assistant using the same data from your [mySuperior account](https://mysuperior.superiorpropane.com/account/individualLogin).

## About Superior Propane

[Superior Propane](https://mysuperior.superiorpropane.com/) has been serving customers since 1922 in Canada. Their **mySuperior** customer portal provides 24/7 access to:
- View fuel levels and tank percentages
- Schedule deliveries
- Manage your account
- Make payments
- Track delivery history

This integration brings all that tank monitoring data directly into your Home Assistant dashboard.

## Features

- **Multi-Tank Support**: Automatically discovers and monitors all tanks on your Superior Propane account
- **Real-Time Monitoring**: Track tank level %, current volume, capacity, reading dates, and delivery history
- **Energy Dashboard Integration**: Built-in consumption tracking with proper `state_class: total_increasing` for Home Assistant's Energy Dashboard
- **Smart Analytics**: Monitor consumption rates, calculate days since last delivery, and track usage patterns
- **Native HA Integration**: No external scripts, automations, or additional hardware required
- **HACS Compatible**: Easy installation and automatic updates
- **Secure Authentication**: Uses your existing mySuperior portal credentials

## Tank Data Tracked

For each propane tank on your Superior Propane account, the integration provides:

### Key Indicators
- **Level** (%) - Current tank fill percentage according to the monitoring system
- **Current Volume** (L) - Exact volume currently in the tank in your unit system

### Delivery and Maintenance Information
- **Last SMART Tank Update** - Date of last level measurement by Superior Propane
- **Last Delivery** - Date of last propane delivery
- **Number of Days Since Delivery** - Automatically calculated number of days since last refill

### Energy Dashboard Integration
- **Total Consumption** (m³) - Cumulative gas consumption with the "total_increasing" status class
- **Consumption Rate** (m³/h) - Current consumption rate for trend analysis
- **Average Price Paid** (CAD/m³) - Average price paid for propane deliveries from your account

## What you need

- Active Superior Propane account with propane service
- Registered [mySuperior account](https://mysuperior.superiorpropane.com/account/individualLogin)
- Email address and password for your mySuperior account

## Installation

You can install this integration via [HACS](#hacs) or [manually](#manual).

### HACS

Search for the Superior Propane integration and choose install. Reboot Home Assistant and configure the Superior Propane integration via the integrations page or press the blue button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=superior_propane)

### Manual

Copy the `custom_components/superior_propane` to your custom_components folder. Reboot Home Assistant and configure the Superior Propane integration via the integrations page or press the blue button below.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=superior_propane)

## Task List

### To do

- [ ] Ability to configure this custom component via entries in the configuration.yaml file
- [ ] Adjust refresh rates based on reading frequency
- [ ] Add delivery switch when 'adds_delivery_date' is not declared
- [ ] Convert gas consumption units from m³ to liters of liquid

### Completed

- [x] Validated proper operation when there is more than one tank in the customer account

## Inspiration / Credits

- https://github.com/connorgallopo/Superior-Plus-Propane | Forked project, initial inspiration!
