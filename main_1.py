# -*- coding: utf-8 -*-
import sys

from scrapy.crawler import CrawlerProcess

from spiders.merchant_spider import MerchantSpider
from spiders.product_spider import ProductSpider
from spiders.store_spider import StoreSpider

if __name__ == '__main__':

    username = sys.argv[1]
    password = sys.argv[2]
    ajaxcount = 200

    #
    # crawl tab product
    #

    from scrapy import optional_features
    optional_features.remove('boto')

    process = CrawlerProcess({'ITEM_PIPELINES': {
        'pipelines.DupePipeline': 300,
        'pipelines.ToRedisPipeline': 400,
    }, 'LOG_LEVEL': 'INFO', 'LOG_FILE': 'target/log.multiwish.1', 'CONCURRENT_REQUESTS': '200'})

    process.crawl(ProductSpider, username=username, password=password, ajaxcount=66,
                  tabs={'Latest': 'tabbed_feed_latest'})
    process.crawl(ProductSpider, username=username, password=password, ajaxcount=ajaxcount,
                  tabs={'Recently Viewed': 'recently_viewed__tab',
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
        process.crawl(MerchantSpider, username=username, password=password,
                      redis_key='{}:url'.format(ProductSpider.name),
                      merchant_rating_count=100, merchant_rating_score=3.0, product_similar_max=1000,
                      product_similar_rating_score=2.0, product_similar_rating_count=20,
                      ajaxcount=ajaxcount)


    #
    # crawl excellent product
    #
    def filter(product):
        price = product['commerce_product_info']['variations'][0]['localized_price'][
            'localized_value']

        cp = 10
        symbol = product['commerce_product_info']['variations'][0]['localized_price']['symbol']
        if symbol != '$':
            cp = 10 * 6.46

        rating_count = product['product_rating']['rating_count']

        rating_score = product['product_rating']['rating']

        if float(price) > cp and rating_count >= 100 and rating_score >= 4.0:
            print '{} {} {} {}{}'.format(product['external_url'], rating_count, rating_score, price, symbol)
            return True
        else:
            return False


    process.crawl(StoreSpider, username=username, password=password, redis_key='{}:url'.format(MerchantSpider.name),
                  product_rating_count=100, product_rating_score=4.0, product_rating_min_count=20,
                  ajaxcount=ajaxcount,
                  filter=filter)

    process.start()  # the script will block here until all crawling jobs are finished
