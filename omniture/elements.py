# encoding: utf-8

import utils
from copy import copy


class Value(object):
    def __init__(self, title, id, parent, extra={}):
        self.title = title
        self.id = id
        self.parent = parent
        self.properties = {'id': id}

        for k, v in extra.items():
            setattr(self, k, v)

    @classmethod
    def list(cls, name, items, parent, title='title', id='id'):
        values = [cls(item[title], item[id], parent, item) for item in items]
        return utils.AddressableList(values, name)

    def __repr__(self):
        return "<{title}: {id} in {parent}>".format(**self.__dict__)

    def copy(self):
        value = self.__class__(self.title, self.id, self.parent)
        value.properties = copy(self.properties)
        return value

    def serialize(self):
        return self.properties

    def __str__(self):
        return self.title


class Element(Value):
    def range(self, *vargs):
        l = len(vargs)
        if l == 1:
            start = 0
            stop = vargs[0]
        elif l == 2:
            start, stop = vargs

        top = stop - start

        element = self.copy()
        element.properties['startingWith'] = str(start)
        element.properties['top'] = str(top)

        return element

    def search(self, keywords, type='AND'):
        type = type.upper()

        types = ['AND', 'OR', 'NOT']
        if type not in types:
            raise ValueError("Search type should be one of: " + ", ".join(types))

        element = self.copy()
        element.properties['search'] = {
            'type': type, 
            'keywords': utils.wrap(keywords), 
        }
        return element

    def select(self, keys):
        element = self.copy()
        element.properties['selected'] = utils.wrap(keys)
        return element


class Segment(Element):
    pass

