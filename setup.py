#!/usr/bin/env python

from setuptools import setup

setup(name             = 'Canoris',
      version          = '0.10',
      description      = 'Client library for accessing the Canoris API.',
      author           = 'Vincent Akkermans',
      author_email     = 'vincent.akkermans@upf.edu',
      url              = 'http://www.canoris.com',
      packages         = ['canoris'],
      install_requires = ['simplejson',
                          'poster',
                          'httplib2']
     )
