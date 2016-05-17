from flask import Flask, request,jsonify, render_template
import json, re, sqlite3, uuid, requests
from time import gmtime, strftime

app = Flask(__name__)
app.debug = True

#api token for the slackbot pong tracker. Should move this to another config file
slacktoken = 'xoxb-43423956055-9ETImQVlt3eYHXhiKSbHdCTr'




#check the message passed to /pong to see if the user wants to see leaderboard
def check_leaderboard(response_text):

    #split the response into distinct words and check each word to see if its leaderboard. 
    #Since im using the in operator going word by word should prevent mistakes
    response_array = response_text.split()
    
    for word in response_array:
        if word.lower() == 'leaderboard':
            return True
    return False



def find_slack_user(name):

    username = name.replace("@","") #get rid of @ sign since slack usernames are stored without it

    conn = sqlite3.connect('/home/ubuntu/pong/pong.db')
    c = conn.cursor()
    resp = c.execute('SELECT id FROM users WHERE name = ?', (username,))

    for row in resp:
        userid=row[0]

    conn.close()

    return userid



#take slack text and parse out who lost
def find_reported_loser(resp_text):

    #split each word and look for the @mention
    response_words_array = resp_text.split()

    for word in response_words_array:
        if '@' in word:
            return find_slack_user(word)    





def get_channel_id(userid):

    payload = {'token': slacktoken , 'user': userid}
    r = requests.get('https://slack.com/api/im.open', params = payload) 

    parsed_json = r.json()
    channel = parsed_json['channel']['id']       

    return channel



def send_slack_message(msg_type, matchid, winner, loser, channel):

    if msg_type =='verify': 

        channel = get_channel_id(loser)
        text = 'Hi <@'+loser+'> please confirm that <@'+winner+'> beat you in ping pong: <http://ec2-52-25-91-7.us-west-2.compute.amazonaws.com/confirm/'+matchid+'|I lost> - <http://ec2-52-25-91-7.us-west-2.compute.amazonaws.com/dispute/'+matchid+'/'+loser+'|Hell no>'
  
    elif msg_type == 'confirmed':
        channel = get_channel_id(winner)
        text = 'Congrats <@'+winner+'>! <@'+loser+'> has confirmed your win. The leaderboard has been udpated.'

    elif msg_type == 'dupe':
        channel = get_channel_id(loser)
        text = 'You have already reported this result. You can only claim one win or loss per message'

    else:
        channel = get_channel_id(winner)
        text = 'Uh oh, <@'+winner+'>. Looks like we have a problem. <@'+loser+'> is disputing your recent win. Fight it out amongst yourselves and try reporting the match again later when you both agree.'

    icon = 'http://pngimg.com/upload/small/ping_pong_PNG10361.png'
    payload = {'token': slacktoken, 'channel': channel, 'text': text, 'username': 'Pong Tracker', 'as_user': 'false', 'icon_url': icon, 'unfurl_links': 'false', 'unfurl_media': 'false'}
    r = requests.get('https://slack.com/api/chat.postMessage', params =payload)

def report_match(response_object):
    
    channel = response_object.get("channel_id")
    matchid = str(uuid.uuid1())
    reported_winner = response_object.get("user_id")
    reported_loser = str(find_reported_loser(response_object.get("text")))
    confirmed = 0
    date = str(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    msg_type = 'verify'

    conn = sqlite3.connect('/home/ubuntu/pong/pong.db')
    c = conn.cursor()
    c.execute('INSERT INTO matches(id,winner,loser,confirmed,date) VALUES (?,?,?,?,?)',(matchid, reported_winner, reported_loser, confirmed, date,))
    conn.commit()
    conn.close()

    send_slack_message(msg_type, matchid, reported_winner, reported_loser, channel)
#confirmation to reporting user
#send request to validate result to losing user

    return request.form.get("text")

def display_leaderboard():
    ldrs = []    
    conn = sqlite3.connect('/home/ubuntu/pong/pong.db')
    c = conn.cursor()
    leaderboard = c.execute('SELECT users.real_name, matches.winner, COUNT(matches.winner) as wins  from matches INNER JOIN users on users.id = matches.winner WHERE confirmed = 1 GROUP BY matches.winner ORDER BY wins desc LIMIT 5')
    for row in leaderboard:
        name = row[0]
        wins = row[2]
    ldrs.append(str(name)+ ': '+ str(wins)+ ' wins')
    conn.close()

   #need storage for leaderboard
    #logging every match reported?
    return 'Top 5 Pong Players:'+'\n'+ '1. '+ldrs[0] +'\n'#+ '2. '+ldrs[1] +'\n'+ '3. '+ldrs[2] +'\n'+ '4. '+ldrs[3] +'\n'+ '5. '+ldrs[4]

@app.route('/')
def index():
    count = 1
    name_rank = []
    conn = sqlite3.connect('/home/ubuntu/pong/pong.db')
    c = conn.cursor()
    leaderboard = c.execute('SELECT users.real_name, matches.winner, COUNT(matches.winner) as wins  from matches INNER JOIN users on users.id = matches.winner WHERE confirmed = 1 GROUP BY matches.winner ORDER BY wins desc')
    for row in leaderboard:
        name = row[0]
        wins = row[2]
        rank = count
        
        name_rank.append({'name':str(name), 'wins': str(wins), 'rank': str(rank) })
        count += 1
    conn.close()

    return render_template('pong.html', name_rank=name_rank)

@app.route('/score', methods=['POST'])
def pong():
    response = request.form    
    response_text= request.form.get("text")

    if check_leaderboard(response_text):
        return display_leaderboard()

    elif 'beat' in response_text:
        report_match(response)
        return "Congrats on the win! I'm going to verify this with the loser. If verified, I'll update the leaderboard."
    
    else:
        return 'Sorry, you must enter "I beat @username" to report a match or "leaderboard" to see the top 5 players.'

@app.route('/confirm/<matchid>')
def confirmed(matchid):
    conn = sqlite3.connect('/home/ubuntu/pong/pong.db')
    c = conn.cursor()
    
    c.execute('UPDATE matches SET confirmed = ? WHERE id =?', (1, matchid,))
    conn.commit()
    rslt = c.execute('SELECT winner, loser, channel, confirmed FROM matches WHERE id =?',(matchid,))

    for row in rslt:
        winner = row[0]
        loser = row[1]
        channel = row[2]
        confirmed = row[3]
    conn.close()

    if confirmed == 1:
        msg_type = 'dupe'
        send_slack_message(msg_type, matchid, winner, loser, channel)
        return render_template('thankyou.html')

    
    else:
        msg_type = 'confirmed'

        send_slack_message(msg_type, matchid, winner, loser, channel)
        return render_template('thankyou.html') 
#update db to show match is confirmed
#message both users about confirmation
#update standings?

@app.route('/dispute/<matchid>/<userid>')
def disputed(matchid, userid):
#need to render a template here to thank the user-or come up with better solution
#delete match from db
    conn = sqlite3.connect('/home/ubuntu/pong/pong.db')
    c = conn.cursor()
    rslt = c.execute('SELECT winner, loser, channel FROM matches WHERE id =?',(matchid,))
    winner = None
    loser = None #need to pass sending user to this url so i know where to message to in the case that there is no match in the db. OR dont delete stuff an add column to track reported
    channel = None

    for row in rslt:
        winner = row[0]
        loser = row[1]
        channel= row[2]

    if winner == None:
        conn.close()
        msg_type = 'dupe'
        
        send_slack_message(msg_type, matchid, winner, userid, channel)
        return render_template('thankyou.html')
    else:
 
        c.execute('DELETE FROM matches WHERE id =?', (matchid,))
        conn.commit()
        conn.close()

#message both users to resolve their differences and report the match again later
        msg_type = 'disputed'
        send_slack_message(msg_type, matchid, winner, loser, channel)
        return render_template('thankyou.html')

if __name__ == '__main__':
    app.run()


