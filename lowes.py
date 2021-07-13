import requests
import pandas as pd
import time
import datetime
import random
import argparse
import logging
import json
from review_classification import predict_labels

URL_search = "https://www.lowes.com/rnr/r/get-by-product/{}/pdp/prod?sortMethod=SubmissionTime&sortDirection=desc&offset="
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "referer": None
}
TAGs = ["sound", "no cooling", "condensate drain issues", "8.8 error code", "missing parts", "used unit", "wifi"]


def extract(reviews, dates, ratings, titles, bodies, images, earliest=None):
    if not reviews:
        return False
    for review in reviews:
        date = review["SubmissionTime"][:10]
        if earliest and datetime.datetime.strptime(date, "%Y-%m-%d").date() < earliest:
            return False
        dates.append(date)
        ratings.append(review["Rating"])
        titles.append(review["Title"])
        bodies.append(review["ReviewText"])
        images.append("\n".join(image["Sizes"]["normal"]["Url"] for image in review["Photos"]))
    return True


def parse_product(model_no, url, day_lim=None):
    product_id = url.split("/")[-1]
    url_search = URL_search.format(product_id)
    HEADERS["referer"] = url
    earliest = datetime.date.today() - datetime.timedelta(days=day_lim) if day_lim else None
    dates, ratings, titles, bodies, images = [], [], [], [], []
    offset = 0
    to_continue = True
    while to_continue:
        response = requests.get(url_search + str(offset), headers=HEADERS)
        if response.status_code == 200:
            reviews = response.json()["Results"]
            to_continue = extract(reviews, dates, ratings, titles, bodies, images, earliest)
            offset += 10
        time.sleep(1 + random.random())
    result = pd.DataFrame({"Date": dates, "Rating": ratings, "Title": titles, "Body": bodies, "Image": images})
    result["Model No."] = model_no
    result["Model Description"] = model2desc[model_no]
    return result[["Model No.", "Model Description", "Date", "Rating", "Title", "Body", "Image"]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract customer reviews for product on Lowes")
    parser.add_argument("--input", type=str, default="lowes_input",
                        help="Name of input .json file (default lowes_input)")
    parser.add_argument("--days", type=int, default=7, help="Limit of days before today (default 7)")
    parser.add_argument("--output", type=str, default="Lowes_Reviews",
                        help="Name of output .xlsx file (default Lowes_Reviews)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with open(args.input + ".json") as f:
        data = json.load(f)
    urls, model2desc = data["urls"], data["model2desc"]
    results = []
    for MODEL, urls_to_do in urls.items():
        logging.info("Getting model {}".format(MODEL))
        for target_url in urls_to_do:
            try:
                results.append(parse_product(MODEL, target_url, args.days))
                if results[-1] is not None and len(results[-1]) > 0:
                    logging.info("Success: {}, extracted {} reviews".format(MODEL, len(results[-1])))
                else:
                    logging.warning("No new reviews: {}".format(target_url))
            except Exception:
                logging.error("Failed: {}".format(target_url))
    final = pd.concat(results)
    final.drop_duplicates(inplace=True)
    final["Date"] = pd.to_datetime(final["Date"], format="%Y-%m-%d").map(lambda date_: date_.date())
    final = predict_labels(final, TAGs, True)
    final.to_excel("outputs/" + args.output + ".xlsx", header=True, index=False)
    logging.info("Process completed!")
