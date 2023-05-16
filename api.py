import os
from typing import List, Union
from urllib.parse import urlparse

import dash
import flask
from dash import dcc, html
from dash.dependencies import Input, Output, State
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.wsgi import WSGIMiddleware
from redis import Redis
from rq import Queue
from rq.job import Job
from typing_extensions import Annotated

from worker import crawl_URL

app = FastAPI()

def create_dash_app(prefix='/'):
    server = flask.Flask(__name__)
    app = dash.Dash(__name__, server=server, requests_pathname_prefix=prefix)

    app.scripts.config.serve_locally = False

    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        html.H1('Crawler'),
        html.A('Swagger Docs', href='/docs'),
        html.Br(),
        html.A('Dashboard', id="dashboard-link"),
    ], className="container")

    @app.callback(
        Output("dashboard-link", "href"),
        Input("dashboard-link", "n_clicks"),
        State("url", "href")
    )
    def dashboard_link(n_clicks, href):
        destination = urlparse(href).netloc.split(':')[0] + ':9181'
        print(destination)
        return 'http://'+destination+'/'

    return app

redis_conn = Redis(host='crawler_redis', port=6379)
q = Queue('crawler_queue', connection=redis_conn)

@app.post('/crawl', status_code=201)
def addTask(urls: Annotated[List[str], Query(description="A list of URLs to crawl.")],
            return_source: Annotated[bool, Query(description="If `True`, the page source will be returned. This source is the full page source unless `simplify_source` is `True`, in which case it is a simplified page source (see that parameter for more info).")] = True,
            simplify_source: Annotated[bool, Query(description="If `True` and `return_source` is `True`, the page source will be simplified before being returned. This saves bandwidth. Simplification is performed via <a href='https://support.mozilla.org/en-US/kb/firefox-reader-view-clutter-free-web-pages'>Firefox Reader View</a>.")] = True,
            load_wait_time: Annotated[float, Query(description=f"It is sometimes difficult to tell if a page is finished loading. Set this value to a float representing the number of seconds you want to wait to ensure the page is fully loaded. This can be 0 unless the page involves lots of dynamic, client side content. This is in addition to the default page load timeout of {os.environ['MAX_PAGE_LOAD_TIMEOUT']}")] = 0.0,
            # load_wait_until_xpath_element: Annotated[Union[str, None], Query(description=f"It is sometimes difficult to tell if a page is finished loading, and simply waiting an amount of time is inefficient or impractical. Set this value to an xpath string representing a property in the page to look for and wait until it is loaded before returning. Note: this will run until a maximum timeout of {os.environ['MAX_PAGE_LOAD_TIMEOUT']} seconds, so very long running operations will not work here. ")] = None, # TODO: Consider adding this option
            results_ttl: Annotated[int, Query(description="The time to live for the results (i.e., how long the results will be available before they will be deleted to save space)")] = os.environ['DEFAULT_RESULTS_TTL'],
            x_paths: Annotated[Union[List[str], None], Query(description="A list of xpaths to search for an extract data. A common use case may be to set `return_source` to false, but set this to the data elements you're interested in examining. In this condition, you will only receive the results of interest if they exist. Note: xpaths may be different when using `simplified_source`. To determine those xpaths in the browser, open Firefox and load your page in <a href='https://support.mozilla.org/en-US/kb/firefox-reader-view-clutter-free-web-pages'>Reader View</a> as this is the simplification method. ")] = None,
            chatgpt_prompt: Annotated[Union[str, None], Query(description="A prompt to give chatgpt which will contain the `return_source` data. Use <return_source> in your prompt which will then be replaced with the `return_source` value in your prompt. Note that this can be quite large, so it is best to set `simplfy_source` to `True`. You must set a `openai_key` to use this option or you will get an error.")] = None,
            openai_key: Annotated[Union[str, None], Query(description="Your OpenAI key to be used with `chatgpt_prompt`. You must provide this to use that prompt. You can get a key at <a href='https://platform.openai.com/account/api-keys'>OpenAI API Key</a>.")] = None):
    if chatgpt_prompt and not openai_key:
        raise HTTPException(status_code=400, detail="chatgpt_prompt was provided but openai_key was not - you must provide both or do not set either")
    job_config = {
        'return_source': return_source,
        'simplify_source': simplify_source,
        'load_wait_time': load_wait_time,
        'results_ttl': results_ttl,
        'x_paths': x_paths,
        'chatgpt_prompt': chatgpt_prompt,
        'openai_key': openai_key,
    }
    ids = []
    for url in urls:
        job_config['url'] = url
        job = q.enqueue(crawl_URL, job_config, result_ttl=job_config['results_ttl'])
        ids.append(job.get_id())
    size = len(q)
    
    return {'jobIDs': ids, 'currentQueueSize': size}

@app.get('/queueSize')
def queueSize():
    """Get the number of items in the queue"""
    return {'currentQueueSize': len(q)}

@app.get('/jobStatus')
def jobStatus(jobID: Annotated[str, Query(description="Returned from `/crawl`.")]):
    """Get the job status and position in queue"""
    job = Job.fetch(jobID, connection=redis_conn)
    return {"status": job.get_status(), "position": job.get_position()}

@app.get('/jobResults')
def jobStatus(jobIDs: Annotated[List[str], Query(description="A list of JobIDs. Returned from `/crawl`.")]):
    """Get the job status and position in queue"""
    results = {}
    for jobId in jobIDs:
        try:
            job = Job.fetch(jobId, connection=redis_conn)
            if job.get_status() != "finished":
                raise HTTPException(status_code=102, detail="job is not finished yet, use /jobStatus endpoint to get job status and wait until finished to try again")
            result = job.latest_result()  #  returns Result(id=uid, type=SUCCESSFUL)
            if result.type == result.Type.FAILED:
                results[jobId] = result.return_value
            else: 
                raise HTTPException(status_code=500, detail="the job exists and is flagged finished, but it did not succeed")
        except HTTPException as e:
            results[jobId] = e
    return results
        

# Note: This must be at the end or you'll get 405 errors on other endpointss
dash_app = create_dash_app(prefix="/")
app.mount("/", WSGIMiddleware(dash_app.server))