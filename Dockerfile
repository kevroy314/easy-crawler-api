FROM python:3.9

ENV DEBIAN_FRONTEND noninteractive
# Note: Go to https://github.com/mozilla/geckodriver/releases/ if you want to find latest version
ENV GECKODRIVER_VER v0.33.0
# Note: Go to https://download.mozilla.org/?product=firefox-latest&os=linux64&lang=en-US if you want to find latest version
ENV FIREFOX_VER 112.0.2

ENV MAX_PAGE_LOAD_TIMEOUT 3600
ENV DEFAULT_RESULTS_TTL 86400

# Prepare for firefox/geckodriver install
RUN set -x \
   && apt update \
   && apt upgrade -y \
   && apt install -y \
       firefox-esr

# Install firefox
RUN set -x \
   && apt install -y \
       libx11-xcb1 \
       libdbus-glib-1-2 \
   && curl -sSLO https://download-installer.cdn.mozilla.net/pub/firefox/releases/${FIREFOX_VER}/linux-x86_64/en-US/firefox-${FIREFOX_VER}.tar.bz2 \
   && tar -jxf firefox-* \
   && mv firefox /opt/ \
   && chmod 755 /opt/firefox \
   && chmod 755 /opt/firefox/firefox

# Install geckodriver
RUN set -x \
   && curl -sSLO https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VER}/geckodriver-${GECKODRIVER_VER}-linux64.tar.gz \
   && tar zxf geckodriver-*.tar.gz \
   && mv geckodriver /usr/bin/

WORKDIR /home/crawler

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY api.py ./
COPY worker.py ./
