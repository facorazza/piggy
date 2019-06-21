import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="piggy",
    version="0.0.2",
    author="Federico A. Corazza",
    author_email="federico.corazza@live.it",
    description="Piggy is an asynchronous Python library which helps managing Instagram accounts and facilitates their growth.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Imperator26/piggy",
    packages=setuptools.find_packages(),
    install_requires=['requests', 'asyncio', 'aiohttp', 'aiosqlite', 'aiofiles', 'regex'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
