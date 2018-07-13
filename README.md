Viper skeleton application
=======================

Introduction
------------
Serves as a skeleton application for the [nx.viper](https://github.com/Nixiware/viper) framework.
It is meant to be used as a starting point for projects.

Requirements
------------
* nx.viper
* Python 3.6

Optional

* MySQL / MariaDB
* SMTP server

Features
------------



Usage
------------


Deployment
------------

```
/home/application/viper-skeleton-application/venv/bin/twistd -l log/application.log -y service.tac --nodaemon --pidfile=viper-skeleton-application.pid
```

Notice
------------
Viper is currently in Beta stage.