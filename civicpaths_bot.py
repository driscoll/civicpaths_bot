#!/usr/bin/python
"""
Civic Paths Bot

Simple module for creating bots that track
and RT tweets based on keywords/phrases. 

Developed for the Civic Paths research group
    http://civicpaths.uscannenberg.org

Depends on Mike Verdone's Python Twitter Tools: 
    http://mike.verdone.ca/twitter/

Copyright 2011 Kevin Driscoll <driscollkevin@gmail.com>

"""

import twitter
import json
import urlparse
from sys import exit
from os import getcwd
from random import randint
from time import sleep, strptime
from datetime import datetime
from calendar import timegm

TWIT_DATETIME_FORMAT = '%a, %d %b %Y %H:%M:%S +0000'
HISTORY_FILENAME = 'civicpaths_history.json'
CONFIG_FILENAME = 'civicpaths_config.json'

# Constants stored in global dict 
config = {
    "KEYWORDS" : [],        # strings to track
    "BOT_USER_ID": "",      # Twitter user ID
    "CONSUMER_KEY": "",     # OAuth tokens, keys
    "CONSUMER_SECRET": "",
    "OAUTH_TOKEN": "",
    "OAUTH_TOKEN_SECRET": ""
}

# Load constants from CONFIG_FILENAME
try:
    config_fp = open(CONFIG_FILENAME,'r')
except IOError:
    # If the file isn't found, generate a blank one
    print "\nCould not find {0}".format(CONFIG_FILENAME)
    json.dump(config,open(CONFIG_FILENAME,'w'),indent=4) 
    print "Generated blank config: {0}/{1}".format(getcwd(), CONFIG_FILENAME)
    print "\nEdit that file by hand and try again.\n"
    exit(1) 

# Load config data from the JSON
try:
    config = json.load(config_fp)
except ValueError:
    print "Couldn't understand {0}. Check for typos.".format(CONFIG_FILENAME)

for key in config.keys():
    if config[key] == "" or config[key] == []:
        print '\nYour configuration file is missing some important info.'
        print 'Take a look at: {0}/{1}'.format(getcwd(), CONFIG_FILENAME)
        print
        exit(1)

# Generate global OAuth object 
api = twitter.Twitter(auth=twitter.OAuth(config['OAUTH_TOKEN'], config['OAUTH_TOKEN_SECRET'], config['CONSUMER_KEY'],config['CONSUMER_SECRET']),format='json',api_version=None)

class History(object):
    """Collect history on this bot's activity
    """
    def __init__(self, filename=HISTORY_FILENAME):
        self.lastupdate = ''
        self.since_id = 1
        self.tweets = {} 
        self.load(filename)

    def remember(self, tweet):
        """Add a new tweet to the history
        """
        self.tweets[tweet[u'id_str']] = tweet

    def status(self):
        """Print out information about the history
        """
        if self.lastupdate:
            print u'Last update: {0}'.format(self.lastupdate)
        else:
            print u'Last update: Never.'
        print u'since_id: {0}'.format(self.since_id)
        print u'Tweets in memory: {0}'.format(len(self.tweets))
        print

    def load(self, fn):
        """Import history from JSON file
        """ 
        print "Loading history from {0}/{1}".format(getcwd(), fn)
        try:
            h = open(fn, 'r')
            json_history = json.load(h)
            h.close()
            self.lastupdate = json_history[u'lastupdate']
            self.since_id = json_history[u'since_id']
            self.tweets = json_history[u'tweets']
            self.status()
        except:
            print u'Couldn\'t open {0}/{1}'.format(getcwd(), HISTORY_FILENAME)

    def dump(self):
        """Write history to JSON file on disk
        """
        # Throw out duplicates from this list
        unique_id_str = uniqify(self.tweets.keys())
        
        # Reverse sort list of IDs 
        unique_id_str.sort(key=lambda k:int(k),reverse=True)
        
        # Highest unique_id is our starting point 
        # for future searches
        # It's possible that we have zero tweets
        # in the history which will raise an exception
        # for example, the first time this bot runs...
        try:
            self.since_id = unique_id_str[0]
        except:
            self.since_id = 1

        # Create new dict of unique tweets
        unique_tweets = {}
        for id_str in unique_id_str:
            unique_tweets[id_str] = self.tweets[id_str]

        # Prepare data for writing as JSON 
        json_history = {
            u'lastupdate' : self.lastupdate, 
            u'since_id' : self.since_id,
            u'tweets' : unique_tweets
        }

        # Export JSON of past tweet IDs
        print u'Writing history to \'{0}\\{1}\''.format(getcwd(), HISTORY_FILENAME)
        print
        h = open(HISTORY_FILENAME, 'w')
        json.dump(json_history, h, indent=4)
        h.close()

def shorten(s):
    """Limit tweets to 140 chars without losing URLs
    Returns s shortened to 140 chars"""
    if (len(s) > 140):
        link = s.find('http')
        if (link == -1):
            return (s[:137] + u'...')
        else:
            return (s[:((140 - len(s[link:]))-4)] + '... ' + s[link:])
    return s

def uniqify(seq):
    """Nice uniqify function from:
        http://www.peterbe.com/plog/uniqifiers-benchmark
    Returns unique list"""
    # Not order preserving
    keys = {}
    for e in seq:
        keys[e] = 1
    return keys.keys()

def unescape(s):
    s = s.replace(u'&lt;', u'<')
    s = s.replace(u'&gt;', u'>')
    s = s.replace(u'&quot;', u'\"')
       # this has to be last:
    s = s.replace(u'&amp;', u'&')
    return s

def rewrite(tweet):
    """Prepare a tweet for RTing by
        prepending "RT @username"
        and shortening to fit in 140 chars

        tweet   : (Tweet)

    Returns str to be tweeted"""
    # Find the user's screen name
    from_user = tweet[u'from_user'] 
    # Strip away the screen name from the tweet
    text = tweet[u'text'][(len(from_user)+2):] 
    rt = u'RT @{0} {1}'.format(from_user, unescape(text)) 
    # If it is > 140 chars, chop it down 
    if len(rt) > 140:
        rt = shorten(rt)    
    # For testing, uncomment these lines:
    # rt = rt.replace('@','_')
    # rt = rt.replace('#','_')
    return rt

def search(q, since_id=1):
    """Query search.twitter.com for str q

        q        : (str) e.g. u'#civicpaths'
        since_id : (int) earliest ID to search from
            if undefined, you may max out. 

    Returns list of tweets"""
    search = twitter.Twitter(domain="search.twitter.com")
    tweets = []
    r = search.search(q=q,
           result_type="recent",
           rpp="100",
           show_user="false",
           with_twitter_user_id="1",
           since_id=since_id)
    tweets += r[u'results']
    while (u'next_page' in r.keys()):
        q = urlparse.parse_qs(r['next_page'].lstrip('?'))
        for p in q.keys():
            q[p] = q[p][0]
        r = search.search(**q)
        tweets += r[u'results']
    return tweets 

def search_many(keywords, since_id=1):
    """Search twitter and enqueue responses

        keywords = list of strings to search for
       
    Returns list of tweets (each is a dict)
    """
    # Query search API for each keyword 
    results = []
    for keyw in keywords:
        print u'Searching for \'{0}\''.format(keyw)
        results += search(keyw, since_id)
    print u'{0} new tweets...'.format(len(results))
    return  results

def process(new_tweets, old_tweet_ids=[]):
    """Run a battery of heuristic tests to
        determine which tweets to RT
        
        new_tweets : (list) of Tweets 
        old_tweet_ids : (list) of tweet IDs to ignore
    
    Returns list of tweets to RT"""
    # Empty queue for new tweets
    queue = []
    
    # These are counters for reporting the 
    # different tweets we keep or throw out
    # They are just for fun and not reqd
    our = 0
    dupe = 0
    new = 0

    # Iterate over each new tweet and
    # test it against our battery of heuristics
    for twit in new_tweets:

        # Check to be sure it's not from us!
        if (twit[u'from_user_id'] == config["BOT_USER_ID"]):
            our += 1

        # Prevent dupes
        elif (twit[u'id_str'] in old_tweet_ids):
            dupe += 1

        else:
            new += 1
            queue.append(twit)
            
    print 'Found {0} new tweets, {1} of our tweets, and {2} duplicates.'.format(new, our, dupe)
    print

    # To ensure proper chronology, 
    # sort queue by date created 
    # (this is cute but 
    #   there's gotta be a better way)
    #
    return sorted(queue, key=lambda k: timegm(strptime(k[u'created_at'],TWIT_DATETIME_FORMAT)), reverse=False) 

def send(status):
    """Send a tweet

        status : (str) content of the tweet
        
    Return outcome from Twitter API or None on error"""
    try:
        outcome = api.statuses.update(status=status)
    except twitter.TwitterHTTPError as twiterror:
        print u'Oops. Error updating status. Status not updated!'
        error = json.load(twiterror.e)
        # TODO we could handle these errors better
        if (error[u'error'].find('duplicate') > -1):
            print 'Duplicate!'
        print twiterror
        print error    
    except UnicodeEncodeError as twiterror:
        print u'Twitter module raised this error:'
        print twiterror
    else:
        print u'Tweet {0} created at {1}'.format(outcome[u'id_str'], outcome[u'created_at'])
        try:
            print u'    {0}'.format(status)
        except UnicodeEncodeError:
            print u'(Tried and failed to print the tweet. Weird charmap issue?)'
        print
        return outcome 
    return None 

def chill(sec=1, r=6):
    """Sleep for sec seconds
        sec = integer
        r = max random int coefficient
    """
    sec *= randint(1,r)
    print u'Sleeping for {0} seconds...'.format(sec)
    sleep(sec)
    print u'Awake!'
    print
    

def typical():
    """Typical use case:
        * Load history
        * Search 
        * Process tweets
        * Send RTs
        * Dump history
    """
    history = History()    

    queue = search_many(config['KEYWORDS'], history.since_id)

    # Reset the lastupdate to now
    history.lastupdate = datetime.strftime(datetime.now(), TWIT_DATETIME_FORMAT)

    new_tweets = process(queue, history.tweets.keys())

    for tweet in new_tweets:
        if (send(rewrite(tweet))):
            history.remember(tweet)
        chill(2)
    
    history.dump()

if __name__=='__main__':
    typical() 

