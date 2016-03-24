# -*- coding: utf-8 -*-
import json
import logging
from urllib import quote, urlencode

import re
import scrapy
from pybloom import ScalableBloomFilter
from scrapy_redis.spiders import RedisSpider

import items


class MerchantSpider(RedisSpider):
    name = "merchant"
    allowed_domains = ["wish.com"]
    start_urls = (
        'http://www.wish.com/',
    )

    def __init__(self, username, password, redis_key='products', merchant_rating_count=10000, merchant_rating_score=4.0,
                 product_similar_max=1000,
                 ajaxcount=200):
        self.username = username
        self.password = password
        self.redis_key = redis_key
        self.merchants = ScalableBloomFilter(mode=ScalableBloomFilter.LARGE_SET_GROWTH)
        self.rating_count = merchant_rating_count
        self.rating_score = merchant_rating_score
        self.similar_max = product_similar_max
        self.ajaxcount = ajaxcount
        self.urls = ScalableBloomFilter(mode=ScalableBloomFilter.LARGE_SET_GROWTH)
        self.logon = False
        self.xsrf = ''

    def start_requests(self):
        yield scrapy.Request('https://www.wish.com/', callback=self.login, priority=100)

    def login(self, response):
        match = re.compile(r'.*_xsrf=(.*?);').match(str(response.headers))

        if match:
            self.xsrf = match.group(1)
            self.log('merchant spider before login', logging.INFO)
            yield scrapy.Request(
                'https://www.wish.com/api/email-login?email={}&password={}&_buckets=&_experiments='.format(
                    quote(self.username), quote(self.password)),
                method='POST',
                headers={
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Content-Type': ' application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-XSRFToken': self.xsrf
                },
                callback=self.after_login, priority=80)

    def after_login(self, response):
        self.logon = True
        self.log('merchant spider login success.', logging.INFO)

    def next_request(self):
        request = super(MerchantSpider, self).next_request()

        if request is not None and self.urls.add(request.url):
            return self.next_request()
        else:
            return request

    def parse(self, response):
        while not self.logon:
            yield

        xscript = response.xpath('//script')
        merchant_name = xscript.re_first(r'"merchant_name": "(.*?)",')
        merchant_rating = xscript.re_first(r'"merchant_rating": (.*?),')
        merchant_rating_count = xscript.re_first(r'"merchant_rating_count": (.*?),')

        if merchant_name.startswith('\u'):
            merchant_name = eval("'" + merchant_name.decode('unicode-escape') + "'")

        if merchant_name not in self.merchants:
            self.merchants.add(merchant_name)

            if int(merchant_rating_count) >= self.rating_count and float(merchant_rating) >= self.rating_score:
                self.log(
                    'found merchant:{}, count:{}, rating:{}'.format(merchant_name, merchant_rating_count,
                                                                    merchant_rating),
                    logging.INFO)
                merchant_url = "https://www.wish.com/merchant/%s" % quote(merchant_name)
                item = items.MerchantItem()
                item['url'] = merchant_url
                yield item

        contest_id = response.url.split(r'/')[-1]
        yield self.feed_similar_ajax(contest_id)

    def feed_similar_ajax(self, contest_id, offset=0):
        formdata = {
            'contest_id': contest_id,
            'feed_mode': 'similar',
            'count': str(self.ajaxcount),
            'offset': str(offset),
            '_buckets': '',
            '_experiments': '',
        }

        return scrapy.Request(
            'https://www.wish.com/api/related-feed/get',
            method='POST', body=urlencode(formdata),
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': ' application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-XSRFToken': self.xsrf
            },
            meta={
                'contest_id': formdata.get('contest_id', None)
            },
            callback=self.parse_feed_ajax)

    def parse_feed_ajax(self, response):
        json_data = json.loads(response.body)
        data = json_data.get('data', None)
        if data is not None:
            next_offset = data.get('next_offset')
            feed_ended = data.get('feed_ended', True)
            products = data.get('items', [])

            for url in (product.get('external_url') for product in products if
                        product.get('external_url') not in self.urls):
                # self.log('put back to product url:{}'.format(url), logging.INFO)

                self.urls.add(url)
                item = items.ProductItem()
                item['url'] = url
                yield item

            if int(next_offset) >= self.similar_max:
                feed_ended = True

            if not feed_ended:
                # self.log('relate ajax, contest_id:{}, offset:{}'.format(response.meta['contest_id'], next_offset),
                #          logging.INFO)
                yield self.feed_similar_ajax(response.meta['contest_id'], next_offset)
            else:
                pass
                # self.log('relate ajax, contest_id:{}, total:{}'.format(response.meta['contest_id'], next_offset),
                #          logging.INFO)