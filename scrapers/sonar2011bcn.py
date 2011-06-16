#!/usr/bin/env python

import urllib2
import re
import sys
import datetime
try:
    import simplejson as json
except ImportError:
    import json

BASE_URL = 'http://2011.sonar.es'
PROGRAM_URL = 'http://2011.sonar.es/en/programa-concerts-djs-agenda.php'
DAY_SEPARATOR_PATTERN = re.compile(
        r'<div class="agenda_dia_title">(.*?)</div>')
PERFORMANCE_PATTERN = re.compile(
        r'<div class="conc_place_desc_item">(.*?)</div>')
MYSONAR_HTML = '<a href="/en/usuaris.php" class="miniMySonarBtn"><img src="/img/programa/mysonar.gif" alt="mysonar" /></a>&nbsp;'
ARTISTNAME_URL_EXTRACTOR = re.compile(
        r'<a href="(/en/artistes/.*.html)">(.*?)</a>')

data = urllib2.urlopen(PROGRAM_URL).read()

last_offset = sys.maxint
date_ranges = []
for match in reversed(list(DAY_SEPARATOR_PATTERN.finditer(data))):
    offset, date_string = match.start(), match.group(1)
    day = int(date_string.split()[1])
    date = datetime.date(
            day=day,
            month=6,
            year=2011)
    date_ranges.append((offset, last_offset, date))
    last_offset = offset

def get_date(offset):
    for start, end, date in date_ranges:
        if start < offset < end:
            return date
    raise Exception('bad offset', offset, date_ranges)

events = []
for match in PERFORMANCE_PATTERN.finditer(data):
    offset, data = match.start(), match.group(1)
    time_string, place, type, description = [x.strip()
            for x in data.replace(MYSONAR_HTML, '').split('::')]
    date = get_date(offset)
    hour, minute = map(int, time_string.split(':'))
    timestamp = datetime.datetime(
            year=date.year, month=date.month, day=date.day,
            hour=hour, minute=minute)
    url, artistname = ARTISTNAME_URL_EXTRACTOR.search(description).groups()
    event = dict(
            timestamp=timestamp.isoformat(),
            place=place,
            type=type,
            description=description,
            url=BASE_URL + url,
            artist=dict(name=artistname))
    events.append(event)

json.dump(
        dict(
            name='Sonar',
            year=2011,
            location='Barcelona',
            events=events),
    sys.stdout, indent=4, sort_keys=True)
