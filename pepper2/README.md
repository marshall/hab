PEPPER-2 On Board Computer
===

## Components

* BeagleBone Black
* Xtend900 1w radio transceiver
* [SSD1306 128x32 OLED SPI display](https://github.com/adafruit/Adafruit_SSD1306)
* Adafruit Ultimate GPS Breakout v3
* Virtuabotix DHT22 Temp & Humidity module (internal)
* DS18B20 temperature sensor (external)

## Wiring

<table>
    <tr><th>Component</th><th>Label</th><th>BeagleBone Black pin</th></tr>
    <tr><td>Adafruit GPS</td><td>RX</td><td>P9_24 - UART1_TXD</td></tr>
    <tr><td>Adafruit GPS</td><td>TX</td><td>P9_26 - UART1_RXD</td></tr>
    <tr><td>Xtend900</td><td>DI</td><td>P8_37 - UART5_TXD</td></tr>
    <tr><td>Xtend900</td><td>DO</td><td>P8_38 - UART5_RXD</td></tr>
    <tr><td>SSD1306</td><td>CS</td><td>P9_17 - SPI0_CS0</td></tr>
    <tr><td>SSD1306</td><td>RST</td><td>P9_13</td></tr>
    <tr><td>SSD1306</td><td>D/C</td><td>P9_15</td></tr>
    <tr><td>SSD1306</td><td>CLK</td><td>P9_22 - SPI0_SCLK</td></tr>
    <tr><td>SSD1306</td><td>DATA</td><td>P9_18 - SPI0_D1</td></tr>
    <tr><td>DHT22</td><td>DTA</td><td>P8_17</td></tr>
    <tr><td>DS18B20</td><td>DTA</td><td>P9_28</td></tr>
</table>

## Voltage

<table>
    <tr><th>Component</th><th>Voltage</th></tr>
    <tr><td>DHT22</td><td>3.3v</td></tr>
    <tr><td>DS18B20</td><td>3.3v</td></tr>
    <tr><td>SSD1306</td><td>3.3v</td></tr>
    <tr><td>Adafruit GPS</td><td>3.3v</td></tr>
    <tr><td>Xtend900</td><td>5v - VDD_5V / P9_5</td></tr>
</table>
