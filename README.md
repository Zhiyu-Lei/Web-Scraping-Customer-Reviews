# Web Scraping Customer Reviews

This project contains the pipelines to extract customer reviews from Homedepot, Walmart and Amazon, and to classify negative reviews (designed for AC products) with star rating less than 3 to certain issues.

## Extract Customer Reviews
Please make sure webdriver for Chrome is in the project directory and named "chromedriver"!

For Homedepot and Walmart, two modes are available:
+ Get reviews for an entire category. The URL of the content page is required to be included in the `URLs` dictionary variable with category name as the key, and URLs of each product's review page will be extracted first by parsing the content page.
  + Command for Homedepot: `python homedepot.py [-h] --category CATEGORY [--days DAYS] [--output OUTPUT]`
  + Command for Walmart: `python walmart.py [-h] --category CATEGORY [--days DAYS] [--output OUTPUT]`
+ Get reviews for a specific product. The URL of the product's review page is required to be passed through command line arguments.
  + Command for Homedepot: `python homedepot.py [-h] --mode product --product PRODUCT [--days DAYS] [--output OUTPUT]`
  + Command for Walmart: `python walmart.py [-h] --mode product --product PRODUCT [--days DAYS] [--output OUTPUT]`

For Amazon, only the mode of getting reviews for some specific products is available. The URL for the product's review page is required to be included in the `amazon_input.json` config file with three objects named "urls", "size2model" and "model2desc" in the following format:
```json
{
    "urls": {
        "category1": "url of customer review page for a specific product in category1",
        "category2": {
            "product1": "url of customer review page for product1 in category2",
            "product2": "url of customer review page for product2 in category2"
        }
    },
    "size2model": {
        "modelSize1": ["model1", "model1 description"],
        "modelSize2": ["model2", "model2 description"],
        "modelSize3": ["model3", "model3 description"]
    },
    "model2desc": {
        "model4": "model4 description",
        "model5": "model5 description",
        "model6": "model6 description"
    }
}
```

Command to run: `amazon.py [-h] [--category CATEGORY] [--days DAYS] [--output OUTPUT]`

---

## Classify Negative Reviews
The training data and classification tags are for AC products. For some tags, rule based approach is used by regular expression matching in review texts. For the rest, maching learning based approach is used by vectorizing the review texts first with TF-IDF and then training a Naive Bayes classifier for each tag.

Review classification is run directly after customer reviews are extracted successfully from target websites.
