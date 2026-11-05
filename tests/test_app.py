import os
import unittest
from unittest import mock

from spotipy.exceptions import SpotifyException

os.environ.setdefault("MUSIX_API_KEY", "test-key")
os.environ.setdefault("SPOTIFY_CLIENT_ID", "test-id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test-secret")

from application import app
from application import recommendations

LYRICS = "we drive all night under the city lights, and the radio plays our song again"

TRACK = {"artist_name": "Test Artist", "track_name": "Test Song", "track_id": 7}
SPOTIFY_RESULT = {"tracks": {"items": [{
    "album": {"images": [{"url": "https://i.scdn.co/image/big"}, {"url": "https://i.scdn.co/image/medium"}]},
    "preview_url": None,
    "external_urls": {"spotify": "https://open.spotify.com/track/abc"},
}]}}


def musixmatch_found(method, **params):
    if method == "matcher.track.get":
        return {"header": {"status_code": 200}, "body": {"track": TRACK}}
    return {"header": {"status_code": 200},
            "body": {"lyrics": {"lyrics_body": LYRICS + "...\n\n******* This Lyrics is NOT for Commercial use *******"}}}


def musixmatch_missing(method, **params):
    return {"header": {"status_code": 404}, "body": []}


def spotify_returning(result):
    client = mock.Mock()
    client.search.return_value = result
    return mock.patch.object(recommendations, "spotify_client", return_value=client)


class LoadRecommendationsTest(unittest.TestCase):
    def test_returns_twenty_catalog_songs(self):
        rec = recommendations.Recommendation("Test Artist", "Test Song")
        rec.lyrics = LYRICS
        rec.load_recommendations()
        songs = rec.get_recommendations()
        self.assertEqual(len(songs), 20)
        self.assertTrue(all(song["name"] and song["artist"] for song in songs))

    def test_still_returns_twenty_after_dropping_the_searched_song(self):
        title = recommendations.CATALOG[0]["name"]
        ranked = [("0", 0.99)] + [(str(i), 0.5) for i in range(1, 25)]
        rec = recommendations.Recommendation("Someone", title)
        rec.lyrics = LYRICS
        with mock.patch.object(recommendations.MODELS["2019"].dv, "most_similar", return_value=ranked):
            rec.load_recommendations()
        names = [song["name"] for song in rec.get_recommendations()]
        self.assertEqual(len(names), 20)
        self.assertNotIn(title, names)

    def test_models_drop_no_word_every_time(self):
        for name, model in recommendations.MODELS.items():
            with self.subTest(model=name):
                self.assertEqual(int((model.wv.expandos["sample_int"] == 0).sum()), 0)

    def test_does_not_change_the_catalog(self):
        before = [dict(song) for song in recommendations.CATALOG[:50]]
        rec = recommendations.Recommendation("Test Artist", "Test Song")
        rec.lyrics = LYRICS
        rec.load_recommendations()
        rec.load_recommendations()
        self.assertEqual(recommendations.CATALOG[:50], before)


class FindTrackInfoTest(unittest.TestCase):
    def test_keeps_the_lyrics_before_the_free_tier_cutoff(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                spotify_returning(SPOTIFY_RESULT):
            rec = recommendations.Recommendation("test artist", "test song")
            self.assertTrue(rec.find_track_info())
        self.assertEqual(rec.get_lyrics(), LYRICS)
        self.assertEqual(rec.get_song_title(), "Test Song")
        self.assertEqual(rec.get_album_image_url(), "https://i.scdn.co/image/medium")
        self.assertEqual(rec.get_spotify_url(), "https://open.spotify.com/track/abc")

    def test_works_without_spotify_keys(self):
        without_spotify = {k: v for k, v in os.environ.items() if not k.startswith("SPOTIFY_")}
        with mock.patch.dict(os.environ, without_spotify, clear=True), \
                mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                mock.patch.object(recommendations, "spotify_client", side_effect=AssertionError("called")):
            rec = recommendations.Recommendation("test artist", "test song")
            self.assertTrue(rec.find_track_info())
        self.assertEqual(rec.get_lyrics(), LYRICS)
        self.assertIsNone(rec.get_album_image_url())

    def test_no_spotify_match_keeps_the_song_without_art(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                spotify_returning({"tracks": {"items": []}}):
            rec = recommendations.Recommendation("a", "b")
            self.assertTrue(rec.find_track_info())
        self.assertIsNone(rec.get_album_image_url())

    def test_spotify_error_keeps_the_song_without_art(self):
        client = mock.Mock()
        client.search.side_effect = SpotifyException(403, -1, "Active premium subscription required for the owner of the app.")
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                mock.patch.object(recommendations, "spotify_client", return_value=client):
            rec = recommendations.Recommendation("a", "b")
            self.assertTrue(rec.find_track_info())
        self.assertEqual(rec.get_lyrics(), LYRICS)
        self.assertIsNone(rec.get_album_image_url())

    def test_sends_search_terms_as_encoded_query_parameters(self):
        response = mock.Mock()
        response.json.return_value = {"message": {"header": {"status_code": 404}, "body": []}}
        with mock.patch.object(recommendations.requests, "get", return_value=response) as get:
            recommendations.Recommendation("Simon & Garfunkel", "The Boxer").find_track_info()
        url, = get.call_args.args
        params = get.call_args.kwargs["params"]
        self.assertEqual(url, "https://api.musixmatch.com/ws/1.1/matcher.track.get")
        self.assertEqual(params["q_artist"], "Simon & Garfunkel")
        self.assertEqual(params["apikey"], "test-key")


class FindTrackTest(unittest.TestCase):
    def setUp(self):
        recommendations.lookup_track.cache_clear()

    def test_reuses_a_track_it_already_found(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found) as api, \
                spotify_returning(SPOTIFY_RESULT):
            first = recommendations.find_track("Test Artist", "Test Song")
            second = recommendations.find_track("Test Artist", "Test Song")
        self.assertEqual(api.call_count, 2)
        self.assertIsNot(first, second)
        self.assertEqual(second.get_lyrics(), LYRICS)

    def test_looks_again_for_a_track_it_did_not_find(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_missing) as api:
            self.assertIsNone(recommendations.find_track("Nobody", "Nothing"))
            self.assertIsNone(recommendations.find_track("Nobody", "Nothing"))
        self.assertEqual(api.call_count, 2)


class RoutesTest(unittest.TestCase):
    def setUp(self):
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        recommendations.lookup_track.cache_clear()

    def test_second_view_of_a_song_spends_no_api_calls(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found) as api, \
                spotify_returning(SPOTIFY_RESULT):
            self.client.get("/recommendations/Test Artist/Test Song")
            page = self.client.get("/recommendations/Test Artist/Test Song")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(api.call_count, 2)

    def test_lookup_page_renders(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Enter song title", page.data)

    def test_slash_in_artist_becomes_a_space(self):
        page = self.client.post("/", data={"artist": "AC/DC", "title": "Back in Black"})
        self.assertEqual(page.status_code, 302)
        self.assertEqual(page.headers["Location"], "/recommendations/AC%20DC/Back%20in%20Black")

    def test_recommendations_page_shows_twenty_songs(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                spotify_returning(SPOTIFY_RESULT):
            page = self.client.get("/recommendations/Test Artist/Test Song")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data.count(b'<div class="recs">'), 20)

    def test_page_without_spotify_leaves_out_the_album_art(self):
        without_spotify = {k: v for k, v in os.environ.items() if not k.startswith("SPOTIFY_")}
        with mock.patch.dict(os.environ, without_spotify, clear=True), \
                mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found):
            page = self.client.get("/recommendations/Test Artist/Test Song")
        self.assertEqual(page.data.count(b'<div class="recs">'), 20)
        self.assertNotIn(b"req-album", page.data)
        self.assertNotIn(b'src="None"', page.data)

    def test_default_page_offers_the_retrain(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                spotify_returning(SPOTIFY_RESULT):
            page = self.client.get("/recommendations/Test Artist/Test Song")
        self.assertIn(b"Picked by our 2019 model", page.data)
        self.assertIn(b'href="/recommendations/Test%20Artist/Test%20Song?model=2026"', page.data)

    def test_retrain_page_uses_the_retrained_model_and_links_back(self):
        retrained = recommendations.MODELS["2026"].dv
        ranked = [(str(i), 0.5) for i in range(21)]
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                spotify_returning(SPOTIFY_RESULT), \
                mock.patch.object(retrained, "most_similar", return_value=ranked) as most_similar:
            page = self.client.get("/recommendations/Test Artist/Test Song?model=2026")
        most_similar.assert_called_once()
        self.assertEqual(page.data.count(b'<div class="recs">'), 20)
        self.assertIn(b"Picked by a 2026 retrain", page.data)
        self.assertIn(b'href="/recommendations/Test%20Artist/Test%20Song"', page.data)

    def test_unknown_model_falls_back_to_2019(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found), \
                spotify_returning(SPOTIFY_RESULT):
            page = self.client.get("/recommendations/Test Artist/Test Song?model=1999")
        self.assertIn(b"Picked by our 2019 model", page.data)

    def test_switching_models_spends_no_api_calls(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_found) as api, \
                spotify_returning(SPOTIFY_RESULT):
            self.client.get("/recommendations/Test Artist/Test Song")
            page = self.client.get("/recommendations/Test Artist/Test Song?model=2026")
        self.assertIn(b"Picked by a 2026 retrain", page.data)
        self.assertEqual(api.call_count, 2)

    def test_unknown_song_shows_whoops(self):
        with mock.patch.object(recommendations, "musixmatch", side_effect=musixmatch_missing):
            page = self.client.get("/recommendations/Nobody/Nothing")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"we did not find the track", page.data)

    def test_robots_keeps_crawlers_off_recommendations(self):
        page = self.client.get("/robots.txt")
        self.assertIn(b"Disallow: /recommendations/", page.data)


if __name__ == "__main__":
    unittest.main()
