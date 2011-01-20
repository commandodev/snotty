from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='snotty',
      version=version,
      description="Streaming nose tests via WebSockets",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ben Ford',
      author_email='ben@boothead.co.uk',
      url='',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'nose',
          'stargate',
          'pyramid_jinja2',

          # -*- Extra requirements: -*-
      ],
      entry_points= {
        'paste.app_factory': ['js-test = snotty.factory:test_app_factory']
      }
      )
