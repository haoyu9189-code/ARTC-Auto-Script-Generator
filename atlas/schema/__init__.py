import json
import os

import jsonschema

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_schema(which):
    """which: 'cell-graph' | 'implicit'"""
    fname = {'cell-graph': 'atlas-cell-graph-1.0.json',
             'implicit': 'atlas-implicit-1.0.json'}[which]
    with open(os.path.join(_HERE, fname), encoding='utf-8') as f:
        return json.load(f)


def validate_graph(doc):
    jsonschema.validate(doc, load_schema('cell-graph'))


def validate_implicit(doc):
    jsonschema.validate(doc, load_schema('implicit'))


from .seeds import seed_graph, SEEDS_DIR  # noqa: E402

__all__ = ['load_schema', 'validate_graph', 'validate_implicit',
           'seed_graph', 'SEEDS_DIR']
