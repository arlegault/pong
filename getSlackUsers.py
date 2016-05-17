#This file is responsible for fetching all users from PB slack team list and inserting any new ones into the db. It should probably be setup as a cron job


import requests, json, sqlite3

def write_new_to_db(user_id, username, fullname, deleted):
    conn = sqlite3.connect('pong.db')
    c = conn.cursor()
    #result = c.execute('SELECT * FROM users WHERE id=?',(user_id,))
    print user_id
    #if result.fetchone() is None:
    c.execute('INSERT OR IGNORE INTO users(id,name,real_name,deleted) VALUES (?,?,?,?)', (user_id, username, fullname, deleted,))
    conn.commit()
    conn.close()
   # else:
    #    conn.close()
        


def update_slack_user_list():
    r = requests.get('https://slack.com/api/users.list?token=REDACTED')

    if r.status_code == 200:
        parsed_json = r.json()
       # parsed_json = json.loads(raw_json)
        for item in parsed_json['members']:
            user_id = item["id"]
            username = item["name"]
            fullname = item['profile']['real_name']
            if item['deleted'] == 'true':
                deleted = 1
            else:
                deleted = 0

            write_new_to_db(user_id, username, fullname, deleted)

update_slack_user_list()
