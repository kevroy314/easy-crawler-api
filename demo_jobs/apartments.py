import pickle as pkl
import json
import requests
from tqdm.auto import tqdm
import time
import pandas as pd
import datetime

job_name = "apartments.com"
job_start_datetime_str = str(datetime.datetime.now()).replace(':', '-').replace(' ', '_')
force_restart = True

# STEP 1: Get a list of URLs to crawl
with open('url_list.pkl', 'rb') as fp:
    url_list = pkl.load(fp)

def build_request(urls, xpaths):
    return 'http://localhost:8080/crawl?' + \
           '&'.join([f'urls={url}' for url in urls]) + \
           '&return_source=false&simplify_source=false&' + \
           '&'.join([f'xpaths={xpath}' for xpath in xpaths])

urls = list(url_list.keys())
urls = [url for url in urls if 'www.apartments.com' in url]

# STEP 2: Get the xpaths you want to extract
xpaths = ['//*[@id="mapResultBox"]/text()']

# STEP 3: Start the jobs and save the job IDS (in case of failures of this script or machine restarts)
prior_job_file = False
try:
    with open(f"{job_name}.pkl", "rb") as fp:
        r = pkl.load(fp)
    prior_job_file = True
except Exception:
    pass
if force_restart or not prior_job_file:
    r = requests.post(build_request(urls, xpaths))
    # Note: This is in case the python kernel goes down so you don't have to guess at your jobIDs
    with open(f"{job_name}.pkl", "wb") as fp:
        pkl.dump(r, fp)

# STEP 4: Monitor the jobs until all are complete
def check_meta_job():
    with open(f"{job_name}.pkl", "rb") as fp:
        r = pkl.load(fp)
    jobIDs = json.loads(r.content)['jobIDs']
    results = requests.get('http://localhost:8080/jobResults?'+'&'.join([f'jobIDs={jid}' for jid in jobIDs]))
    data = json.loads(results.content)

    simple_results_data = {}
    # Test for failures
    for key in data:
        try:
            xpath_result_data = data[key]['xpath_results'][0][0]
            simple_results_data[data[key]['config']['url']] = {'result': xpath_result_data, 'end_time': data[key]['end_time']}
        except (IndexError, KeyError) as e:
            if 'url' in data[key]:
                print(data[key]['config']['url'])
    return len(simple_results_data) == len(jobIDs), data, simple_results_data

meta_results = check_meta_job()
pbar = tqdm(total=len(meta_results[1]), initial=len(meta_results[2]))
last_done = len(meta_results[2])
while not meta_results[0]:
    meta_results = check_meta_job()
    done = len(meta_results[2])
    pbar.update(done - last_done)
    last_done = done
    time.sleep(1)

# STEP 5: Clean the data and assemble it
full_job_data = meta_results[2]

def clean_apartments_result(txt):
    return int(txt.strip().split(' ')[0].replace(',', ''))

simple_results_data_cleaned = {key: clean_apartments_result(full_job_data[key]['result']) for key in full_job_data}
simple_results_data_cleaned

df = pd.DataFrame()
df['url'] = list(simple_results_data_cleaned.keys())
df['count'] = [simple_results_data_cleaned[key] for key in df['url']]
df['city'] = [url_list[key]['city'] for key in df['url']]
df['state'] = [url_list[key]['state'] for key in df['url']]
df['state_abbr'] = [url_list[key]['state_abbr'] for key in df['url']]
df['crawl_end_time'] = [full_job_data[key]['end_time'] for key in full_job_data]
df.to_csv(f'{job_name}_{job_start_datetime_str}.csv')