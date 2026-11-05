"""Convert the 2019 Groover model and catalog for gensim 4.

Usage: python scripts/convert_2019_model.py OLD_D2V_MODEL OLD_SONG_DATA_JSON

Reads the files from teresaibarra/groover's data/ folder and writes
data/d2v.model and data/catalog.json. The catalog keeps only the
fields the recommendations page shows, in the model's tag order.
"""
import json
import pickle
import sys
from collections import namedtuple
from pathlib import Path

from gensim import utils
from gensim.models.doc2vec import Doc2Vec

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_FIELDS = ("name", "artist", "genres", "image_url", "preview_url", "spotify_id")

OldDoctag = namedtuple("OldDoctag", "offset word_count doc_count")


class Unpickler(pickle.Unpickler):
    # gensim 4's Doctag has different slots, so unpickling the 2019 tuples into it drops every offset.
    def find_class(self, module, name):
        if (module, name) == ("gensim.models.doc2vec", "Doctag"):
            return OldDoctag
        return super().find_class(module, name)


def convert_model(src, dst):
    with open(src, "rb") as f:
        model = Unpickler(f, encoding="latin1").load()

    state = model.__dict__
    dv = state.pop("docvecs")
    state["dv"] = dv
    state["__recursive_saveloads"] = ["dv" if a == "docvecs" else a for a in state["__recursive_saveloads"]]

    old = dv.__dict__
    doctags = old.pop("doctags")
    offset2doctag = old.pop("offset2doctag")
    max_rawint = old.pop("max_rawint")
    old["vectors"] = old.pop("vectors_docs")
    old.pop("count", None)
    old["key_to_index"] = {tag: doctag.offset + max_rawint + 1 for tag, doctag in doctags.items()}
    old["index_to_key"] = (list(range(max_rawint + 1)) if max_rawint > -1 else []) + list(offset2doctag)
    old.setdefault("expandos", {})

    compress, subname = utils.SaveLoad._adapt_by_suffix(src)
    model._load_specials(src, None, compress, subname)
    for tag, doctag in doctags.items():
        dv.set_vecattr(tag, "word_count", doctag.word_count)
        dv.set_vecattr(tag, "doc_count", doctag.doc_count)

    model.save(str(dst))
    return Doc2Vec.load(str(dst))


def convert_catalog(src, dst, size):
    with open(src) as f:
        songs = json.load(f)
    if len(songs) != size:
        sys.exit(f"{src} has {len(songs)} songs but the model has {size} tags")
    catalog = [{field: song.get(field) for field in CATALOG_FIELDS} for song in songs]
    for song in catalog:
        song["genres"] = song["genres"] or []
    with open(dst, "w") as f:
        json.dump(catalog, f, separators=(",", ":"))
    return catalog


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    model = convert_model(sys.argv[1], DATA_DIR / "d2v.model")
    if model.dv.index_to_key != [str(i) for i in range(len(model.dv))]:
        sys.exit("model tags are not 0..N-1 in order, so catalog positions would not line up")
    catalog = convert_catalog(sys.argv[2], DATA_DIR / "catalog.json", len(model.dv))
    print(f"wrote {len(model.dv)} song vectors, {len(model.wv)} words, {len(catalog)} catalog entries")


if __name__ == "__main__":
    main()
