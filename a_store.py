from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import datetime
import random
import argparse
import logging

URL = "url of customer review page"  # TODO: paste the actual url


def extract(soup, total_sizes, total_dates, total_ratings, total_titles, total_bodies, earliest=None):
    reviews = soup.find_all("div", {"data-hook": "review"})
    for review in reviews:
        date_raw = review.find("span", {"data-hook": "review-date"})
        date = re.findall("\\S+\\s+\\d+,\\s+\\d+$", date_raw.text)[0]
        if earliest and datetime.datetime.strptime(date, "%B %d, %Y").date() < earliest:
            return False
        total_dates.append(date)
        size = review.find("a", {"data-hook": "format-strip"})
        total_sizes.append(size.text.replace("Size: ", "") if size else None)
        rating = review.find("i", {"data-hook": "review-star-rating"})
        total_ratings.append(int(rating.text[0]) if rating else None)
        title = review.find("a", {"data-hook": "review-title"})
        total_titles.append(title.text.strip() if title else None)
        body = review.find("span", {"data-hook": "review-body"})
        total_bodies.append(body.text.strip() if body else None)
    return True


def parse_product(driver, url, day_lim=None):
    _ = input("Pressen ENTER to proceed")
    driver.get(url)
    prev_url = driver.current_url
    time.sleep(2 + random.random())
    try:
        drop_down = Select(driver.find_element_by_class_name("a-native-dropdown.a-declarative"))
    except NoSuchElementException:
        return None
    drop_down.select_by_value("recent")
    time.sleep(1 + random.random())
    soup = BeautifulSoup(driver.page_source, "html.parser")
    earliest = datetime.date.today() - datetime.timedelta(days=day_lim) if day_lim else None
    total_sizes, total_dates, total_ratings, total_titles, total_bodies = [], [], [], [], []
    to_continue = extract(soup, total_sizes, total_dates, total_ratings, total_titles, total_bodies, earliest)

    while to_continue:
        try:
            next_link = driver.find_element_by_class_name("a-last")
        except NoSuchElementException:
            break
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
        curr_url = driver.current_url
        if curr_url == prev_url:
            break
        soup = BeautifulSoup(driver.page_source, "html.parser")
        to_continue = extract(soup, total_sizes, total_dates, total_ratings, total_titles, total_bodies, earliest)
        prev_url = curr_url

    return pd.DataFrame({"Size": total_sizes, "Date": total_dates, "Rating": total_ratings,
                         "Title": total_titles, "Body": total_bodies})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews for product on Astore")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Astore_Reviews",
                        help="Name of output .xlsx file (default Astore_Reviews)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    DRIVER = webdriver.Chrome(".\\chromedriver")
    result = parse_product(DRIVER, URL, args.days)
    DRIVER.close()
    result.to_excel("outputs\\" + args.output + ".xlsx", header=True, index=False)
    logging.info("Process completed! Extracted {} reviews".format(len(result)))
