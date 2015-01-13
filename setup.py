import os.path


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def read(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()


setup(
    name='pns',
    version='1.3.0',
    author='Alper IPEK',
    author_email='3denizotesi@gmail.com',
    url='https://github.com/Turksat/pns',
    description='Push Notification Service for GCM and APNS',
    long_description=read('README.md'),
    packages=['pns', 'pns.controllers', 'pns.workers'],
    license="Apache 2.0",
    keywords='gcm apns push notification service',
    install_requires=['Flask==0.10.1', 'Flask-SQLAlchemy==2.0', 'Flask-WTF==0.10.3',
                      'pika==0.9.14', 'psycopg2==2.5.4', 'python-gcm==0.1.5', 'apns-clerk==0.1.1'],
    classifiers=['Development Status :: 2 - Pre-Alpha',
                 'Intended Audience :: Developers',
                 'License :: OSI Approved :: Apache Software License',
                 'Programming Language :: Python',
                 'Topic :: Software Development :: Libraries :: Python Modules']
)
