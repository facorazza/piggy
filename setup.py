import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="piggy",
    version="0.0.8",
    author="Federico A. Corazza",
    author_email="federico.corazza@live.it",
    description="Piggy is an asynchronous Python library which helps managing Instagram accounts and facilitates their growth.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Imperator26/piggy",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "cchardet==2.1.4",
        "aiodns==2.0.0",
        "aiohttp==3.5.4",
        "aiosqlite==0.10.0",
        "aiofiles==0.4.0",
        "regex==2019.06.08"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
