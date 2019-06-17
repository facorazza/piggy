# 🐷 P[Ig]*g*y

[![GitHub](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/Imperator26/piggy)
![](https://img.shields.io/badge/Python-%E2%89%A5%203.6-yellow.svg)
![](https://img.shields.io/badge/-asynchronous-blue.svg)

Piggy is an asynchronous Python library which helps managing Instagram accounts and facilitates their growth. It's easy to install and set up, and it doesn't need a browser to be executed.

## Index
- [Installation](#installation)
- [Setup](#setup)
- [Execution](#execution)
- [Disclaimer](#disclaimer)

## Installation
Piggy is easy to install. Fire up your terminal and copy these lines:
```
git clone https://github.com/Imperator26/piggy
cd piggy
python3 setup.py install
```

## Setup
Piggy's juiciest core is the `settings.json` file. Duplicate `settings.sample.json`and rename it in `settings.json`.
Open it with your favourite text editor and add your Instagram `username` and `password`.
```
{
  user:{
    username:"insert your username (or email) here",
    password:"insert your password here"
  }
...
}
```
Ignore everything else for now. We'll come back to it later on.

## Execution
To run Piggy insert:
```
python3 main.py
```

## Disclaimer
This library is a powerful tool; do not abuse it. We can't be held responsible in the unfortunate event that your account gets soft-banned, banned or in any other similar scenario.
🐷
