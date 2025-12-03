import pandas as pd
import requests
from bs4 import BeautifulSoup
import csv

with open('key_inflation.csv', 'w', encoding='utf-8') as file: 
    writer = csv.writer(file) 
    writer.writerow(['date', 'key-rate', 'inflation'])

response = requests.get('https://cbr.ru/hd_base/infl/?UniDbQuery.Posted=True&UniDbQuery.From=17.09.2013&UniDbQuery.To=05.11.2025') 
response.encoding = 'utf-8'
soup = BeautifulSoup(response.text, "html.parser") 
table = soup.find('table')
rows = table.find_all('tr')

for row in rows[1:]:
    columns = row.find_all('td')
    date = columns[0].text
    key_rate = columns[1].text
    inflation = columns[2].text
    with open('key_inflation.csv', 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([date, key_rate, inflation])