#counts the number of chatters in a certain Twitch chat room.
import sys
import socket
import requests
from pass_info import get_username, get_password
from twitch_viewers import remove_non_ascii

names_num = "353"
end_names_num = "366"

port1 = 6667 #irc
port2 = 80 #http
port3 = 443 #https
default_port = port3

i = 0#
def count_users(full_msg):
    data = full_msg.split("\r\n")
    count = 0
    for namegroup in data:
        if ("End of /NAMES list" in namegroup or
            "tmi.twitch.tv " + end_names_num in namegroup):
            if (count == 65959): #This was a number I was getting repeatedly
                print "what."    #When looking at riotgames (300k viewers).
                print namegroup  #I still don't know why it is/was happening, so
                return 0         #it is still printing this for debugging purposes.
            return count - 1
        namegroup = namegroup.split(" ")
        if names_num in namegroup:
            names = namegroup[5:]
            count += len(names)
    if count == 2:
        print full_msg
    if count == 65959: #this was happening a lot, unexplicably. 
        print "wath"
        return 0
    if count == 0:
        return count
    print "here"
    return count - 1 #don't count myself - i'm not actually in chat

def chat_count(chatroom, verbose=False):
    global i
    i = 0
    chan = "#" + chatroom
    nick = get_username()
    PASS = get_password()
    sock = socket.socket()
    sock.connect(("irc.twitch.tv", default_port))
    sock.send("PASS " + PASS + "\r\n")
    sock.send("USER " + nick + " 0 * :" + nick + "\r\n")
    sock.send("NICK " + nick + "\r\n")
    full_msg = ""
    while 1:
       sock.send("JOIN "+chan+"\r\n")
       data = remove_non_ascii(sock.recv(1024))
       i+=1
       if data[0:4] == "PING":
          sock.send(data.replace("PING", "PONG"))
          continue
       full_msg += data #if you keep requesting to JOIN the channel, it will continue returning 
                        #more and more names until "End of /NAMES list"
       if verbose:
           print data
       if ":End of /NAMES list" in data: #do we end the search?
           if verbose:
               print "returning (\"End of /NAMES list\") due to:"
               print data
           return count_users(full_msg)
       if ":jtv MODE #" in data:
           if verbose:
               print "returning (FOUND MODE) due to:"
               print data
           return count_users(full_msg)
       if "366 " + nick in data: #status code for ending the stream of names
           if verbose:
               print "returning (366) due to:"
               print data
           return count_users(full_msg)
       if False and "PRIVMSG" in data: #privmsg's only come in after the names list
           if verbose:
               print "returning (PRIVMSG) due to:"
               print data
           return count_users(full_msg)

def get_users(full_msg):
    l = []
    data = full_msg.split("\r\n")
    for namegroup in data:
        if "End of /NAMES list" in namegroup or \
            "tmi.twitch.tv " + end_names_num in namegroup:
            return l
        namegroup = namegroup.split(" ")
        if names_num in namegroup:
            names = namegroup[5:]
            for name in names:
                name = name.strip(":")
                if name != get_username():
                    l.append(name)
    print "here - i don't think this should occur."
    return l

def user_follows(user):
    follows = requests.get("https://api.twitch.tv/kraken/users/"+user+"/follows/channels")
    return follows.json()['_total']

def avg_user_follows(user):
    r= requests.get("http://tmi.twitch.tv/group/user/" + user + "/chatters")
    chatters = r.json()
    l = chatters['chatters']['viewers']
    skip = int(len(l) / 29.0)
    avg = 0
    cnt = 0
    print "counting..."
    for user in l[::skip]:
        cnt += 1
        total = user_follows(user)
        print cnt, user, total
        avg += total
    avg /= float(cnt)
    return avg

#usage example: "python chat_count.py twitchplayspokemon"
if __name__ == '__main__':
    if len(sys.argv) >= 2:
        args = sys.argv[1:]
        verbose = '-v' in args or '--verbose' in args
        print verbose
        count = 5
        #print avg_user_follows(sys.argv[1])
        count = chat_count(sys.argv[1], verbose=verbose)
        print count, "chatters in %s" %sys.argv[1]

