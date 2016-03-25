# -*- coding: utf-8 -*-
from scrapy.crawler import CrawlerProcess

from spiders.merchant_spider import MerchantSpider
from spiders.product_spider import ProductSpider
from spiders.store_spider import StoreSpider

username = 'yangxue088@163.com'
password = 'xuebie232'
ajaxcount = 200

#
# crawl tab product
#
process = CrawlerProcess({'ITEM_PIPELINES': {
    'pipelines.DupePipeline': 300,
    'pipelines.ToRedisPipeline': 400,
}, 'LOG_LEVEL': 'INFO', 'LOG_FILE': 'target/log.multiwish'})

process.crawl(ProductSpider, username=username, password=password, ajaxcount=ajaxcount,
              tabs={'Latest': 'tabbed_feed_latest', 'Recently Viewed': 'recently_viewed__tab',
                    'Accessories': 'tag_53dc186421a86318bdc87f16', 'Hobbies': 'tag_54ac6e18f8a0b3724c6c473f',
                    })
process.crawl(ProductSpider, username=username, password=password, ajaxcount=ajaxcount,
              tabs={'Gadgets': 'tag_53dc186421a86318bdc87f20', 'Fashion': 'tag_53dc186321a86318bdc87ef8',
                    'Home Decor': 'tag_53e9157121a8633c567eb0c2',})
process.crawl(ProductSpider, username=username, password=password, ajaxcount=ajaxcount, tabs={
    'Watches': 'tag_53dc186421a86318bdc87f1c',
    'Tops': 'tag_53dc186321a86318bdc87ef9', 'Phone Upgrades': 'tag_53dc186421a86318bdc87f0f',
})
process.crawl(ProductSpider, username=username, password=password, ajaxcount=ajaxcount,
              tabs={'Shoes': 'tag_53dc186421a86318bdc87f31',
                    'Wallets & Bags': 'tag_53dc186421a86318bdc87f22', 'Bottoms': 'tag_53dc186321a86318bdc87f07',
                    'Underwear': 'tag_53dc2e9e21a86346c126eae4'})

#
# crawl excellent merchant
#
for i in range(0, 10):
    process.crawl(MerchantSpider, username=username, password=password, redis_key='{}:url'.format(ProductSpider.name),
                  merchant_rating_count=10000, merchant_rating_score=4.0, product_similar_max=1000,
                  product_similar_rating_score=4.0, product_similar_rating_count=500,
                  ajaxcount=ajaxcount)

#
# crawl excellent product
#
process.crawl(StoreSpider, username=username, password=password, redis_key='{}:url'.format(MerchantSpider.name),
              product_rating_count=1000, product_rating_score=4.0, product_rating_min_count=100,
              ajaxcount=ajaxcount)

process.start()  # the script will block here until all crawling jobs are finished
