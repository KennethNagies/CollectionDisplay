# Collection Display

A system for displaying cover art and other images from a  digital collection (Essentially one of those digital picture frames but tailored for my media collection).

## Setup (Raspberry Pi OS):
1. Enable SPI
   - `sudo raspi-config` -> Interface Options -> SPI -> yes
2. Install python dependencies:
   - `sudo apt-get install python3-pip python3-pil python3-numpy`
3. Install pip modules:
   -  `pip3 install RPi.GPIO spidev waveshare-epaper pillow`
4. Reboot

## Usage
1. Run CollectionDisplay.py once to generate an empty config file
2. Fill out config.json
3. Run CollectionDisplay.py
