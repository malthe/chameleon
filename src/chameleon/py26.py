def lookup_attr(obj, key):
    try:
        return getattr(obj, key)
    except AttributeError as exc:
        try:
            get = obj.__getitem__
        except AttributeError:
            raise exc
        try:
            return get(key)
        except KeyError:
            raise exc
