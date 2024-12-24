# Python Getting Started

A barebones Django app, which can easily be deployed to Heroku.

## Deploying to Heroku

Basic deployment:
```term
$ git clone https://github.com/heroku/python-getting-started
$ cd python-getting-started
$ heroku create
$ git push heroku master
$ heroku open
```

To deploy from a non-master branch:
```term
git push heroku django:main
```

For more information about using Python on Heroku, see these Dev Center articles:

- [Python on Heroku](https://devcenter.heroku.com/categories/python)
