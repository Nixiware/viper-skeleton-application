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
* CRUD example
* model example with asynchronous operations
* background services with scheduled and recurring operations

Usage
------------

1. Install dependencies with ```pip install -r requirements.txt```
2. Duplicate ```config/local.json.dist``` to ```config/local.json```
3. Configure ```config/local.json```
4. *optional* - Create a new MySQL database with the contents of ```script/sql/base.sql``` and ```script/sql/up.sql```

To start the application use [twistd](https://twistedmatrix.com/documents/current/core/howto/basics.html) by running:

```
twistd -ny service.tac
```

Deployment
------------


```
/home/application/viper-skeleton-application/venv/bin/twistd -l log/application.log -y service.tac --nodaemon --pidfile=viper-skeleton-application.pid
```

Notice
------------
Viper is currently in Beta stage.

The roadmap before public release is:

1. Documentation