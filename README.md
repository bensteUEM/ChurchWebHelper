# Setup

# Running the app

Downloading the source code of the project by default a .vscode directory contains samples launch configurations
If you are not intending to do changes to this app it is recommended to simply pull the docker image from the latest release as listed on https://github.com/bensteUEM/ChurchWebHelper/releases

Two environment variables can be used to simplify usage by prepopulating respective values during login.
* CT_DOMAIN
* COMMUNI_SERVER

These can be set when launching the container with docker

## ChurchTools Login
A valid churchtools login (with username / password) is required in ordert to perform most actions.
Opening a page might redirect automatically to an authorization page unless username / password is provided with BasicAuth.

Username & Password was chosen in favor of token login in order to ease up individual user logins 

## Communi Login
Some pages require a valid Communi API login
If the session was not authorized before, requests will be redirected to a login page

# Development use
this project was created using VS Code on Ubuntu
to simplify version control and use by others respective configurations are included in the git repo

## Version number
version.py is used to define the version number used by any automation

## launch.json
 'ChurchWebHelper (local)' will start a local flask app by running main_web.py with some params
 'Docker Compose Up' is using docker-compose.yml and will start a production server including the current version number
 'Docker Compose Debug Up' composes a docker container for debugging also including the version number

### nice2know for debugging local docker containers
1. make sure /var/run/docker.sock has group "docker" with rw permissions and user is assigned to group docker
2. docker container IP != local IP - might wanna use the following commands to find the correct IP
 - ```docker container list```
 - ```docker inspect   -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}  container_name_or_id```
default could be http://172.18.0.2:5000

## tasks.json
does trigger the docker-compose commands used for 2 launch configurations.
This is also where the respective ENV vars can be changed.
Unfortuneatly these can not be read from a seperate file.

## Building docker image for GHCR with github actions

some automation is located in .github/.workflows directory
- docker-image_dev_benste.yml will create a docker image on GHCR using the version tag
- docker-image_master.yml will create a "latest" release docker image

The following SECRETS / ENV variables are required within the Github Project
* GITHUB_TOKEN -> Token that has access to clone the repo
* CR_PAT -> Token that has rights to publish to GHCR

# License

This code is provided with a CC-BY-SA license
See https://creativecommons.org/licenses/by-sa/2.0/ for details.

In short this means - feel free to do anything with it
BUT you are required to publish any changes or additional functionality (even if you intended to add functionality for
yourself only!)

Anybody using this code is more than welcome to contribute with change requests to the original repository.

## Contributors

* benste - implemented for use at Evangelische Kirchengemeinde Baiersbronn (https://www.evang-kirche-baiersbronn.de/)