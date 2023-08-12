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
import re
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
BASE_DIR_KEY = "base_dir"
COVER_MATCHERS_KEY = "cover_matchers"
INCLUDE_REGEXES_KEY = "include_regexes"
EXCLUDE_REGEXES_KEY = "exclude_regexes"
UPDATE_SECONDS_KEY = "update_seconds"
SORT_ORDER_KEY = "sort_order"
SORT_ORDER_IN_ORDER = "in_order"
SORT_ORDER_REVERSE = "reverse"
SORT_ORDER_RANDOM = "random"
ORIENTATION_KEY = "orientation"
ORIENTATION_PORTRAIT = "portrait"
ORIENTATION_LANDSCAPE = "landscape"
ORIENTATION_PORTRAIT_FLIPPED = "portrait_flipped"
ORIENTATION_LANDSCAPE_FLIPPED = "landscape_flipped"
DEFAULT_CONFIG_VALUES = {FTP_SERVER_KEY:"", FTP_USER_NAME_KEY:"", FTP_USER_PASSWORD_KEY:"", COVER_MATCHERS_KEY:[{BASE_DIR_KEY:"", INCLUDE_REGEXES_KEY:[".*"], EXCLUDE_REGEXES_KEY:[]}], SORT_ORDER_KEY:SORT_ORDER_RANDOM, UPDATE_SECONDS_KEY:3600, ORIENTATION_KEY:ORIENTATION_PORTRAIT}

logging.basicConfig(level=logging.INFO)

def getRandomCoverImageViaFTP(config_values, previous_cover_path):
    ftp_server = config_values[FTP_SERVER_KEY]
    if (ftp_server == ""):
        raise ValueError("ftp_server not set. Update config.txt")
    ftp_user_name, ftp_user_password = config_values[FTP_USER_NAME_KEY], config_values[FTP_USER_PASSWORD_KEY]
    cover_paths = []
    # Traverse file tree to locate all cover images
    for cover_matcher in config_values[COVER_MATCHERS_KEY]:
        base_mls_list = []
        base_path = cover_matcher[BASE_DIR_KEY]
        with FTP(ftp_server, ftp_user_name, ftp_user_password) as ftp:
            for mls in ftp.mlsd(base_path):
                base_mls_list.append(mls)
            _processPath(cover_matcher, ftp, base_path, base_mls_list, cover_paths)

    if len(cover_paths) == 0:
        logging.debug("Found no cover paths")
        return ("", previous_cover_path)

    index = -1
    sort_order = config_values[SORT_ORDER_KEY]
    found_index = -1
    try:
        found_index = cover_paths.index(previous_cover_path)
    except ValueError:
        found_index = -1

    if sort_order == SORT_ORDER_IN_ORDER:
        index = found_index + 1 if found_index >= 0 else 0
    elif sort_order == SORT_ORDER_REVERSE:
        index = found_index - 1 if found_index >= 0 else len(cover_paths) - 1
    elif sort_order ==  SORT_ORDER_RANDOM:
        index = random.randrange(len(cover_paths))
    else:
        raise ValueError("sort_order not recognized. Update config.txt")

    cover_path = cover_paths[index % len(cover_paths)]
    local_cover_file_name = f"{LOCAL_COVER_BASE_FILE_NAME}.{cover_path.split('.')[-1]}"
    local_cover_path = os.path.join(LOCAL_PATH, local_cover_file_name)
    with FTP(ftp_server, ftp_user_name, ftp_user_password) as ftp:
        try:
            ftp.retrbinary(f"RETR {cover_path}", open(local_cover_path, 'wb').write)
        except Exception as exception:
            logging.error(f"Failed to retrieve file for path {cover_path} due to exception [{exception}]")
            local_cover_path = ""
            cover_path = previous_cover_path
    return (local_cover_path, cover_path)

def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    return [atoi(c) for c in re.split(r'(\d+)', text)]

def _processPath(cover_matcher, ftp, path, mls_list, cover_paths):
    mls_list = sorted(mls_list, key=lambda mls: natural_keys(mls[0]))
    include_regexes, exclude_regexes = cover_matcher[INCLUDE_REGEXES_KEY], cover_matcher[EXCLUDE_REGEXES_KEY]
    matched_pattern = None
    for exclude_pattern in exclude_regexes:
        if re.search(exclude_pattern, path) != None:
            matched_pattern = pattern
            break
    if matched_pattern != None:
        logging.debug(f"Excluding path [{path}] due to matching pattern [{matched_pattern}]")
        return

    if len(mls_list) == 0:
        return
    for mls in mls_list:
        if mls[1]['type'] != 'dir':
            directory_name = os.path.basename(path)
            file_name = mls[0]
            split_file_name = file_name.split('.')
            is_supported_image = len(split_file_name) > 1 and split_file_name[-1] in SUPPORTED_IMAGE_EXTENSIONS
            file_path = os.path.join(path, file_name)
            is_included = False if len(include_regexes) > 0 else True
            for include_pattern in include_regexes:
                if re.search(include_pattern, file_path):
                    is_included = True
                    break
            if is_supported_image and is_included:
                logging.debug(f"appending cover: {file_path}")
                cover_paths.append(file_path)
            continue

        sub_path = os.path.join(path, mls[0])
        sub_mls_list = []
        try:
            for sub_mls in ftp.mlsd(sub_path):
                sub_mls_list.append(sub_mls)
        except:
            logging.error(f"failed to get mlsd for [{sub_path}]")
            continue
        _processPath(cover_matcher, ftp, sub_path, sub_mls_list, cover_paths)


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


def rotateImage(image, config_values):
    rotate_degrees = -1
    orientation = config_values[ORIENTATION_KEY]
    if orientation == ORIENTATION_PORTRAIT:
        rotate_degrees = 0
    elif orientation == ORIENTATION_LANDSCAPE:
        rotate_degrees = 90
    elif orientation == ORIENTATION_PORTRAIT_FLIPPED:
        rotate_degrees = 180
    elif orientation == ORIENTATION_LANDSCAPE_FLIPPED:
        rotate_degrees = 270
    else:
        raise ValueError(f"orientation \"{orientation}\" not recognized")
    return image.rotate(rotate_degrees, expand=True)


def displayImage(image_path, config_values):
    if (not os.path.exists(image_path)):
        logging.error(f"displayImage: no file exists for path {image_path}")
        return
    display = DISPLAY_LIB.EPD()
    display.init()
    with Image.open(image_path) as image:
        image = rotateImage(image, config_values)
        image = fitToDisplay(image, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        display.display(display.getbuffer(image))
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
            displayImage(local_cover_path, config_values)
            previous_cover_path = cover_path
            update_seconds = config_values[UPDATE_SECONDS_KEY]
            logging.debug(f"Sleeping for {update_seconds} seconds")
            time.sleep(update_seconds)
    except KeyboardInterrupt:
        logging.info("Exiting for keyboard interrupt")
        display = DISPLAY_LIB.EPD()
        display.init()
        display.Clear()
        DISPLAY_LIB.epdconfig.module_exit()

if __name__ == "__main__":
    main()
