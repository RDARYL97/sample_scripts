import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

import re
import scrapy

from scrapy import Request
from urllib.parse import urlparse, urlunparse
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import Rule
from scrapy.linkextractors import LinkExtractor
import xml.etree.ElementTree as ET
from api.audit.models import Auditv2Links


class LinkSpider(scrapy.Spider):
    name = "link_spider"

    def __init__(self, start_url=None, *args, **kwargs):
        self.allowed_domains = [urlparse(start_url).netloc]
        self.start_urls = [start_url] if start_url else []

        self.rules = (
            Rule(LinkExtractor(allow_domains=self.allowed_domains), callback='parse', follow=True),
        )

        super().__init__(*args, **kwargs)
        self.links_set = set()  # Use a set to store unique links

    def start_requests(self):
        for url in self.start_urls:
            robots_url = urlunparse(urlparse(url)._replace(path='/robots.txt', query='', fragment=''))
            yield Request(robots_url, callback=self.parse_robots, errback=self.handle_robots_failure,
                          meta={'start_url': url})

        # This part is to immediately start crawling from the initial URL.
        # If you only want to start crawling after robots.txt is checked or fails, you can remove this.
        yield Request(self.start_urls[0], self.parse,
                      headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)'})

    def handle_robots_failure(self, failure):
        # This function will be called if accessing robots.txt fails
        start_url = failure.request.meta['start_url']
        yield Request(start_url, self.parse, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)'})

    def parse_robots(self, response):
        sitemaps = re.findall(r'Sitemap: (\S+)', response.text)
        if sitemaps:
            for sitemap_url in sitemaps:
                yield Request(sitemap_url, self.parse_sitemap,
                              headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)'})
        else:
            # No sitemap found in robots.txt, start crawling from the base URL
            yield Request(response.urljoin('/'), self.parse,
                          headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6)'})

    def parse_sitemap(self, response):
        # Parse the XML response
        root = ET.fromstring(response.text)

        if root.tag[0] == '{':
            # Extract the namespace
            ns_url = root.tag.split('}')[0].strip('{')
            ns = {'ns': ns_url}
            loc_elements = root.findall('.//ns:loc', ns)
        else:
            # No namespace, find all <loc> elements
            loc_elements = root.findall('.//loc')

        print(loc_elements)
        for loc in loc_elements:
            link = loc.text
            if link not in self.links_set:
                self.links_set.add(self.remove_url_fragment(link))
                # Check if the link is another sitemap
                if link.endswith('.xml'):
                    yield response.follow(link, callback=self.parse_sitemap)
                else:
                    yield response.follow(link, callback=self.parse)

    def remove_url_fragment(self, url):
        parsed_url = urlparse(url)
        # Construct the URL without the fragment
        clean_url = urlunparse(
            (parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, '', ''))
        return clean_url

    def parse(self, response):
        self.logger.info('Parsing page URL: %s', response.url)
        links = LinkExtractor(allow_domains=self.allowed_domains).extract_links(response)
        self.logger.info('Found %d links on the page', len(links))

        for link in links:
            self.logger.debug('Link found: %s', link.url)
            if link.url not in self.links_set:
                self.links_set.add(self.remove_url_fragment(link.url))
                yield response.follow(link, callback=self.parse)

    def closed(self, reason):
        unique_links_list = list(self.links_set)
        check = Auditv2Links.objects.filter(url=self.start_urls[0])
        print(check, self.start_urls[0])
        if not check:
            Auditv2Links.objects.create(
                url=self.start_urls[0],
                links=str(unique_links_list)
            )
        else:
            check.update(
                links=str(unique_links_list)
            )


if __name__ == '__main__':
    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'ROBOTSTXT_OBEY': False,
    })

    process.crawl(LinkSpider, start_url='https://stronghitechcoatings.com/')
    process.start()