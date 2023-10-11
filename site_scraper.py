import os
import uuid
from curl_cffi import requests
from dotenv import load_dotenv

from scriptsv2.utils.usable_function import UsableFunc

MAX_RETRIES = 3

INTENTS = ['commercial', 'informational', 'navigational', 'transactional']


class SemrushScraper:
    def __init__(self):
        load_dotenv(UsableFunc.paths('kenv'))
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': '*/*',
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        })
        self.api_key = os.getenv('SEMRUSH_API_KEY')

    def get_site_positions(self, url):
        for _ in range(MAX_RETRIES):
            try:
                position_data = []
                request_id = str(uuid.uuid4())
                data = {
                    "id": 2,
                    "jsonrpc": "2.0",
                    "method": "organic.PositionsTotal",
                    "params": {
                        "request_id": request_id,
                        "report": "organic.positions",
                        "args": {
                            "database": "us",
                            "dateType": "daily",
                            "searchItem": url,
                            "searchType": "domain",
                            "positionsType": "all",
                            "filter": {}
                        },
                        "apiKey": self.api_key
                    }
                }
                response = self.session.post("https://www.semrush.com/dpa/rpc", json=data)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                num_results = response.json()['result']
                data = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "organic.Positions",
                    "params": {
                        "request_id": request_id,
                        "report": "organic.positions",
                        "args": {
                            "database": "us",
                            "dateType": "daily",
                            "searchItem": url,
                            "searchType": "domain",
                            "positionsType": "all",
                            "filter": {},
                            "display": {
                                "order": {
                                    "field": "trafficPercent",
                                    "direction": "desc"
                                },
                                "page": 1,
                                "pageSize": num_results
                            }
                        },
                        "apiKey": self.api_key
                    }
                }
                response = self.session.post("https://www.semrush.com/dpa/rpc", json=data)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                results = response.json()['result']
                for result in results:
                    position_data.append({
                        'keyword': result['phrase'],
                        'intents': [INTENTS[i] for i in result['intents']],
                        'position': result['position'],
                        'volume': result['volume'],
                        'keyword_difficulty': result['keywordDifficulty'],
                        'url': result['url'],
                        'crawled_time': result['crawledTime']
                    })
                if position_data:
                    position_data = sorted(position_data, key=lambda x: x['volume'], reverse=True)
                return {
                    "total": len(position_data),
                    "keywords_data": position_data
                }

            except Exception as e:
                print(str(e))

        return None

    def get_site_competitors(self, url):
        for _ in range(MAX_RETRIES):
            try:
                competitors_data = []
                request_id = str(uuid.uuid4())
                data = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "organic.CompetitorsTotal",
                    "params": {
                        "request_id": request_id,
                        "report": "organic.competitors",
                        "args": {
                            "database": "us",
                            "searchItem": url,
                            "searchType": "domain",
                            "dateType": "daily"
                        },
                        "apiKey": self.api_key
                    }
                }
                response = self.session.post("https://www.semrush.com/dpa/rpc", json=data)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                num_results = response.json()['result']
                data = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "organic.Competitors",
                    "params": {
                        "request_id": request_id,
                        "report": "organic.competitors",
                        "args": {
                            "database": "us",
                            "searchItem": url,
                            "searchType": "domain",
                            "dateType": "daily",
                            "display": {
                                "order": {
                                    "field": "competitionLvl",
                                    "direction": "desc"
                                },
                                "page": 1,
                                "pageSize": num_results
                            }
                        },
                        "apiKey": self.api_key
                    }
                }
                response = self.session.post("https://www.semrush.com/dpa/rpc", json=data)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                results = response.json()['result']
                for result in results:
                    competitors_data.append({
                        'domain': result['domain'],
                        'competition_level': result['competitionLvl'],
                        'common_keywords': result['commonKeywords'],
                        'adwords_position': result['adwordsPositions'],
                        'organic_position': result['organicPositions'],
                        'organic_traffic': result['organicTraffic'],
                        'organic_traffic_cost': result['organicTrafficCost'],
                        'positions': result['positions'],
                        'serp_features_positions': result['serpFeaturesPositions'],
                        'serp_features_traffic': result['serpFeaturesTraffic'],
                        'serp_features_traffic_cost': result['serpFeaturesTrafficCost'],
                        'traffic': result['traffic'],
                        'traffic_cost': result['trafficCost']
                    })
                if competitors_data:
                    competitors_data = sorted(competitors_data, key=lambda x: x['competition_level'], reverse=True)
                return {
                    "total": len(competitors_data),
                    "competitors_data": competitors_data
                }

            except Exception as e:
                print(str(e))

        return None

    def get_pages_data(self, url):
        for _ in range(MAX_RETRIES):
            try:
                pages_data = []
                request_id = str(uuid.uuid4())
                data = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "organic.PagesTotal",
                    "params": {
                        "request_id": request_id,
                        "report": "organic.overview",
                        "args": {
                            "database": "us",
                            "dateType": "daily",
                            "searchItem": url,
                            "searchType": "domain"
                        },
                        "apiKey": self.api_key
                    }
                }
                response = self.session.post("https://www.semrush.com/dpa/rpc", json=data)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                num_results = response.json()['result']
                data = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "organic.Pages",
                    "params": {
                        "request_id": request_id,
                        "report": "organic.pages",
                        "args": {
                            "database": "us",
                            "searchItem": url,
                            "searchType": "domain",
                            "dateType": "daily",
                            "filter": {},
                            "display": {
                                "order": {
                                    "field": "traffic",
                                    "direction": "desc"
                                },
                                "page": 1,
                                "pageSize": num_results
                            }
                        },
                        "apiKey": self.api_key
                    }
                }
                response = self.session.post("https://www.semrush.com/dpa/rpc", json=data)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                results = response.json()['result']
                for result in results:
                    pages_data.append({
                        'url': result['url'],
                        'traffic_percentage': result['trafficPercent'],
                        'keywords_total': result['positions'],
                    })
                if pages_data:
                    pages_data = sorted(pages_data, key=lambda x: x['traffic_percentage'], reverse=True)
                return {
                    "total": len(pages_data),
                    "pages_data": pages_data
                }

            except Exception as e:
                print(str(e))

        return None

    def get_backlinks_data(self, url):
        for _ in range(MAX_RETRIES):
            try:
                backlinks_data = []
                params = {
                    "action": "report",
                    "key": self.api_key,
                    "type": "backlinks",
                    "target": url,
                    "target_type": "root_domain",
                    "display_page": 0,
                    "sort_field": "page_ascore",
                    "sort_type": "desc"
                }
                response = self.session.get("https://www.semrush.com/backlinks/webapi2", params=params)
                if "error" in response.json():
                    raise Exception(
                        f"An error occurred: {response.json()['error']['message']}"
                    )
                results = response.json()
                for data in results["backlinks"]["data"]:
                    backlinks_data.append({
                        "source_url": data["source_url"],
                        "source_title": data["source_title"],
                        "page_ascore": data["page_ascore"],
                        "domain_ascore": data["domain_ascore"],
                        "target_url": data["target_url"],
                        "anchor": data["anchor"],
                        "external_link_num": data["external_link_num"],
                        "internal_link_num": data["internal_link_num"]
                    })
                if backlinks_data:
                    backlinks_data = sorted(backlinks_data, key=lambda x: x['page_ascore'], reverse=True)
                return {
                    "total": len(backlinks_data),
                    "backlinks_data": backlinks_data
                }

            except Exception as e:
                print(str(e))


if __name__ == "__main__":
    result = SemrushScraper().get_backlinks_data('https://www.chiropracticcenter-houston.com/')
    print(result)