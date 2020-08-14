# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


setup(
    name="chiptunesak",
    version="0.3.1",
    description="Generalized pipeline for processing music and targeting various constrained playback environments",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="David Youd",
    author_email="cryptoboy@gmail.com",
    url="https://github.com/c64cryptoboy/ChiptuneSAK",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "matplotlib",
        "mido",
        "more-itertools",
        "numpy",
        "parameterized",
    ],
    entry_points={"console_scripts": []},
    scripts=["examples/lechuck.py"],
    classifiers=[
        # 'Development Status :: 5 - Production/Stable',
        "Environment :: Console",
        "Intended Audience :: Developers",
        'License :: OSI Approved :: MIT License',
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
