from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from engineio.async_drivers import gevent
import threading
import time
import json
import os

app = Flask(__name__)
socketio = SocketIO(app)


def save_score_data():
    with open("scoreboard.json", "w") as f:
        json.dump(score_data, f)

def load_score_data():
    global score_data
    if os.path.exists("scoreboard.json"):
        with open("scoreboard.json", "r") as f:
            score_data.update(json.load(f))

score_data = {
    "team1": {"name": "Team 1", "score": 0},
    "team2": {"name": "Team 2", "score": 0},
    "timer": "30:00",
    "timer_running": False,
    "timer_direction": "down",
    "timer_target": "0:00",
    "period": {"name": "Quarter", "value": 1}
}
load_score_data()

def write_to_file():
    with open("scoreboard.txt", "w") as f:
        f.write(f"{score_data['team1']['name']} {score_data['team1']['score']}\n")
        f.write(f"{score_data['team2']['name']} {score_data['team2']['score']}\n")
        f.write(f"Timer {score_data['timer']}\n")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scoreboard')
def scoreboard():
    return render_template('scoreboard.html')

@app.route('/control')
def control():
    return render_template('control.html')

@socketio.on('update')
def handle_update(data):
    global score_data
    score_data.update(data)
    save_score_data()
    socketio.emit('score_update', score_data)
    

@socketio.on('request_score')
def handle_request():
    emit('score_update', score_data)


def parse_time(timestr):
    m, s = map(int, timestr.split(":"))
    return m * 60 + s

def format_time(seconds):
    m = seconds // 60
    s = seconds % 60
    return f"{m:02}:{s:02}"

timer_thread = None
timer_lock = threading.Lock()

def timer_worker():
    global score_data
    while score_data["timer_running"]:
        with timer_lock:
            current = parse_time(score_data["timer"])
            direction = score_data["timer_direction"]
            target = parse_time(score_data["timer_target"])
            if direction == "up":
                current += 1
                if score_data["timer_target"] != "00:00" and current >= target:
                    score_data["timer_running"] = False
            else:
                current -= 1
                if current <= 0 or (score_data["timer_target"] != "00:00" and current <= target):
                    current = max(current, 0)
                    score_data["timer_running"] = False
            score_data["timer"] = format_time(current)
        socketio.emit('score_update', score_data)
        time.sleep(1)

@socketio.on('timer_control')
def handle_timer_control(data):
    global timer_thread, score_data
    action = data.get('action')
    with timer_lock:
        if action == 'start' and not score_data["timer_running"]:
            score_data["timer_running"] = True
            timer_thread = threading.Thread(target=timer_worker)
            timer_thread.daemon = True
            timer_thread.start()
        elif action == 'stop':
            score_data["timer_running"] = False
        elif action == 'reset':
            score_data["timer_running"] = False
            if score_data["timer_direction"] == "down":
                score_data["timer"] = score_data["timer_target"]
            else:
                score_data["timer"] = "00:00"
        elif action == 'up':
            timer = parse_time(score_data["timer"])
            timer += 1
            timer = format_time(timer)
            score_data["timer"] = timer
        elif action == 'down':
            timer = parse_time(score_data["timer"])
            timer -= 1
            timer = format_time(timer)
            score_data["timer"] = timer
    save_score_data()
    socketio.emit('score_update', score_data)


if __name__ == '__main__':
    print("Server is running at 127.0.0.1:5000")
    print("Keep this window open")
    socketio.run(app, host='127.0.0.1', port=5000)