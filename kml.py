
from __future__ import absolute_import


import pandas as pd
import geopandas as gpd
import mplleaflet
from fastkml import kml
from shapely.ops import polygonize
from shapely.geometry.linestring import LineString
from shapely.geometry.linestring import Point
from shapely.geometry import mapping, shape
import json
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy import inspect
from time import time
from flask import Flask, render_template, request ,redirect , url_for
from kml_to_db import update_kml,kml_to_database

axx = None
poly_base_df = None
points_base_df = None
pinp = None
last_village = None

class dbConf(object):
    name = "LandAcquisation"
    username = "postgres"
    password = "mak%^Sbnsdk3&n)m54@3s&nhY36"
    port = '5432'
    host = 'ci.thrymr.net'

crs = {'init': 'epsg:4326'}


def read_kml(kml_mapping_info_df,engine):
    kml_id = kml_mapping_info_df['id'].values[0]
    file = kml_mapping_info_df['document'].values[0].tobytes()
    village_id = kml_mapping_info_df['village_id'].values[0]
    yojana_id = kml_mapping_info_df['yojana_id'].values[0]

    #engine = create_engine('postgresql://postgres:test@127.0.0.1:5432/kml_to_db')

    poly_check= pd.read_sql_query('SELECT count(*) FROM poly',engine)

    if poly_check['count'][0] == 0:
        r_count= 0
    else:
        check = pd.read_sql_query('select count(*) from poly where kml_id='+str(kml_id),engine)
        r_count = check['count'][0]

    if r_count == 0:
        k = kml.KML()
        k.from_string(file)
        pnts = []
        lines = []
        oth = []
        fs = list(list(k.features())[0].features())
        for f in fs:
            if type(f.geometry) == Point:
                pnts.append(f)
            elif type(f.geometry) == LineString:
                lines.append(f)
            else:
                oth.append(f)

        gdf = kml_line_array_to_polygon_dataframe(lines, kml_id, yojana_id, village_id)
        pdf = kml_point_array_to_dataframe(pnts, kml_id, yojana_id, village_id)
        return gdf, pdf
    else:
        print("This Kml already Exist in DataBase !!")
        return pd.DataFrame(),pd.DataFrame()

def kml_line_array_to_polygon_dataframe(lines, kml_id, yojana_id, village_id):
    global crs
    df = pd.DataFrame(columns=["ID", "geometry"])
    for i, l in enumerate(lines):
        df.set_value(i, "geometry", l.geometry)
        df.set_value(i, "ID", i)

    gdf = gpd.GeoDataFrame(df, crs=crs, geometry=df["geometry"])
    pl = polygonize(gdf["geometry"])

    df = pd.DataFrame(columns=["ID", "geometry", "kml_id", "yojana_id", "village_id"])
    for j, p in enumerate(pl):
        df.set_value(j, "geometry", p.buffer(-0.000001))
        df.set_value(j, "ID", j)
        df.set_value(j, "kml_id", str(kml_id))
        df.set_value(j, "yojana_id", str(yojana_id))
        df.set_value(j, "village_id", str(village_id))

    gdf = gpd.GeoDataFrame(df, crs=crs, geometry=df["geometry"])
    return gdf


def kml_point_array_to_dataframe(pnts, kml_id, yojana_id, village_id):
    global crs
    df = pd.DataFrame(columns=["ID", "NAME", "geometry", "kml_id", "yojana_id", "village_id"])
    for i, p in enumerate(pnts):
        df.set_value(i, "geometry", p.geometry)
        df.set_value(i, "ID", i)
        df.set_value(i, "NAME", p.name)
        df.set_value(i, "kml_id", str(kml_id))
        df.set_value(i, "yojana_id", str(yojana_id))
        df.set_value(i, "village_id", str(village_id))

    gdf = gpd.GeoDataFrame(df, crs=crs, geometry=df["geometry"])
    return gdf

## Table Definations

def create_table_poly():
    print(dbConf.name,)
    con = psycopg2.connect(database =dbConf.name,user=dbConf.username,password=dbConf.password,host=dbConf.host,port=dbConf.port)
    cur = con.cursor()
    cur.execute("CREATE TABLE public.poly\
      (id serial NOT NULL,\
      properties text,\
      geometry text,\
      yojana_id bigint,\
      village_id bigint,\
      kml_id bigint,\
      CONSTRAINT polys_pkey PRIMARY KEY (id))")
    con.commit()
    con.close()
    return

def create_table_points():
    con = psycopg2.connect(database=dbConf.name, user=dbConf.username, password=dbConf.password, host=dbConf.host,
                           port=dbConf.port)
    curr = con.cursor()
    curr.execute("CREATE TABLE public.points\
    (id serial NOT NULL ,\
      properties text,\
      geometry text,\
      name text,\
      yojana_id bigint,\
      village_id bigint,\
      kml_id bigint,\
      CONSTRAINT point_pkey PRIMARY KEY (id))")
    con.commit()
    con.close()
    return


def createDfTable(tablename, passDf):
    st = time()
    df = passDf.copy()
    columnlist = list(df)
    length = len(columnlist)
    if tablename == 'poly':
        insertQuery = "INSERT INTO " + tablename + " (geometry,properties,yojana_id,village_id,kml_id) values ( "
    elif tablename == 'points':
        insertQuery = "INSERT INTO " + tablename + " (geometry,properties,name,yojana_id,village_id,kml_id) values ( "

    con = con = psycopg2.connect(database =dbConf.name,user=dbConf.username,password=dbConf.password,host=dbConf.host,port=dbConf.port)
    cur = con.cursor()

    for i, row in df.iterrows():
        insQuery = insertQuery
        if tablename == 'poly':
            insQuery = insQuery + "'" + str(row['geometry']) + "','" + \
                       str(row['properties']) + "'," + str(row['yojana_id']) + "," + str(row['village_id']) + "," + str(
                row['kml_id']) + ");"
        if tablename == 'points':
            insQuery = insQuery + "'" + str(row['geometry']) + "','" + \
                       str(row['properties']) + "','" + str(row['name']) + "'," + str(row['yojana_id']) + "," + str(
                row['village_id']) + "," + str(row['kml_id']) + ");"

        cur.execute(insQuery)
    con.commit()
    con.close()
    return print("Sucessful, time = ", time() - st)


def dfChangeToTable(tablename, gdf):
    obj = json.loads(gdf.to_json())

    if tablename == "poly":
        df_table = pd.DataFrame(columns=["id", "geometry", "properties", "yojana_id", "village_id", "kml_id"])

        for i in range(len(obj['features'])):
            df_table.set_value(i, "id", int(i))
            df_table.set_value(i, "geometry", json.dumps(obj['features'][i]['geometry']))
            df_table.set_value(i, "properties", json.dumps(obj['features'][i]['properties']))
            df_table.set_value(i, "yojana_id", obj['features'][i]['properties']["yojana_id"])
            df_table.set_value(i, "village_id", obj['features'][i]['properties']["village_id"])
            df_table.set_value(i, "kml_id", obj['features'][i]['properties']["kml_id"])
        createDfTable(tablename, df_table)
    elif tablename == "points":
        df_table = pd.DataFrame(columns=["id", "geometry", "properties", "Name", "yojana_id", "village_id", "kml_id"])

        for j in range(len(obj['features'])):
            df_table.set_value(j, "id", int(j))
            df_table.set_value(j, "geometry", json.dumps(obj['features'][j]['geometry']))
            df_table.set_value(j, "properties", json.dumps(obj['features'][j]['properties']))
            df_table.set_value(j, "name", obj['features'][j]['properties']["NAME"])
            df_table.set_value(j, "yojana_id", obj['features'][j]['properties']["yojana_id"])
            df_table.set_value(j, "village_id", obj['features'][j]['properties']["village_id"])
            df_table.set_value(j, "kml_id", obj['features'][j]['properties']["kml_id"])

        createDfTable(tablename, df_table)
    return print("Successfully Created Table")

def update_kml(kml_id):
    engine = create_engine('postgresql://postgres:mak%^Sbnsdk3&n)m54@3s&nhY36@ci.thrymr.net:5432/LandAcquisation')
    kml_mapping_info_df = pd.read_sql_query('SELECT * from kml_mapping_info where id=' + str(kml_id), engine)
    kml_id = kml_mapping_info_df['id'].values[0]

    #engine = create_engine('postgresql://postgres:test@127.0.0.1:5432/kml_to_db')

    con = psycopg2.connect(database =dbConf.name,user=dbConf.username,password=dbConf.password,host=dbConf.host,port=dbConf.port)

    poly_check = pd.read_sql_query('SELECT count(*) FROM poly', engine)
    if poly_check['count'][0] == 0:
        r_count= 0
    else:
        cur = con.cursor()
        cur.execute("delete from poly where kml_id= "+str(kml_id))

    points_check = pd.read_sql_query('SELECT count(*) FROM points', engine)
    if points_check['count'][0] == 0:
        r_count= 0
    else:
        curr = con.cursor()
        curr.execute("delete from points where kml_id= "+str(kml_id))
    con.commit()
    con.close()
    kml_to_database(kml_id)
    print("Update Successful !!!")
    return


def kml_to_database(kml_id):
    #check table is there or not
    engine = create_engine('postgresql://postgres:mak%^Sbnsdk3&n)m54@3s&nhY36@ci.thrymr.net:5432/LandAcquisation')
    inspector = inspect(engine)
    #print(inspector.get_table_names())

    if 'poly' not in inspector.get_table_names():
        create_table_poly()

    if 'points'  not in inspector.get_table_names():
        create_table_points()

    ## Read Kml file from database
    kml_mapping_info_df = pd.read_sql_query('SELECT * from kml_mapping_info where id='+str(kml_id),engine)

    g_df,p_df=read_kml(kml_mapping_info_df,engine)
    if len(g_df) != 0 and len(p_df) != 0:
        g_df.to_file("shape/gdf")
        p_df.to_file("shape/pdf")
        #insert data in database
        dfChangeToTable("poly",g_df)
        dfChangeToTable("points",p_df)
    else:
        return None


def readfromDatabase(yojana_id, village_id, idlist=None, table="poly"):
    if table == "points":
        selectQuery = "SELECT id,geometry,properties,name,yojana_id,village_id,kml_id from " + table
    else:
        selectQuery = "SELECT id, geometry, properties,yojana_id,village_id,kml_id from " + table
    query = None
    if (idlist != None):
        print(idlist)
        length = len(idlist)
        query = selectQuery + " where id in( "

        for i, col in enumerate(idlist):
            query = query + str(col)
            if (i != length - 1):
                query = query + ","
        query = query + ") and " + "yojana_id=" + str(yojana_id) + "and village_id=" + str(village_id) + ";"
    else:
        query = selectQuery + " where yojana_id=" + str(yojana_id) + "and village_id=" + str(village_id) + ";"

    df = pd.DataFrame(columns=["id", "geometry", "properties"])
    conn = psycopg2.connect(database=dbConf.name, user=dbConf.username, password=dbConf.password, host=dbConf.host,
                           port=dbConf.port)
    # conn = psycopg2.connect(database = "LandAcquisation", user = "postgres", password = "mak%^Sbnsdk3&n)m54@3s&nhY36", host = "127.0.0.1", port = "5432")
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    for j, row in enumerate(rows):
        df.set_value(j, "id", row[0])
        df.set_value(j, "geometry", shape(json.loads(row[1])))
        df.set_value(j, "properties", row[2])
        if table == "points":
            df.set_value(j, "Name", row[3])
    geodf = gpd.GeoDataFrame(df, crs={'init': 'epsg:4326'}, geometry=df["geometry"])
    print("Operation done successfully")
    conn.close()
    return geodf

def name_to_id(point_in_poly, name):
    return point_in_poly.loc[(point_in_poly["Name"] == name),["id_right"]].values[0][0]

def change_global_variables(yojana_id,village_id):
    print(yojana_id,village_id)

    poly_base_df = readfromDatabase(yojana_id,village_id)
    points_base_df = readfromDatabase(yojana_id,village_id,table="points")

    if len(poly_base_df) !=0 and len(points_base_df) != 0:
        point_in_poly = gpd.sjoin(points_base_df,poly_base_df,how="inner",op="intersects")
        pinp = point_in_poly[["Name","id_right"]]
        ax = poly_base_df.plot(color= 'white',alpha= 0.7)
        return ax,poly_base_df, pinp
    else:
        return None,pd.DataFrame(),pd.DataFrame()

app = Flask(__name__)

@app.route("/")
def index():
	return render_template('village.html')

@app.route("/village",methods=['Post'])
def village():
    yojana_id = request.form['yojana_id']
    village_id = request.form['village_id']
    plot = request.form['plot']
    print(village_id,yojana_id,plot)

    axx , base_df, pnt_map = change_global_variables(yojana_id,village_id)
    if axx!= None and len(base_df) !=0 and len(pnt_map)!=0:
        pnt = name_to_id(pnt_map,plot)
        chdf = readfromDatabase(yojana_id,village_id,[pnt])
        ax = chdf.plot(ax=axx, color="#0000FF",alpha=0.9)
        return mplleaflet.fig_to_html( fig=ax.figure, template='base_plot.html',crs=base_df.crs,od=base_df.to_json(), otherjson= chdf.to_json())
    else:
        return "NO DATA"

@app.route("/upload",methods=['post'])
def upload():
    kml_upload_id=request.form['kml_upload_id']
    print(kml_upload_id)
    kml_to_database(kml_upload_id)
    print("upload")
    return "Successfully Uploaded "


@app.route("/update",methods=['post'])
def update():
    kml_update_id = request.form['kml_update_id']
    print(kml_update_id)
    update_kml(kml_update_id)
    print("Update")
    return "Successfully updated "

if __name__ == "__main__":
    app.run(port = 7755)
