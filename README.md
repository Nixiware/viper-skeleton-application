Viper skeleton application
=======================

Introduction
------------
Serves as starting point for building applications using the [nx.viper](https://github.com/Nixiware/viper) framework.


Requirements
------------
* Python 3.6

Optional

* MySQL / MariaDB
* SMTP server

Features
------------
* environment based configuration
* HTTP REST API interface
* support for building multiple interfaces including sockets, WebSockets and anything [Twisted](https://github.com/twisted/twisted) supports
* CRUD example
* model example with asynchronous database operations
* background services with scheduled and recurring operations

Usage
------------

1. Create a virtual environment using [virtualenv](https://virtualenv.pypa.io/en/stable/) and activate it
2. Install dependencies with ```pip install -r requirements.txt```
3. Duplicate ```config/local.json.dist``` to ```config/local.json```
4. Configure ```config/local.json```
5. *optional* - Create a new MySQL database with the contents of ```script/sql/base.sql``` and ```script/sql/up.sql```

To start the application use [twistd](https://twistedmatrix.com/documents/current/core/howto/basics.html) by running:

```
twistd -ny service.tac
```

Deployment
------------

*systemd* can be used for deployment. Create a new service file for the application at ```/etc/systemd/system/viper-application.service``` with the following content:

```
[Unit]
Description=Viper application

[Service]
ExecStart=/path/to/viper/application/venv/bin/twistd -l log/application.log -y service.tac --nodaemon --pidfile=viper-application.pid

WorkingDirectory=/path/to/viper/application

User=nobody
Group=nobody

Restart=always

[Install]
WantedBy=multi-user.target
```

Replace any values to match your target deployment and make sure the application is not running as *root*.



More details can be found in the [official Twisted documentation](https://twistedmatrix.com/documents/current/core/howto/systemd.html).

Notice
------------
Viper is currently in Beta stage.

The roadmap before public release is:

1. Documentation