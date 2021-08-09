import argparse
from urllib.parse import urlparse
import urllib
import csv
import tweepy
import re
import pandas as pd
import numpy as np

from city_to_state import city_to_state_dict
from two_letter_states import us_state_abbrev

import us

def get_state_abbr(x):
    if re.match('({})'.format("|".join(us_state_abbrev.keys()).lower()), x.lower()):
        tokens = [re.match('({})'.format("|".join(us_state_abbrev.keys()).lower()), x.lower()).group(0)]
    elif re.match('({})'.format("|".join(city_to_state_dict.keys()).lower()), x.lower()):
        k = re.match('({})'.format("|".join(city_to_state_dict.keys()).lower()), x.lower()).group(0)
        tokens = [city_to_state_dict.get(k.title(), np.nan)]
    else:
        tokens = [j for j in re.split("\s|,", x) if j not in ['in', 'la', 'me', 'oh', 'or']]
    for i in tokens:
        if re.match('\w+', str(i)):
            if us.states.lookup(str(i)):
                return us.states.lookup(str(i)).abbr

# URL CLEANUP
def url_fix(s, charset='utf-8'):
    if isinstance(s, unicode):
        s = s.encode(charset, 'ignore')
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = urllib.quote(path, '/%')
    qs = urllib.quote_plus(qs, ':&=')
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


# COMMAND PARSER
def tw_parser():
    global qw, ge, l, t, c, d

    # USE EXAMPLES:
    # =-=-=-=-=-=-=
    # % twsearch <search term>            --- searches term
    # % twsearch <search term> -g sf      --- searches term in SF geographic box <DEFAULT = none>
    # % twsearch <search term> -l en      --- searches term with lang=en (English) <DEFAULT = en>
    # % twsearch <search term> -t {m,r,p} --- searches term of type: mixed, recent, or popular <DEFAULT = recent>
    # % twsearch <search term> -c 12      --- searches term and returns 12 tweets (count=12) <DEFAULT = 1>
    # % twsearch <search term> -o {ca, tx, id, co, rtc)   --- searches term and sets output options <DEFAULT = ca, tx>

    # Parse the command
    parser = argparse.ArgumentParser(description='Twitter Search')
    parser.add_argument(action='store', dest='query', help='Search term string')
    parser.add_argument('-g', action='store', dest='loca', help='Location (lo, nyl, nym, nyu, dc, sf, nb')
    parser.add_argument('-l', action='store', dest='l', help='Language (en = English, fr = French, etc...)')
    parser.add_argument('-t', action='store', dest='t', help='Search type: mixed, recent, or popular')
    parser.add_argument('-c', action='store', dest='c', help='Tweet count (must be <50)')
    args = parser.parse_args()

    qw = args.query  # Actual query word(s)
    ge = ''

    # Location
    loca = args.loca
    if (not (loca in ('lo', 'nyl', 'nym', 'nyu', 'dc', 'sf', 'nb')) and (loca)):
        print("WARNING: Location must be one of these: lo, nyl, nym, nyu, dc, sf, nb")
        exit()
    if loca:
        ge = locords[loca]

    # Language
    l = args.l
    if (not l):
        l = "en"
    if (not (l in ('en', 'fr', 'es', 'po', 'ko', 'ar'))):
        print(
            "WARNING: Languages currently supported are: en (English), fr (French), es (Spanish), po (Portuguese), ko (Korean), ar (Arabic)")
        exit()

    # Tweet type
    t = args.t
    if (not t):
        t = "recent"
    if (not (t in ('mixed', 'recent', 'popular'))):
        print("WARNING: Search type must be one of: (m)ixed, (r)ecent, or (p)opular")
        exit()

    # Tweet count
    if args.c:
        c = int(args.c)
        if (c > cmax):
            print("Resetting count to ", cmax, " (maximum allowed)")
            c = cmax
        if (not (c) or (c < 1)):
            c = 1
    if not (args.c):
        c = 1

    print("Query: %s, Location: %s, Language: %s, Search type: %s, Count: %s" % (qw, ge, l, t, c))


# AUTHENTICATION (OAuth)
def tw_oauth(authfile):
    with open(authfile, "r") as f:
        ak = f.readlines()
    f.close()
    auth1 = tweepy.auth.OAuthHandler(ak[0].replace("\n", ""), ak[1].replace("\n", ""))
    auth1.set_access_token(ak[2].replace("\n", ""), ak[3].replace("\n", ""))
    return tweepy.API(auth1)


def tw_search_json(query, cnt=5):
    authfile = './auth.k'
    api = tw_oauth(authfile)
    results = {}
    meta = {
        'username': 'text',
        'hashtag': 'text',
        'usersince': 'date',
        'followers': 'numeric',
        'friends': 'numeric',
        'authorid': 'text',
        'tweetid': 'text',
        'authorloc': 'geo',
        'geoenable': 'boolean',
        'source': 'text'
    }
    data = []
    for tweet in tweepy.Cursor(api.search, q=query, count=cnt).items():
        dTwt = {}
        dTwt['username'] = tweet.author.name
        dTwt['usersince'] = tweet.author.created_at  # author/user profile creation date
        dTwt['followers'] = tweet.author.followers_count  # number of author/user followers (inlink)
        dTwt['friends'] = tweet.author.friends_count  # number of author/user friends (outlink)
        dTwt['authorid'] = tweet.author.id  # author/user ID#
        dTwt['authorloc'] = tweet.author.location  # author/user location
        dTwt['geoenable'] = tweet.author.geo_enabled  # is author/user account geo enabled?
        dTwt['source'] = tweet.source  # platform source for tweet
        data.append(dTwt)
    results['meta'] = meta
    results['data'] = data
    return results


# TWEEPY SEARCH FUNCTION
def tw_search(api):
    counter = 0
    # Open/Create a file to append data
    csvFile = open('result.csv', 'w', encoding="utf-8", newline='')
    # Use csv Writer
    csvWriter = csv.writer(csvFile)
    csvWriter.writerow(["created", "text", "tweet_id", "coordinates", "lat", "long",
                        "retwc", "hashtag", "username", "usersince",
                        "followers", "friends", "authorid", "authorloc", "geoenable", "source", "is_usa_loc"])

    for tweet in tweepy.Cursor(api.search,
                               q=qw,
                               g=ge,
                               lang=l,
                               result_type=t,
                               count=c).items():

        # TWEET INFO
        created = tweet.created_at  # tweet created
        text = tweet.text  # tweet text
        tweet_id = tweet.id  # tweet ID# (not author ID#)
        coordinates = tweet.coordinates  # geographic co-ordinates

        try:
            lat = tweet.coordinates["coordinates"][0] # latitude
        except:
            lat = "None"

        try:
            long = tweet.coordinates[u'coordinates'][1] # longitude
        except:
            long = "None"

        retwc = tweet.retweet_count  # re-tweet count
        try:
            hashtag = tweet.entities[u'hashtags'][0][u'text']  # hashtags used
        except:
            hashtag = "None"
        try:
            rawurl = tweet.entities[u'urls'][0][u'url']  # URLs used
            urls = url_fix(rawurl)
        except:
            urls = "None"
        # AUTHOR INFO
        username = tweet.author.name  # author/user name
        usersince = tweet.author.created_at  # author/user profile creation date
        followers = tweet.author.followers_count  # number of author/user followers (inlink)
        friends = tweet.author.friends_count  # number of author/user friends (outlink)
        authorid = tweet.author.id  # author/user ID#
        authorloc = tweet.author.location  # author/user location
        # TECHNOLOGY INFO
        geoenable = tweet.author.geo_enabled  # is author/user account geo enabled?
        source = tweet.source  # platform source for tweet

        user_loc_str = str(tweet.user.location).upper()
        if tweet.user.location:
            is_usa_loc = get_state_abbr(user_loc_str)
        else:
            is_usa_loc = get_state_abbr(user_loc_str)
        # Dongho 03/28/16
        csvWriter.writerow([created, str(text).encode("utf-8"),
                            str(tweet_id), coordinates, lat, long, retwc, hashtag, str(username), usersince,
                            followers, friends, str(authorid), authorloc, geoenable, source, is_usa_loc])
        counter = counter + 1
        if (counter == c):
            break

    csvFile.close()


# MAIN ROUTINE
def main():
    global api, cmax, locords

    # Geo-coordinates of five metropolitan areas
    # London, NYC (lower, middle, upper), Wash DC, San Francisco, New Brunswick (NJ)
    locords = {'lo': '0, 51.503, 20km',
               'nyl': '-74, 40.73, 2mi',
               'nym': '-74, 40.74, 2mi',
               'nyu': '-73.96, 40.78, 2mi',
               'dc': '-77.04, 38.91, 2mi',
               'sf': '-122.45, 37.74, 5km',
               'nb': '-74.45, 40.49, 2mi'}
    # Maximum allowed tweet count (note: Twitter sets this to ~180 per 15 minutes)
    cmax = 50000
    # OAuth key file
    authfile = './auth.k.txt'

    tw_parser()
    api = tw_oauth(authfile)
    tw_search(api)


if __name__ == "__main__":
    main()
