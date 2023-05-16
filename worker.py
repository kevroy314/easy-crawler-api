import time
import os
import datetime

from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.firefox.options import Options

from lxml import etree

import logging

logging.basicConfig(
     level=logging.DEBUG, 
     format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
     datefmt='%H:%M:%S'
 )

logging.debug("Worker starting - setting up driver.")

# FireFox binary path (Must be absolute path)
FIREFOX_BINARY = FirefoxBinary('/opt/firefox/firefox')
 
# FireFox PROFILE
PROFILE = webdriver.FirefoxProfile()
PROFILE.set_preference("browser.cache.disk.enable", False)
PROFILE.set_preference("browser.cache.memory.enable", False)
PROFILE.set_preference("browser.cache.offline.enable", False)
PROFILE.set_preference("network.http.use-cache", False)
PROFILE.set_preference("general.useragent.override","Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:72.0) Gecko/20100101 Firefox/72.0")
 
# FireFox Options
FIREFOX_OPTS = Options()
FIREFOX_OPTS.log.level = "trace"    # Debug
FIREFOX_OPTS.headless = True
GECKODRIVER_LOG = '/geckodriver.log'

FF_OPT = {
    'firefox_binary': FIREFOX_BINARY,
    'firefox_profile': PROFILE,
    'options': FIREFOX_OPTS,
    'service_log_path': GECKODRIVER_LOG
}

def get_driver():
    driver = webdriver.Firefox(**FF_OPT)
    driver.set_page_load_timeout(os.environ['MAX_PAGE_LOAD_TIMEOUT'])
    return driver

logging.debug(f"Driver finished setting up with FF_OPT={FF_OPT} and page load timeout of {os.environ['MAX_PAGE_LOAD_TIMEOUT']}")

def _extract_xpath(dom, xpath):
    return [etree.tostring(x) if not isinstance(x, str) else x for x in dom.xpath(xpath)]

def crawl_URL(config: dict):
    start_time = datetime.datetime.now()
    with get_driver() as driver:
        # config = json.loads(configJSON)
        # print(config)
        logging.debug(f'Starting crawl of {config}')
        # Load either the simplified or regular page
        if config['simplify_source']:
            logging.debug('Running simplified view')
            driver.get(f'about:reader?url={config["url"]}')
        else:
            logging.debug('Running full view')
            driver.get(config['url'])
        # Wait extra time if user requests
        logging.debug("Sleeping for user specified time")
        time.sleep(config['load_wait_time'])

        # Create the preliminary results
        logging.debug("Creating preliminary results")
        result = {'config': config, 'page_source': driver.page_source}

        driver.close()

    # If there are xpath searches provided, create a soup and etree dom, then iterate through them and return the results
    if config['xpaths'] is not None and len(config['xpaths']) > 0:
        logging.debug("xpath requests found, creating soup and dom tree")
        # soup = BeautifulSoup(result['page_source'])
        dom = etree.HTML(result['page_source'])
        logging.debug("Iterating through xpath requests")
        xpath_results = [_extract_xpath(dom, xpath) for xpath in config['xpaths']]
        result['xpath_results'] = xpath_results
    
    # logging.debug("Attempting chatgpt prompt")
    # TODO: ChatGPT Integration

    if not config['return_source']:
        del result['page_source']

    end_time = datetime.datetime.now()
    result['start_time'] = start_time
    result['end_time'] = end_time
    logging.info(f"Done crawling {config}, returning results")
    return result
