import re
import pickle
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer

KEYWORDS_DICT = {
    "8.8 error code": re.compile("blink.+?88|beep.+?88|flash.+?88|88.+?error|8\\.8"),
    "sound": re.compile("nois|loud|buzz|rattl|sound[a-z\\s]+like|make[a-z\\s]+sound"),
    "missing parts": re.compile("missing|(?:not|n't|n’t)[a-z\\s]+(?:come|receive|contain)"),
    "used unit": re.compile("used\\s+(?:unit|item)|(?:be|was|were)[a-z\\s]+used|previous\\s+return|repackage|restock"),
    "wifi": re.compile("wifi|wi-fi")
}
STOPWORDS = stopwords.words("english")
for negation in ("not", "no", "don", "don't", "aren", "aren't", "didn", "didn't", "doesn", "doesn't", "isn", "isn't"):
    STOPWORDS.remove(negation)


def process_text(review, stemmer=PorterStemmer()):
    title, text = review["Title"], review["Body"]
    title = "" if type(title) != str else title
    text = "" if type(text) != str else text
    if not (title.endswith("...") and title[:-3] in text):
        text = " ".join((title, text))
    text = re.sub("[^A-Za-z]", " ", text.lower())
    tokenized_text = word_tokenize(text)
    clean_text = [stemmer.stem(word) for word in tokenized_text if word not in STOPWORDS]
    return " ".join(clean_text)


def vectorize(labeled_data):
    training_text = labeled_data.apply(process_text, axis=1)
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=300)
    vectors = vectorizer.fit_transform(training_text)
    with open("review_classification\\text_vectorizer.vec", "wb") as vectorizer_file:
        pickle.dump(vectorizer, vectorizer_file)
    return vectorizer, vectors


def train_separate_model(labeled_data, vectors, tag):
    nb_classifier = MultinomialNB()
    nb_classifier.fit(vectors, labeled_data[tag])
    with open("review_classification\\classifier for " + tag + ".model", "wb") as model_file:
        pickle.dump(nb_classifier, model_file)
    return nb_classifier


def train_models(tags_to_train, training_data_path="review_classification\\training_data.csv"):
    data = pd.read_csv(training_data_path)
    data["Category"] = data["Category"].map(lambda cat: cat.strip().lower() if type(cat) == str else "")
    split_tags = CountVectorizer(tokenizer=lambda x: re.split("\\s+/\\s+", x), binary=True)
    tags = pd.DataFrame(split_tags.fit_transform(data["Category"]).toarray(), columns=split_tags.get_feature_names())
    tags.drop(columns=[""], inplace=True)
    labeled = data.join(tags)[data["Category"] != ""]
    vectorizer, vectors = vectorize(labeled)
    return vectorizer, {tag: train_separate_model(labeled, vectors, tag) for tag in tags_to_train}


def predict_labels(unlabeled_data, candidate_tags, one_hot_encoding=False):
    columns = unlabeled_data.columns.to_list()
    processed_text = unlabeled_data.apply(process_text, axis=1)
    tags_ml = set()

    def rule_based(review, pattern):
        if review["Rating"] >= 3:
            return 0
        title, text = review["Title"], review["Body"]
        if type(title) == str and re.search(pattern, title.lower()):
            return 1
        if type(text) == str and re.search(pattern, text.lower()):
            return 1
        return 0

    for tag in candidate_tags:
        if tag in KEYWORDS_DICT:
            unlabeled_data[tag] = unlabeled_data.apply(rule_based, args=(KEYWORDS_DICT[tag],), axis=1)
        else:
            tags_ml.add(tag)
    try:
        with open("review_classification\\text_vectorizer.vec", "rb") as vectorizer_file:
            vectorizer = pickle.load(vectorizer_file)
        models = dict()
        for tag in tags_ml:
            with open("review_classification\\classifier for " + tag + ".model", "rb") as model_file:
                models[tag] = pickle.load(model_file)
    except FileNotFoundError:
        vectorizer, models = train_models(tags_ml)
    vectors = vectorizer.transform(processed_text)
    for tag, model in models.items():
        unlabeled_data[tag] = model.predict(vectors)
        unlabeled_data[tag] = unlabeled_data.apply(
            lambda review: 0 if (review["Rating"] >= 3 or review.isna()["Body"] or
                                 review["Body"] == "" or review["Body"] == "Rating provided by a verified purchaser")
            else review[tag], axis=1
        )
    unlabeled_data["Category"] = unlabeled_data.apply(lambda review: " / ".join(
        (tag for tag in candidate_tags if review[tag] == 1)), axis=1)
    if one_hot_encoding:
        columns.extend(candidate_tags)
    columns.append("Category")
    return unlabeled_data[columns]


if __name__ == "__main__":
    ex_vectorizer, ex_models = train_models(["no cooling", "condensate drain issues"])
