# Easy Crawler API (ECAPI)

This crawler runs in docker and gives a user the ability to easily spin up asynchronous crawling jobs using selenium.

## Server Setup

On the server side, run:

`docker-compose up --build`

## Client Usage

Clients can navigate to [localhost:8080](localhost:8080) to get to the main page (visualized below) which is a simple Dash page.

Manual interaction can be done via the FastAPI page [localhost:8080/docs](localhost:8080/docs). The call order is:
 * `/crawl`
 * `/jobStatus` (optional)
 * `/jobResult`

Jobs can be monitored via the admin interface (Note: you should change the password in the Dockerfile before deploying) at [localhost:9181](localhost:9181).

Note: The server will, by default, save the results for 1 day. You should save your results separately.