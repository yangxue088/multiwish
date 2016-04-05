# -*- coding: utf-8 -*-
import json
import logging
from urllib import quote, urlencode

import re
import scrapy
from pybloom import ScalableBloomFilter

import items


class ProductSpider(scrapy.Spider):
    name = "product"
    allowed_domains = ["wish.com"]
    start_urls = (
        'https://www.wish.com/',
    )

    urls = ScalableBloomFilter(mode=ScalableBloomFilter.LARGE_SET_GROWTH)

    def __init__(self, username, password, ajaxcount=100, tabs=None):
        if not tabs:
            tabs = {}

        self.username = username
        self.password = password
        self.ajaxcount = ajaxcount
        self.tabs = tabs
        self.logon = False

    def start_requests(self):
        yield scrapy.Request('https://www.wish.com/', callback=self.login, priority=100)

    def login(self, response):
        match = re.compile(r'.*_xsrf=(.*?);').match(str(response.headers))

        if match:
            xsrf = match.group(1)
            self.log('product spider before login', logging.INFO)
            yield scrapy.Request(
                'https://www.wish.com/api/email-login?email={}&password={}&_buckets=&_experiments='.format(
                    quote(self.username), quote(self.password)),
                method='POST',
                headers={
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Content-Type': ' application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-XSRFToken': xsrf
                }, meta={'xsrf': xsrf},
                callback=self.request_tab, priority=80)

    def request_tab(self, response):
        self.log('product spider login success', logging.INFO)
        self.logon = True

        if self.tabs is None or len(self.tabs) == 0:
            return

        while not self.logon:
            yield

        self.log('begin to crawl tabs: {}'.format(self.tabs))

        for tabname, tabid in self.tabs.items():
            yield self.feed_tab_ajax(response.meta['xsrf'], tabname, tabid)

    def feed_tab_ajax(self, xsrf, tabname, tabid, offset=0):
        formdata = {
            'count': str(self.ajaxcount),
            'offset': str(offset),
            'request_id': tabid,
            'request_categories': 'false',
            '_buckets': '',
            '_experiments': ''
        }

        return scrapy.Request(
            'https://www.wish.com/api/feed/get-filtered-feed',
            method='POST', body=urlencode(formdata),
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': ' application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-XSRFToken': xsrf
            },
            meta={
                'xsrf': xsrf,
                'tabname': tabname,
                'tabid': tabid
            },
            callback=self.parse_tab_ajax, priority=50)

    def parse_tab_ajax(self, response):
        json_data = json.loads(response.body)
        data = json_data.get('data', None)
        if data is not None:
            next_offset = data.get('next_offset')
            no_more_items = data.get('no_more_items', True)
            products = data.get('products', [])

            for url in (product.get('external_url') for product in products if
                        not ProductSpider.urls.add(product.get('external_url'))):
                item = items.ProductItem()
                item['url'] = url
                yield item

            if next_offset >= 10000:
                no_more_items = True

            if not no_more_items:
                self.log('feed tab ajax:{}, offset:{}'.format(response.meta['tabname'], next_offset), logging.INFO)
                yield self.feed_tab_ajax(response.meta['xsrf'], response.meta['tabname'], response.meta['tabid'],
                                         next_offset)
            else:
                self.log('feed tab ajax:{}, total:{}'.format(response.meta['tabname'], next_offset), logging.INFO)
