from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import datetime
import random
import argparse
import logging
from review_classification import predict_labels

URLs = {
    "Window": "https://www.walmart.com/browse/home-improvement/window-air-conditioners/1072864_133032_133026_587566",
    "Portable": "https://www.walmart.com/browse/home-improvement/portable-air-conditioners/1072864_133032_133026_587564",
    "Dehumidifier": "https://www.walmart.com/browse/home-improvement/dehumidifiers/1072864_133032_1231459_112918"
}
TAGs = ["sound", "no cooling", "condensate drain issues", "8.8 error code", "missing parts", "used unit", "wifi"]


def extract(soup, dates, ratings, titles, bodies, images, earliest=None):
    reviews = soup.find_all("div", {"class": "Grid ReviewList-content"})
    for review in reviews:
        date = review.find("span", {"class", "review-date-submissionTime"}).text
        if earliest and datetime.datetime.strptime(date, "%B %d, %Y").date() < earliest:
            return False
        dates.append(date)
        rating_raw = review.find_all("span", {"aria-hidden": "true"})
        rating = 0
        for r in rating_raw[:5]:
            if "rated" in str(r):
                rating += 1
        ratings.append(rating)
        title = review.find("h3")
        titles.append(title.text if title else None)
        body = review.find("p")
        bodies.append(body.text if body else None)
        images_raw = review.find_all("img", {"class": "review-media-thumbnail"})
        images.append("\n".join("https:" + image.attrs["src"] for image in images_raw))
    return True


def parse_product(driver, url, day_lim=None, keyword=None):
    driver.get(url)
    time.sleep(2 + random.random())
    try:
        drop_down = Select(driver.find_element_by_class_name("field-input.field-input--compact"))
    except NoSuchElementException:
        return None
    drop_down.select_by_value("submission-desc")
    time.sleep(1 + random.random())
    soup = BeautifulSoup(driver.page_source, "html.parser")
    model_description = soup.find("div", {"class": "LinesEllipsis"}).text
    assert not keyword or keyword.lower() in model_description.lower()
    earliest = datetime.date.today() - datetime.timedelta(days=day_lim) if day_lim else None
    dates, ratings, titles, bodies, images = [], [], [], [], []
    to_continue = extract(soup, dates, ratings, titles, bodies, images, earliest)

    while to_continue:
        try:
            next_link = driver.find_element_by_class_name("paginator-btn.paginator-btn-next")
        except NoSuchElementException:
            break
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
        soup = BeautifulSoup(driver.page_source, "html.parser")
        to_continue = extract(soup, dates, ratings, titles, bodies, images, earliest)

    result = pd.DataFrame({"Date": dates, "Rating": ratings, "Title": titles, "Body": bodies, "Image": images})
    if len(result) == 0:
        return None
    main_page = driver.find_element_by_class_name("button-wrapper")
    time.sleep(1 + random.random())
    driver.execute_script("arguments[0].click()", main_page)
    time.sleep(1 + random.random())
    model_no = driver.current_url
    tables = pd.read_html(driver.page_source)
    if len(tables) == 1:
        features, items = tables[0][0].to_list(), tables[0][1].to_list()
    elif len(tables) > 1:
        features, items = tables[0].iloc[:, 0].to_list(), tables[1].iloc[1:, 0].to_list()
    else:
        features, items = [], []
    for feature, item in zip(features, items):
        if feature in ("Manufacturer Part Number", "manufacturer_part_number"):
            model_no = item
        if feature == "Model":
            model_no = item
            break
    result["Model No."] = model_no
    result["Model Description"] = model_description
    result["Manufacturer"] = model_description.split()[0]
    return result[["Manufacturer", "Model No.", "Model Description", "Date", "Rating", "Title", "Body", "Image"]]


def parse_content(driver, url):
    driver.get(url)
    time.sleep(2 + random.random())
    target_items = set()
    while True:
        for item in driver.find_elements_by_class_name("Grid-col.u-size-6-12.u-size-1-4-m.u-size-1-5-xl"):
            try:
                item.find_element_by_class_name("stars-reviews-count")
                target_items.add(re.findall('href="(\\S+)"\\s+tabindex="-1"', item.get_attribute("innerHTML"))[0])
            except NoSuchElementException:
                pass
        try:
            next_link = driver.find_element_by_class_name(
                "elc-icon.paginator-hairline-btn.paginator-btn.paginator-btn-next")
        except NoSuchElementException:
            break
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
    return target_items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews from Walmart")
    parser.add_argument("--mode", type=str, default="category", help="Extract category/product (default category)")
    parser.add_argument("--category", type=str, help="Category of products")
    parser.add_argument("--product", type=str, help="URL of the single product")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Walmart_Reviews",
                        help="Name of output .xlsx file (default Walmart_Reviews)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, filename="logging.log", filemode="w")
    DRIVER = webdriver.Chrome(".\\chromedriver")
    DRIVER.set_page_load_timeout(10)
    _ = input("Press ENTER to proceed")
    if args.mode == "category" and args.category in URLs:
        URL = URLs[args.category]
        targets = parse_content(DRIVER, URL)
        logging.info("Found {} products".format(len(targets)))
        results = []
        for target in targets:
            target_url = "https://www.walmart.com/reviews/product/" + target.split("/")[-1]
            try:
                results.append(parse_product(DRIVER, target_url, args.days, args.category))
                if results[-1] is not None and len(results[-1]) > 0:
                    logging.info("Success: {}, extracted {} reviews".format(results[-1].iloc[0, 2], len(results[-1])))
                else:
                    logging.warning("No new reviews: {}".format(target_url))
            except AssertionError:
                logging.warning("Category does not match: {}".format(target_url))
            except ElementNotInteractableException:
                logging.error("Failed: {}".format(target_url))
                _ = input("Press ENTER to proceed")
            except TimeoutException:
                logging.error("Timeout: {}".format(target_url))
                DRIVER.quit()
                DRIVER = webdriver.Chrome(".\\chromedriver")
                DRIVER.set_page_load_timeout(10)
            except Exception:
                logging.error("Failed: {}".format(target_url))
        DRIVER.quit()
        final = pd.concat(results)
        final["Date"] = pd.to_datetime(final["Date"], format="%B %d, %Y").map(lambda date_: date_.date())
        final = predict_labels(final, TAGs, True)
        final.to_excel("outputs\\" + args.output + ".xlsx", header=True, index=False)
        logging.info("Process completed!")
    elif args.mode == "product":
        product_result = parse_product(DRIVER, args.product, args.days)
        DRIVER.quit()
        product_result["Date"] = pd.to_datetime(product_result["Date"], format="%B %d, %Y").map(lambda dt: dt.date())
        product_result = predict_labels(product_result, TAGs, True)
        product_result.to_excel("outputs\\" + args.output + ".xlsx", header=True, index=False)
        logging.info("Process completed! Extracted {} reviews".format(len(product_result)))
    else:
        DRIVER.quit()
        logging.error("Invalid mode or category")
