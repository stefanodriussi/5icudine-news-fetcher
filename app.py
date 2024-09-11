# 5IC Udine news fetcher
# 10/09/2024
# Stefano Chittaro - Kitops

# This script allows for automated fetching of "NOTIZIE IN EVIDENZA" from the official website of
# Istituto Comprensivo V - Udine and subsequent announcement via Telegram bot
# It was developed because crucial information for parents is posted there (e.g. strikes) but the school does not provide
# any way to get such information in a notification manner

import requests
import re
import csv
import io
import os
import threading
import time
from bs4 import BeautifulSoup

# Dynamic configuration
telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_BOT_CHATID")
csv_file_path = os.environ.get("CSV_FILE_PATH")
schedule_interval = int(os.getenv("SCHEDULE_INTERVAL_SECONDS", 7200))

# Static configuration
school_url = 'https://5icudine.edu.it'
telegram_url = f'https://api.telegram.org/bot{telegram_bot_token}/sendPhoto'

# Define task schedulation
def schedule_task():
    while True:
        news_fetch()
        time.sleep(schedule_interval)

# Add newspost URL to a defined CSV file
def add_string_to_csv(file_path, string_to_add):
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([string_to_add])

# Check whether newspost URL is already present in the CSV file
# meaning: it has already been announced
def check_and_add_string(file_path, string_to_add):
    with open(file_path, mode='r', newline='') as file:
        reader = csv.reader(file)
        string_found = False
        for row in reader:
            if string_to_add in row:
                string_found = True
                break

    if string_found:
        return 1
    else:
        add_string_to_csv(file_path, string_to_add)
        return 0

# Send request to fetch the HTML source from the school website
response = requests.get(school_url)
html_source = response.text

# Parse the fetched HTML and filter through it to find the <div> element containing the newsposts
soup = BeautifulSoup(html_source, 'html.parser')
articles = soup.find_all("div", "layout-articolo2")

# iterate through the found newsposts, checking they already have been announced (href present in the CSV)
# and, if not, send a telegram image with title and href as caption
def news_fetch():
    print("fetching...")
    for link in reversed(articles):
        # Fetch newsposts details
        link_title = link.find('a').get('title')
        link_href = link.find('a').get('href')
        link_day = link.find_all("span", class_="dataGiorno")[0].get_text()
        link_month = link.find_all("span", class_="dataMese")[0].get_text()
        link_year = link.find_all("span", class_="dataAnno")[0].get_text()

        # This required regexp magic to get the image url from CSS properties
        link_image_url = re.search(r"(?P<url>https?://[^\s]+)\);", link.find_all("div", class_="immagine_post")[0].get("style")).group("url")

        # Check whether the newspost shall be notified via Telegram by checking whether the newspost href is already stored
        # in the CSV file
        shall_notify = check_and_add_string(csv_file_path, link_href)

        # If this has not been notified, then prepare payload, fetch the newspost image and send the Telegram API request
        if (shall_notify==0):
            params = {
                'chat_id': telegram_chat_id,
                'caption': link_title+": "+link_href,
                'parse_mode': 'html'
            }

            remote_image = requests.get(link_image_url)
            photo = io.BytesIO(remote_image.content)
            photo.name = 'img.png'

            files = {
                'photo': photo
            }
            response = requests.post(telegram_url, data=params, files=files)
            if response.status_code == 200:
                print("Message sent successfully: "+link_title)
            else:
                print(f"Failed to send message. Response code: {response.status_code}")
                print(response.text)

# Actual start of the task scheduler
task_thread = threading.Thread(target=schedule_task)
task_thread.start()
