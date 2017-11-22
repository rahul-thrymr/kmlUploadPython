from __future__ import absolute_import

import json
import os
import uuid
import base64

import six
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from .mplexporter.exporter import Exporter
from jinja2 import Environment, PackageLoader
from shapely.geometry import mapping, shape
from .leaflet_renderer import LeafletRenderer
from .links import JavascriptLink, CssLink
from . import maptiles

# We download explicitly the CSS and the JS.
_leaflet_js = JavascriptLink('https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.js')
_leaflet_css = CssLink('https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet.css')
_attribution = '<a href="https://github.com/jwass/mplleaflet">mplleaflet</a>'

env = Environment(loader=PackageLoader('mplleaflet', 'templates'),
                  trim_blocks=True, lstrip_blocks=True)


def dict_to_geopanda(dc):
    df = pd.DataFrame.from_dict(dc["features"])
    point_df = pd.DataFrame(columns=list(df))
    lines_df = pd.DataFrame(columns=list(df))
    poly_df = pd.DataFrame(columns=list(df))
    
    pnc,lnc,plc =0,0,0
    
    for i,r in df.iterrows():
        if len(r.geometry["coordinates"]) == 1:
            if r.geometry["type"] == "LineString":
                if len(r.geometry["coordinates"][0]) == 1:
                    r.geometry["type"] = "Point"
                    poly_df.set_value(plc,"geometry",shape(r.geometry))
                    poly_df.set_value(plc,"properties",r.properties)
                    poly_df.set_value(plc,"type",plc)
                    poly_df.set_value(plc,"id",i)
                    plc= plc + 1                     
            else:
                if r.geometry["type"] == "Point":
                    pass
                else:
                    poly_df.set_value(plc,"geometry",shape(r.geometry))
                    poly_df.set_value(plc,"properties",r.properties)
                    poly_df.set_value(plc,"type",plc)
                    poly_df.set_value(plc,"id",i)
                    plc= plc + 1 
          
        elif len(r.geometry["coordinates"]) == 2:
            if type(r.geometry["coordinates"][0]) != list:
                if r.geometry["type"] == "LineString":
                    pass
                else:
                    point_df.set_value(pnc,"geometry",shape(r.geometry))
                    point_df.set_value(pnc,"properties",r.properties)
                    point_df.set_value(pnc,"type",pnc)
                    point_df.set_value(pnc,"id",i)
                    pnc= pnc + 1 

                
    crs = {'init': 'epsg:4326'}
    pl_gdf = gpd.GeoDataFrame(poly_df, crs=crs,geometry=poly_df["geometry"])
    pn_gdf = gpd.GeoDataFrame(point_df, crs=crs,geometry=point_df["geometry"])
    
    return pn_gdf, pl_gdf
        
def buff_points(indf):
    ingdf = indf.copy()
    for i, g in ingdf.iterrows():
        ingdf.set_value(i,"geometry",g.geometry.buffer(+0.000001))
    return ingdf



def fig_to_html(fig=None, template='base_kml.html', tiles=None, crs=None,
                epsg=None, otherjson="",embed_links=False, od=None):
    """
    Convert a Matplotlib Figure to a Leaflet map

    Parameters
    ----------
    fig : figure, default gcf()
        Figure used to convert to map
    template : string, default 'base.html'
        The Jinja2 template to use
    tiles : string or tuple
        The tiles argument is used to control the map tile source in the
        Leaflet map. Several simple shortcuts exist: 'osm', 'mapquest open',
        and 'mapbox bright' may be specified to use those tiles.

        The argument may be a tuple of two elements. The first element is the
        tile URL to use in the map's TileLayer, the second argument is the
        attribution to display.  See
        http://leafletjs.com/reference.html#tilelayer for more information on
        formatting the URL.

        See also maptiles.mapbox() for specifying Mapbox tiles based on a
        Mapbox map ID.
    crs : dict, default assumes lon/lat
        pyproj definition of the current figure. If None, then it is assumed
        the plot is longitude, latitude in X, Y.
    epsg : int, default 4326
        The EPSG code of the current plot. This can be used in place of the
        'crs' parameter.
    embed_links : bool, default False
        Whether external links (except tiles) shall be explicitly embedded in
        the final html.

    Note: only one of 'crs' or 'epsg' may be specified. Both may be None, in
    which case the plot is assumed to be longitude / latitude.

    Returns
    -------
    String of html of the resulting webpage

    """
    if tiles is None:
        tiles = maptiles.osm
    elif isinstance(tiles, six.string_types):
        if tiles not in maptiles.tiles:
            raise ValueError('Unknown tile source "{}"'.format(tiles))
        else:
            tiles = maptiles.tiles[tiles]

    template = env.get_template(template)

    if fig is None:
        fig = plt.gcf()
    dpi = fig.get_dpi()

    renderer = LeafletRenderer(crs=crs, epsg=epsg,od=od)
    exporter = Exporter(renderer)
    exporter.run(fig)

    attribution = _attribution + ' | ' + tiles[1]

    mapid = str(uuid.uuid4()).replace('-', '')

    gjdata = json.dumps(renderer.geojson())
    
    '''
    with open("gj.txt","w") as gjfile:
        gjfile.write(gjdata)
    with open("od.txt","w") as odfile:
        odfile.write(od)
    '''

    gj = json.loads(gjdata)
    ot = json.loads(od)
    pn_gdf, pl_gdf = dict_to_geopanda(gj)
    pn_odf, pl_odf = dict_to_geopanda(ot)
    
    print(len(pn_gdf.index),len(pl_gdf.index),len(pn_odf.index),len(pl_odf.index))
    #try:
        #point_in_poly = gpd.sjoin(pn_gdf,pl_gdf,how="inner",op="intersects")
        #map_both = point_in_poly[["id_left","id_right"]]
    #except:
        #pass
    
    try:
        poly_in_poly = gpd.sjoin(pl_odf,pl_gdf,how="inner",op="intersects")
        map_poly =  poly_in_poly[["id_left","id_right"]]
        for i,r in map_poly.iterrows():
            gj["features"][int(r["id_right"])]["properties"]["data"]= json.dumps(ot["features"][int(r["id_left"])]["properties"])
    except:
        pass

    #try:
        #point_in_point = gpd.sjoin(buff_points(pn_odf),buff_points(pn_gdf),how="inner",op="intersects")
        #map_point = point_in_point[["id_left","id_right"]]
        #for i,r in map_point.iterrows():
            #gj["features"][int(r["id_right"])]["properties"]["data"]= json.dumps(ot["features"][int(r["id_left"])]["properties"])
    #except:
        #pass
        #print(gj["features"][int(r["id_right"])]["properties"]["data"])
    #for g in gj:
    #    for t in ot:
    #geo_data = shape(gj[0]["geometry"])#["geometry"]["coordinates"]
    #other_geo = shape(ot[0]["geometry"])#["geometry"]["coordinates"][0]
    
    gjdata = json.dumps(gj)
    

    #print(geo_data, other_geo)
    #print(gj.keys(),ot.keys())
    #print(od)
    
    params = {
        'geojson': gjdata,
        'otherdata':otherjson,
        'width': fig.get_figwidth()*dpi,
        'height': fig.get_figheight()*dpi,
        'mapid': mapid,
        'tile_url': tiles[0],
        'attribution': attribution,
        'links': [_leaflet_js,_leaflet_css],
        'embed_links': embed_links,
    }
    html = template.render(params)

    return html


def fig_to_geojson(fig=None, **kwargs):
    """
    Returns a figure's GeoJSON representation as a dictionary

    All arguments passed to fig_to_html()

    Returns
    -------
    GeoJSON dictionary

    """
    if fig is None:
        fig = plt.gcf()
    renderer = LeafletRenderer(**kwargs)
    exporter = Exporter(renderer)
    exporter.run(fig)

    return renderer.geojson()


def save_html(fig=None, fileobj='_map.html', **kwargs):
    if isinstance(fileobj, str):
        fileobj = open(fileobj, 'w')
    if not hasattr(fileobj, 'write'):
        raise ValueError("fileobj should be a filename or a writable file")
    html = fig_to_html(fig, **kwargs)
    fileobj.write(html)
    fileobj.close()


def display(fig=None, closefig=True, **kwargs):
    """
    Convert a Matplotlib Figure to a Leaflet map. Embed in IPython notebook.

    Parameters
    ----------
    fig : figure, default gcf()
        Figure used to convert to map
    closefig : boolean, default True
        Close the current Figure
    """
    from IPython.display import HTML
    if fig is None:
        fig = plt.gcf()
    if closefig:
        plt.close(fig)

    html = fig_to_html(fig, **kwargs)

    # We embed everything in an iframe.
    iframe_html = '<iframe src="data:text/html;base64,{html}" width="{width}" height="{height}"></iframe>'\
    .format(html = base64.b64encode(html.encode('utf8')).decode('utf8'),
            width = '100%',
            height= int(60.*fig.get_figheight()),
           )
    return HTML(iframe_html)

def show(fig=None, path='_map.html', **kwargs):
    """
    Convert a Matplotlib Figure to a Leaflet map. Open in a browser

    Parameters
    ----------
    fig : figure, default gcf()
        Figure used to convert to map
    path : string, default '_map.html'
        Filename where output html will be saved

    See fig_to_html() for description of keyword args.

    """
    import webbrowser
    fullpath = os.path.abspath(path)
    with open(fullpath, 'w') as f:
        save_html(fig, fileobj=f, **kwargs)
    webbrowser.open('file://' + fullpath)
