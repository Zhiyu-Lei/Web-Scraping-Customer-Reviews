# Web Scraping Customer Reviews

This project contains the pipelines to extract customer reviews from Homedepot, Walmart, Amazon and Lowe's, and to classify negative reviews (designed for AC products) with star rating less than 3 to certain issues.

Please make sure all the required site-packages are installed (running command `pip3 install -r requirements.txt`), Stopwords Corpus (`stopwords`) and Punkt Tokenizer Models (`punkt`) are downloaded from nltk, and webdriver for Chrome is in the project directory and named "chromedriver"!

## Extract Customer Reviews
For Homedepot and Walmart, two modes are available:
+ Get reviews for an entire category. The URL of the content page is required to be included in the `URLs` dictionary variable with category name as the key, and URLs of each product's review page will be extracted first by parsing the content page.
  + Command for Homedepot: `python homedepot.py [-h] --category CATEGORY [--days DAYS] [--output OUTPUT]`
  + Command for Walmart: `python walmart.py [-h] --category CATEGORY [--days DAYS] [--output OUTPUT]`
+ Get reviews for a specific product. The URL of the product's review page is required to be passed through command line arguments.
  + Command for Homedepot: `python3 homedepot.py [-h] --mode product --product PRODUCT [--days DAYS] [--output OUTPUT]`
  + Command for Walmart: `python3 walmart.py [-h] --mode product --product PRODUCT [--days DAYS] [--output OUTPUT]`

For Amazon and Lowe's, only the mode of getting reviews for some specific products is available. The URLs of the products' review pages are required to be included in the `amazon_input.json` config file with three objects "urls", "size2model" and "model2desc", and the `lowes_input.json` config file with two objects "urls" and "model2desc", with the following formats respectively:
```json
{
    "urls": {
        "category1": "url of customer review page for a specific model in category1",
        "category2": {
            "model1": "url of customer review page for model1 in category2",
            "model2": "url of customer review page for model2 in category2"
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
```json
{
    "urls": {
        "model1": ["urls of detail pages for model1"],
        "model2": ["urls of detail pages for model2"]
    },
    "model2desc": {
        "model1": "model1 description",
        "model2": "model2 description"
    }
}
```
+ Command for Amazon: `python3 amazon.py [-h] [--input INPUT] [--category CATEGORY] [--days DAYS] [--output OUTPUT]`
+ Command for Lowe's: `python3 lowes.py [-h] [--input INPUT] [--days DAYS] [--output OUTPUT]`

The output spreadsheet contains information of manufacturers, model numbers, model descriptions, dates, star ratings, review titles, review bodies and links to attached images, and is stored as an xlsx file in the "output" directory.

---

## Classify Negative Reviews
The training data and classification tags are for AC products. For some tags, rule based approach is used by regular expression matching in review texts. For the rest, maching learning based approach is used by vectorizing the review texts first with TF-IDF and then training a Naive Bayes classifier for each tag.

Review classification is run directly after customer reviews are extracted successfully from target websites.
