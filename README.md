# Setup

THIS README IS OUTDATED and needs to be updated to reflect the correct project SPLIT! see #1

## Using project source code directly

Downloading the source code of the project by default a config.py
needs to be added in the "secure" folder for default execution.
Please be aware that this will include sensitive information and should never be shared with 3rd parties and is
therefore included in gitignore

It should look like this:

```
# COMMENT FOR WHICH USER / DATE this is -> DO NOT SHARE
ct_domain = 'https://YOUR-DOMAIN.DE'
ct_token = 'TOKEN SECRET VERY LONG RANDOM STRING'
ct_users = {'USER_EMAIL': 'USER_PASSWORD'}
```

## Using it as a module

If you want to use this code as a python module certain classes will require params similar to the config file in order
to access your system

- check the docstrings for correct usage

The latest release can be found on https://github.com/bensteUEM/ChurchWebHelper/releases

It can be installed using
```pip install git+https://github.com/bensteUEM/ChurchWebHelper.git@vX.X.X#egg=ChurchToolsAPI'```
replacing X.X.X by a released version number

## Using it via docker or github actions

For use within a Docker container or for tests using GithubActions ENV variables can be used to pass the required
configurations values these are

* CT_DOMAIN
* CT_TOKEN
* CT_USERS

Values can be written like entered in a text box - no quotation marks are required. The CT_Users String is interpreted
as dict like shown in the sample of config.py but must include {}

### CT Token

CT_TOKEN can be obtained / changed using the "Berechtigungen" option of the user which should be used to access the CT
instance. It is highly recommended to setup a custom user with minimal permissions for use with this module.
However please check the log files and expect incomplete results if the user is msising permissions.

# Development use

The script was coded using VS Code. 
Test cases are automatically run when pushed to GitHub. This ensures that basic functionality is checked against at least one environment.
You are more than welcome to contribute additional code using respective feature branches and pull requests.

# License

This code is provided with a CC-BY-SA license
See https://creativecommons.org/licenses/by-sa/2.0/ for details.

In short this means - feel free to do anything with it
BUT you are required to publish any changes or additional functionality (even if you intended to add functionality for
yourself only!)

Anybody using this code is more than welcome to contribute with change requests to the original repository.

## Contributors

* benste - implemented for use at Evangelische Kirchengemeinde Baiersbronn (https://www.evang-kirche-baiersbronn.de/)