import json

from google.ads.googleads.client import GoogleAdsClient
import yaml
import os

from scriptsv2.utils.usable_function import UsableFunc
from scriptsv2.logs.logs_config import CustomLogger

yaml_path = UsableFunc.paths('gkp_yaml')
secrets_dir = UsableFunc.paths('secrets')

logs_dir = os.path.join(os.path.dirname(secrets_dir), 'logs', 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
keyword_tool_logs_dir = os.path.join(logs_dir, 'keyword_tool_scripts')
if not os.path.exists(keyword_tool_logs_dir):
    os.makedirs(keyword_tool_logs_dir)

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'gkp.log'))

with open(yaml_path, 'r') as file:
    config = yaml.safe_load(file)

CUSTOMER_ID = str(config['client_customer_id'])
LOCATION_ID = ["2840"]   # location code for US. Refer to https://developers.google.com/google-ads/api/reference/data/geotargets
LANGUAGE_ID = "1000"   # language code for english. Refer to https://developers.google.com/google-ads/api/reference/data/codes-formats#expandable-7

MAX_RETRIES = 5


class GKP:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized Google Keyword Planner')
        logging.info('Initialized Google Keyword Planner')
        self.client = GoogleAdsClient.load_from_storage(yaml_path)
        self.customer_id = CUSTOMER_ID
        self.location_rn = LOCATION_ID
        self.language_rn = LANGUAGE_ID

    def get_keywords(self, keyword=None, url=None):
        print('Getting Keywords from Google Keyword Planner')
        logging.info('Getting Keywords from Google Keyword Planner')
        for i in range(MAX_RETRIES):
            try:
                if not (keyword or url):
                    logging.error("Neither URL nor Keyword was specified")
                    raise Exception(
                        "Neither URL nor Keyword was specified"
                    )
                request = self.client.get_type("GenerateKeywordIdeasRequest")
                request.customer_id = self.customer_id
                request.language = self.client.get_service("GoogleAdsService").language_constant_path(self.language_rn)
                request.geo_target_constants = self.map_locations_ids_to_resource_names(self.client, self.location_rn)
                request.include_adult_keywords = False
                request.keyword_plan_network = self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
                if not keyword and url:
                    request.url_seed.url = url
                if keyword and not url:
                    request.keyword_seed.keywords.append(keyword)
                if keyword and url:
                    request.keyword_and_url_seed.url = url
                    request.keyword_and_url_seed.keywords.append(keyword)

                gkp_service = self.client.get_service("KeywordPlanIdeaService")
                keyword_ideas = gkp_service.generate_keyword_ideas(request=request)
                if not keyword_ideas:
                    raise Exception(
                        "An error occurred getting keyword ideas on gkp"
                    )
                keywords_list = []
                for idea in keyword_ideas:
                    keywords_list.append({
                        'keyword': idea.text,
                        'search volume': idea.keyword_idea_metrics.avg_monthly_searches,
                        'keyword difficulty': idea.keyword_idea_metrics.competition_index,
                        "source": "GKP"
                    })

                sorted_list = []
                if keywords_list:
                    sorted_list = sorted(keywords_list, key=lambda x: x['search volume'], reverse=True)

                print(f'Successfully retrieved {len(sorted_list)} keywords from Google Keyword Planner')
                logging.info(f'Successfully retrieved {len(sorted_list)} keywords from Google Keyword Planner')

                return sorted_list

            except Exception as e:
                if self.debug:
                    print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")

            if i + 1 < MAX_RETRIES:
                if self.debug:
                    print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Error getting keywords from Google Keyword Planner")
                logging.error("Error getting keywords from Google Keyword Planner")
                return

    @staticmethod
    def map_locations_ids_to_resource_names(client, location_ids):
        build_resource_name = client.get_service(
            "GeoTargetConstantService"
        ).geo_target_constant_path

        return [build_resource_name(location_id) for location_id in location_ids]


if __name__ == "__main__":
    # print(GKP(debug=True).get_keywords(keyword="car rental san antonio"))
    print(json.dumps(GKP(debug=True).get_keywords(url='https://chadix.ai/'), indent=4))