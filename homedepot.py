from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import tqdm
import pandas as pd
import re
import time
import datetime
import random
import argparse
import logging
from review_classification import predict_labels
from file_output import df2excel

URLs = {
    "Window": "https://www.homedepot.com/b/Heating-Venting-Cooling-Air-Conditioners-Window-Air-Conditioners/N-5yc1vZc4lu",
    "Portable": "https://www.homedepot.com/b/Heating-Venting-Cooling-Air-Conditioners-Portable-Air-Conditioners/N-5yc1vZc4m4",
    "Dehumidifier": "https://www.homedepot.com/b/Heating-Venting-Cooling-Dehumidifiers/N-5yc1vZc4l8"
}
TAGs = ["sound", "no cooling", "condensate drain issues", "8.8 error code", "missing parts", "used unit", "wifi"]


def extract(soup, dates, ratings, titles, bodies, images, earliest=None):
    reviews = soup.find_all("div", {"class": "review_item"})
    for review in reviews:
        date = review.find("span", {"class": "review-content__date"}).text.strip()
        if earliest and datetime.datetime.strptime(date, "%b %d, %Y").date() < earliest:
            return False
        dates.append(date)
        rating_raw = review.find("span", {"class": "stars"}).attrs["style"]
        ratings.append(int(re.findall("\\d+", rating_raw)[0]) // 20)
        title = review.find("span", {"class": "review-content__title"})
        titles.append(title.text.strip() if title else None)
        body = review.find("div", {"class": "review-content-body"})
        bodies.append(body.text.strip() if body else None)
        images_raw = review.find_all("div", {"class": "media-carousel__media"})
        images.append("\n".join(
            re.findall('url\\("?(\\S+?)"?\\)', image.find("button").attrs["style"])[0] for image in images_raw))
    return True


def parse_product(driver, url, day_lim=None, err_terminate=False):
    driver.get(url)
    time.sleep(2 + random.random())
    drop_down = Select(driver.find_element_by_class_name("drop-down__select"))
    drop_down.select_by_value("newest")
    time.sleep(1 + random.random())
    drop_down.select_by_value("newest")
    time.sleep(1 + random.random())
    soup = BeautifulSoup(driver.page_source, "html.parser")
    title = soup.find("h1", {"class": "page-title"}).text.replace("\n", " ").replace("<!-- -->", "")
    model_description = re.findall("Customer\\s+Reviews\\s+for\\s+(.+)", title)[0]
    model = soup.find_all("h2", {"class": "product-info-bar__detail--24WIp"})[1].text.replace("<!-- -->", "")
    model_no = re.findall("Model\\s+#(.+)$", model)[0]
    earliest = datetime.date.today() - datetime.timedelta(days=day_lim) if day_lim else None
    dates, ratings, titles, bodies, images = [], [], [], [], []
    to_continue = extract(soup, dates, ratings, titles, bodies, images, earliest)
    prev_page = "1"

    while to_continue:
        links = driver.find_elements_by_class_name("hd-pagination__link")
        if not links:
            break
        next_link = links[-1]
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
        soup = BeautifulSoup(driver.page_source, "html.parser")
        try:
            curr_page = soup.find("span", {"class": "pager-summary__bold"}).text
        except AttributeError:
            if err_terminate:
                logging.warning("Terminated after page {}: {}".format(prev_page, url))
                break
            else:
                raise AttributeError
        if curr_page == prev_page:
            time.sleep(5 + random.random())
            continue
        elif curr_page == "1":
            break
        to_continue = extract(soup, dates, ratings, titles, bodies, images, earliest)
        prev_page = curr_page

    result = pd.DataFrame({"Date": dates, "Rating": ratings, "Title": titles, "Body": bodies, "Image": images})
    result["Model No."] = model_no
    result["Model Description"] = model_description
    result["Manufacturer"] = model_description.split()[0]
    return result[["Manufacturer", "Model No.", "Model Description", "Date", "Rating", "Title", "Body", "Image"]]


def parse_content(driver, url):
    driver.get(url)
    time.sleep(7 + random.random())
    target_items = set()
    for item in driver.find_elements_by_class_name("browse-search__pod"):
        try:
            item.find_element_by_class_name("product-pod__ratings-count")
            target_items.add(re.findall('<a href="(\\S+)"\\s+class="header', item.get_attribute("innerHTML"))[0])
        except NoSuchElementException:
            pass
    prev_page = "1"
    while True:
        next_link = driver.find_elements_by_class_name("hd-pagination__link")[-1]
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(2 + random.random())
        soup = BeautifulSoup(driver.page_source, "html.parser")
        curr_page = soup.find("span", {"class": "results-pagination__counts--number"}).text.strip().split("-")[0]
        if curr_page == prev_page:
            time.sleep(3 + random.random())
            continue
        elif curr_page == "1":
            break
        for item in driver.find_elements_by_class_name("browse-search__pod"):
            try:
                item.find_element_by_class_name("product-pod__ratings-count")
                target_items.add(re.findall('<a href="(\\S+)"\\s+class="header', item.get_attribute("innerHTML"))[0])
            except NoSuchElementException:
                pass
        prev_page = curr_page
    return target_items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews from Homedepot")
    parser.add_argument("--mode", type=str, default="category", help="Extract category/product (default category)")
    parser.add_argument("--category", type=str, help="Category of products")
    parser.add_argument("--product", type=str, help="URL of the single product")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--predict_labels", action="store_true", help="Indicate labels prediction")
    parser.add_argument("--output", type=str, default="Homedepot_Reviews",
                        help="Name of output .xlsx file (default Homedepot_Reviews)")
    args = parser.parse_args()
    DRIVER = webdriver.Chrome("./chromedriver")
    DRIVER.set_page_load_timeout(10)
    _ = input("Press ENTER to proceed")
    if args.mode == "category" and args.category in URLs:
        logging.basicConfig(level=logging.INFO, filename="logging.log", filemode="w")
        URL = URLs[args.category]
        targets = parse_content(DRIVER, URL)
        logging.info("Found {} products".format(len(targets)))
        results = []
        for target in tqdm.tqdm(targets):
            target_url = "https://www.homedepot.com/p/reviews" + target[2:]
            try:
                results.append(parse_product(DRIVER, target_url, args.days))
                if results[-1] is not None and len(results[-1]) > 0:
                    logging.info("Success: {}, extracted {} reviews".format(results[-1].iloc[0, 2], len(results[-1])))
                else:
                    logging.warning("No new reviews: {}".format(target_url))
            except TimeoutException:
                logging.error("Timeout: {}".format(target_url))
                DRIVER.quit()
                DRIVER = webdriver.Chrome("./chromedriver")
                DRIVER.set_page_load_timeout(10)
            except Exception:
                logging.error("Failed: {}".format(target_url))
        DRIVER.quit()
        final = pd.concat(results)
    elif args.mode == "product":
        logging.basicConfig(level=logging.INFO)
        final = parse_product(DRIVER, args.product, args.days, err_terminate=True)
        DRIVER.quit()
        if final is None or len(final) == 0:
            logging.warning("No new reviews: {}".format(args.product))
            quit()
        logging.info("Success, extracted {} reviews".format(len(final)))
    else:
        DRIVER.quit()
        final = None
        logging.error("Invalid mode or category")
        quit()
    final["Date"] = pd.to_datetime(final["Date"], format="%b %d, %Y").map(lambda dt: dt.date())
    if args.predict_labels:
        final = predict_labels(final, TAGs, True)
    file_name = df2excel(final, args.output)
    logging.info("Process completed! File stored at {}".format(file_name))
