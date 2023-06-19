#!/usr/bin/python
# -*- coding:utf-8 -*-
import argparse
import sys
import os
import logging
import epaper
import time
from PIL import Image
import traceback
import random
from ftplib import FTP
import json
from collections import deque

DISPLAY_WIDTH = 448
DISPLAY_HEIGHT = 600
LOCAL_PATH = os.path.dirname(os.path.realpath(__file__))
LOCAL_COVER_BASE_FILE_NAME = "cover"
CONFIG_FILE_NAME = "config.txt"
BASE_GAMES_DIR = "Media/Games"
COVERS_DIR_NAME = "Covers"
DISPLAY_LIB = epaper.epaper("epd5in65f")
SUPPORTED_IMAGE_EXTENSIONS = {"jpg", "bmp", "png"}

FTP_SERVER_KEY = "ftp_server"
FTP_USER_NAME_KEY = "ftp_user_name"
FTP_USER_PASSWORD_KEY = "ftp_user_password"
BASE_DIRS_KEY = "base_dirs"
COVER_DIRS_KEY = "cover_dirs"
INCLUDE_KEY = "include"
EXCLUDE_KEY = "exclude"
DEFAULT_CONFIG_VALUES = {FTP_SERVER_KEY:"", FTP_USER_NAME_KEY:"", FTP_USER_PASSWORD_KEY:"", BASE_DIRS_KEY:[], COVER_DIRS_KEY:[], INCLUDE_KEY:[], EXCLUDE_KEY:[]}

logging.basicConfig(level=logging.INFO)

def getRandomCoverImageViaFTP(config_values, previous_cover_path):
    ftp_server = config_values[FTP_SERVER_KEY]
    if (ftp_server == ""):
        raise ValueError("ftp_server not set. Update config.txt")
    ftp_user_name, ftp_user_password = config_values[FTP_USER_NAME_KEY], config_values[FTP_USER_PASSWORD_KEY]
    with FTP(ftp_server, ftp_user_name, ftp_user_password) as ftp:
        cover_paths = []

        # Traverse file tree to locate all cover images
        for base_path in config_values[BASE_DIRS_KEY]:
            base_mls_list = []
            for mls in ftp.mlsd(base_path):
                base_mls_list.append(mls)
            _processPath(config_values, ftp, base_path, base_mls_list, cover_paths)

        if len(cover_paths) == 0:
            return ("", previous_cover_path)

        rand_index = random.randrange(len(cover_paths))
        cover_path = cover_paths[rand_index]
        if (cover_path == previous_cover_path):
            rand_index = (rand_index + 1) % len(cover_paths)
            cover_path = cover_paths[rand_index]

        local_cover_file_name = f"{LOCAL_COVER_BASE_FILE_NAME}.{cover_path.split('.')[-1]}"
        local_cover_path = os.path.join(LOCAL_PATH, local_cover_file_name)
        try:
            ftp.retrbinary(f"RETR {cover_path}", open(local_cover_path, 'wb').write)
        except:
            logging.error(f"Failed to retrieve file")
            local_cover_path = ""
            cover_path = previous_cover_path
    return (local_cover_path, cover_path)

def _processPath(config_values, ftp, path, mls_list, cover_paths):
    include_list, exclude_list = config_values[INCLUDE_KEY], config_values[EXCLUDE_KEY]
    for exclude_string in exclude_list:
        if exclude_string in path:
            logging.debug(f"excluding path [{path}] due to exclude string \"{exclude_string}\"")
            return
    if len(mls_list) == 0:
        return
    for mls in mls_list:
        if mls[1]['type'] != 'dir':
            directory_name = os.path.basename(path)
            is_cover_dir = directory_name in config_values[COVER_DIRS_KEY]
            file_name = mls[0]
            split_file_name = file_name.split('.')
            is_supported_image = len(split_file_name) > 1 and split_file_name[-1] in SUPPORTED_IMAGE_EXTENSIONS
            is_included = len(include_list) == 0
            file_path = os.path.join(path, file_name)
            for include_string in include_list:
                if include_string in file_path:
                    is_included = True
                    break
            if is_cover_dir and is_supported_image and is_included:
                logging.debug(f"appending cover: {file_path}")
                cover_paths.append(file_path)
            continue

        sub_path = os.path.join(path, mls[0])
        sub_mls_list = []
        for sub_mls in ftp.mlsd(sub_path):
            sub_mls_list.append(sub_mls)
        _processPath(config_values, ftp, sub_path, sub_mls_list, cover_paths)


def getRandomLocalCoverPath(previous_cover_path):
    cover_paths = []
    for directory in os.walk(IMAGES_DIR):
        directory_name = directory[0]
        local_cover_paths = []
        for file_name in directory[2]:
            cover_path = os.path.join(directory_name, file_name)
            local_cover_paths.append(cover_path)
        cover_paths.extend(local_cover_paths)

    rand_index = random.randrange(len(cover_paths))
    cover_path = cover_paths[rand_index]
    if (cover_path == previous_cover_path):
        new_index = (rand_index + 1) % len(cover_paths)
        cover_path = cover_paths[new_index]

    return cover_path


def fitToDisplay(image, display_size):
    image_width, image_height = image.size
    image_ratio = image_width / image_height
    display_width, display_height = display_size
    width_diff = display_width - image_width
    resize_width, resize_height = (display_width, int(display_width / image_ratio))
    if (resize_height > display_height):
        height_diff = display_height - image_height
        resize_width, resize_height = (int(display_height * image_ratio), display_height)

    left_padding = int((display_width - resize_width) / 2)
    top_padding = int((display_height - resize_height) / 2)
    fit_image = Image.new(image.mode, display_size, (0, 0, 0))
    fit_image.paste(image.resize((resize_width, resize_height)), (left_padding, top_padding))
    return fit_image


def displayImage(image_path):
    if (not os.path.exists(image_path)):
        logging.error(f"displayImage: no file exists for path {image_path}")
        return
    display = DISPLAY_LIB.EPD()
    display.init()
    with Image.open(image_path) as image:
        with fitToDisplay(image, (DISPLAY_WIDTH, DISPLAY_HEIGHT)) as fit_image:
            display.display(display.getbuffer(fit_image))
    display.sleep()

def createConfig():
    with open(os.path.join(LOCAL_PATH, CONFIG_FILE_NAME), 'w', encoding="utf-8") as config_file:
        json.dump(DEFAULT_CONFIG_VALUES, config_file, indent=4)

def readConfig():
    with open(os.path.join(LOCAL_PATH, CONFIG_FILE_NAME), 'r', encoding="utf-8") as config_file:
        config_values = json.load(config_file)
    logging.debug(config_values)
    return config_values

def main():
    if (not os.path.exists(os.path.join(LOCAL_PATH, CONFIG_FILE_NAME))):
        createConfig()
        print("Config file created. Fill it out and run again")
        return

    config_values = readConfig()
    try:
        previous_cover_path = ""
        while (True):
            for extension in SUPPORTED_IMAGE_EXTENSIONS:
                old_cover_path = os.path.join(LOCAL_PATH, f"{LOCAL_COVER_BASE_FILE_NAME}.{extension}")
                if (os.path.exists(old_cover_path)):
                    os.remove(old_cover_path)
            local_cover_path, cover_path = getRandomCoverImageViaFTP(config_values, previous_cover_path)
            logging.debug(f"Displaying: {cover_path}")
            displayImage(local_cover_path)
            previous_cover_path = cover_path
            time.sleep(300)
    except KeyboardInterrupt:
        logging.info("Exiting for keyboard interrupt")
        display = DISPLAY_LIB.EPD()
        display.init()
        display.Clear()
        DISPLAY_LIB.epdconfig.module_exit()

if __name__ == "__main__":
    main()
