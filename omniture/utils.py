import copy
import datetime
from dateutil.parser import parse as parse_date

class memoize:
  def __init__(self, function):
    self.function = function
    self.memoized = {}

  def __call__(self, *args):
    try:
      return self.memoized[args]
    except KeyError:
      self.memoized[args] = self.function(*args)
      return self.memoized[args]


class AddressableList(list):
    def __init__(self, items, name='items'):
        super(AddressableList, self).__init__(items)
        self.name = name

    def __getitem__(self, key):
        if isinstance(key, int):
            return super(AddressableList, self).__getitem__(key)
        else:
            matches = [item for item in self if item.title == key or item.id == key]
            count = len(matches)
            if count > 1:
                matches = map(repr, matches)
                error = "Found multiple matches for {key}: {matches}. ".format(
                    key=key, matches=", ".join(matches))
                advice = "Use the identifier instead."
                raise KeyError(error + advice)
            elif count == 1:
                return matches[0]
            else:
                raise KeyError("Cannot find {key} among the available {name}".format(
                    key=key, name=self.name))


class AddressableDict(AddressableList):
    def __getitem__(self, key):
        item = super(AddressableDict, self).__getitem__(key)
        return item.value


def date(obj):
    if obj is None:
        return None
    elif isinstance(obj, datetime.date):
        if hasattr(dt, 'date'):
            return obj.date()
        else:
            return obj
    elif isinstance(obj, basestring):
        return parse_date(obj).date()
    else:
        raise ValueError("Can only convert strings into dates, received {}".format(obj.__class__))


def wrap(obj):
    if isinstance(obj, list):
        return obj
    else:
        return [obj]


def affix(prefix, base, suffix, connector='_'):
    if prefix:
        prefix = prefix + connector
    else:
        prefix = ''

    if suffix:
        suffix = connector + suffix
    else:
        suffix = ''

    return prefix + base + suffix


def translate(d, mapping):
    d = copy.copy(d)

    for src, dest in mapping.items():
        if src in d:
            d[dest] = d[src]
            del d[src]

    return d