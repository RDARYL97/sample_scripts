import os
import json
import requests
from scriptsv2.utils.usable_function import UsableFunc
from dotenv import load_dotenv
from scriptsv2.logs.logs_config import CustomLogger
import boto3
import random

logging = CustomLogger.log('google_serp.log')
MAX_RETRIES = 3

load_dotenv(UsableFunc.paths('env'))
os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('BEDROCK_ACCESS_KEY')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('BEDROCK_SECRET_KEY')

BUCKET_NAME = 'chadix-creds'
FILE_KEY = 'google_api_keys.json'

s3 = boto3.client('s3')
response = s3.get_object(
    Bucket=BUCKET_NAME,
    Key=FILE_KEY
)
file_content_bytes = response['Body'].read()
file_content_string = file_content_bytes.decode('utf-8')
api_keys_list = json.loads(file_content_string)


class GoogleSearch:
    @staticmethod
    def google_search_config():
        title_limit = 10
        return title_limit

    @staticmethod
    def search_title(**kwargs):
        search_term = kwargs.get('search_term')
        api_key = random.choice(api_keys_list)
        title_dict = {}  # Initialize an empty dictionary to store results
        limit_title = GoogleSearch.google_search_config()  # Default is 20 Titles
        print(f"Begin getting Google Top 10 results from keyword: '{search_term}'\n")
        logging.info(f"Begin getting Google Top 10 results from keyword: '{search_term}'\n")
        # Custom Google Search API
        service_url = 'https://www.googleapis.com/customsearch/v1'

        # Retry the API call for each key
        for _ in range(MAX_RETRIES):
            try:
                # API call and response processing code goes here...
                # print(f"API Key: {api_key}")
                params = {
                    'q': search_term,
                    'key': api_key,
                    'cx': 'd41575ea43eb14ec0',
                    'num': limit_title  # This line specifies that we want 10 results
                }
                params.update(kwargs)

                response = requests.get(service_url, params=params)
                print(f"Response Status Code: {response.status_code}")  # Print response status code
                response_json = json.loads(response.text)
                # Check if 'items' in response_json

                print(json)
                if 'items' in response_json:
                    # Iterate over the items in the result
                    for item in response_json['items']:
                        title_dict[item['title']] = item['title']

                    print(f"Top 10 Google Organic result fetched!: \n{title_dict}")
                    logging.info(f"Top 10 Google Organic result fetched!: \n{title_dict}")

                    return title_dict
                else:
                    logging.info("No 'items' in the response. The keyword might have returned no results, or there might be an issue with the request.")
                    print("No 'items' in the response. The keyword might have returned no results, or there might be an issue with the request.")
                    # When quota exceeded error occurs (Response Code: 429), switch to next API key by not breaking the loop
                    if response.status_code == 429:
                        api_key = random.choice(api_keys_list)
                        continue
                    return None
            except Exception as e:
                logging.error(f"Error occurred: {e}. Retrying with the next key...")
                print(f"Error occurred: {e}. Retrying with the next key...")
        print("All attempts failed.")
        logging.error("All attempts failed.")
        return None


if __name__ == "__main__":
    GoogleSearch.search_title(search_term="create ai")
