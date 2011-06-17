#urlfetch monkeypatch
from google.appengine.api import urlfetch
old_fetch = urlfetch.fetch
def new_fetch(url, payload=None, method='GET', headers={},
          allow_truncated=False, follow_redirects=True,
          deadline=30.0, *args, **kwargs):
  return old_fetch(url, payload, method, headers, allow_truncated,
                   follow_redirects, deadline, *args, **kwargs)
urlfetch.fetch = new_fetch

try:
    import simplejson as json
except ImportError:
    import json
import urllib2
import urllib

DEFAULT_BASE_URL = 'http://ella.bmat.ws'

class ResolverError(Exception): pass

class ArtistResolver(object):
    def __init__(self, base_url=DEFAULT_BASE_URL,
            username=None, password=None):
        self.base_url = base_url
        if username:
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, base_url, username, password)
            authhandler = urllib2.HTTPBasicAuthHandler(passman)
            self.opener = urllib2.build_opener(authhandler)
        else:
            self.opener = urllib2.build_opener()

    def resolve(self, name):
        resolve_url = self.base_url + '/collections/bmat/artists/search?' + \
                urllib.urlencode(dict(
                    q='artist:(%s)'%name.encode('utf-8')))
        try:
            response = json.load(self.opener.open(
                urllib2.Request(resolve_url,
                    headers={'Accept': 'application/json'})))
        except urllib2.HTTPError, e:
            raise ResolverError('http error resolving artist', name, e)
        results = response['response']['results']
        entity = None
        if len(results):
            entity = results[0]['entity']
        return entity

    def similar(self, seeds):
        similar_url = self.base_url + '/collections/sonar/artists/similar_to?'\
                + urllib.urlencode(dict(
                    seeds=seeds,
                    limit='500'))
        response = json.load(self.opener.open(
            urllib2.Request(similar_url,
                    headers={'Accept': 'application/json'})))['response']
        similarities = dict()
        for result in response['results']:
            score = float(result['score'])
            id = result['entity']['id']
            similarities[id] = score
        return similarities
