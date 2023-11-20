import os
import re
import json
import concurrent.futures
from fake_useragent import UserAgent
import cloudscraper
from urllib.parse import urlparse
from datetime import datetime
from dotenv import load_dotenv

from scriptsv2.logs.logs_config import CustomLogger
from scriptsv2.utils.usable_function import UsableFunc
from scriptsv2.utils.google_api.google_maps import get_url_netloc

MAX_RETRIES = 3
logging = CustomLogger.log("keyword_ranking.log")
env_path = UsableFunc.paths('env')
load_dotenv(env_path)


class KeywordRanking:
    def __init__(self):
        logging.info('Initialized KeywordRanking')
        self.session = cloudscraper.Session()
        self.user_agent = UserAgent()
        self.session.headers.update({
            'Accept': "*/*"
        })
        self.proxy = {
            'http': os.getenv('PROXY'),
            'https': os.getenv('PROXY')
        }
        self.session.headers.update({
            'content-type': 'application/x-www-form-urlencoded',
        })
        self.api_key = os.getenv('SERPAPI_KEY')
        self.latest_error = None
        self.exact_location = None

    def get_keywords_ranking(self, keywords, website_url=None, location='United States', max_retries=MAX_RETRIES):
        if type(keywords) not in [str, list]:
            raise TypeError(
                'Error: Keyword argument must be a string or a list'
            )
        if isinstance(keywords, str):
            keywords = [keywords]
        results = []
        thread_pool_size = min(4, len(keywords))
        # eocode, exact_location = self.get_location_code(location)
        with concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
            threads = []
            for keyword in keywords:
                thread = executor.submit(
                    self._get_rank,
                    keyword,
                    website_url=website_url,
                    location=location,
                    max_retries=max_retries,
                )
                threads.append(thread)
            for thread in concurrent.futures.as_completed(threads):
                result = thread.result()
                results.append(result)
            if results:
                return {
                    'status': 'success',
                    'data': {
                        'location': self.exact_location,
                        'date_retrieved': datetime.now().strftime("%m-%d-%Y"),
                        'results': results
                    }
                }
        return {
            'status': 'failed',
            'error': self.latest_error
        }

    def _get_rank(self, keyword, website_url=None, location='United States', max_retries=MAX_RETRIES):
        google_result = self.get_google_top_results(keyword, location, total=200, max_retries=max_retries)
        if google_result:
            logging.info('Getting keyword rank in results')
            for rank, result in google_result['result'].items():
                if get_url_netloc(website_url.lower()) == get_url_netloc(result['base_url']):
                    return {
                        'keyword': keyword,
                        'rank': int(rank),
                        'result_url': result['base_url'],
                    }

        return {
            'keyword': keyword,
            'rank': None,
            'result_url': None,
        }

    def get_google_top_results(self, q, location='United States', total=10, max_retries=MAX_RETRIES):
        for i in range(max_retries):
            try:
                self.session.cookies.clear()
                self.session.headers.update({
                    "User-Agent": self.user_agent.random
                })
                response = self.session.get('https://ads.google.com/anon/AdPreview', proxies=self.proxy)
                token = re.search(r"xsrfToken: '(.*?)'", response.text).group(1)
                self.session.headers.update({
                    'content-type': 'application/x-www-form-urlencoded',
                    'x-framework-xsrf-token': token
                })
                if not isinstance(location, int):
                    location, self.exact_location = self.get_location_code(location)
                logging.info('Getting google search link in a specified location')
                uule = self.get_uule(q, location)
                logging.info('Getting google results')
                self.session.headers.pop('x-framework-xsrf-token', None)
                params = {
                    "q": q,
                    "uule": uule,
                    "api_key": self.api_key,
                    "num": total
                }
                response = self.session.get('https://serpapi.com/search', params=params)
                # response = self.session.get(search_url, proxies=self.proxy)
                if response.json()['search_metadata']['status'] != 'Success':
                    raise Exception(f"Status: {response.json()['search_metadata']['status']}")
                search_results = {}
                for result in response.json()['organic_results']:
                    href_link = result['link']
                    parsed_url = urlparse(href_link)
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    search_results.update({
                        result['position']: {
                            'title': result['title'],
                            'result_url': href_link,
                            'base_url': base_url
                        }
                    })

                if not search_results:
                    raise Exception('No search results found')

                return {
                    'result': search_results
                }

            except Exception as e:
                self.latest_error = str(e)
                print(str(e))
                logging.error(f"An error occurred: {str(e)}")

            if i + 1 < max_retries:
                print("Retrying...")
                logging.info("Retrying...")
                self.__init__()

    def get_uule(self, q, geocode):
        url = 'https://ads.google.com/aw_anonymous_diagnostic/_/rpc/PreviewService/GetPreviewAnonymous'
        data = {
            "__ar": json.dumps({
                "2": q,
                "4": {
                    "2": "en",
                    "3": geocode,
                    "5": "30000"
                }
            })
        }
        response = self.session.post(url, data=data, proxies=self.proxy)
        if response.status_code != 200:
            raise Exception(
                'Error getting uule parameter for search url'
            )
        uule_match = re.search(r'uule\\u003dw\+(.*?)\\u0026', response.text)
        if not uule_match:
            raise Exception(
                'uule parameter was not found'
            )
        uule = f"w {uule_match.group(1)}"

        return uule

    def get_location_code(self, address):
        url = 'https://ads.google.com/aw_anonymous_diagnostic/_/rpc/GeopickerDataService/GetLocationDataSuggestions'
        data = {
            "__ar": json.dumps({
                "1": address,
                "4": 1
            })
        }
        response = self.session.post(url, data=data, proxies=self.proxy)
        if response.status_code != 200:
            raise Exception(
                'Error getting geolocation code'
            )

        return response.json()["1"][0]["1"]["1"], response.json()["1"][0]["1"]["3"]


# Example usage
if __name__ == "__main__":
    keyword_list = [
        'car rental txcarrent',
        'car rental san antonio',
        'txcarrent car rental in san antonio tx',
        'txcarrent'
    ]
    rank_result = KeywordRanking().get_keywords_ranking(
        keyword_list,
        website_url='https://txcarrent.com',
        location='us'
    )

    print(json.dumps(rank_result, indent=4))

    # print(KeywordRanking().get_google_top_results(
    #     "coffee",
    #     "Butuan City, PH"
    # ))
