"""
This is the main file that groover uses to
generate recommendations. This file
communicates and controls other programs in
the groover application.
"""
from flask import render_template, flash, redirect, request, url_for
from application import app
from application.forms import LoginForm
from application.recommendations import DEFAULT_MODEL, MODELS, RETRAINED_MODEL, find_track

@app.route('/', methods=['GET', 'POST'])
def lookup():
    """
    This method validates the forms on the homepage,
    which can be found in forms.py, and then sends the
    result and user to another webpage.
    """
    form = LoginForm()
    if form.validate_on_submit():
        if set(form.artist.data).intersection("%^&*()<>?+=") or set(form.title.data).intersection("%^&*()<>?+="):
            flash('Whoops! Please omit special characters.', category='error')
            return render_template('whoops.html', title='error')
        artist = str(form.artist.data)
        artist=artist.replace('#','').replace('/',' ')
        title = str(form.title.data)
        title=title.replace('#','').replace('/',' ')
        return redirect(url_for('recommendations', artist=artist, title=title))
    if (form.artist.data and not form.title.data) or (not form.artist.data and form.title.data):
        flash('Whoops! Please enter both the song name and artist.', category='error')
        return render_template('whoops.html', title='Input error')
    return render_template('lookup.html', title='Smarter Music Recommendations', form=form)

@app.route('/about')
def about():
    """
    This will send the user to our about page, with a link
    to our GitHub
    """
    return render_template('about.html', title='About')

@app.route('/robots.txt')
def robots():
    """
    keeps crawlers off recommendation pages, since each
    one spends Musixmatch and Spotify quota
    """
    return app.send_static_file('robots.txt')

@app.route('/recommendations/<artist>/<title>')
def recommendations(artist, title):
    """
    This method will find our track information using various
    helper functions in the Recommendation class. It will send
    the user to the recommendation page or will ask for more input
    if search is unsuccessful.
    """
    model = request.args.get('model', DEFAULT_MODEL)
    if model not in MODELS:
        model = DEFAULT_MODEL
    rec = find_track(artist, title)
    if rec:
        rec.load_recommendations(model)
        other_model = RETRAINED_MODEL if model == DEFAULT_MODEL else None
        other_model_url = url_for('recommendations', artist=artist, title=title, model=other_model)
        return render_template('recommendations.html', title='Your Recommendations', rec=rec,
                               model=model, other_model_url=other_model_url)
    flash('Whoops, we did not find the track "{}" by {}!'.format(\
    title, artist), category='error')
    return render_template('whoops.html', title='Song Not Found')
