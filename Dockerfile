FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive

# installing required packages
RUN apt-get update && \
    apt-get install -y python-dev python3-pip

# creating user
RUN useradd application -m
RUN mkdir /home/application/source
RUN mkdir /home/application/log

# adding source files
WORKDIR /home/application/source
ADD . /home/application/source

# installing dependencies
RUN pip3 install --trusted-host pypi.python.org -r requirements.txt

# exposing HTTP port
EXPOSE 8001

# starting Twistd in foreground
CMD twistd -l /home/application/log/application.log -y service.tac --nodaemon --pidfile=stiricurate-proxy.pid