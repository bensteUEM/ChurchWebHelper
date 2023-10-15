# Setup

# Running the app

Downloading the source code of the project by default a .vscode directory contains samples launch configurations
If you are not intending to do changes to this app it is recommended to simply pull the docker image from the latest release as listed on https://github.com/bensteUEM/ChurchWebHelper/releases

Two environment variables can be used to simplify usage by prepopulating respective values during login.
* CT_DOMAIN
* COMMUNI_SERVER

These can be set when launching the container with docker

# Development use
this project was created using VS Code on Ubuntu
to simplify version control and use by others respective configurations are included in the git repo

## Version number
version.py is used to define the version number used by any automation

## launch.json
 'ChurchWebHelper (local)' will start a local flask app by running main_web.py with some params
 'Docker Compose Up' is using docker-compose.yml and will start a production server including the current version number
 'Docker Compose Debug Up' composes a docker container for debugging also including the version number

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