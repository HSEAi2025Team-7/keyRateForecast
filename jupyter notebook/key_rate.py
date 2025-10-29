import requests 
from bs4 import BeautifulSoup 
import spacy 
import re

nlp = spacy.load("ru_core_news_sm")

def get_web_content(url):
    text = requests.get(url).text
    return BeautifulSoup(text, 'html.parser').get_text()

def clean_text(text):

    text = re.sub(r'<[^>]+>|http\S+|[^\w\s\.\,\!]', '', text)

    text = re.sub(r'\b\d+[\.,]?\d*\b', '<NUM>', text)
    
    return ' '.join(text.split())

def filter_words(text):

    doc = nlp(text.lower())
    
    words = [token.lemma_ for token in doc if not token.is_punct and not token.is_space]
    
    stop_words = {'и','в','на','с','по','о'}
    
    return ' '.join(w for w in words if len(w) >= 2 and w not in stop_words)

def show_result(text):

    print(f"Результат ({len(text)} символов):")

    print(text[:1500] + "..." if len(text) > 1500 else text)

url = 'https://www.cbr.ru/'

original = get_web_content(url)

cleaned = clean_text(original)

filtered = filter_words(cleaned)

show_result(filtered)