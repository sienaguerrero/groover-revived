# Groover 🎵

Song recommendations from lyrics. Groover started as a spring 2019 Harvey Mudd CS121 team project and was revived in 2026 to run on current Python. Hosted at https://groover.siena.codes.

Type a song and its artist. Groover gets the lyrics from Musixmatch, turns them into a vector with a Doc2Vec model trained on the lyrics of 57,581 songs, and shows the 20 songs whose vectors point the most nearly the same way. Each one comes with the album art, 30-second preview, and Spotify link saved when the model was trained.

## What's here

- `application/`: the Flask app. `recommendations.py` calls Musixmatch and Spotify and ranks songs with the model.
- `data/d2v.model`: the 2019 model, converted to gensim 4's format.
- `data/catalog.json`: name, artist, genres, album art, preview, and Spotify ID for each song, in the model's order. The 2019 lyrics are left out.
- `scripts/convert_2019_model.py`: makes both data files from the 2019 originals.
- `tests/`: unit tests. They stub Musixmatch and Spotify, so they need no keys.
- `deploy/`: the systemd unit, the Caddy site, and the droplet setup steps.

## Run it locally

Groover needs Python 3.12.

```bash
python3.12 -m venv venv
```

```bash
venv/bin/pip install -r requirements.txt
```

```bash
venv/bin/python -m nltk.downloader punkt_tab
```

Create a `.env` file in the repo root with these three lines, each followed by its value:

```
MUSIX_API_KEY=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

```bash
venv/bin/flask --app groover run
```

Then open http://127.0.0.1:5000.

## API keys

- **Musixmatch:** a free developer key from https://developer.musixmatch.com. The free plan returns roughly the first 30% of each song's lyrics, which is what the 2019 app used too.
- **Spotify:** the client ID and secret of an app made at https://developer.spotify.com/dashboard. Since February 2026, Development Mode apps only work while the app owner has Spotify Premium.

## Tests

```bash
venv/bin/python -m unittest discover tests
```

## What changed from 2019

- Python 3.7 to 3.12, gensim 3 to 4, NLTK's `punkt` tokenizer data to `punkt_tab`, and Heroku to a DigitalOcean droplet.
- The model and catalog load once at startup instead of on every request.
- A search always returns 20 songs. The 2019 code asked for 20 and then dropped the searched song, so a song already in the catalog got 19.
- A slash in a name, as in AC/DC, becomes a space instead of breaking the page's URL.
- Missing lyrics or no Spotify match shows the "Whoops" page instead of an error.
- Musixmatch calls use HTTPS and encode the search terms.
- `robots.txt` keeps crawlers off recommendation pages, since each one spends API quota.
- The favicon is an inline emoji, because the 2019 image link no longer loads.

## The model

The 2019 model was saved by gensim 3, and gensim 4 cannot load it directly. `scripts/convert_2019_model.py` rewrites it in gensim 4's format without retraining, so the word and song vectors are the 2019 ones. The model has 20 dimensions, a 97,547-word vocabulary, and a 5-word context window.

It rarely matches a song back to itself. In a check of 200 catalog songs run through the app's own inference, none ranked itself first, and the median song ranked itself about 13,000th of 57,581. Retraining on the same lyrics with a standard learning-rate schedule brings 191 of the 200 back first, so the weakness comes from the 2019 training run rather than the lyrics.

Each song in the catalog keeps the album art, preview, and Spotify link that Spotify returned in 2019.

## History

[Teresa Ibarra](https://github.com/teresaibarra), [Siena Guerrero](https://github.com/sienaguerrero), [Jocelyn Chen](https://github.com/jocelynyhc), [Trevor Walker](https://github.com/trevor-walker32), and [Walker Quinn](https://github.com/wsquinn) built Groover for CS121 Software Development at Harvey Mudd College in spring 2019. The original code and the team's full commit history are at [teresaibarra/groover](https://github.com/teresaibarra/groover). This repo starts fresh instead of carrying that history.

## Deploys

Every push to `main` runs the tests, then copies the app to the droplet and restarts it, through `.github/workflows/deploy.yml`. The deploy job is skipped until the repo's `DEPLOY_HOST` variable is set. [`deploy/README.md`](deploy/README.md) has the one-time droplet setup.
