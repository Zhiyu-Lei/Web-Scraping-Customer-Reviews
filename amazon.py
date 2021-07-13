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
import json
from review_classification import predict_labels

TAGs = ["sound", "no cooling", "condensate drain issues", "8.8 error code", "missing parts", "used unit", "wifi"]


def extract(soup, models, descriptions, dates, ratings, titles, bodies, images, badges, earliest=None):
    reviews = soup.find_all("div", {"data-hook": "review"})
    for review in reviews:
        date = re.findall("\\S+\\s+\\d+,\\s+\\d+$", review.find("span", {"data-hook": "review-date"}).text)[0]
        if earliest and datetime.datetime.strptime(date, "%B %d, %Y").date() < earliest:
            return False
        dates.append(date)
        size_raw = review.find("a", {"data-hook": "format-strip"})
        size = size_raw.text.replace("Size: ", "") if size_raw else None
        model_no, model_description = size2model.get(size, (size, size))
        models.append(model_no)
        descriptions.append(model_description)
        rating = review.find("i", {"data-hook": "review-star-rating"})
        ratings.append(int(rating.text[0]) if rating else None)
        title = review.find("a", {"data-hook": "review-title"})
        titles.append(title.text.strip() if title else None)
        body = review.find("span", {"data-hook": "review-body"})
        bodies.append(body.text.strip() if body else None)
        images_raw = review.find_all("img", {"data-hook": "review-image-tile"})
        images.append("\n".join(image.attrs["src"] for image in images_raw))
        badge = review.find("span", {"data-hook": "avp-badge"})
        badges.append(badge.text.strip() if badge else None)
    return True


def parse_product(driver, url, model=None, day_lim=None):
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
    models, descriptions, dates, ratings, titles, bodies, images, badges = [], [], [], [], [], [], [], []
    to_continue = extract(soup, models, descriptions, dates, ratings, titles, bodies, images, badges, earliest)

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
        to_continue = extract(soup, models, descriptions, dates, ratings, titles, bodies, images, badges, earliest)
        prev_url = curr_url

    result = pd.DataFrame({"Model No.": models, "Model Description": descriptions, "Date": dates, "Rating": ratings,
                           "Title": titles, "Body": bodies, "Image": images, "Badge": badges})
    if model:
        result["Model No."] = model
        result["Model Description"] = model2desc[model]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews for product on Amazon")
    parser.add_argument("--input", type=str, default="amazon_input",
                        help="Name of input .json file (default amazon_input)")
    parser.add_argument("--category", type=str, help="Category of products")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Amazon_Reviews",
                        help="Name of output .xlsx file (default Amazon_Reviews)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with open(args.input + ".json") as f:
        data = json.load(f)
    urls, size2model, model2desc = data["urls"], data["size2model"], data["model2desc"]
    if args.category not in urls:
        logging.error("Invalid category: {}".format(args.category))
        quit()
    DRIVER = webdriver.Chrome("./chromedriver")
    DRIVER.set_page_load_timeout(10)
    _ = input("Press ENTER to proceed")
    urls_to_do = urls[args.category]
    if type(urls_to_do) == str:
        product_result = parse_product(DRIVER, urls_to_do, day_lim=args.days)
    else:  # dict
        product_result = pd.concat(
            parse_product(DRIVER, target_url, model, args.days) for model, target_url in urls_to_do.items())
    DRIVER.quit()
    product_result["Date"] = pd.to_datetime(product_result["Date"], format="%B %d, %Y").map(lambda date_: date_.date())
    product_result = predict_labels(product_result, TAGs, True)
    product_result.to_excel("outputs/" + args.output + ".xlsx", header=True, index=False)
    logging.info("Process completed! Extracted {} reviews".format(len(product_result)))
