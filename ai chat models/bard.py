import random, json, ast, os, re

from dotenv import load_dotenv
import boto3
import requests

from scriptsv2.utils.usable_function import UsableFunc
from scriptsv2.logs.logs_config import CustomLogger
from scriptsv2.utils.progressbar.progress_icon import ProgressBar

load_dotenv(UsableFunc.paths('env'))
os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('BEDROCK_ACCESS_KEY')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('BEDROCK_SECRET_KEY')

BUCKET_NAME = 'chadix-creds'
FILE_KEY = 'bard_cookies.json'

s3 = boto3.client('s3')
file_object = s3.get_object(
    Bucket=BUCKET_NAME,
    Key=FILE_KEY
)
file_content_bytes = file_object['Body'].read()
file_content_string = file_content_bytes.decode('utf-8')
bard_json = json.loads(file_content_string)

CHOICES = ["**navigational**", "**informational**", "**commercial**", "**transactional**"]

SESSION_HEADERS = {
    "Host": "bard.google.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
}

MAX_RETRIES = 3
logging = CustomLogger.log("bard.log")


class BardAPI:
    def __init__(self):
        print('Initialized Bard')
        logging.info('Initialized Bard')
        self.cookies = random.choice(bard_json)['cookies']
        proxy = os.getenv('PROXY')
        self.proxy = {
            'http': proxy,
            'https': proxy
        }
        self.session = requests.Session()
        self.session.headers.update(SESSION_HEADERS)
        self.pbar = None

    def _get_snim0e(self) -> str:
        print('Getting snim0e token of the page')
        logging.info('Getting snim0e token of the page')
        resp = self.session.get(
            "https://bard.google.com/", timeout=30, proxies=self.proxy, stream=True
        )
        response_bytes = b""
        for chunk in resp.iter_content(chunk_size=2048):
            response_bytes += chunk
            break
        response_text = response_bytes.decode("utf-8")
        if resp.status_code != 200:
            raise Exception(
                f"Response code not 200. Response Status is {resp.status_code}"
            )
        snim0e = re.search(r"SNlM0e\":\"(.*?)\"", response_text)
        if not snim0e:
            raise Exception(
                "SNlM0e value not found"
            )
        if snim0e.group(1):
            return snim0e.group(1)
        else:
            raise Exception(
                "SNlM0e value not found"
            )

    def get_search_intent(self, search_keyword: str) -> list:
        print('Getting search intent')
        logging.info('Getting search intent')
        for _ in range(MAX_RETRIES):
            try:
                prompt = f'''
                    whats the user search intent for: {search_keyword} 
                    Is navigational, informational, commercial, or transactional?
                    '''
                response = self.prompt(prompt)
                if response is not None:
                    answer = find_first_word(response, CHOICES)
                    if not answer:
                        raise Exception(
                            "No search intent on response, trying again"
                        )
                    print([True, search_keyword, answer])
                    logging.info([True, search_keyword, answer])
                    return [True, search_keyword, answer]

                else:
                    raise Exception(
                        "An error occurred getting response"
                    )

            except Exception as e:
                print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")
                if str(e) == "SNlM0e value not found":
                    self.cookies = random.choice(bard_json)['cookies']
                    print("Switching account")
                    logging.error("Switching account")

            if _ + 1 < MAX_RETRIES:
                print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Bard script send prompt encountered an error")
                logging.error("Bard script send prompt encountered an error")
                return [False, search_keyword, f"Search intent script encountered an error"]

    def send_prompt(self, prompt):
        for _ in range(MAX_RETRIES):
            try:
                bard_response = self.prompt(prompt)
                return bard_response

            except Exception as e:
                print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")
                if str(e) == "SNlM0e value not found":
                    self.cookies = random.choice(bard_json)['cookies']
                    print("Switching account")
                    logging.error("Switching account")

            if _ + 1 < MAX_RETRIES:
                print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Bard script send prompt encountered an error")
                logging.error("Bard script send prompt encountered an error")
                return

    def prompt(self, prompt):
        self.session.cookies.update(self.cookies)
        page_token = self._get_snim0e()
        params = {
            "bl": "boq_assistant-bard-web-server_20230419.00_p1",
        }

        input_text_struct = [
            [prompt],
            None,
            ["", "", ""],
        ]
        data = {
            "f.req": json.dumps([None, json.dumps(input_text_struct)]),
            "at": page_token,
        }
        print(f'Sending prompt: {prompt}')
        logging.info(f'Sending prompt {prompt}')

        resp = self.session.post(
            "https://bard.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate",
            params=params,
            data=data,
            timeout=600,
            proxies=self.proxy,
        )
        raw_list = resp.text.split(")]}'\n\n")[1]
        raw_list = raw_list.replace("null", "None")
        raw_list = raw_list.replace('true', 'False')
        raw_list = raw_list.replace('false', 'False')
        response_list = ast.literal_eval(raw_list)[0][2]
        if not response_list:
            raise Exception(resp.text)
        final_list = ast.literal_eval(response_list)
        bard_response = final_list[4][0][1][0]
        return bard_response


def find_first_word(paragraph, word_list):
    pattern = r'[^a-zA-Z0-9\s*]'

    # Use regular expression substitution to remove special characters
    cleaned_paragraph = re.sub(pattern, '', paragraph)
    for word in cleaned_paragraph.lower().split(' '):
        # Check if the word is in the word list
        if word in word_list:
            earliest_word = word
            return earliest_word.replace('*', '')

    for word in cleaned_paragraph.lower().split(' '):
        if f'**{word}**' in word_list:
            earliest_word = word
            return earliest_word


# for testing purposes only
if __name__ == "__main__":
    # get search intent example. input: word/phrase (str), output: bool + search intent (list)
    # result = BardAPI().get_search_intent("Ai tools?")
    # if result[0]:
    #     print(f'Search intent of "{result[1]}" is {result[2]}')

    # send prompt example. input: prompt (str), output: bard AI response (str)

    prompt = """
     Write it in English language.

[PURPOSE]
The purpose of this website is to introduce The Attic AI, an innovative AI-powered knowledge management solution. With natural language processing technology, The Attic AI allows companies to create searchable databases from unstructured content, transforming documents into interactive chatbots. This provides instant access to accurate information for employees and customers.

The owner of The Attic AI has over 10 years of experience developing AI assistants and knowledge management systems. The homepage introduces the product benefits, such as saving time and boosting productivity. It targets decision-makers in customer service, sales, marketing, product design, and software engineering.

The goal is to attract visitors to explore pricing options, view demos, and envision the impact on their business. Testimonials establish credibility and calls-to-action encourage contacting for a consultation or free trial.

As an authority in AI knowledge management, the aim is to convince visitors that The Attic AI is the easiest and most powerful way to organize their informational attic. Highlighting versatility, security, compliance, and multilingual capabilities establishes why businesses should choose this solution over alternatives. The site showcases how it can revolutionize information access to boost productivity and delight users.
[/PURPOSE]

[TOPIC OUTLINE]
## Introduction
- Brief overview of AI creation
- Importance of AI in today's digital world

## What is AI Art Generation?
- Definition of AI Art Generation
- How it works 
- Examples of AI Art Generation 

### Different Types of AI Art Generators
- Stable Diffusion 
- DALL-E 2 
- CLIP-Guided Diffusion 
- VQGAN+CLIP 
- Neural Style Transfer 

## How to Create Stunning Images with OpenArt?
- Overview of OpenArt platform
    - Features and benefits
    - Pricing details
    - Community engagement opportunities (Discord)
    
### Step-by-step Guide to Creating Images on OpenArt
1. Signing up process  
2. Navigating through the platform  
3. Using different models for image creation  
4. Exploring creative variations  

## NightCafe Creator: An Innovative Platform for Creating AI Artwork Online 
- Brief introduction about NightCafe Creator platform

### How to Use NightCafe Creator for Generating Unique Artworks?
1. Describing what you want to see  
2. Choosing a style   
3. Participating in daily challenges   

## Hotpot.AI: A Comprehensive Tool for Automating Creativity with Artificial Intelligence  
- Introduction to Hotpot.AI platform

### Detailed Guide on Using Hotpot.AI for Image Creation 
1. Understanding different features like Power Editor, Photo Upscaler, Object Remover etc.
2. Exploring custom styles option   
3. Making use of tips & limitations section   

## Can I Use My Created Images Commercially? 
   - Understanding licensing and copyright laws 
   - Commercial usage of images created on platforms like OpenArt, NightCafe Creator, and Hotpot.AI 

## What are the Limitations of AI Art Generation? 
- Discussing potential limitations and challenges in AI art generation
- Tips to overcome these limitations

## Conclusion
- Recap of key points discussed
- Encouraging users to explore different platforms for creating AI-generated art or images
[/TOPIC OUTLINE]

[PRE-INSTRUCTIONS]
We are going to work on creating a title for a piece of content. The intent for the primary keyword “Create AI” is "Informational" and will be used to write content for theattic.ai. The target niche for this site is: 

“Target Niche: 

Key Demographics:

- Age: 25-54
- Gender: Male and female
- Income: $50,000+
- Education: Bachelor's degree or higher
- Occupation: Professionals, business owners, entrepreneurs, freelancers, solopreneurs

Interests:
- Knowledge management 
- Artificial intelligence
- Productivity
- Efficiency

Needs:
- A way to organize and retrieve information quickly and easily
- A way to provide accurate and helpful answers to customer and employee queries
- A way to save time and boost productivity

Behaviors:
- Uses a variety of digital tools and resources to get the job done
- Is comfortable with new technologies
- Values efficiency and productivity

Preferences:
- A cloud-based solution that can be accessed from anywhere
- A solution that is easy to use and implement

Summary:

The target niche for The Attic AI is small business owners interested in AI and efficiency tools."
[/PRE-INSTRUCTIONS]

[SERP ANALYSIS OF COMMON WORDS] 
| Word | Count |
| --- | --- |
| AI | 10 |
| Art | 8 |
| Generator | 7 |
| Image | 4 |
| Create | 3 |
| Free | 2 |
| Online | 2 |
| Text | 1 |
| Tool | 1 |
[/SERP ANALYSIS OF COMMON WORDS]

[INSTRUCTIONS]
Give me an SEO Title that is based on the Topic Outline, that creates curiosity and is engaging for the primary keyword “Create AI” that has an intent of "Informational". It should have a slight bit of clickbait just to get someone to click (similar to how Mr. Beast on YouTube does his titles). The title should be approximately 50 characters (no more) and must make logical sense. Prioritize placing the exact primary keyword at the beginning of the title, followed by the keywords from the table above, in order.
[/INSTRUCTIONS]

[IMPORTANT NOTE]
- Do not use bold or italic in the title
- Make sure to capitalize the first letter of each word, Do not capitalize articles, conjunctions or prepositions
[/IMPORTANT NOTE]
USING GOOGLE BARD
Initialized Bard
Getting snim0e token of the page
Sending prompt: Write it in English language.

[PURPOSE]
The purpose of this website is to introduce The Attic AI, an innovative AI-powered knowledge management solution. With natural language processing technology, The Attic AI allows companies to create searchable databases from unstructured content, transforming documents into interactive chatbots. This provides instant access to accurate information for employees and customers.

The owner of The Attic AI has over 10 years of experience developing AI assistants and knowledge management systems. The homepage introduces the product benefits, such as saving time and boosting productivity. It targets decision-makers in customer service, sales, marketing, product design, and software engineering.

The goal is to attract visitors to explore pricing options, view demos, and envision the impact on their business. Testimonials establish credibility and calls-to-action encourage contacting for a consultation or free trial.

As an authority in AI knowledge management, the aim is to convince visitors that The Attic AI is the easiest and most powerful way to organize their informational attic. Highlighting versatility, security, compliance, and multilingual capabilities establishes why businesses should choose this solution over alternatives. The site showcases how it can revolutionize information access to boost productivity and delight users.
[/PURPOSE]

[TOPIC OUTLINE]
## Introduction
- Brief overview of AI creation
- Importance of AI in today's digital world

## What is AI Art Generation?
- Definition of AI Art Generation
- How it works 
- Examples of AI Art Generation 

### Different Types of AI Art Generators
- Stable Diffusion 
- DALL-E 2 
- CLIP-Guided Diffusion 
- VQGAN+CLIP 
- Neural Style Transfer 

## How to Create Stunning Images with OpenArt?
- Overview of OpenArt platform
    - Features and benefits
    - Pricing details
    - Community engagement opportunities (Discord)
    
### Step-by-step Guide to Creating Images on OpenArt
1. Signing up process  
2. Navigating through the platform  
3. Using different models for image creation  
4. Exploring creative variations  

## NightCafe Creator: An Innovative Platform for Creating AI Artwork Online 
- Brief introduction about NightCafe Creator platform

### How to Use NightCafe Creator for Generating Unique Artworks?
1. Describing what you want to see  
2. Choosing a style   
3. Participating in daily challenges   

## Hotpot.AI: A Comprehensive Tool for Automating Creativity with Artificial Intelligence  
- Introduction to Hotpot.AI platform

### Detailed Guide on Using Hotpot.AI for Image Creation 
1. Understanding different features like Power Editor, Photo Upscaler, Object Remover etc.
2. Exploring custom styles option   
3. Making use of tips & limitations section   

## Can I Use My Created Images Commercially? 
   - Understanding licensing and copyright laws 
   - Commercial usage of images created on platforms like OpenArt, NightCafe Creator, and Hotpot.AI 

## What are the Limitations of AI Art Generation? 
- Discussing potential limitations and challenges in AI art generation
- Tips to overcome these limitations

## Conclusion
- Recap of key points discussed
- Encouraging users to explore different platforms for creating AI-generated art or images
[/TOPIC OUTLINE]

[PRE-INSTRUCTIONS]
We are going to work on creating a title for a piece of content. The intent for the primary keyword “Create AI” is "Informational" and will be used to write content for theattic.ai. The target niche for this site is: 

“Target Niche: 

Key Demographics:

- Age: 25-54
- Gender: Male and female
- Income: $50,000+
- Education: Bachelor's degree or higher
- Occupation: Professionals, business owners, entrepreneurs, freelancers, solopreneurs

Interests:
- Knowledge management 
- Artificial intelligence
- Productivity
- Efficiency

Needs:
- A way to organize and retrieve information quickly and easily
- A way to provide accurate and helpful answers to customer and employee queries
- A way to save time and boost productivity

Behaviors:
- Uses a variety of digital tools and resources to get the job done
- Is comfortable with new technologies
- Values efficiency and productivity

Preferences:
- A cloud-based solution that can be accessed from anywhere
- A solution that is easy to use and implement

Summary:

The target niche for The Attic AI is small business owners interested in AI and efficiency tools."
[/PRE-INSTRUCTIONS]

[SERP ANALYSIS OF COMMON WORDS] 
| Word | Count |
| --- | --- |
| AI | 10 |
| Art | 8 |
| Generator | 7 |
| Image | 4 |
| Create | 3 |
| Free | 2 |
| Online | 2 |
| Text | 1 |
| Tool | 1 |
[/SERP ANALYSIS OF COMMON WORDS]

[INSTRUCTIONS]
Give me an SEO Title that is based on the Topic Outline, that creates curiosity and is engaging for the primary keyword “Create AI” that has an intent of "Informational". It should have a slight bit of clickbait just to get someone to click (similar to how Mr. Beast on YouTube does his titles). The title should be approximately 50 characters (no more) and must make logical sense. Prioritize placing the exact primary keyword at the beginning of the title, followed by the keywords from the table above, in order.
[/INSTRUCTIONS]

[IMPORTANT NOTE]
- Do not use bold or italic in the title
- Make sure to capitalize the first letter of each word, Do not capitalize articles, conjunctions or prepositions
[/IMPORTANT NOTE]
    """
    print(BardAPI().send_prompt(prompt))
