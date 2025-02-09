#!/usr/bin/env python
import json
from threading import Lock

from flask import Flask, render_template, session, request
from flask_cors import CORS
from flask_restplus import Api, Resource
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect

async_mode = None

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'secret!'
api = Api(app)
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins="*")
thread = None
thread_lock = Lock()


class EventAPI(Resource):
    def get(self):
        data = {}
        with open('demo_event.json') as json_file:
            data = json.load(json_file)
        payload = {"success": True,
                   "message": "success",
                   "data": data}
        return payload, 200


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)
        count += 1
        socketio.emit('my_response',
                      {'data': 'Server generated event {}'.format(count),
                       'count': count},
                      namespace='/socketio')


@app.route('/index.html')
def index():
    return render_template('index.html')


class MyNamespace(Namespace):
    def on_my_event(self, message):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': message['data'], 'count': session['receive_count']})

    def on_my_broadcast_event(self, message):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': message['data'], 'count': session['receive_count']},
             broadcast=True)

    def on_join(self, message):
        join_room(message['room'])
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': 'In rooms: ' + ', '.join(rooms()),
              'count': session['receive_count']})

    def on_leave(self, message):
        leave_room(message['room'])
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': 'In rooms: ' + ', '.join(rooms()),
              'count': session['receive_count']})
        print("Leave room")

    def on_close_room(self, message):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': 'Room ' + message['room'] + ' is closing.',
              'count': session['receive_count']},
             room=message['room'])
        close_room(message['room'])

    def on_my_room_event(self, message):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': message['data'], 'count': session['receive_count']},
             room=message['room'])

    def on_disconnect_request(self):
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response',
             {'data': 'Disconnected!', 'count': session['receive_count']})
        disconnect()

    def on_my_ping(self):
        emit('my_pong')

    def on_connect(self):
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(background_thread)
        emit('my_response', {'data': 'Connected', 'count': 0})
        socketio.emit('my_response',
                      {'data': 'Client connected {}'.format(request.sid),
                       'count': 0}, namespace='/event')

    def on_disconnect(self):
        socketio.emit('my_response',
                      {'data': 'Client disconnected {}'.format(request.sid),
                       'count': 0}, namespace='/socket')
        print('Client disconnected', request.sid)


socketio.on_namespace(MyNamespace('/socket'))
api.add_resource(EventAPI, '/api/event')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)
