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

URLs = {
    "category1": "url of content page for category1",
    "category2": "url of content page for category2",
    "category3": "url of content page for category3"
}  # TODO: paste the actual urls


def extract(soup, total_dates, total_ratings, total_titles, total_bodies, earliest=None):
    reviews = soup.find_all("div", {"class": "Grid ReviewList-content"})
    for review in reviews:
        date = review.find("span", {"class", "review-date-submissionTime"}).text
        if earliest and datetime.datetime.strptime(date, "%B %d, %Y").date() < earliest:
            return False
        total_dates.append(date)
        rating_raw = review.find_all("span", {"aria-hidden": "true"})
        rating = 0
        for r in rating_raw[:5]:
            if "rated" in str(r):
                rating += 1
        total_ratings.append(rating)
        title = review.find("h3")
        total_titles.append(title.text if title else None)
        body = review.find("p")
        total_bodies.append(body.text if body else None)
    return True


def parse_product(driver, url, day_lim=None):
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
    earliest = datetime.date.today() - datetime.timedelta(days=day_lim) if day_lim else None
    total_dates, total_ratings, total_titles, total_bodies = [], [], [], []
    to_continue = extract(soup, total_dates, total_ratings, total_titles, total_bodies, earliest)

    while to_continue:
        try:
            next_link = driver.find_element_by_class_name("paginator-btn.paginator-btn-next")
        except NoSuchElementException:
            break
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
        soup = BeautifulSoup(driver.page_source, "html.parser")
        to_continue = extract(soup, total_dates, total_ratings, total_titles, total_bodies, earliest)

    result = pd.DataFrame({"Date": total_dates, "Rating": total_ratings, "Title": total_titles, "Body": total_bodies})
    if len(result) == 0:
        return None
    main_page = driver.find_element_by_class_name("button-wrapper")
    time.sleep(1 + random.random())
    driver.execute_script("arguments[0].click()", main_page)
    time.sleep(1 + random.random())
    model_no = None
    for row in driver.find_elements_by_tag_name("tr"):
        cols = row.text.split()
        try:
            if cols[0] == "Model":
                model_no = cols[1]
                break
        except IndexError:
            break
    result["Model No."] = model_no
    result["Model Description"] = model_description
    return result[["Model No.", "Model Description", "Date", "Rating", "Title", "Body"]]


def parse_content(driver, url):
    driver.get(url)
    _ = input("Press ENTER to proceed")
    target_items = re.findall('href="(\\S+)"\\s+tabindex="-1"\\s+data-type="itemTitles"', driver.page_source)
    time.sleep(2 + random.random())
    while True:
        try:
            next_link = driver.find_element_by_class_name("elc-icon.paginator-hairline-btn.paginator-btn.paginator-btn-next")
        except NoSuchElementException:
            break
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
        target_items.extend(re.findall('href="(\\S+)"\\s+tabindex="-1"\\s+data-type="itemTitles"', driver.page_source))
    return target_items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews from Wstore")
    parser.add_argument("--mode", type=str, default="category", help="Extract category/product (default category)")
    parser.add_argument("--category", type=str, help="Category of products")
    parser.add_argument("--product", type=str, help="URL of the single product")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Wstore_Reviews",
                        help="Name of output .xlsx file (default Wstore_Reviews)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    DRIVER = webdriver.Chrome(".\\chromedriver")
    _ = input("Press ENTER to proceed")
    if args.mode == "category":
        URL = URLs[args.category]
        targets = set(parse_content(DRIVER, URL))
        logging.info("Found {} products".format(len(targets)))
        results = []
        for target in targets:
            target_url = "header url" + target.split("/")[-1]  # TODO: paste the actual header url
            try:
                results.append(parse_product(DRIVER, target_url, args.days))
                if results[-1] is not None and len(results[-1]) > 0:
                    logging.info("Success: {}, extracted {} reviews".format(results[-1].iloc[0, 1], len(results[-1])))
                else:
                    logging.warning("No new reviews: {}".format(target_url))
            except Exception:
                logging.error("Failed: {}".format(target_url))
        DRIVER.close()
        final = pd.concat(results)
        final.to_excel("outputs\\" + args.output + ".xlsx", header=True, index=False)
        logging.info("Process completed!")
    elif args.mode == "product":
        product_result = parse_product(DRIVER, args.product, args.days)
        DRIVER.close()
        product_result.to_excel("outputs\\" + args.output + ".xlsx", header=True, index=False)
        logging.info("Process completed! Extracted {} reviews".format(len(product_result)))
    else:
        DRIVER.close()
        logging.error("Invalid mode: {}".format(args.mode))
