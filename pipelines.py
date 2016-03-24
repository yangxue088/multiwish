# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

from pybloom import ScalableBloomFilter
from scrapy.exceptions import DropItem
from scrapy_redis.pipelines import RedisPipeline

from items import ProductItem, MerchantItem, ExcellentProductItem

from spiders.merchant_spider import MerchantSpider

from spiders.product_spider import ProductSpider

class DupePipeline(object):

    urls = ScalableBloomFilter(mode=ScalableBloomFilter.LARGE_SET_GROWTH)

    def process_item(self, item, spider):
        if item is None or item['url'] is None:
            raise DropItem("none item found.")
        else:
            if DupePipeline.urls.add(spider.name + item['url']):
                raise DropItem('duplicate item found')
            else:
                return item

class ToRedisPipeline(RedisPipeline):

    def _process_item(self, item, spider):
        if isinstance(item, ProductItem):
            self.server.rpush('{}:url'.format(ProductSpider.name), item['url'])
        elif isinstance(item, MerchantItem):
            self.server.rpush('{}:url'.format(MerchantSpider.name), item['url'])
            self.server.rpush('excellent:merchant', self.encoder.encode(item))
        elif isinstance(item, ExcellentProductItem):
            self.server.rpush('excellent:product', item['url'])
        else:
            self.server.rpush('{}:url'.format(spider.name), item['url'])
        return item
