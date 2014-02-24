import socket
import requests
import sys # for printing to stderr
from twitch_viewers import user_viewers
from twitch_viewers import removeNonAscii
from twython import Twython
import tweepy
from time import gmtime, strftime
from get_passwords import get_passwords
from get_exceptions import get_exceptions
from chat_count import chat_count

#delete tweets if someone stopped streaming?
delete = 0
tweetmode = False #true if you want it to tweet, false if you don't

errlog = open('errlog.txt', 'w')

passes = get_passwords()

APP_KEY =            passes[0]
APP_SECRET =         passes[1]
OAUTH_TOKEN =        passes[2]
OAUTH_TOKEN_SECRET = passes[3]

twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

id = 0

auth = tweepy.OAuthHandler(APP_KEY, APP_SECRET)
auth.set_access_token(OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
api = tweepy.API(auth)

# these users are known to have small chat to viewer ratios for valid reasons
# example: chat disabled, or chat hosted not on the twitch site, or mainly viewed on front page of twitch
exceptions = get_exceptions()

def user_chatters(user):
    chatters = 0
    chatters2 = 0
    req = requests.get("http://tmi.twitch.tv/group/user/" + user)
    try:
        while (req.status_code != 200):
            print "----TMI error getting " + user, str(req.status_code), "-", strftime("%b %d %H:%M:%S", gmtime()) + "----"
            req = requests.get("http://tmi.twitch.tv/group/user/" + user)
        try:
            chat_data = req.json()
        except ValueError:
            return user_chatters(user)
        chatters = chat_data['chatter_count']
    except TypeError:
        print "recursing, got some kinda error"
        return user_chatters(user)
    '''
    if (chatters > 0):
        try:
            chatters2 = chat_count(user)
        except socket.error as error:
            print "oh. error getting chatters via module"
            return user_chatters(user)
        if (chatters2 > 3):
            print "returning %d via module" %chatters2
            return chatters2
    '''
    return chatters

def user_ratio(user):
    exceptions = get_exceptions()
    if (user in exceptions):
        print user, "is alright :)"
        return 1
    chatters = user_chatters(user)
    while True:
        try:
            chatters2 = chat_count(user)
            break
        except socket.error as error:
            print "error getting chatters. o well. try again."
            pass
    viewers = user_viewers(user)
    if (viewers != 0):
        ratio = float(chatters) / viewers
        print user + ": " + str(chatters) + " / " + str(viewers) + " = %0.3f" %ratio,
        if (chatters2 < 2):
            print "                  ",
        print "(%d from module (vs %d))".format(chatters2, chatters)
    else: 
        return 1 # user is offline

    return ratio

suspicious = []
confirmed = []
user_threshold = 200
ratio_threshold = 0.16 #if false positives, lower this number. if false negatives, raise this number
expected_ratio = 0.7 #eventually tailor this to each game/channel. Tailoring to channel might be hard.

def send_tweet(user, ratio, game, viewers):
    name = "http://www.twitch.tv/" + user
    if (ratio < ratio_threshold):
        found = 0
        for item in suspicious:
            if item[0] == name:
                item[1] = ratio #update the ratio each time
                item[2] = game
                found = 1
        if not found:
            print "Tweeting!"
            suspicious.append([name, ratio, game])
            originame = name[21:]
            chatters = int(viewers * ratio) # TODO: something more intelligent than chatters, take into account the average game ratio and calculate the expected number of viewers
            game_tweet = game.split(":")[0] #manually shorten the tweet, many of these by inspection
            if (game_tweet == "League of Legends"):
                game_tweet = "LoL"
            if (game_tweet == "Call of Duty" and len(game.split(":")) > 1):
                game_tweet = "CoD:" + game.split(":")[1] #CoD: Ghosts, CoD: Modern Warfare
            if (game_tweet == "Counter-Strike" and len(game.split(":")) > 1):
                game_tweet = "CS: " 
                for item in game.split(":")[1].split(" "): 
                    if (len(item) > 0):
                        game_tweet += item[0] #first initial - CS:S, CS:GO
            if (game_tweet == "StarCraft II" and len(game.split(":")) > 1):
                game_tweet = "SC2: "
                for item in game.split(":")[1].split(" "):
                    if (len(item) > 0):
                        game_tweet += item[0] #first initial - SC2: LotV
            #TODO: change expected_ratio to be each game - is this a good idea? avg skewed by botting viewers...
            fake_viewers = int(viewers - (1 / expected_ratio) * chatters)
            estimate = "(~" + str(fake_viewers) + " extra viewers of "+ str(viewers) + " total)"
            tweet = name + " (" + game_tweet + ") might have a false-viewer bot " + estimate
            if (ratio < 0.15):
                tweet = name + " (" + game_tweet + ") appears to have a false-viewer bot " + estimate
            if (ratio < 0.09):
                tweet = name + " (" + game_tweet + ") almost definitely has a false-viewer bot " + estimate
            if (len(tweet) + 2 + len(originame) <= 140): #max characters in a tweet
                tweet = tweet + " #" + originame
            print("tweeting: '" + tweet + "'")
            try:
                twitter.update_status(status=tweet)
            except:
                print "couldn't tweet :("
                errlog.write("Twitter mad, couldn't tweet :(.\n")
                pass

def game_ratio(game):
    global tweetmode
    try:
        r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
    except:
        print "uh oh caught exception when connecting. try again. see game_ratio(game)."
        game_ratio(game)
    while (r.status_code != 200):
        print r.status_code, ", service unavailable"
        r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
    gamedata = r.json()
#TODO make a dictionary with keys as the game titles and values as the average and count
    count = 0 # number of games checked
    avg = 0
    while len(gamedata.keys()) != 2:
        r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
        while (r.status_code != 200):
            print r.status_code, ", service unavailable"
            r = requests.get('https://api.twitch.tv/kraken/streams?game=' + game)
        gamedata = r.json()
    if len(gamedata['streams']) > 0:
        for i in range(0, len(gamedata['streams'])):
            viewers =  gamedata['streams'][i]['viewers']
            if viewers < user_threshold:
                break

            user = gamedata['streams'][i]['channel']['name'].lower() 
            name = "http://www.twitch.tv/" + user

            ratio = 0
            while ratio == 0:
                ratio = user_ratio(user)
            for item in suspicious:
                if (item[0] == name):
                    if (ratio > 2 * ratio_threshold):
                        suspicious.remove(item)
                        game = item[2]
                        tweet = name + " (playing " + game + ") appears to have a false-viewer bot"
                        print "tweet text: ", tweet
                        statuses = twitter.search(q=tweet)['statuses']
                        if (len(statuses) == 1):
                            id = statuses[0]['id']
                            print "Destroying tweet ", id
                            print "With text "+tweet
                            if (delete):
                                api.destroy_status(id)
                        else:
                            print "Something went wrong."
                            print "number of stati found:", len(statuses)
            if (tweetmode):
                send_tweet(user, ratio, game, viewers)
            avg += ratio
            count += 1
    else:
        print "couldn't find " + game + " :("
        return 0
    if count != 0:
        avg /= count
    # for the game specified, go through all users more than <user_threshold> viewers, find ratio, average them
    return avg

def remove_offline():
    for item in suspicious:
        name = item[0]
        originame = name[21:] #remove the http://www.twitch.tv/
        if (user_viewers(originame) < user_threshold):
            print originame + " appears to have gone offline (or stopped botting)! removing from suspicious list"
            suspicious.remove(item)
            if (delete):
                game = item[2]
                tweet = name + " (playing " + game.split(":")[0] + ") appears to have a false-viewer bot"
                print "tweet text: ", tweet
                statuses = twitter.search(q=tweet)['statuses']
                if (len(statuses) > 0):
                    for i in range(0, len(statuses)):
                        id = statuses[i]['id']
                        print "Destroying tweet ", id
                        print "With text "+tweet
                        api.destroy_status(id)
                else:
                    errlog.write("Something went wrong.\n")
                    errlog.write("searched for: "+ tweet + "\nBut didn't find it.\n")

#ratio = 0
def search_all_games():
    topdata = topreq.json()
    for i in range(0,len(topdata['top'])):
        game = removeNonAscii(topdata['top'][i]['game']['name'])
        print "__" + game + "__"
        ratio = game_ratio(game)
        print
        print "Average ratio for " + game + ": %0.3f" %ratio
        if (len(suspicious) == 0):
            print "We don't think anyone is botting " + game + "! :D:D"
        else: 
            print
            print
            print "We are suspicious of: "
            for item in suspicious:
                print "%0.3f:" %item[1], item[0]
            print "total of " + str(len(suspicious)) + " botters"
        print
        print

topreq = requests.get("https://api.twitch.tv/kraken/games/top")
while (topreq.status_code != 200):
    topreq = requests.get("https://api.twitch.tv/kraken/games/top")
topdata = topreq.json()

while 1:
    search_all_games()
    remove_offline()

