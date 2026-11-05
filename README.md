# Groover 🎵

Song recommendations from lyrics. Groover started as a spring 2019 Harvey Mudd CS121 team project and was revived in 2026 to run on current Python. Hosted at https://groover.siena.codes.

Type a song and its artist. Groover gets the lyrics from [LRCLIB](https://lrclib.net), a free and open lyrics database, turns them into a vector with a Doc2Vec model trained on the lyrics of 57,581 songs, and shows the 20 songs whose vectors point the most nearly the same way. Each one comes with the album art, 30-second preview, and Spotify link saved when the model was trained.

## What's here

- `application/`: the Flask app. `recommendations.py` calls LRCLIB and Spotify and ranks songs with the model.
- `data/d2v.model`: the 2019 model, converted to gensim 4's format.
- `data/d2v-retrain.model`: the same lyrics retrained in 2026 with a standard learning-rate schedule.
- `data/catalog.json`: name, artist, genres, album art, preview, and Spotify ID for each song, in the models' order. The 2019 lyrics are left out.
- `scripts/convert_2019_model.py`: makes `d2v.model` and `catalog.json` from the 2019 originals.
- `scripts/train_model.py`: makes `d2v-retrain.model` from the 2019 lyrics.
- `tests/`: unit tests. They stub LRCLIB and Spotify, so they need no network or keys.
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

```bash
venv/bin/flask --app groover run
```

Then open http://127.0.0.1:5000.

## Lyrics and album art

- **Lyrics:** no key needed. Groover searches [LRCLIB](https://lrclib.net), which is free and asks clients to name themselves in the `User-Agent` header. Its lyrics come from its users, not from publishers. Groover only uses them in memory to find a song's vector, and never shows or stores them.
- **Album art, optional:** Spotify supplies the searched song's album art. To turn it on, create a `.env` file in the repo root with the client ID and secret of an app made at https://developer.spotify.com/dashboard. Since February 2026, Development Mode apps only work while the app owner has Spotify Premium. Without Spotify, or when it fails, the page shows the 20 recommendations without that one image, since their art comes from the catalog.

```
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

## Tests

```bash
venv/bin/python -m unittest discover tests
```

## What changed from 2019

- Python 3.7 to 3.12, gensim 3 to 4, NLTK's `punkt` tokenizer data to `punkt_tab`, and Heroku to a DigitalOcean droplet.
- The model and catalog load once at startup instead of on every request.
- A search always returns 20 songs. The 2019 code asked for 20 and then dropped every song with the searched title, so a song already in the catalog got 19 or fewer.
- A slash in a name, as in AC/DC, becomes a space instead of breaking the page's URL.
- Missing lyrics shows the "Whoops" page instead of an error.
- Spotify is optional. A Spotify error or a song Spotify can't find no longer blocks the recommendations.
- Lyrics come from LRCLIB instead of Musixmatch, whose API now costs money. LRCLIB returns full lyrics, where Musixmatch's free tier returned about the first 30%.
- `robots.txt` keeps crawlers off recommendation pages, since each one spends API quota.
- The favicon is an inline emoji, because the 2019 image link no longer loads.

## The model

The 2019 model was saved by gensim 3, and gensim 4 cannot load it directly. `scripts/convert_2019_model.py` rewrites it in gensim 4's format without retraining, so the word and song vectors are the 2019 ones. The model has 20 dimensions, a 97,547-word vocabulary, and a 5-word context window.

gensim 3 stores a word's "always keep" downsampling threshold as `2**32`, and gensim 4's upgrade code casts it to a 32-bit integer, where it wraps to 0. Left alone, that makes search drop 97,478 of the 97,547 words every time. The script caps the threshold at `2**32 - 1` first. With that fix, 152 of 200 sampled catalog songs come back as their own top match when searched with their full lyrics, and 190 land in their own top 20.

Each song in the catalog keeps the album art, preview, and Spotify link that Spotify returned in 2019.

The results page also links to the same search run through a retrained model, at `?model=2026`. It uses the same lyrics, song order, 20 dimensions, and 5-word window as 2019, trained in one call so the learning rate slides from 0.025 to 0.0001 across 40 passes. The 2019 loop called training 50 times, and after the first call it held the rate at 0.0152 or higher. Searched with their full lyrics, which is what LRCLIB returns, 191 of the 200 sampled songs come back first from the retrain, against 152 from the 2019 model. Switching models reuses the song's lyrics and art, so it spends no extra API calls.

## History

[Teresa Ibarra](https://github.com/teresaibarra), [Siena Guerrero](https://github.com/sienaguerrero), [Jocelyn Chen](https://github.com/jocelynyhc), [Trevor Walker](https://github.com/trevor-walker32), and [Walker Quinn](https://github.com/wsquinn) built Groover for CS121 Software Development at Harvey Mudd College in spring 2019. The original code and the team's full commit history are at [teresaibarra/groover](https://github.com/teresaibarra/groover). This repo starts fresh instead of carrying that history.

## Deploys

Every push to `main` runs the tests, then copies the app to the droplet and restarts it, through `.github/workflows/deploy.yml`. The deploy job is skipped until the repo's `DEPLOY_HOST` variable is set. [`deploy/README.md`](deploy/README.md) has the one-time droplet setup.
