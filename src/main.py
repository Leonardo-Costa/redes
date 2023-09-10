from flask import Flask, render_template
from flask_socketio import SocketIO, send

app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)
app.static_folder = 'static'

@socketio.on('message')
def handleMessage(message):
    print('mensagem recebida: ' + message)
    if message != "usuário conectado!":
        send(message, broadcast=True)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='localhost')