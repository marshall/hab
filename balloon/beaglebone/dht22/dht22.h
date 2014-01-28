/*
 * dht22.h - support for the DHT22 temperature and humidity sensor
 *
 * Copyright (c) 2014 Marshall Culpepper
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 *
 * For further information, see the Documentation/hwmon/sht15 file.
 */

/**
 * struct dht22_platform_data - dht22 connectivity info
 * @gpio_data: no. of gpio to which bidirectional data line is
 *             connected.
 * @checksum:  flag to indicate the checksum should be validated.
 */
struct dht22_platform_data {
    int gpio_data;
    bool checksum;
};
