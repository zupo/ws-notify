# Install
$ virtualenv .
$ source bin/activate
$ pip install -r requirements.txt

# Run with Foreman so env is set like in production
$ heroku config:pull --overwrite
$ foreman start
