
from . import app
import os
import json
import pymongo
import sys

from flask import jsonify, request, make_response, abort, url_for
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId


SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")

with open(json_url, encoding="utf-8") as f:
    songs_list = json.load(f)


mongodb_service = os.environ.get("MONGODB_SERVICE")
mongodb_username = os.environ.get("MONGODB_USERNAME")
mongodb_password = os.environ.get("MONGODB_PASSWORD")
mongodb_port = os.environ.get("MONGODB_PORT")

print(f"The value of MONGODB_SERVICE is: {mongodb_service}")

if mongodb_service is None:
    app.logger.error("Missing MongoDB server in the MONGODB_SERVICE variable")
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = (
        f"mongodb://{mongodb_username}:{mongodb_password}"
        f"@{mongodb_service}"
    )
else:
    url = f"mongodb://{mongodb_service}"

if mongodb_port:
    url = f"{url}:{mongodb_port}"

print(f"Connecting to MongoDB service: {mongodb_service}")

try:
    client = MongoClient(url)
    db = client.songs

    # Initialize the sample database.
    # WARNING: This resets the songs collection whenever this module loads.
    db.songs.drop()
    db.songs.insert_many(songs_list)

except OperationFailure as e:
    app.logger.error(f"MongoDB authentication error: {str(e)}")
    raise


def parse_json(data):
    return json.loads(json_util.dumps(data))


# Health endpoint
@app.route("/health", methods=["GET"])
def healthz():
    return jsonify({"status": "OK"}), 200


# Count endpoint
@app.route("/count", methods=["GET"])
def count():
    """Return the number of songs."""
    total = db.songs.count_documents({})
    return {"count": total}, 200


# List all songs
@app.route("/song", methods=["GET"])
def songs():
    results = list(db.songs.find({}))
    return {"songs": parse_json(results)}, 200


# Get a song by ID
@app.route("/song/<int:id>", methods=["GET"])
def get_song_by_id(id):
    song = db.songs.find_one({"id": id})

    if song is None:
        return {"message": f"song with id {id} not found"}, 404

    return parse_json(song), 200


# Create a song
@app.route("/song", methods=["POST"])
def create_song():
    song_in = request.get_json()

    if not song_in or "id" not in song_in:
        return {"message": "song data and id are required"}, 400

    song = db.songs.find_one({"id": song_in["id"]})

    if song:
        return {
            "Message": f"song with id {song_in['id']} already present"
        }, 302

    insert_result: InsertOneResult = db.songs.insert_one(song_in)

    return {
        "inserted id": parse_json(insert_result.inserted_id)
    }, 201


# Update a song
@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    song_in = request.get_json()

    if song_in is None:
        return {"message": "JSON request body is required"}, 400

    song = db.songs.find_one({"id": id})

    if song is None:
        return {"message": "song not found"}, 404

    updated_data = {"$set": song_in}
    result = db.songs.update_one({"id": id}, updated_data)

    if result.modified_count == 0:
        return {
            "message": "song found, but nothing updated"
        }, 200

    return parse_json(db.songs.find_one({"id": id})), 201


# Delete a song
@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):
    result = db.songs.delete_one({"id": id})

    if result.deleted_count == 0:
        return {"message": "song not found"}, 404

    return "", 204
