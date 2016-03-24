# -*- coding: utf-8 -*-
import json
import logging
from urllib import quote, urlencode

import re
import scrapy
from pybloom import ScalableBloomFilter
from scrapy_redis.spiders import RedisSpider

import items


class StoreSpider(RedisSpider):
    name = "store"
    allowed_domains = ["wish.com"]
    start_urls = (
        'http://www.wish.com/',
    )

    def __init__(self, username, password, redis_key='merchants', product_rating_count=1000, product_rating_score=4.0,
                 product_rating_min_count=100,
                 ajaxcount=200):
        self.username = username
        self.password = password
        self.redis_key = redis_key
        self.merchants = ScalableBloomFilter(mode=ScalableBloomFilter.LARGE_SET_GROWTH)
        self.rating_count = product_rating_count
        self.rating_score = product_rating_score
        self.rating_min_count = product_rating_min_count
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
            self.log('store spider before login', logging.INFO)
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
        self.log('store spider login success.', logging.INFO)

    def next_request(self):
        request = super(StoreSpider, self).next_request()
        if request is not None and self.merchants.add(request.url):
            return self.next_request()
        else:
            return request

    def parse(self, response):
        while not self.logon:
            yield

        self.log('store spider parse response.', logging.INFO)

        xscript = response.xpath('//script')
        next_offset = xscript.re_first("\['next_offset'\] = (.*?);")
        merchant_name = xscript.re_first("\['merchant_name'\] = \"(.*?)\";")

        if merchant_name.startswith('\u'):
            merchant_name = eval("'" + merchant_name.decode('unicode-escape') + "'")

        match = re.search("\['orig_feed_items'\] = (\[.*?\]);\n", response.body)
        if match:
            feed_items = match.group(1)
            products = json.loads(feed_items)

            ids = []
            for product in products:
                ids.append(product.get('id'))
                url = product.get('external_url')

                product_rating = product['product_rating']

                # self.log('product:{}, count:{}, score:{}'.format(product['id'], product_rating['rating_count'],
                #                                                  product_rating[
                #                                                      'rating']), logging.INFO)

                if product_rating['rating_count'] < self.rating_min_count:
                    ids = []
                    break

                if product_rating['rating_count'] >= self.rating_count and product_rating[
                    'rating'] >= self.rating_score:
                    self.log('found product:{}, count:{}, rating:{}, merchant:{}'.format(url,
                                                                                         product_rating['rating_count'],
                                                                                         product_rating['rating'],
                                                                                         merchant_name),
                             logging.INFO)
                    item = items.ExcellentProductItem()
                    item['url'] = url
                    item['merchant'] = merchant_name
                    yield item

            if len(ids) > 0:
                yield self.feed_merchant_ajax(merchant_name, next_offset, ids)

    def feed_merchant_ajax(self, merchant_name, offset, last_cids, num_results=0):
        formdata = {
            'start': str(offset),
            'query': merchant_name,
            'is_commerce': 'true',
            'transform': 'true',
            'count': str(self.ajaxcount),
            'include_buy_link': 'true',
            'num_results': str(num_results),
            '_buckets': '',
            '_experiments': '',
            'last_cids[]': last_cids
        }

        return scrapy.Request('https://www.wish.com/api/merchant', method='POST', body=urlencode(formdata),
                              headers={
                                  'Accept': 'application/json, text/javascript, */*; q=0.01',
                                  'Content-Type': ' application/x-www-form-urlencoded; charset=UTF-8',
                                  'X-Requested-With': 'XMLHttpRequest',
                                  'X-XSRFToken': self.xsrf,
                              }, meta={'merchant_name': merchant_name}, callback=self.parse_merchant_ajax)

    def parse_merchant_ajax(self, response):
        self.log('store spider parse reponse', logging.INFO)

        json_data = json.loads(response.body)
        data = json_data.get('data', None)
        if data is not None:
            next_offset = data.get('next_offset')
            num_results = data.get('num_results')
            merchant_name = response.meta['merchant_name']

            ids = []
            for product in data.get('results'):
                ids.append(product.get('id'))
                url = product.get('external_url')

                product_rating = product['product_rating']

                # self.log('product:{}, count:{}, score:{}'.format(product['id'], product_rating['rating_count'],
                #                                                  product_rating[
                #                                                      'rating']), logging.INFO)

                if product_rating['rating_count'] < self.rating_min_count:
                    ids = []
                    break

                if product_rating['rating_count'] >= self.rating_count and product_rating[
                    'rating'] >= self.rating_score:
                    self.log('found product:{}, count:{}, rating:{}, merchant:{}'.format(url,
                                                                                         product_rating['rating_count'],
                                                                                         product_rating['rating'],
                                                                                         merchant_name),
                             logging.INFO)
                    item = items.ExcellentProductItem()
                    item['url'] = url
                    item['merchant'] = merchant_name
                    yield item

            if len(ids) > 0:
                self.log('store spider feed ajax:{}, offset:{}'.format(merchant_name, next_offset), logging.INFO)
                yield self.feed_merchant_ajax(merchant_name, next_offset, ids, num_results)
            else:
                self.log('store spider feed ajax:{}, total:{}'.format(merchant_name, next_offset), logging.INFO)
