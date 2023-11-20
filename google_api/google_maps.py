import os
import requests
import boto3
import math
from dotenv import load_dotenv
from urllib.parse import urlparse
import concurrent.futures
from itertools import repeat
from scriptsv2.utils.usable_function import UsableFunc

load_dotenv(UsableFunc.paths('env'))
os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('BEDROCK_ACCESS_KEY')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('BEDROCK_SECRET_KEY')

BUCKET_NAME = 'chadix-creds'
FILE_KEY = 'google_api.txt'


def get_url_netloc(url):
    url = url.replace("http://", "https://").replace("www.", "")
    if not url.startswith("https://"):
        url = f"https://{url}"
    return urlparse(url).netloc


def add_coordinates_and_miles(reference_coordinates, miles_to_subtract):
    degrees_latitude = miles_to_subtract[0] / 69
    degrees_longitude = miles_to_subtract[1] / (69 * math.cos(math.radians(reference_coordinates[0])))
    new_latitude = reference_coordinates[0] + degrees_latitude
    new_longitude = reference_coordinates[1] + degrees_longitude

    return new_latitude, new_longitude


class GoogleMapsAPI:
    def __init__(self):
        s3 = boto3.client('s3')
        file_object = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=FILE_KEY
        )
        file_content_bytes = file_object['Body'].read()
        self.api_key = file_content_bytes.decode('utf-8')

    def get_business_profile(self, url):
        """
        Retrieve business profile information for a given URL.

        Args:
            url (str): The URL associated with the business for which you want to retrieve the profile.

        Returns:
            dict or None: A dictionary containing business profile information if a match is found, or None if no match
            is found.
        """
        query_result = self.auto_complete_query(get_url_netloc(url))
        place_ids = [query["place_id"] for query in query_result]
        for place_id in place_ids:
            details = self.get_place_details(place_id)
            if details:
                if get_url_netloc(details["website"]) == get_url_netloc(url):
                    print(place_id)
                    return details

        return None

    def get_place_details(self, place_id):
        """
        Retrieve detailed information about a business using its place ID.

        Args:
            place_id (str): The place ID associated with the business for which you want to retrieve details.

        Returns:
            dict: A dictionary containing detailed information about the business.
        """
        params = {
            "place_id": place_id,
            "fields": "name,rating,user_ratings_total,website,formatted_address,"
                      "types,business_status,formatted_phone_number,geometry",
            "key": self.api_key
        }
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params=params
        )

        result = response.json()["result"]
        geometry = result.get("geometry", None)
        if geometry:
            coordinates = geometry["location"]
        else:
            coordinates = None
        result.pop("geometry", None)
        result["coordinates"] = coordinates

        return result

    def auto_complete_query(self, url):
        params = {
            "input": url,
            "key": self.api_key
        }
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params=params
        )
        results = []
        for result in response.json()['predictions']:
            results.append(result)

        return results

    def get_local_competitors(self, keyword, coordinates=(None, None), radius=0, top=10):
        """
        Retrieve information about local competitors based on a given keyword and location.

        Args:
            keyword (str): The keyword or search term to use for identifying competitors.
            coordinates (tuple, required): A tuple representing the latitude and longitude of the location.
            radius (int, required): The search radius in miles around the specified location.
            top (int, optional): Max number of profiles to be returned. Can return lower if the specified value
                                is higher than the total results. Defaults to 10. Set to None or False to disable
                                and return all values

        Returns:
            list: A list of competitor profiles, each containing detailed information about a local competitor.
        """
        if None in coordinates or type(coordinates) != tuple:
            return "Please specify a valid coordinate"
        if not radius:
            return "Please specify a radius"
        radius_in_meters = radius * 1609.344
        params = {
            "keyword": keyword,
            "location": f"{coordinates[0]},{coordinates[1]}",
            "radius": radius_in_meters,
            "key": self.api_key
        }
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params=params
        )
        results = response.json()["results"]
        place_ids = []
        for result in results:
            place_ids.append(result['place_id'])

        competitors_profile = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for result in executor.map(self.get_place_details, place_ids):
                competitors_profile.append(result)
        if top:
            return competitors_profile[:top]
        else:
            return competitors_profile

    def get_area_rankings(
        self,
        url=None,
        keyword=None,
        distance=None,
        size=None,
        shape="circle"
    ):
        coordinates = tuple(self.get_business_profile(url)["coordinates"].values())
        coordinates_list = self.generate_coordinates(shape, coordinates, distance, size)
        area_rankings = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for result in executor.map(self.get_keyword_rank, repeat(url), repeat(keyword), coordinates_list, repeat(distance*size)):
                area_rankings.append(result)

        return area_rankings

    def get_keyword_rank(self, url, keyword, coordinates, radius=10):
        rank_profiles = self.get_local_competitors(keyword, coordinates=coordinates, radius=radius, top=None)
        index = None
        for i, profile in enumerate(rank_profiles):
            if "website" not in profile:
                continue
            if get_url_netloc(profile["website"]) == get_url_netloc(url):
                index = i + 1
                break
        return {
            coordinates: {
            "keyword": keyword,
            "url": url,
            "local_rank": index,
            "rank_profiles": rank_profiles
        }}

    @staticmethod
    def generate_coordinates(shape, center_coordinate, distance, size):
        coordinates = []
        if shape.lower() == 'circle':
            circle_count = math.ceil(size / 2)
            for i in range(circle_count):
                radius = distance * (i if size % 2 else i + 0.5)
                circumference = 2 * math.pi * radius

                if not circumference:
                    coordinates.append(center_coordinate)
                    continue

                n = round(circumference / distance)
                angle_increment = (2 * math.pi) / n

                for j in range(n):
                    angle = j * angle_increment
                    x = round(radius * math.cos(angle + math.pi / 2), 8)
                    y = round(radius * math.sin(angle + math.pi / 2), 8)
                    coordinate = add_coordinates_and_miles(center_coordinate, (x,y))
                    coordinates.append(coordinate)

        elif shape.lower() == 'square':
            coordinates.append(center_coordinate)
            for i in range(size):
                for sign in [(1, 1), (-1, 1), (-1, -1), (1, -1)]:
                    x = center_coordinate[0] + sign[0] * i * distance / 2
                    y = center_coordinate[1] + sign[1] * i * distance / 2
                    for j in range(i):
                        x_0 = x - sign[0] * j * distance
                        y_0 = y - sign[1] * j * distance
                        coordinates.append((x_0, y))
                        coordinates.append((x, y_0))
        else:
            raise Exception('Invalid shape. Please choose between "circle" and "square"')

        return list(set(coordinates))


if __name__ == "__main__":
    # print(GoogleMapsAPI().get_business_profile("https://beardfamilychiro.com/"))
    print(GoogleMapsAPI().auto_complete_query("quartermoonplumbing.com"))
    # print(GoogleMapsAPI().get_keyword_rank("https://quartermoonplumbing.com/", "plumbing", (35.0654111, -92.4370819)))
    # area_rankings = GoogleMapsAPI().get_area_rankings(
    #     url="https://quartermoonplumbing.com/",
    #     keyword="plumbing",
    #     distance=1,
    #     size=5,
    # )
    # print(len(area_rankings))
    # print(area_rankings)

    # coordinates = GoogleMapsAPI.generate_coordinates("square", (0,0) , 1, 4)
    # print(coordinates)
    # for coordinate in coordinates:
    #     coordinate = list(coordinate)
    #     print(f"{coordinate[0]},{coordinate[1]}")
