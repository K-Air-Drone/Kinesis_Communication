import falcon
import psycopg2
import json

class DGACDrone:
    def getDrone(self, req, resp):
        try:
            # ➤ Chaîne de connexion PostgreSQL — à adapter à ton environnement
            db = psycopg2.connect(
                dbname="drones",
                user="postgres",
                password="drone123",
                host="localhost",
                port="5432"
            )
            cur = db.cursor()

            # ➤ Récupération des paramètres GET
            lat = req.get_param('lat')
            lon = req.get_param('lon')
            rayon = int(req.get_param('rayon') or 1000)
            rayon = min(rayon, 50000)

            limite = req.get_param('limite')
            limite_min = req.get_param('limite_min')

            if lat is None or lon is None:
                resp.status = falcon.HTTP_400
                resp.text = json.dumps({'erreur': 'lat et lon sont obligatoires'})
                return

            lat = float(lat.replace(',', '.'))
            lon = float(lon.replace(',', '.'))

            # ➤ Construction du WHERE dynamique
            where = ""
            params = {'lat': lat, 'lon': lon, 'dist': rayon}

            if limite:
                where += " AND limite = %(limite)s"
                params['limite'] = int(limite)
            if limite_min:
                where += " AND limite >= %(limite_min)s"
                params['limite_min'] = int(limite_min)

            # ➤ Requête SQL
            query = f"""
            SELECT json_build_object(
                'source', 'DGAC / SIA',
                'derniere_maj', '2021-01',
                'type', 'FeatureCollection',
                'nb_features', COUNT(d.*),
                'features', COALESCE(
                    json_agg(json_build_object(
                        'type', 'Feature',
                        'properties', json_build_object(
                            'limite_alti_m', limite,
                            'distance_m', ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)::int,
                            'cap_deg', CASE
                                WHEN ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography) > 0
                                THEN DEGREES(ST_Azimuth(
                                    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
                                    ST_ClosestPoint(geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))
                                ))::int
                                ELSE NULL
                            END
                        ),
                        'geometry', ST_AsGeoJSON(geom, 6)::json
                    ) ORDER BY ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)), '[]'::json
                )
            )::text
            FROM drones d
            WHERE ST_Buffer(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(dist)s)::geometry && geom
            AND ST_DWithin(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, geom::geography, %(dist)s)
            {where}
            """

            cur.execute(query, params)
            result = cur.fetchone()[0]

            # ➤ Réponse JSON
            resp.status = falcon.HTTP_200
            resp.content_type = 'application/json'
            resp.set_header('Access-Control-Allow-Origin', '*')
            resp.text = result

            cur.close()
            db.close()

        except Exception as e:
            print("Erreur API:", e)
            resp.status = falcon.HTTP_500
            resp.text = json.dumps({"erreur": str(e)})

    def on_get(self, req, resp):
        self.getDrone(req, resp)

# ➤ Application Falcon
app = falcon.App()
app.add_route('/drone', DGACDrone())

# ➤ Lancement local avec wsgiref
if __name__ == '__main__':
    from wsgiref import simple_server
    print("API démarrée sur http://localhost:8000/drone")
    with simple_server.make_server('127.0.0.1', 8000, app) as httpd:
        httpd.serve_forever()
