from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
import requests
import pandas as pd
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
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
POST_DATA = {"itemId": None, "paginationContext": {"filters": [], "limit": 20, "page": None, "sort": "submission-desc"}}
TAGs = ["sound", "no cooling", "condensate drain issues", "8.8 error code", "missing parts", "used unit", "wifi"]


def extract(reviews, dates, ratings, titles, bodies, images, earliest=None):
    if not reviews:
        return False
    for review in reviews:
        date = review["reviewSubmissionTime"]
        if earliest and datetime.datetime.strptime(date, "%m/%d/%Y").date() < earliest:
            return False
        dates.append(date)
        ratings.append(review["rating"])
        titles.append(review.get("reviewTitle", None))
        bodies.append(review.get("reviewText", None))
        images.append("\n".join(image["Sizes"]["normal"]["Url"] for image in review["photos"]))
    return True


def parse_product(product_id, url, day_lim=None, keyword=None):
    url_search = "https://www.walmart.com/terra-firma/fetch?rgs=REVIEWS_MAP"
    POST_DATA["itemId"] = product_id
    page = requests.get(url, headers=HEADERS).text
    soup = BeautifulSoup(page, "html.parser")
    model_description = soup.find("h1").text
    assert not keyword or keyword.lower() in model_description.lower()
    earliest = datetime.date.today() - datetime.timedelta(days=day_lim) if day_lim else None
    dates, ratings, titles, bodies, images = [], [], [], [], []
    page_no = 1
    to_continue = True
    while to_continue:
        POST_DATA["paginationContext"]["page"] = page_no
        result = requests.post(url_search, headers=HEADERS, json=POST_DATA, timeout=5)
        if result.status_code == 200:
            reviews = result.json()["payload"]["reviews"][product_id]["customerReviews"]
            to_continue = extract(reviews, dates, ratings, titles, bodies, images, earliest)
            page_no += 1
        else:
            print("Fail", url, result.status_code)
            time.sleep(4 + random.random())
        time.sleep(1 + random.random())
    result = pd.DataFrame({"Date": dates, "Rating": ratings, "Title": titles, "Body": bodies, "Image": images})

    model_no = url
    tables = pd.read_html(page)
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
    _ = input("Press ENTER to proceed")
    time.sleep(2 + random.random())
    target_items = set()
    while True:
        for item in driver.find_elements_by_class_name("Grid-col.u-size-6-12.u-size-1-4-m.u-size-1-5-xl"):
            try:
                item.find_element_by_class_name("stars-reviews-count")
                product_id = item.find_element_by_class_name("search-result-gridview-item-wrapper")\
                    .get_attribute("data-id")
                product_url = item.find_element_by_tag_name("a").get_attribute("href")
                target_items.add((product_id, product_url))
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
    parser.add_argument("--productID", type=str, help="ID of the single product")
    parser.add_argument("--productURL", type=str, help="URL of the single product")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Walmart_Reviews",
                        help="Name of output .xlsx file (default Walmart_Reviews)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, filename="logging.log", filemode="w")
    if args.mode == "category" and args.category in URLs:
        DRIVER = webdriver.Chrome("./chromedriver")
        DRIVER.set_page_load_timeout(10)
        _ = input("Press ENTER to proceed")
        URL = URLs[args.category]
        targets = parse_content(DRIVER, URL)
        DRIVER.quit()
        logging.info("Found {} products".format(len(targets)))
        results = []
        for target_id, target_url in targets:
            logging.info("Getting product ID {}".format(target_id))
            try:
                results.append(parse_product(target_id, target_url, args.days, args.category))
                if results[-1] is not None and len(results[-1]) > 0:
                    logging.info("Success: {}, extracted {} reviews".format(results[-1].iloc[0, 2], len(results[-1])))
                else:
                    logging.warning("No new reviews: {}".format(target_url))
            except AssertionError:
                logging.warning("Category does not match: {}".format(target_url))
            except Exception:
                logging.error("Failed: {}".format(target_url))
        final = pd.concat(results)
        final["Date"] = pd.to_datetime(final["Date"], format="%m/%d/%Y").map(lambda date_: date_.date())
        final = predict_labels(final, TAGs, True)
        final.to_excel("outputs/" + args.output + ".xlsx", header=True, index=False)
        logging.info("Process completed!")
    elif args.mode == "product":
        product_result = parse_product(args.productID, args.productURL, args.days)
        if product_result is None or len(product_result) == 0:
            logging.warning("No new reviews: {}".format(args.productURL))
            quit()
        product_result["Date"] = pd.to_datetime(product_result["Date"], format="%m/%d/%Y").map(lambda dt: dt.date())
        product_result = predict_labels(product_result, TAGs, True)
        product_result.to_excel("outputs/" + args.output + ".xlsx", header=True, index=False)
        logging.info("Process completed! Extracted {} reviews".format(len(product_result)))
    else:
        logging.error("Invalid mode or category")
