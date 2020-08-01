#!/usr/bin/env python
from setuptools import setup

setup(name='server-web-53',
      version='0.1',
      description='Web-53 lab simple server',
      author='NSALAB',
      author_email='experts@nsalab.org',
      url='https://nsalab.org/web53',
      install_requires=['pyyaml','boto3','redis','flask','requests'] 
     )