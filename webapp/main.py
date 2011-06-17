#!/usr/bin/env python

import os
import yaml
facebook_app_auth = yaml.load(open(
        os.path.join(os.path.dirname(__file__), "facebook_app_auth.yaml")))

FACEBOOK_APP_ID = facebook_app_auth['ID']
FACEBOOK_APP_SECRET = facebook_app_auth['SECRET']

BMAT_USERNAME = 'musichackday'
BMAT_PASSWORD = 'mhd2011_bcn'

import bmat

resolver = bmat.ArtistResolver(username=BMAT_USERNAME, password=BMAT_PASSWORD)

import base64
import cgi
import Cookie
import email.utils
import hashlib
import hmac
import logging
import os.path
import time
import urllib
import wsgiref.handlers
import datetime

from django.utils import simplejson as json
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template

festival = json.load(open(
        os.path.join(os.path.dirname(__file__),
            "sonar2011bcn.withbmatids.json")))

for event in festival['events']:
    event['start'] = datetime.datetime.strptime(event['timestamp'],
            '%Y-%m-%dT%H:%M:%S')
    event['end'] = event['start'] + datetime.timedelta(hours=2)
    event['description'] = event['description'].replace('href="',
            'href="http://2011.sonar.es')

for event in festival['events']:
    for event2 in festival['events']:
        if event is not event2 and event2['place'] == event['place'] and \
                event['start'] <= event2['start'] <= event['end']:
                    event['end'] = min(event['end'],
                            event2['start'] + datetime.timedelta(minutes=-1))

def build_schedule(scores):
    prioritized_events = festival['events'][:]
    prioritized_events.sort(cmp=lambda x, y: cmp(
        scores.get(y['artist'].get('bmat_id', None), 0),
        scores.get(x['artist'].get('bmat_id', None), 0)))
    my_events = []
    left_out = []
    def conflicts(event):
        for event2 in my_events:
            if event['artist'] == event2['artist']:
                return event2
            if event['start'] <= event2['start'] <= event['end'] or \
                    event2['start'] <= event['start'] <= event2['end']:
                        return event2
        return False
    for event in prioritized_events:
        conflict = conflicts(event)
        if not conflict:
            my_events.append(event)
        else:
            left_out.append(dict(event=event, conflict=conflict))
    my_events.sort(cmp=lambda x, y: cmp(x['start'], y['start']))
    schedule = dict(
            my_events=my_events,
            left_out=left_out)
    return schedule

logging.info('festival program: %s' % festival)

class User(db.Model):
    id = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    name = db.StringProperty(required=True)
    profile_url = db.StringProperty(required=True)
    access_token = db.StringProperty(required=True)

    likes = db.ListProperty(db.Key)
    
    @property
    def liked_artists(self):
        if not hasattr(self, "_liked_artists"):
            liked_artists = list()
            for key in self.likes:
                liked_artists.append(Artist.get(key))
            self._liked_artists = liked_artists
        return self._liked_artists

    @property
    def seeds(self):
        if not hasattr(self, "_seeds"):
            seeds = list()
            for artist in self.liked_artists:
                if artist.bmat_id:
                    seeds.append(artist.bmat_id)
            self._seeds = ','.join('bmat:artist/%s' %
                    x for x in seeds)
        return self._seeds

    @property
    def schedule(self):
        if not hasattr(self, "_schedule"):
            scores = resolver.similar(self.seeds)
            self._schedule = build_schedule(scores)
        return self._schedule

class Artist(db.Model):
    name = db.StringProperty(required=True)
    bmat_id = db.StringProperty(required=False)


class BaseHandler(webapp.RequestHandler):
    @property
    def current_user(self):
        """Returns the logged in Facebook user, or None if unconnected."""
        if not hasattr(self, "_current_user"):
            self._current_user = None
            user_id = parse_cookie(self.request.cookies.get("fb_user"))
            if user_id:
                self._current_user = User.get_by_key_name(user_id)
        return self._current_user

    def get_artist(self, artist_name):
        artist = Artist.get_by_key_name(artist_name.lower())
        if artist is None:
            logging.debug('new artist: %s' % artist_name)
            bmat_id = None
            try:
                entity = resolver.resolve(artist_name)
                if entity:
                    bmat_id = entity['id']
            except bmat.ResolverError, e:
                logging.error('error resolving artist "%s": %s' %
                        (artist_name, e))
            artist = Artist(key_name=artist_name.lower(),
                    name=artist_name, bmat_id=bmat_id)
            artist.put()
        else:
            logging.debug('artist already existed: %s' % artist_name)
        return artist


class HomeHandler(BaseHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), "sonicscout.html")
        schedule = None
        args = dict(current_user=self.current_user)
        self.response.out.write(template.render(path, args))


class LoginHandler(BaseHandler):
    def get(self):
        verification_code = self.request.get("code")
        args = dict(client_id=FACEBOOK_APP_ID, redirect_uri=self.request.path_url)
        if self.request.get("code"):
            args["scope"] = 'user_likes,friends_likes'
            args["client_secret"] = FACEBOOK_APP_SECRET
            args["code"] = self.request.get("code")
            response = cgi.parse_qs(urllib.urlopen(
                "https://graph.facebook.com/oauth/access_token?" +
                urllib.urlencode(args)).read())
            access_token = response["access_token"][-1]

            # Download the user profile and cache a local instance of the
            # basic profile info
            profile = json.load(urllib.urlopen(
                "https://graph.facebook.com/me?" +
                urllib.urlencode(dict(access_token=access_token))))
            music = json.load(urllib.urlopen(
                "https://graph.facebook.com/me/music?" +
                urllib.urlencode(dict(access_token=access_token))))
            likes = list()
            for page in music['data']:
                artist_name = None
                category = page['category']
                if category == 'Musician/band':
                    artist_name = page['name'].strip()
                elif category == 'Album':
                    artist_name = page['name'].split(', by ')[-1].strip()
                else:
                    logging.error('Unsupported category "%s" for page %s' %
                            (category, page))
                if artist_name is not None:
                    artist = self.get_artist(artist_name)
                    if artist.key() not in likes:
                        likes.append(artist.key())
            user = User(key_name=str(profile["id"]), id=str(profile["id"]),
                        name=profile["name"], access_token=access_token,
                        profile_url=profile["link"], likes=likes)
            user.put()
            set_cookie(self.response, "fb_user", str(profile["id"]),
                       expires=time.time() + 30 * 86400)
            self.redirect("/")
        else:
            self.redirect(
                "https://graph.facebook.com/oauth/authorize?" +
                urllib.urlencode(args))


class LogoutHandler(BaseHandler):
    def get(self):
        set_cookie(self.response, "fb_user", "", expires=time.time() - 86400)
        self.redirect("/")


def set_cookie(response, name, value, domain=None, path="/", expires=None):
    """Generates and signs a cookie for the give name/value"""
    timestamp = str(int(time.time()))
    value = base64.b64encode(value)
    signature = cookie_signature(value, timestamp)
    cookie = Cookie.BaseCookie()
    cookie[name] = "|".join([value, timestamp, signature])
    cookie[name]["path"] = path
    if domain: cookie[name]["domain"] = domain
    if expires:
        cookie[name]["expires"] = email.utils.formatdate(
            expires, localtime=False, usegmt=True)
    response.headers._headers.append(("Set-Cookie", cookie.output()[12:]))


def parse_cookie(value):
    """Parses and verifies a cookie value from set_cookie"""
    if not value: return None
    parts = value.split("|")
    if len(parts) != 3: return None
    if cookie_signature(parts[0], parts[1]) != parts[2]:
        logging.warning("Invalid cookie signature %r", value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - 30 * 86400:
        logging.warning("Expired cookie %r", value)
        return None
    try:
        return base64.b64decode(parts[0]).strip()
    except:
        return None


def cookie_signature(*parts):
    """Generates a cookie signature.

    We use the Facebook app secret since it is different for every app (so
    people using this example don't accidentally all use the same secret).
    """
    hash = hmac.new(FACEBOOK_APP_SECRET, digestmod=hashlib.sha1)
    for part in parts: hash.update(part)
    return hash.hexdigest()


def main():
    util.run_wsgi_app(webapp.WSGIApplication([
        (r"/", HomeHandler),
        (r"/auth/login", LoginHandler),
        (r"/auth/logout", LogoutHandler),
    ]))


if __name__ == "__main__":
    main()
