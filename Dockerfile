FROM ubuntu:20.04

ENV DEBIAN_FRONTEND noninteractive

ENV DB_HOST=database

# install required packages
RUN apt-get update && \
    apt-get install -y netcat-traditional python3-pip

# create user
RUN useradd application -m
RUN mkdir /home/application/source
RUN mkdir /home/application/log

# add source files
WORKDIR /home/application/source
ADD . /home/application/source

# install dependencies
RUN pip3 install --trusted-host pypi.python.org -r requirements.txt

# expose HTTP port
EXPOSE 8000

# run start script
COPY script/container/run.sh /run.sh
RUN chmod 755 /run.sh
ENTRYPOINT ["/run.sh"]

# start Twistd in foreground
CMD twistd -l /home/application/log/application.log -y service.tac --nodaemon --pidfile=