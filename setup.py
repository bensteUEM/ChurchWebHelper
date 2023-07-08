from setuptools import setup, find_packages
from versions import VERSION

with open("README.md", "r") as file:
    description = file.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='ChurchWebHelper',
    version=VERSION,
    author='bensteUEM',
    author_email='benedict.stein@gmail.com',
    description='A python package to make use of ChurchTools API and Communi API with a docker packaged WebUI',
    long_description=description,
    long_description_content_type="text/markdown",
    url='https://github.com/bensteUEM/ChurchWebHelper',
    license='CC-BY-SA',
    python_requires='>=3.8',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'ChurchToolsWebService': ['templates/*.html', 'static/*']
    },
    install_requires=requirements,
)