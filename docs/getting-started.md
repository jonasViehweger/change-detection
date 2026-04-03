# Getting Started

This guide will help you set up and start monitoring changes in satellite time series data.

## Registration

No formal registration is necessary. All that is necessary is an account with [Copernicus Dataspace Ecosystem](https://dataspace.copernicus.eu/) and a valid set of Sentinel Hub Client ID and Secret.

See [this guide](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html#registering-oauth-client) on how to get your Oauth client ID and Secret.
With these you can use your free CDSE quota to create and monitor any area in the world.

Once you have the Client ID and Secret ready, head over to [the log in page](https://login.de) and enter the dashboard.

## Overview

![Overview page](./assets/screenshots/overview-empty-light.png#only-light)
![Overview page](./assets/screenshots/overview-empty-dark.png#only-dark)

Once logged in you will be able to see the overview. If it is your first time logging in, this overview should be empty. So now let's start monitoring our first area by clicking on "Create New Monitor" on the top right.

### Creating a new monitor

This will bring you to a creation wizard.

![Creation Wizard](./assets/screenshots/wizard-step-1-light.png#only-light)
![Creation Wizard](./assets/screenshots/wizard-step-1-dark.png#only-dark)

#### AOI

In this creation wizard we first need to define our area of interest (AOI) that we want to monitor.

You can either supply a GeoJSON file or draw a polygon if you do not have a GeoJSON file ready.

!!! info

    The GeoJSON must have a column which defines a unique ID for each polygon

#### Resolution

Then you need to pick a monitoring resolution. The monitoring resolution will determine the minimum size of changes that will be able to be tracked. The used Sentinel 2 data is limited to a minimum resolution of 10 m per pixel, however if only very large changes are expected you can save processing costs and monitor larger areas by setting a coarser resolution of up to 100 m per pixel.

!!! info

    Due to the used cloud processing tool, AOIs are limited to 2500x2500 pixels. This means that at the highest resolution of 10 m per pixel each Polygon is restricted to a maximum extent of 2.5 km height by 2.5km width.

#### Monitoring sensitivity and confirmation period

The monitoring sensitivity sets how sensitive the monitoring should be. The lower the sensitivity the more false alarms there can be. If you only want to monitor very large changes it can be possible to further decrease the sensitivity.

Due to the nature of satellite data, clouds or other image artifacts can trigger the monitoring. To decrease the impact of those artifacts, the confirmation period exists. It specifies for how many subsequent satellite acquisitions a change needs to persist to actually be confirmed as a change.

The defaults should be fine for most applications.

#### Monitoring start

![Creation Wizard](./assets/screenshots/wizard-step-2-light.png#only-light)
![Creation Wizard](./assets/screenshots/wizard-step-2-dark.png#only-dark)

In the next step you set the start of the monitoring. This is usually the current day to start monitoring for the future. However to be able to test how the system performs on areas where you know a change you would like to monitor has already happened, the start date can also be set to a date in the past.

#### Name

Finally just give a descriptive name to your monitor and you will be good to go.

### Monitor overview

![Creation Wizard](./assets/screenshots/overview-initializing-light.png#only-light)
![Creation Wizard](./assets/screenshots/overview-initializing-dark.png#only-dark)

In the monitoring overview your newly created monitor should now be visible. Right after creation it is getting initialized. Depending on how many AOIs are monitored, this initialization might take a few minutes. Refresh the overview page to see if it is finished.

![Creation Wizard](./assets/screenshots/overview-after-init-light.png#only-light)
![Creation Wizard](./assets/screenshots/overview-after-init-dark.png#only-dark)

Once the initialization is finished, the status changes to `INITIALIZED`. If the monitoring start of your monitor is in the past you can now bring your monitor up to date. For this you can use the update button on the right hand side of the column.

![Creation Wizard](./assets/screenshots/overview-updating-light.png#only-light)
![Creation Wizard](./assets/screenshots/overview-updating-dark.png#only-dark)

Once the update is done you can see in the overview if any changes happened during that time. If there were changes, the disturbed area will be red and show total disturbed area as well as percentage of monitored area which was disturbed.

![Creation Wizard](./assets/screenshots/overview-monitored-light.png#only-light)
![Creation Wizard](./assets/screenshots/overview-monitored-dark.png#only-dark)

You can have a more detailed look at what happened in the detail view for the monitor which you can view by clicking on the row.

### Monitor detail

![Creation Wizard](./assets/screenshots/detail-light.png#only-light)
![Creation Wizard](./assets/screenshots/detail-dark.png#only-dark)

The Detail view is split in two major parts.

#### Disturbance Timeline

The disturbance timeline is visible on the left. It shows a timeline for each Polygon. By default it shows a yearly view split into weeks. For each week it shows if there was a cloud free satellite acquisition in that week. If there wasn't an acquisition the week is colored in grey. If there was an acquisition, it shows if a NEW disturbance was detected that week. If not, the bar is green, if yes it is colored red or orange based on how much area was disturbed. You can click each bar to see the satellite image which was acquired in that week.

!!! info

    Once an area was disturbed, it is removed from the monitoring. Afterwards only areas that are newly disturbed are flagged in the disturbance timeline

#### Satellite view

On the right hand side is an interactive satellite view. By default it shows the most recent cloud free acquisition for the monitored area and all pixels which the monitor flagged as possible disturbances. You can toggle these disturbances in the top right by clicking on "Disturbed Areas".

Once you click on a bar, it will show the satellite image from that date and ONLY the newly disturbed pixels in red which were added on this date.

In the top right you also have the option to interactively apply a forest disturbance classification to the currently displayed satellite image. The classification gives a first idea on what caused the disturbance. The classes are bark beetle (orange), wildfire (red), clear cut (grey) and windthrow (blue). See [here](https://custom-scripts.sentinel-hub.com/sentinel-2/forest_disturbance_classification/) for more information on this classification.
