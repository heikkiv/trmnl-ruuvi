import requests
import time
import threading
import traceback
import datetime
import logging
import sys
import ruuvi_decoders

# Import configuration from config.py
from config import trmnl_url, ruuvi_token, ruuvi_api_url, update_interval, retry_interval

def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler('log.txt', mode='w')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(screen_handler)
    return logger


def get_measurements():
    # Use the configuration variables
    token = ruuvi_token
    url = ruuvi_api_url
    headers = {'Authorization': 'Bearer ' + token}
    r = requests.get(url, headers=headers)

    sensors = {}
    if r.status_code == 200:
        decoder = ruuvi_decoders.Df5Decoder()
        for sensor in r.json()['data']['sensors']:
            name = sensor['name']
            mes = sensor['measurements']
            data = mes[0]['data']
            data = data[data.index('FF9904')+6:]
            dataDict = decoder.decode_data(data)
            sensors[name] = dataDict
    return sensors


def update_measurements_trmnl(logger):
    while True:
        try:
            sensors = get_measurements()
            data = {
                "merge_variables": {
                    'outside': sensors['Terrace']['temperature'],
                    'livingroom': sensors['Living room']['temperature'],
                    'bedroom': sensors['Bedroom']['temperature'],
                    'study': sensors['Outside']['temperature']
                }
            }
            logger.info(data)
            response = requests.post(trmnl_url, json=data)
            logger.info(response.status_code)
            
            now = datetime.datetime.now()
            logger.info('Updated measurements, sleeping')
            time.sleep(update_interval)
        except Exception as e:
            logger.info(traceback.format_exc())
            time.sleep(retry_interval)


def main():
    logger = setup_custom_logger('measurement_updater')
    logger.info('Started')
    update_measurements_trmnl(logger)
    logger.info('Finished')

if __name__ == '__main__':
    main()
