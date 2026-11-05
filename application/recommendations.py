"""
This file handles the input from routes and generates the
recommendations using the API calls to lrclib and spotipy
"""
import copy
import json
import os
import re
from functools import cache, lru_cache
from pathlib import Path

import requests
import spotipy
from gensim.models.doc2vec import Doc2Vec
from nltk.tokenize import word_tokenize
from spotipy.exceptions import SpotifyBaseException
from spotipy.oauth2 import SpotifyClientCredentials

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LRCLIB_SEARCH = "https://lrclib.net/api/search"
USER_AGENT = "Groover 2026 (https://groover.siena.codes)"
RECOMMENDATION_COUNT = 20
DEFAULT_MODEL = "2019"
RETRAINED_MODEL = "2026"

MODELS = {
    DEFAULT_MODEL: Doc2Vec.load(str(DATA_DIR / "d2v.model")),
    RETRAINED_MODEL: Doc2Vec.load(str(DATA_DIR / "d2v-retrain.model")),
}
with open(DATA_DIR / "catalog.json") as catalog_file:
    CATALOG = json.load(catalog_file)


@cache
def spotify_client():
    credentials = SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"))
    return spotipy.Spotify(client_credentials_manager=credentials, requests_timeout=10)


def lrclib_search(title, artist):
    response = requests.get(LRCLIB_SEARCH, params={"track_name": title, "artist_name": artist},
                            headers={"User-Agent": USER_AGENT}, timeout=10)
    if response.status_code != 200:
        print('LRCLIB search failed:', response.status_code)
        return []
    return response.json()


def match_key(text):
    return re.sub(r"[^0-9a-z]", "", text.casefold())


def best_match(records, title, artist):
    with_lyrics = [record for record in records if record.get("plainLyrics")]
    same_title = [record for record in with_lyrics if match_key(record["trackName"]) == match_key(title)]
    same_both = [record for record in same_title if match_key(record["artistName"]) == match_key(artist)]
    return (same_both or same_title or with_lyrics or [None])[0]


# Recommendation Generator
class Recommendation:
    """
    The recommendation class will initialize the song display
    to be used on the recommendation page
    """
    def __init__(self, artist, title):
        self.artist = artist
        self.title = title
        self.track_id = None
        self.lyrics = None
        self.album_image_url = None
        self.preview_url = None
        self.recommendations = None
        self.spotify_url = None

    # Retrieve song info from LRCLIB and Spotify
    def find_track_info(self):
        """
        finds the song and its lyrics on LRCLIB, then finds
        its album art and link on Spotify if it's set up.
        """
        records = lrclib_search(self.get_song_title(), self.get_artist())
        match = best_match(records, self.get_song_title(), self.get_artist())
        if match is None:
            print('Track not found.')
            return False

        #Get the song's name and lyrics from LRCLIB
        self.artist = match["artistName"]
        self.title = match["trackName"]
        self.track_id = match["id"]
        self.lyrics = match["plainLyrics"]

        #Get album art and a preview url from Spotify
        if not (os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET")):
            return True
        try:
            results = spotify_client().search(q='track:' + self.get_song_title() +
                                              ' artist:' + self.get_artist(), type='track')
        except (SpotifyBaseException, requests.RequestException) as error:
            print('Spotify search failed:', error)
            return True
        items = results['tracks']['items']
        if items:
            track = items[0]
            images = track["album"]["images"]
            if images:
                self.album_image_url = images[min(1, len(images) - 1)]["url"]
            self.preview_url = track["preview_url"]
            self.spotify_url = track['external_urls']['spotify']
        return True


    # Determine song recommendations using model
    def load_recommendations(self, model_name=DEFAULT_MODEL):
        """
        clean the input so it works with our model (lowercase, etc)
        use doc to vec which returns indices in the database that
        we will use to list recommendations.
        """
        #Clean lyrics for analysis
        lyrics = self.get_lyrics().strip().replace('\n', ' ').lower()
        lyrics = re.sub(r"[\(\[].*?[\)\]]", r"", lyrics)

        #Get most similar lyrics
        model = MODELS[model_name]
        test_data = word_tokenize(lyrics)
        vector_1 = model.infer_vector(test_data, alpha=0.025, min_alpha=0.001, epochs=55)

        list_of_tuples = model.dv.most_similar(positive=[vector_1],
                                               topn=RECOMMENDATION_COUNT * 2)
        recommendations = []

        #Store generated song recommendations from model
        for ranking_tuple in list_of_tuples:
            song = dict(CATALOG[int(ranking_tuple[0])])
            song['genres'] = [g.title() for g in song['genres']]
            if song['name'] != self.get_song_title():
                recommendations.append(song)

        self.recommendations = recommendations[:RECOMMENDATION_COUNT]
        return True


    def get_artist(self):
        """
        helper function to return artist name
        """
        return self.artist

    def get_song_title(self):
        """
        helper function to return song name
        """
        return self.title

    def get_track_id(self):
        """
        helper function to return track id so
        we could find it using the API for
        spotify and lrclib
        """
        return self.track_id

    def get_lyrics(self):
        """
        helper function to return 1/3 of the
        song lyrics
        """
        return self.lyrics

    def get_album_image_url(self):
        """
        helper function to return album art
        associated with song
        """
        return self.album_image_url

    def get_preview_url(self):
        """
        helper function to return preview url
        so user can see song on rec page
        """
        return self.preview_url

    def get_spotify_url(self):
        """
        helper function to return url so
        user can visit song on spotify
        """
        return self.spotify_url

    def get_recommendations(self):
        """
        helper function to return
        recommendations using our
        model
        """
        return self.recommendations


# Raising instead of returning None keeps failures, like a spent daily quota, out of the cache.
@lru_cache(maxsize=256)
def lookup_track(artist, title):
    rec = Recommendation(artist, title)
    if not rec.find_track_info():
        raise LookupError(f"{title} by {artist} not found")
    return rec


def find_track(artist, title):
    try:
        return copy.copy(lookup_track(artist, title))
    except LookupError:
        return None
