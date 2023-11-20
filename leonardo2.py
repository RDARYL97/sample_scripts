import os
import time
import json
from typing import Union

import requests
import boto3
from dotenv import load_dotenv
from scriptsv2.leonardo.queries import GRAPH_QUERIES, elements_dict

from scriptsv2.utils.usable_function import UsableFunc

env_path = UsableFunc.paths('env')

load_dotenv(UsableFunc.paths('env'))

os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('BEDROCK_ACCESS_KEY')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('BEDROCK_SECRET_KEY')

BUCKET_NAME = 'chadix-creds'
FILE_KEYS = ['leonardo_creds.json', 'leonardo_creds_2.json']

MAX_RETRIES = 3
CURRENT_LEONARDO_INDEX = 0

MODEL_OPTIONS = {
    'DreamShaper v7': 'ac614f96-1082-45bf-be9d-757f2d31c174',
    'Absolute Reality v1.6': 'e316348f-7773-490e-adcd-46757c738eb7',
    'Leonardo Diffusion': 'b820ea11-02bf-4652-97ae-9ac0cc00593d',
    'RPG 4.0': 'a097c2df-8f0c-4029-ae0f-8fd349055e61',
    '3D Animation Style': 'd69c8273-6b17-4a30-a13e-d6637ae1c644',
    'Leonardo Diffusion XL': '1e60896f-3c26-4296-8ecc-53e2afecc132'
}


class Leonardo:
    def __init__(self):
        self.current_index = self.toggle_index()
        self.session = requests.Session()
        self.api_url = 'https://api.leonardo.ai/v1/graphql'
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        })
        self.s3 = boto3.client('s3')
        response = self.s3.get_object(
            Bucket=BUCKET_NAME,
            Key=FILE_KEYS[self.current_index]
        )
        file_content_bytes = response['Body'].read()
        file_content_string = file_content_bytes.decode('utf-8')
        self.credentials_json = json.loads(file_content_string)
        self.user_id = self.credentials_json['leonardo']['uuid']
        self.session.cookies.set('__Secure-next-auth.session-token.0', self.credentials_json['leonardo']['session_token_0'])
        self.session.cookies.set('__Secure-next-auth.session-token.1', self.credentials_json['leonardo']['session_token_1'])

    @staticmethod
    def toggle_index():
        global CURRENT_LEONARDO_INDEX
        CURRENT_LEONARDO_INDEX = 1 - CURRENT_LEONARDO_INDEX

        return CURRENT_LEONARDO_INDEX

    def _authenticate(self):
        print('Getting new authorization code')
        self.session.cookies.clear()
        self.session.headers.pop('Authorization', None)
        response = self.session.get('https://app.leonardo.ai/api/auth/session')
        if response.status_code != 200:
            raise Exception(
                f'Status: {response.status_code} at app.leonardo.ai/api/auth/session'
            )
        csrf = None
        for cookie in response.cookies:
            if cookie.name == '__Host-next-auth.csrf-token':
                csrf = cookie.value.split('%')[0]
                break
        if not csrf:
            raise Exception(
                'csrf cookie not found'
            )
        url = 'https://app.leonardo.ai/api/auth/callback/credentials'
        self.session.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded'
        })
        data = {
            'username': self.credentials_json['leonardo']['email'],
            'password': self.credentials_json['leonardo']['password'],
            'redirect': 'false',
            'csrfToken': csrf,
            'callbackUrl': 'https://app.leonardo.ai/auth/login',
            'json': 'true'
        }
        response = self.session.post(url, data=data)
        if response.status_code != 200:
            raise Exception(
                f'Status: {response.status_code} at app.leonardo.ai/api/auth/callback/credentials'
            )
        for cookie in response.cookies:
            if cookie.name == '__Secure-next-auth.session-token.0':
                self.credentials_json['leonardo']['session_token_0'] = cookie.value
            if cookie.name == '__Secure-next-auth.session-token.1':
                self.credentials_json['leonardo']['session_token_1'] = cookie.value
        self.s3.put_object(
            Bucket=BUCKET_NAME,
            Key=FILE_KEYS[self.current_index],
            Body=json.dumps(self.credentials_json, indent=2),
            ContentType='application/json'
        )

    def generate_images(
            self,
            image_prompt: Union[str, list],
            model_option: str = 'DreamShaper v7',
            type_option: str = 'DYNAMIC',
            num_images: int = 4,
            width: int = 512,
            height: int = 768,
            enable_alchemy: bool = True,
            elements: list = None,
            negative_prompt: str = ''
    ) -> dict:
        if elements:
            elements = [{
                "akUUID": elements_dict.get(pair[0].lower(), None),
                "weight": pair[1]
            } for pair in elements if elements_dict.get(pair[0], None) is not None]
        else:
            elements = []
        print(elements)
        if type(image_prompt) not in [list, str]:
            raise Exception(
                'Invalid prompt type. Must be string or list only'
            )
        if type(image_prompt) == str:
            image_prompt = [image_prompt]

        for _ in range(MAX_RETRIES):
            try:
                print('Sending image prompt')
                result = {}
                response = self.session.get('https://app.leonardo.ai/api/auth/session')
                if 'accessToken' not in response.json():
                    raise Exception(
                        'Session token expired'
                    )
                auth_token = response.json()['accessToken']
                self.session.headers.update({
                    'Authorization': f"Bearer {auth_token}"
                })
                for prompt in image_prompt:
                    data = {
                        "query": GRAPH_QUERIES['CreateSDGenerationJob'],
                        "variables": {
                            "arg1": {
                                "prompt": prompt,
                                "negative_prompt": negative_prompt,
                                "nsfw": True,
                                "num_images": num_images,
                                "width": width,
                                "height": height,
                                "num_inference_steps": 10,
                                "guidance_scale": 15,
                                "init_strength": 0.55,
                                "sd_version": "v1_5",
                                "elements": elements,
                                "modelId": MODEL_OPTIONS[model_option],
                                "presetStyle": type_option.upper(),
                                "scheduler": "LEONARDO",
                                "public": True,
                                "tiling": False,
                                "leonardoMagic": True,
                                "imagePrompts": [],
                                "imagePromptWeight": 0.45,
                                "alchemy": enable_alchemy,
                                "highResolution": False,
                                "contrastRatio": 0.5,
                                "poseToImage": False,
                                "poseToImageType": "POSE",
                                "weighting": 1,
                                "highContrast": True,
                                "expandedDomain": True,
                                "leonardoMagicVersion": "v3",
                                "photoReal": False
                            }
                        },
                    }
                    response = self.session.post(self.api_url, json=data)
                    if "errors" in response.json():
                        raise Exception(response.json()['errors'][0]['message'])
                    generation_id = response.json()['data']['sdGenerationJob']['generationId']
                    start_time = time.time()
                    max_wait_time = 3*60  # max wait time to render images
                    print('Rendering images')
                    while time.time()-start_time < max_wait_time:
                        data = {
                            "query": GRAPH_QUERIES['GetAIGenerationFeed'],
                            "variables": {
                                "where": {
                                    "userId": {"_eq": self.user_id},
                                    "status": {"_in": ["COMPLETE", "FAILED"]},
                                    "id": {"_in": [generation_id]}
                                },
                                "offset": 0
                            }
                        }
                        response = self.session.post(self.api_url, json=data)
                        if "errors" in response.json():
                            raise Exception(response.json()['errors'][0]['message'])
                        if response.json()['data']['generations']:
                            images = []
                            for generated_image in response.json()['data']['generations'][0]['generated_images']:
                                images.append(generated_image['url'])

                            result[prompt] = images
                            break
                if not result:
                    raise Exception(
                        'Timeout error, rendering exceeded set timeout'
                    )
                return result

            except Exception as e:
                print(f'An error occurred: {str(e)}')
                if str(e) == 'Session token expired':
                    self._authenticate()
                if _ + 1 < MAX_RETRIES:
                    print("Retrying...")


''' 
AVAILABLE MODEL OPTIONS
    DreamShaper v7  <---- default
    Absolute Reality v1.6
    Leonardo Diffusion
    RPG 4.0
    3D Animation Style

AVAILABLE TYPE OPTIONS
    ANIME
    CREATIVE
    DYNAMIC  <---- default
    ENVIRONMENT
    GENERAL
    ILLUSTRATION
    PHOTOGRAPHY
    RAYTRACED
    RENDER_3D
    SKETCH_BW
'''

'''
DEFAULT VALUES
    model_option            DreamShaper v7
    type_option                    DYNAMIC
    num_images                           4
    width                              512
    height                             768
    enable_alchemy                    True
'''

'''
AVAILABLE ELEMENTS
    Baroque
    Biopunk
    Celtic Punk
    Crystalline
    Ebony & Gold
    Gingerbread
    Glass & Steel
    Inferno
    Ivory & Gold
    Lunar Punk
    Pirate Punk
    Tiki
    Toxic Punk
    
Elements usage, pass a list of tuple in the format of (element model, weight). 
Weight(decimal) ranges from -1 to 2
Maximum of 4 elements for each prompt

Example: 
elements = [("Baroque", 0.4), ("Inferno", 2), ("Glass & Steel", -0.5), ("Ivory & Gold", -1)]
'''

# Example usage
if __name__ == "__main__":
    ''' prompt can be a string or a list for batch image generations '''
    start_time = time.time()
    prompt = [
            'Spiderman is shooting the web to a shitzu dog, Shiro, so that he can eat bone',
            'Best beef recipe with carrots and potato'
        ]

    # prompt = ['cat in planet mercury', 'cat in planet venus', 'cat in planet earth', 'cat in planet mars']

    ''' simple image prompt using default values '''
    # generated_images = Leonardo().generate_images(prompt)

    ''' customized image prompt '''
    generated_images = Leonardo().generate_images(
        prompt,
        model_option='DreamShaper v7',
        type_option='ILLUSTRATION',
        num_images=2,
        width=1024,
        height=768,
        elements=[("Toxic Punk", 0.5), ("Tiki", -1)]
    )

    print(generated_images)

    '''
    Sample output format
    {
    prompt1: [img1, img2, img3, img4],
    prompt2: [img1, img2, img3, img4],
    prompt3: [img1, img2, img3, img4],
    prompt4: [img1, img2, img3, img4]
    }
    '''

    end_time = time.time()

    # Calculate total time in seconds
    total_time_seconds = int(end_time - start_time)

    # Calculate minutes and remaining seconds
    minutes = total_time_seconds // 60
    seconds = total_time_seconds % 60

    # Format the time
    formatted_time = f"{minutes} minutes and {seconds} seconds"

    print("TOTAL PROCESSING TIME: ", formatted_time)
