import requests
from bs4 import BeautifulSoup
import spacy
import re
from urllib.parse import urljoin, urlparse
import time
from collections import Counter
import nltk
from nltk.util import ngrams

#Загрузка модели spaCy для русского языка
nlp = spacy.load("ru_core_news_sm")

def get_page(url):
    #Загружает 
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Ошибка загрузки {url}: {e}")
        return None

def clean_text(text):
    #Очищает текст от лишних символов и заменяет числа
    text = re.sub(r'<[^>]+>|http\S+|[^\w\s\.\,\!]', '', text)
    text = re.sub(r'\b\d+[\.,]?\d*\b', '<NUM>', text)
    return ' '.join(text.split())

def lemmatize_text(text):
    #Лемматизирует текст, убирает стоп‑слова
    doc = nlp(text.lower())
    stop_words = {'и', 'в', 'на', 'с', 'по', 'о', 'не', 'но', 'а', 'то', 'как'}
    return ' '.join([
        token.lemma_ for token in doc
        if not token.is_punct and not token.is_space
        and len(token.lemma_) >= 3 and token.lemma_ not in stop_words
    ])

def find_news_urls(soup, base_url):
    #Находит ссылки на новости
    domain = urlparse(base_url).netloc
    links = set()
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/news/' in href or '/press/' in href:
            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc == domain:
                links.add(full_url)
    
    return list(links)

def extract_content(soup):
    #извлекает основной текст
    if soup.find('article'):
        return soup.find('article').get_text()
    if soup.find('div', class_='content'):
        return soup.find('div', class_='content').get_text()
    return soup.get_text()

def crawl_site(start_url, depth=3, limit=6):
    #обходит сайт
    visited = set()
    queue = [(start_url, 0)]
    all_texts = []
    count = 0
    domain = urlparse(start_url).netloc

    while queue and count < limit:
        url, level = queue.pop(0)
        
        if url in visited or level > depth:
            continue
            
        visited.add(url)

        soup = get_page(url)
        if not soup:
            continue
        
        if '/news/' in url or '/press/' in url:

            # Извлекаем и обрабатываем текст
            text = extract_content(soup)
            cleaned = clean_text(text)
            lemmatized = lemmatize_text(cleaned)
            
            all_texts.append(lemmatized)
            count += 1

        # Добавляем новые ссылки в очередь
        if level < depth:
            for link in find_news_urls(soup, url):
                if link not in visited:
                    queue.append((link, level + 1))
        
        time.sleep(0.5)
    
    return " ".join(all_texts)

def analyze_top_words_and_phrases(text, top_n=10):
    #Анализирует топ-частые слова и словосочетания 

    words = text.split()
    
    # Считаем частоту слов
    word_freq = Counter(words)
    top_words = word_freq.most_common(top_n)

    # словосочетания 
    biagrams = list(ngrams(words, 2))
    bigram_freq = Counter(biagrams)
    top_phrases = bigram_freq.most_common(top_n)
    
    return dict(top_words), dict(top_phrases)

def print_analysis(top_words, top_phrases):

    print("ТОП-ЧАСТЫЕ СЛОВА:")

    for word, freq in top_words.items():
        print(f"{word}: {freq}")
    

    print("ТОП-ЧАСТЫЕ СЛОВОСОЧЕТАНИЯ :")

    for phrase, freq in top_phrases.items():
        print(f"{' '.join(phrase)}: {freq}")

if __name__ == "__main__":
    URL = "https://www.cbr.ru/"
    DEPTH = 3
    LIMIT = 6
    TOP_N = 10
    
    print(f"Обход сайта: {URL}")
    
    final_text = crawl_site(URL, DEPTH, LIMIT)
    
    if final_text:
        print(f"\n\nОбъединённый текст ({len(final_text)} символов):")
        print(final_text[:1500] + "..." if len(final_text) > 1500 else final_text)
        
        print("АНАЛИЗ ЧАСТОТНОСТИ СЛОВ И СЛОВОСОЧЕТАНИЙ")

        top_words, top_phrases = analyze_top_words_and_phrases(final_text, TOP_N)
        print_analysis(top_words, top_phrases)
    else:
        print("\nТексты не собраны.")
