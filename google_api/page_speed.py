import os
import requests
from dotenv import load_dotenv
from scriptsv2.utils.usable_function import UsableFunc
from concurrent.futures import ThreadPoolExecutor

load_dotenv(UsableFunc.paths('env'))
API_KEY = os.getenv('PAGESPEED_API_KEY')
api_url = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'


def fetch_and_store_data(website_url, category, device):
    params = {
        "url": website_url,
        "key": API_KEY,
        "strategy": device,
        "category": category
    }
    response = requests.get(api_url, params=params)
    score = response.json()['lighthouseResult']['categories']['-'.join(category.lower().split('_'))]['score']
    return category, device, score


def get_pagespeed_score(website_url):
    categories = ['PERFORMANCE', 'ACCESSIBILITY', 'BEST_PRACTICES', 'SEO']
    devices = ['desktop', 'mobile']
    performance_result = {}
    # Number of concurrent threads
    concurrent_threads = 8

    with ThreadPoolExecutor(max_workers=concurrent_threads) as executor:
        futures = []
        for category in categories:
            for device in devices:
                futures.append(executor.submit(fetch_and_store_data, website_url, category, device))

        for future in futures:
            category, device, score = future.result()
            if category not in performance_result:
                performance_result[category] = {}
            performance_result[category][device] = score

    return performance_result


if __name__ == "__main__":
    print(get_pagespeed_score("https://quartermoonplumbing.com/"))
