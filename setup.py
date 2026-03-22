"""Setup for CodeDojo."""

from setuptools import setup, find_packages

setup(
    name="codedojo",
    version="1.0.0",
    description="🥋 CodeDojo — AI-powered Python coding sensei",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "anthropic>=0.40.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "codedojo=codedojo.cli:main",
        ],
    },
)
