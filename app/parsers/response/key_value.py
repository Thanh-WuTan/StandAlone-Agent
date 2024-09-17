from objects.fact import *
from objects.relationship import *
from objects.base_parser import *


class Parser(BaseParser):
    """
    Expects info to be given in the following format:
    ** source>target
    where source is the key and target is the value.

    Saves the following relationship
    - source: filepath
      edge: <has_hash>  -> this can be named anything
      target: hash
    """

    def parse(self, blob):
        relationships = []
        for match in self.line(blob.strip()):
            for mp in self.mappers:
                strings = match.split('>')
                source = strings[0].strip()
                target = strings[1].strip()
                relationships.append(
                    Relationship(source=Fact(mp.source, source),
                                 edge=mp.edge,
                                 target=Fact(mp.target, target))
                )
        return relationships
