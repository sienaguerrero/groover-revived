"""
This file handles the input from routes and generates the
recommendations using the API calls to musixmatch and spotipy
"""
import json
import os
import re
from functools import cache
from pathlib import Path

import requests
import spotipy
from gensim.models.doc2vec import Doc2Vec
from nltk.tokenize import word_tokenize
from spotipy.oauth2 import SpotifyClientCredentials

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MUSIXMATCH_API = "https://api.musixmatch.com/ws/1.1/"
RECOMMENDATION_COUNT = 20
DEFAULT_MODEL = "2019"

MODELS = {
    "2019": Doc2Vec.load(str(DATA_DIR / "d2v.model")),
}
with open(DATA_DIR / "catalog.json") as catalog_file:
    CATALOG = json.load(catalog_file)


@cache
def spotify_client():
    credentials = SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"))
    return spotipy.Spotify(client_credentials_manager=credentials, requests_timeout=10)


def musixmatch(method, **params):
    params["apikey"] = os.getenv("MUSIX_API_KEY")
    response = requests.get(MUSIXMATCH_API + method, params=params, timeout=10)
    return response.json()["message"]


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

    # Retrieve song info from Musixmatch and Spotify
    def find_track_info(self):
        """
        matches the song on Musixmatch, then loads its lyrics,
        then finds its album art and link on Spotify.
        """
        matched = musixmatch("matcher.track.get", q_track=self.get_song_title(),
                             q_artist=self.get_artist())
        if matched["header"]["status_code"] != 200:
            print('Track not found.')
            return False

        #Get initial Musixmatch information
        track = matched["body"]["track"]
        self.artist = track["artist_name"]
        self.title = track["track_name"]
        self.track_id = track["track_id"]

        #Make another API call for the lyrics
        lyrical = musixmatch("track.lyrics.get", track_id=self.get_track_id())
        if lyrical["header"]["status_code"] != 200:
            print('Lyrics not found.')
            return False
        self.lyrics = lyrical["body"]["lyrics"]["lyrics_body"].split("...")[0]
        if not self.lyrics.strip():
            print('Lyrics not found.')
            return False

        #Get album art and a preview url from Spotify
        results = spotify_client().search(q='track:' + self.get_song_title() +
                                          ' artist:' + self.get_artist(), type='track')
        items = results['tracks']['items']
        if not items:
            print('Track not found.')
            return False
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
                                               topn=RECOMMENDATION_COUNT + 1)
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
        spotify and musixmatch
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
