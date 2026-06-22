FROM mcr.microsoft.com/devcontainers/python:3.14

RUN mkdir -p /home/vscode/.ssh && chown -R vscode:vscode /home/vscode/.ssh

RUN pip install --no-cache-dir -r Flask>=3.0,<4.0 \
                                  Flask-SocketIO>=5.3,<6.0 \
                                  python-socketio>=5.10,<6.0 \
                                  python-engineio>=4.8,<5.0


RUN apt-get update && apt-get install -y --no-install-recommends \
    sshpass \
    fastfetch \
    curl \
    meld \
    && rm -rf /var/lib/apt/lists/*
