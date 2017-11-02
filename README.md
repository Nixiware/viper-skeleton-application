Viper skeleton application
=======================

Introduction
------------
Serves as a skeleton application for the nx.viper framework package.
It is meant to be used as a starting point for any project.

Requirements
------------
* Python 3
* MySQL 5.5 / MariaDB 10

Known issues
------------
1. The example HTTP interface does not work reliable over TLS. The connection is performed succesfuly in Chrome, Safari and Postman, but it fails in Firefox and older versions of curl / openssl.
This issue is triggered when additional chain certificates are included in the TLS options. 

Notice
------------
Viper is currently in Alpha stage.