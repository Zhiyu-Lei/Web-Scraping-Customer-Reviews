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
    reviews = str(soup.find("div", {"class": "ratings-reviews"})).replace("\n", " ")
    dates = re.findall('<span\\s+class="review-content__date">(.+?)</span>', reviews)
    ratings = re.findall('<span\\s+class="stars"\\s+style="width:\\s*(\\d+)', reviews)
    ratings.pop(0)
    ratings_new = [int(rating) // 20 for rating in ratings]
    titles = re.findall('<span\\s+class="review-content__title">(.*?)</span>', reviews)
    bodies = re.findall('<div\\s+class="review-content-body">(.*?)</div>', reviews)
    to_continue = True
    if earliest:
        dates_new = [date for date in dates if datetime.datetime.strptime(date, "%b %d, %Y").date() >= earliest]
        if len(dates_new) < len(dates):
            to_continue = False
            dates = dates_new
            ratings_new, titles, bodies = ratings_new[:len(dates)], titles[:len(dates)], bodies[:len(dates)]
    total_dates.extend(dates)
    total_ratings.extend(ratings_new)
    total_titles.extend(titles)
    total_bodies.extend(bodies)
    return to_continue


def parse_product(driver, url, day_lim=None):
    driver.get(url)
    time.sleep(2 + random.random())
    try:
        drop_down = Select(driver.find_element_by_class_name("drop-down__select"))
    except NoSuchElementException:
        return None
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
    total_dates, total_ratings, total_titles, total_bodies = [], [], [], []
    to_continue = extract(soup, total_dates, total_ratings, total_titles, total_bodies, earliest)
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
        curr_page = soup.find("span", {"class": "pager-summary__bold"}).text
        if curr_page == prev_page:
            time.sleep(5 + random.random())
            continue
        elif curr_page == "1":
            break
        to_continue = extract(soup, total_dates, total_ratings, total_titles, total_bodies, earliest)
        prev_page = curr_page

    result = pd.DataFrame({"Date": total_dates, "Rating": total_ratings, "Title": total_titles, "Body": total_bodies})
    result["Model No."] = model_no
    result["Model Description"] = model_description
    return result[["Model No.", "Model Description", "Date", "Rating", "Title", "Body"]]


def parse_content(driver, url):
    driver.get(url)
    products = re.findall('<a href="(\\S+)"\\s+class="header\\s+product-pod--ie-fix">', driver.page_source)
    prev_page = "1"
    time.sleep(5 + random.random())
    while True:
        next_link = driver.find_elements_by_class_name("hd-pagination__link")[-1]
        time.sleep(1 + random.random())
        next_link.click()
        time.sleep(1 + random.random())
        soup = BeautifulSoup(driver.page_source, "html.parser")
        curr_page = soup.find("span", {"class": "results-pagination__counts--number"}).text.strip().split("-")[0]
        if curr_page == prev_page:
            time.sleep(3 + random.random())
            continue
        elif curr_page == "1":
            break
        products.extend(re.findall('<a href="(\\S+)"\\s+class="header\\s+product-pod--ie-fix">', driver.page_source))
        prev_page = curr_page
    return products


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews from Hstore")
    parser.add_argument("--mode", type=str, default="category", help="Extract category/product (default category)")
    parser.add_argument("--category", type=str, help="Category of products")
    parser.add_argument("--product", type=str, help="URL of the single product")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Hstore_Reviews",
                        help="Name of output .xlsx file (default Hstore_Reviews)")
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
            target_url = "header url" + target[2:]  # TODO: paste the actual header url
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
