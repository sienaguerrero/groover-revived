"""Retrain Groover's Doc2Vec model on the 2019 lyrics with a standard schedule.

Usage: python scripts/train_model.py SONG_DATA_JSON

SONG_DATA_JSON is data/song_data.json from teresaibarra/groover. Writes
data/d2v-retrain.model. Songs keep their 2019 positions, so
data/catalog.json lines up with both models.
"""
import json
import os
import re
import sys
from pathlib import Path

from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from nltk.tokenize import word_tokenize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS = {"dm": 1, "vector_size": 20, "window": 5, "min_count": 1, "epochs": 40}


def tokens(lyrics):
    lyrics = lyrics.strip().replace("\n", " ").lower()
    return word_tokenize(re.sub(r"[\(\[].*?[\)\]]", r"", lyrics))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        songs = json.load(f)
    documents = [TaggedDocument(tokens(song["lyrics"]), [str(i)]) for i, song in enumerate(songs)]
    model = Doc2Vec(workers=os.cpu_count(), seed=121, **SETTINGS)
    model.build_vocab(documents)
    model.train(documents, total_examples=model.corpus_count, epochs=model.epochs)
    model.save(str(DATA_DIR / "d2v-retrain.model"))
    print(f"trained {len(model.dv)} song vectors and {len(model.wv)} words")


if __name__ == "__main__":
    main()
