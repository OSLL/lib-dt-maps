import os
from abc import abstractmethod, ABC

from types import SimpleNamespace
from typing import TextIO, Iterator, Tuple, Union, Generic, TypeVar, Dict, Optional, Any, Iterable

from dt_maps.exceptions import EntityNotFound, FieldNotFound
from dt_maps.types.commons import EntityHelper


class MapAsset:
    """
    Class representing a map asset.

    Args:
        fpath (:obj:`str`):     path to the asset
    """

    def __init__(self, fpath: str):
        self._fpath = fpath

    @property
    def fpath(self) -> str:
        """
        File path to the asset
        """
        return self._fpath

    def exists(self) -> bool:
        """
        Whether the asset exists on disk
        """
        return os.path.isfile(self._fpath)

    def read(self, mode: str) -> Union[str, bytes]:
        """
        Read the asset file content from disk.

        Args:
            mode (:obj:`str`):     reading mode as in :py:meth:`open`

        Returns:
            :obj:`str,bytes`:      asset file content
        """
        with open(self._fpath, mode) as fin:
            return fin.read()

    def write(self, mode: str, data: Union[str, bytes]):
        """
        Writes the content of ``data`` to the asset file on disk.

        Args:
            mode (:obj:`str`):          write mode as in :py:meth:`open`
            data (:obj:`str,bytes`):    asset content to write to disk
        """
        self._make_dirs()
        with open(self._fpath, mode) as fout:
            return fout.write(data)

    def open(self, mode: str) -> TextIO:
        """
        Wrapper around :py:meth:`open` used to open the file.

        Args:
            mode (:obj:`str`):   mode as in :py:meth:`open`
        """
        self._make_dirs()
        return open(self._fpath, mode)

    def _make_dirs(self):
        """
        Make directories up to the asset location.
        """
        os.makedirs(os.path.dirname(self._fpath), exist_ok=True)


ET = TypeVar("ET", bound=EntityHelper)


class MapLayer(Dict[str, ET], Generic[ET]):
    """
    Class representing a map layer.
    It is a subclass of :py:class:`dict`.

    A layer ``X`` accessed on a map ``map`` using the
    syntax ``map.layers.X`` is an object instance of this class.

    Use the ``[]`` operator to access a layer, the same way you would access
    a dictionary. For example, the frame with key ``frame_0`` can be accessed
    using the following code,

    .. code-block:: python

        map.layers.frames["frame_0"]
    """

    def __init__(self, m, name: str, *args, **kwargs):
        self._map = m
        self._name: str = name
        self._ET: Optional[type(ET)] = None
        self._cache: Dict[str, ET] = {}
        super(MapLayer, self).__init__(*args, **kwargs)

    def _get_raw(self, key: str) -> dict:
        # get item from underlying dictionary
        try:
            return super(MapLayer, self).__getitem__(key)
        except KeyError:
            raise EntityNotFound(self._name, key=key)

    def __getitem__(self, key: str) -> ET:
        # check cached
        if key in self._cache:
            return self._cache[key]
        # get item from underlying dictionary
        item = self._get_raw(key)
        # turn 'dict' into 'T'
        if self._ET:
            wrapped = self._ET.create(self._map, key)
        else:
            wrapped = item
        # cache and return
        self._cache[key] = wrapped
        return wrapped

    def read(self, key: str, field_path: Union[str, Iterable[str]]):
        field_path = field_path if isinstance(field_path, (list, tuple)) else [field_path]
        value = self._get_raw(key)
        for field in field_path:
            try:
                value = value[field]
            except KeyError:
                raise FieldNotFound(key, self._name, '.'.join(field_path))
        return value

    def write(self, key: str, field_path: Union[str, Iterable[str]], value: Any):
        field_path = field_path if isinstance(field_path, (list, tuple)) else [field_path]
        field_parent = self.read(key, field_path[:-1])
        field_parent[field_path[-1]] = value

    def register_entity_helper(self, entity_type: type(ET)):
        """
        Instruct the map layer to wrap entities with the given type.
        For example, we use the class :py:class:`dt_maps.types.frames.Frame` to wrap the
        entities in the 'frames' layer. This makes it easier to use frames by allowing us
        to do,

        .. code-block:: python

            map.layers.frames["frame_0"].pose.x = 12.0


        instead of,

        .. code-block:: python

            map.layers.frames["frame_0"]["pose"]["x"] = 12.0

        Args:
            entity_type (:obj:`type`):  class to use to wrap entities in this layer
        """
        self._ET = entity_type

    def get(self, key: str) -> Optional[ET]:
        return self.__getitem__(key)

    def get(self, key: str, default: Any) -> Optional[ET]:
        try:
            return self.__getitem__(key)
        except (KeyError, EntityNotFound):
            return default

    def as_raw_dict(self):
        """
        Raw representation of the map layer as a Python dictionary.

        Return:
            :obj:`dict`     raw dictionary representing the layer
        """
        return dict(self)


class MapLayerNamespace(SimpleNamespace):

    def __init__(self, *args, **kwargs):
        super(MapLayerNamespace, self).__init__(*args, **kwargs)

    def get(self, name: str) -> MapLayer:
        return self.__dict__.get(name)

    def has(self, name: str) -> bool:
        return self.__dict__.get(name, None) is not None

    def items(self) -> Iterator[Tuple[str, MapLayer]]:
        return iter([(k, v) for k, v in self.__dict__.items()])

    # known layers ==>

    @property
    def frames(self) -> MapLayer[str]:
        return self.__getitem__("frames")

    @property
    def tile_maps(self) -> MapLayer[str]:
        return self.__getitem__("tile_maps")

    @property
    def tiles(self) -> MapLayer[str]:
        return self.__getitem__("tiles")

    # known layers <==

    def __getitem__(self, layer: str) -> MapLayer:
        if layer in self.__dict__:
            return self.__dict__[layer]
        raise KeyError(f"Map has no layer '{layer}'")

    def __iter__(self) -> Iterator[str]:
        return iter(self.__dict__.keys())

    def __len__(self) -> int:
        return len(self.__dict__)
