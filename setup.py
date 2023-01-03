import os
from setuptools import setup


def readfile(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), 'rt', encoding='utf-8') as f:
        return f.read()


setup(
    name='timus_api',
    version='0.1.0',
    author='Gleb Katkov',
    author_email='gkigki111@gmail.com',
    description='A tool to access https://acm.timus.ru/ services programmatically',
    license='MIT',
    keywords='timus api',
    url='https://github.com/dr-bright/timus_api',
    long_description=readfile('README.md')
)

