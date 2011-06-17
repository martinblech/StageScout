#!/usr/bin/env python

import sys
import urllib2
import urllib
try:
    import simplejson as json
except ImportError:
    import json
from pprint import pprint
import bmat

USERNAME = 'musichackday'
PASSWORD = 'mhd2011_bcn'

resolver = bmat.ArtistResolver(username=USERNAME, password=PASSWORD)

festival = json.load(sys.stdin)

for event in festival['events']:
    artist = event['artist']
    name = artist['name']
    entity = resolver.resolve(name)
    if entity:
        artist['bmat_id'] = entity['id']

json.dump(festival,
    sys.stdout, indent=4, sort_keys=True)
